"""
scripts/synthesizer.py
Bitcoin Intel — детерминированный синтезатор нарративов.

Путь 2: подключены exceptions, logger, state_machine, @measure_performance.
§17: previous_synthesis передаётся как параметр (не читается внутри).

Реализует 12-шаговый алгоритм из BLUEPRINT_ADDENDUM.md §24.
Запускать: PYTHONHASHSEED=0 python3 scripts/synthesizer.py

ВАЖНО: PYTHONHASHSEED=0 обязателен для воспроизводимости.
"""

import os
import sys
import json
from datetime import date, datetime, timezone
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    assert_deterministic_env,
    assert_required_files_exist,
    calculate_max_possible_score,
    calculate_confidence,
    get_strength,
    FRESHNESS_SCORE, WEIGHT_SCORE, ROLE_SCORE, CONTRADICTION_BONUS,
    SCORE_HOT, WINDOW_DAYS_DEFAULT, STALE_THRESHOLD, ARCHIVE_THRESHOLD,
    SIGNALS_PATH, SYNTHESIS_CACHE_PATH, SYNTHESIS_STORE_PATH,
    LEGACY_LINKS_ENABLED, ENCODING, JSON_ENSURE_ASCII, DATE_FORMAT,
    ERROR_EXIT_CODES, NULL_DEFAULTS,
)
from infrastructure.file_lock import safe_read_json, atomic_write_json_safe
from infrastructure.logger import get_logger, measure_performance
from domain.exceptions import (
    BitcoinIntelError,
    EmptyClusterError,
    SynthesizerError,
)
from domain.lifecycle import on_synthesis_superseded

# §4: assert_deterministic_env — первое при старте
assert_deterministic_env()

logger = get_logger("synthesizer")


# ─── Bridges ──────────────────────────────────────────────────────────────────
BRIDGES = {
    "active": [
        "при этом",
        "однако",
        "в то время как",
        "тогда как",
    ],
    "tension": [
        "что усугубляется тем что",
        "несмотря на то что",
        "вопреки тому что",
    ],
    "resolution": [
        "после чего",
        "в результате чего",
        "что означает что",
    ],
    "structural": [
        "на фоне того что",
        "в условиях",
        "в структуре которой",
    ],
}


def select_bridge(phase: str, seed: int) -> str:
    """
    Детерминированный выбор bridge-фразы.
    seed % len(options) — детерминировано, не зависит от PYTHONHASHSEED.
    """
    options = BRIDGES.get(phase, BRIDGES["active"])
    if not options:
        raise SynthesizerError(f"No bridges defined for phase: {phase}")
    return options[seed % len(options)]


# ─── Dataclasses ──────────────────────────────────────────────────────────────
@dataclass
class SignalScore:
    freshness:     int = 0
    weight:        int = 0
    role:          int = 0
    contradiction: int = 0

    @property
    def total(self) -> int:
        return self.freshness + self.weight + self.role + self.contradiction


@dataclass
class SynthesisResult:
    cluster:           str
    tension:           str
    narrative:         str
    takeaway:          str
    strength:          str
    confidence:        float
    phase:             str
    score:             SignalScore
    anchor_signal_id:  str
    signal_count:      int
    phase_changed:     bool  = False
    structural_change: dict  = field(default_factory=dict)
    rationale:         str   = ""
    signals_used:      list  = field(default_factory=list)
    signals_ignored:   list  = field(default_factory=list)
    generated_at:      str   = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ─── Вспомогательные ──────────────────────────────────────────────────────────
def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _age_days(signal_date_str: str) -> int:
    try:
        d = datetime.strptime(signal_date_str, DATE_FORMAT).date()
        return (_today_utc() - d).days
    except ValueError:
        return 999


def _freshness(age: int) -> int:
    if age <= 7:
        return FRESHNESS_SCORE["fresh"]
    if age <= STALE_THRESHOLD:
        return FRESHNESS_SCORE["recent"]
    return FRESHNESS_SCORE["stale"]


def _weight_score(weight: str) -> int:
    return WEIGHT_SCORE.get(weight, 1)


def _role_score(role: str) -> int:
    return ROLE_SCORE.get(role, 0)


def _get_contradicts(signal: dict) -> list:
    """Читает contradicts из links.* (legacy) или relationships (новый путь)."""
    if LEGACY_LINKS_ENABLED:
        return (signal.get("links") or {}).get("contradicts", []) or []
    return []


def _score_signal(signal: dict) -> SignalScore:
    age         = _age_days(signal.get("date", "2000-01-01"))
    contradicts = _get_contradicts(signal)
    return SignalScore(
        freshness=_freshness(age),
        weight=_weight_score(signal.get("weight", "media")),
        role=_role_score(signal.get("narrative_role", "background")),
        contradiction=len(contradicts) * CONTRADICTION_BONUS,
    )


def _rank_signals(signals: list[dict]) -> list[tuple[dict, SignalScore]]:
    """
    Ранжирует сигналы по importance DESC.
    4-уровневый tiebreaker (TD6):
      1. score.total DESC
      2. weight_score DESC
      3. date DESC
      4. id ASC — гарантирует детерминизм
    """
    scored = [(s, _score_signal(s)) for s in signals]
    scored.sort(key=lambda x: (
        -x[1].total,
        -_weight_score(x[0].get("weight", "media")),
        -(datetime.strptime(
            x[0].get("date", "2000-01-01"), DATE_FORMAT
        ).toordinal()),
        x[0].get("id", ""),
    ))
    return scored


def _detect_phase(signals: list[dict]) -> str:
    """ШАГ 3: определяет фазу кластера по распределению narrative_role."""
    roles  = [s.get("narrative_role", "background") for s in signals]
    counts = {r: roles.count(r) for r in set(roles)}
    if counts.get("resolution", 0) > 0:
        return "resolution"
    if counts.get("trigger", 0) > 0 and counts.get("complication", 0) > 0:
        return "active"
    if counts.get("complication", 0) > counts.get("trigger", 0):
        return "tension"
    return "structural"


def _select_tension_source(signals: list[dict]) -> Optional[dict]:
    """
    ШАГ 6: выбирает сигнал-источник tension.
    Приоритет: MAX(contradicts) → MAX(weight) → MAX(date).
    """
    candidates = [s for s in signals if s.get("tension")]
    if not candidates:
        return None
    candidates.sort(key=lambda s: (
        -len(_get_contradicts(s)),
        -_weight_score(s.get("weight", "media")),
        -(datetime.strptime(
            s.get("date", "2000-01-01"), DATE_FORMAT
        ).toordinal()),
    ))
    return candidates[0]


def _capitalize(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def deduplicate_signals(signals: list[dict]) -> tuple[list[dict], list[str]]:
    """
    §16: Удаляет дублирующие сигналы перед синтезом.
    Дубликат = одинаковый (date, actor, cluster, dir).
    Из группы оставляет сигнал с наибольшим weight_score.

    Returns:
        (deduplicated, ignored_ids)
    """
    seen:        dict[tuple, dict] = {}
    ignored_ids: list[str]         = []

    for signal in signals:
        key = (
            signal.get("date", ""),
            signal.get("actor", ""),
            signal.get("cluster", ""),
            signal.get("dir", ""),
        )
        if key in seen:
            existing_score = _weight_score(seen[key].get("weight", ""))
            new_score      = _weight_score(signal.get("weight", ""))
            if new_score > existing_score:
                ignored_ids.append(seen[key]["id"])
                seen[key] = signal
            else:
                ignored_ids.append(signal["id"])
        else:
            seen[key] = signal

    if ignored_ids:
        logger.warning(
            f"Deduplicated {len(ignored_ids)} signals: {ignored_ids}",
            extra={"cluster": signals[0].get("cluster") if signals else ""}
        )

    return list(seen.values()), ignored_ids


# ─── Основной синтез ──────────────────────────────────────────────────────────
@measure_performance("synthesize_cluster")
def synthesize_cluster(
    cluster_key:        str,
    signals:            list[dict],
    previous_synthesis: Optional[dict] = None,   # §17: передаётся снаружи
) -> SynthesisResult:
    """
    12-шаговый алгоритм синтеза нарратива для кластера.

    §17: previous_synthesis передаётся как параметр — synthesizer не читает
    файлы сам. Это гарантирует соблюдение архитектурного контракта:
    Delivery Context не записывает, Synthesis Context не читает файлы напрямую.

    Args:
        cluster_key:        ключ кластера
        signals:            список сигналов кластера
        previous_synthesis: dict предыдущего синтеза или None (загружает caller)

    Raises:
        EmptyClusterError: если нет активных сигналов в окне WINDOW_DAYS_DEFAULT
    """
    logger.debug(
        f"Synthesizing cluster '{cluster_key}' ({len(signals)} signals)",
        extra={"cluster": cluster_key}
    )

    # §16: Дедупликация перед синтезом
    signals, ignored_ids = deduplicate_signals(signals)

    # ШАГ 1: Фильтрация по окну и статусу
    # DEGRADE GRACEFULLY: corrupt signal → skip + WARNING
    active_signals = []
    for s in signals:
        try:
            age    = _age_days(s.get("date", "2000-01-01"))
            status = s.get("status", "active")
            if age <= WINDOW_DAYS_DEFAULT and status != "archived":
                active_signals.append(s)
        except Exception as e:
            logger.warning(
                f"Skipping corrupt signal {s.get('id', '?')}: {e}",
                extra={"cluster": cluster_key, "signal_id": s.get("id")}
            )

    if not active_signals:
        raise EmptyClusterError(cluster_key, WINDOW_DAYS_DEFAULT)

    # ШАГ 2: Ранжирование
    ranked         = _rank_signals(active_signals)
    ranked_signals = [s for s, _ in ranked]
    signals_used   = [s.get("id", "") for s in ranked_signals]

    # ШАГ 3: Фаза
    phase = _detect_phase(ranked_signals)

    # ШАГ 4: Разбивка по ролям
    triggers       = [s for s in ranked_signals if s.get("narrative_role") == "trigger"]
    complications  = [s for s in ranked_signals if s.get("narrative_role") == "complication"]
    resolutions    = [s for s in ranked_signals if s.get("narrative_role") == "resolution"]

    anchor_trigger      = triggers[0]      if triggers      else ranked_signals[0]
    anchor_complication = complications[0] if complications else None
    anchor_resolution   = resolutions[0]   if resolutions   else None

    # ШАГ 5: Contradiction weighting (учтён в _score_signal)

    # ШАГ 6: Tension
    tension_source = _select_tension_source(ranked_signals)
    if tension_source:
        tension = _capitalize(tension_source.get("tension", "") or "")
    else:
        mi_a = (anchor_trigger.get("macro_implication") or "").split(". ")[0]
        mi_b = (anchor_complication or ranked_signals[-1]).get(
            "macro_implication", ""
        ).split(". ")[0]
        tension = f"{mi_a} — vs — {mi_b}" if mi_b else mi_a

    # ШАГ 7–8: Narrative (partA + bridge + partB)
    partA  = (anchor_trigger.get("macro_implication") or "").split(". ")[0]
    bridge = select_bridge(phase, seed=len(active_signals))
    complication_for_b = anchor_complication or (
        ranked_signals[1] if len(ranked_signals) > 1 else anchor_trigger
    )
    partB_raw = (complication_for_b.get("macro_implication") or "").split(". ")[0]
    partB     = partB_raw[0].lower() + partB_raw[1:] if partB_raw else ""
    narrative = f"{partA} — {bridge} {partB}" if partB else partA

    # ШАГ 9: Takeaway
    takeaway_candidates = [c for c in [
        anchor_complication, anchor_trigger, anchor_resolution,
        max(ranked, key=lambda x: x[1].weight)[0] if ranked else None,
    ] if c]
    takeaway = ""
    for candidate in takeaway_candidates:
        mi = candidate.get("macro_implication") or ""
        candidate_takeaway = mi.split(". ")[0] if mi else ""
        if (candidate_takeaway
                and candidate_takeaway not in narrative
                and candidate_takeaway not in tension):
            takeaway = candidate_takeaway
            break

    # ШАГ 10: Phase changed
    phase_changed = (
        previous_synthesis is not None
        and previous_synthesis.get("phase") != phase
    )

    # §17: Structural change detection
    structural_change: dict = {}
    if previous_synthesis and phase_changed:
        prev_phase = previous_synthesis.get("phase")
        structural_change = {
            "detected":   True,
            "from_phase": prev_phase,
            "to_phase":   phase,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(
            f"Structural change in '{cluster_key}': {prev_phase} → {phase}",
            extra={"cluster": cluster_key}
        )

    # ШАГ 11: Confidence
    all_scores   = [sc for _, sc in ranked]
    total_score  = sum(sc.total for sc in all_scores)
    has_contradicts = any(_get_contradicts(s) for s in active_signals)
    all_stale    = all(
        _age_days(s.get("date", "2000-01-01")) > STALE_THRESHOLD
        for s in active_signals
    )
    confidence = calculate_confidence(
        score_total=total_score,
        n_signals=len(active_signals),
        has_contradicts=has_contradicts,
        all_stale=all_stale,
        has_tension=bool(tension_source),
    )

    # Суммарный score
    cluster_score = SignalScore()
    for sc in all_scores:
        cluster_score.freshness     += sc.freshness
        cluster_score.weight        += sc.weight
        cluster_score.role          += sc.role
        cluster_score.contradiction += sc.contradiction

    # ШАГ 12: Rationale
    anchor_id  = (tension_source or anchor_trigger).get("id", "?")
    anchor_obj = tension_source or anchor_trigger
    rationale  = (
        f"Tension from {anchor_id} "
        f"(contradicts: {len(_get_contradicts(anchor_obj))}, "
        f"weight: {anchor_obj.get('weight','?')}); "
        f"partA from {anchor_trigger.get('id','?')}; "
        f"phase: {phase}; bridge: '{bridge}'; "
        f"confidence: {confidence:.2f}; "
        f"signals_used: {len(signals_used)}; "
        f"ignored_duplicates: {ignored_ids}"
    )

    logger.info(
        f"Synthesized '{cluster_key}': {get_strength(cluster_score.total)} | "
        f"phase={phase} | score={cluster_score.total} | "
        f"confidence={confidence:.2f} | signals={len(active_signals)}",
        extra={"cluster": cluster_key}
    )

    return SynthesisResult(
        cluster=cluster_key,
        tension=tension,
        narrative=narrative,
        takeaway=takeaway,
        strength=get_strength(cluster_score.total),
        confidence=confidence,
        phase=phase,
        score=cluster_score,
        anchor_signal_id=anchor_id,
        signal_count=len(active_signals),
        phase_changed=phase_changed,
        structural_change=structural_change,
        rationale=rationale,
        signals_used=signals_used,
        signals_ignored=ignored_ids,
    )


# ─── Запуск (§9 Error Propagation + §17 previous_synthesis loader) ────────────

def _load_previous_synthesis(cluster_key: str) -> Optional[dict]:
    """
    §17: Загружает предыдущий синтез для кластера.
    Вызывается в main() — вне synthesize_cluster(), соблюдая архитектурный контракт.
    DEGRADE GRACEFULLY: если файл не найден → None.
    """
    store = Path(SYNTHESIS_STORE_PATH)
    if not store.exists():
        return None
    files = sorted(store.glob(f"synthesis_{cluster_key}_*.json"))
    if not files:
        return None
    try:
        return json.loads(files[-1].read_text(encoding=ENCODING))
    except Exception as e:
        logger.warning(
            f"Could not load previous synthesis for '{cluster_key}': {e}",
            extra={"cluster": cluster_key}
        )
        return None


def _save_synthesis(cluster_key: str, result: SynthesisResult,
                    synthesis_id: str) -> None:
    """Сохраняет синтез в synthesis_store/ с уникальным именем."""
    store = Path(SYNTHESIS_STORE_PATH)
    store.mkdir(exist_ok=True)
    output = {
        "id":               synthesis_id,
        "cluster":          result.cluster,
        "status":           "generated",
        "tension":          result.tension,
        "narrative":        result.narrative,
        "takeaway":         result.takeaway,
        "strength":         result.strength,
        "confidence":       round(result.confidence, 3),
        "phase":            result.phase,
        "score":            result.score.total,
        "signal_count":     result.signal_count,
        "anchor_signal_id": result.anchor_signal_id,
        "phase_changed":    result.phase_changed,
        "structural_change":result.structural_change,
        "rationale":        result.rationale,
        "signals_used":     result.signals_used,
        "signals_ignored":  result.signals_ignored,
        "generated_at":     result.generated_at,
    }
    filepath = store / f"{synthesis_id}.json"
    atomic_write_json_safe(str(filepath), output)
    logger.info(f"Synthesis saved: {filepath.name}", extra={"cluster": cluster_key})


@measure_performance("build_cache")
def main() -> None:
    # §4: проверить файлы до старта
    assert_required_files_exist()

    raw = safe_read_json(SIGNALS_PATH, default=[], raise_on_corrupt=True)
    all_signals = raw.get("signals", []) if isinstance(raw, dict) else raw

    # Группируем по кластерам
    clusters: dict[str, list] = {}
    for s in all_signals:
        key = s.get("cluster")
        if key:
            clusters.setdefault(key, []).append(s)

    if not clusters:
        logger.warning("No clusters found in signals.json")
        print("⚠ No clusters found in signals.json")
        sys.exit(ERROR_EXIT_CODES["success"])

    results    = {}
    succeeded  = 0
    failed     = 0
    ts         = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    for cluster_key, signals in clusters.items():
        try:
            # §17: загружаем previous_synthesis вне synthesize_cluster()
            previous = _load_previous_synthesis(cluster_key)

            result = synthesize_cluster(cluster_key, signals, previous_synthesis=previous)

            # Сохранить в synthesis_store/
            synthesis_id = f"synthesis_{cluster_key}_{ts}"
            _save_synthesis(cluster_key, result, synthesis_id)

            # Если есть предыдущий синтез — lifecycle hook
            if previous and previous.get("id"):
                try:
                    on_synthesis_superseded(previous["id"], synthesis_id)
                except Exception as e:
                    # DEGRADE GRACEFULLY — lifecycle сбой не останавливает синтез
                    logger.warning(f"Lifecycle hook failed for {cluster_key}: {e}")

            results[cluster_key] = {
                "tension":          result.tension,
                "narrative":        result.narrative,
                "takeaway":         result.takeaway,
                "strength":         result.strength,
                "confidence":       round(result.confidence, 3),
                "phase":            result.phase,
                "score":            result.score.total,
                "signal_count":     result.signal_count,
                "anchor_signal_id": result.anchor_signal_id,
                "phase_changed":    result.phase_changed,
                "structural_change":result.structural_change,
                "rationale":        result.rationale,
                "signals_used":     result.signals_used,
                "signals_ignored":  result.signals_ignored,
                "generated_at":     result.generated_at,
                "synthesis_id":     synthesis_id,
            }
            print(
                f"✓ {cluster_key}: {result.strength} | "
                f"score={result.score.total} | phase={result.phase} | "
                f"signals={result.signal_count}"
            )
            succeeded += 1

        except EmptyClusterError as e:
            # DEGRADE GRACEFULLY — пустой кластер не останавливает остальные
            logger.warning(str(e), extra={"cluster": cluster_key})
            print(f"⚠ {cluster_key}: skipped — {e}")
            failed += 1

        except Exception as e:
            # DEGRADE GRACEFULLY — ошибка одного кластера не останавливает остальные
            logger.error(
                f"Failed to synthesize '{cluster_key}': {e}",
                extra={"cluster": cluster_key}
            )
            print(f"✗ {cluster_key}: ERROR — {e}")
            failed += 1

    # Записать synthesis_cache.json
    os.makedirs(os.path.dirname(SYNTHESIS_CACHE_PATH), exist_ok=True)
    atomic_write_json_safe(SYNTHESIS_CACHE_PATH, results)

    print(f"\n✓ Cache written: {SYNTHESIS_CACHE_PATH} ({succeeded} clusters, {failed} skipped)")

    # §9: exit code отражает результат
    sys.exit(
        ERROR_EXIT_CODES["success"] if failed == 0
        else ERROR_EXIT_CODES["business_logic_error"]
    )


if __name__ == "__main__":
    try:
        main()
    except BitcoinIntelError as e:
        print(f"⛔ {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["business_logic_error"])
    except Exception as e:
        logger.exception("Unexpected error in synthesizer")
        print(f"💥 Unexpected error: {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["system_error"])
