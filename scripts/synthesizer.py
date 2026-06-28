"""
scripts/synthesizer.py
Bitcoin Intel — детерминированный синтезатор нарративов

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

# Обязательная проверка детерминизма — первое что делает скрипт
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    assert_deterministic_env,
    calculate_max_possible_score,
    calculate_confidence,
    get_strength,
    FRESHNESS_SCORE, WEIGHT_SCORE, ROLE_SCORE, CONTRADICTION_BONUS,
    SCORE_HOT, WINDOW_DAYS_DEFAULT, STALE_THRESHOLD, ARCHIVE_THRESHOLD,
    SIGNALS_PATH, SYNTHESIS_CACHE_PATH,
    LEGACY_LINKS_ENABLED,
    ENCODING, JSON_ENSURE_ASCII,
    DATE_FORMAT,
)

assert_deterministic_env()

# ─── Bridges ─────────────────────────────────────────────────────────────────
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

    ИСПРАВЛЕНО (B1): заменено abs(hash(seed)) % len(options)
    на seed % len(options) — hash() недетерминирован между процессами.
    seed = len(signals) стабилен для одного набора данных.
    """
    options = BRIDGES.get(phase, BRIDGES["active"])
    return options[seed % len(options)]


# ─── Dataclasses ─────────────────────────────────────────────────────────────
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
    cluster:          str
    tension:          str
    narrative:        str
    takeaway:         str
    strength:         str
    confidence:       float
    phase:            str
    score:            SignalScore
    anchor_signal_id: str
    signal_count:     int
    phase_changed:    bool = False
    rationale:        str = ""
    generated_at:     str = field(default_factory=lambda: datetime.now(timezone.utc).strftime(DATE_FORMAT))


# ─── Вспомогательные функции ─────────────────────────────────────────────────
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
        return signal.get("links", {}).get("contradicts", [])
    # После миграции — читать из relationships.json
    return []


def _score_signal(signal: dict) -> SignalScore:
    age  = _age_days(signal.get("date", "2000-01-01"))
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
    Тиебрейкеры (TD6):
      1. score.total DESC
      2. weight_score DESC
      3. date DESC (свежее)
      4. id ASC (лексикографический — всегда уникален, гарантирует детерминизм)
    """
    scored = [(s, _score_signal(s)) for s in signals]
    scored.sort(key=lambda x: (
        -x[1].total,
        -_weight_score(x[0].get("weight", "media")),
        x[0].get("date", ""),   # DESC → берём строку, потом инвертируем ниже
        x[0].get("id", ""),
    ))
    # date DESC требует отдельной инверсии
    scored.sort(key=lambda x: (
        -x[1].total,
        -_weight_score(x[0].get("weight", "media")),
        -(datetime.strptime(x[0].get("date", "2000-01-01"), DATE_FORMAT).toordinal()),
        x[0].get("id", ""),
    ))
    return scored


def _detect_phase(signals: list[dict]) -> str:
    """ШАГ 3: определяет фазу кластера по распределению narrative_role."""
    roles = [s.get("narrative_role", "background") for s in signals]
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
        -(datetime.strptime(s.get("date", "2000-01-01"), DATE_FORMAT).toordinal()),
    ))
    return candidates[0]


def _capitalize(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


# ─── Основной синтез ──────────────────────────────────────────────────────────
def synthesize_cluster(cluster_key: str, signals: list[dict],
                        previous_phase: Optional[str] = None) -> SynthesisResult:
    """
    12-шаговый алгоритм синтеза нарратива для кластера.

    Args:
        cluster_key:    ключ кластера (например 'strategy_model_stress')
        signals:        список сигналов кластера из signals.json
        previous_phase: фаза предыдущего синтеза (для phase_change detection)

    Returns:
        SynthesisResult с tension, narrative, takeaway, confidence и т.д.
    """
    today = _today_utc()

    # ШАГ 1: фильтрация
    active_signals = [
        s for s in signals
        if _age_days(s.get("date", "2000-01-01")) <= WINDOW_DAYS_DEFAULT
        and s.get("status", "active") != "archived"
    ]

    if not active_signals:
        return SynthesisResult(
            cluster=cluster_key, tension="", narrative="Нет активных сигналов.",
            takeaway="", strength="weak", confidence=0.1,
            phase="structural", score=SignalScore(),
            anchor_signal_id="", signal_count=0,
        )

    # ШАГ 2: ранжирование
    ranked = _rank_signals(active_signals)
    ranked_signals = [s for s, _ in ranked]

    # ШАГ 3: фаза
    phase = _detect_phase(ranked_signals)

    # ШАГ 4: разбивка по ролям
    triggers      = [s for s in ranked_signals if s.get("narrative_role") == "trigger"]
    complications = [s for s in ranked_signals if s.get("narrative_role") == "complication"]
    resolutions   = [s for s in ranked_signals if s.get("narrative_role") == "resolution"]

    anchor_trigger     = triggers[0]      if triggers      else ranked_signals[0]
    anchor_complication = complications[0] if complications else None
    anchor_resolution  = resolutions[0]   if resolutions   else None

    # ШАГ 5: contradiction weighting (уже учтён в _score_signal)

    # ШАГ 6: tension
    tension_source = _select_tension_source(ranked_signals)
    if tension_source:
        tension = _capitalize(tension_source.get("tension", ""))
    else:
        # Last resort: строим из двух macro_implication
        mi_a = anchor_trigger.get("macro_implication", "").split(". ")[0]
        mi_b = (anchor_complication or ranked_signals[-1]).get("macro_implication", "").split(". ")[0]
        tension = f"{mi_a} — vs — {mi_b}" if mi_b else mi_a

    # ШАГ 7–8: narrative (partA + bridge + partB)
    partA = anchor_trigger.get("macro_implication", "").split(". ")[0]
    bridge = select_bridge(phase, seed=len(active_signals))
    complication_for_partB = anchor_complication or (
        ranked_signals[1] if len(ranked_signals) > 1 else anchor_trigger
    )
    partB_raw = complication_for_partB.get("macro_implication", "").split(". ")[0]
    partB = partB_raw[0].lower() + partB_raw[1:] if partB_raw else ""
    narrative = f"{partA} — {bridge} {partB}" if partB else partA

    # ШАГ 9: takeaway
    takeaway_candidates = [c for c in [
        anchor_complication, anchor_trigger, anchor_resolution,
        max(ranked, key=lambda x: x[1].weight)[0] if ranked else None
    ] if c]
    takeaway = ""
    for candidate in takeaway_candidates:
        mi = candidate.get("macro_implication", "")
        candidate_takeaway = mi.split(". ")[0] if mi else ""
        if candidate_takeaway and candidate_takeaway not in narrative and candidate_takeaway not in tension:
            takeaway = candidate_takeaway
            break

    # ШАГ 10: phase_changed
    phase_changed = (previous_phase is not None and previous_phase != phase)

    # ШАГ 11: confidence
    all_scores = [sc for _, sc in ranked]
    total_score = sum(sc.total for sc in all_scores)
    has_contradicts = any(_get_contradicts(s) for s in active_signals)
    all_stale = all(_age_days(s.get("date", "2000-01-01")) > STALE_THRESHOLD for s in active_signals)

    confidence = calculate_confidence(
        score_total=total_score,
        n_signals=len(active_signals),
        has_contradicts=has_contradicts,
        all_stale=all_stale,
        has_tension=bool(tension_source),
    )

    # Суммарный score для отображения
    cluster_score = SignalScore()
    for sc in all_scores:
        cluster_score.freshness     += sc.freshness
        cluster_score.weight        += sc.weight
        cluster_score.role          += sc.role
        cluster_score.contradiction += sc.contradiction

    # ШАГ 12: rationale
    anchor_id = (tension_source or anchor_trigger).get("id", "?")
    rationale = (
        f"Tension из {anchor_id} (contradicts: {len(_get_contradicts(tension_source or anchor_trigger))}, "
        f"weight: {(tension_source or anchor_trigger).get('weight','?')}); "
        f"partA из {anchor_trigger.get('id','?')}; "
        f"phase: {phase}; bridge: '{bridge}'; "
        f"confidence: {confidence:.2f}"
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
        rationale=rationale,
    )


# ─── Запуск ───────────────────────────────────────────────────────────────────
def main():
    with open(SIGNALS_PATH, encoding=ENCODING) as f:
        all_signals = json.load(f)

    # Группируем по кластерам
    clusters: dict[str, list] = {}
    for s in all_signals:
        key = s.get("cluster")
        if key:
            clusters.setdefault(key, []).append(s)

    results = {}
    for cluster_key, signals in clusters.items():
        result = synthesize_cluster(cluster_key, signals)
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
            "rationale":        result.rationale,
            "generated_at":     result.generated_at,
        }
        print(f"✓ {cluster_key}: {result.strength} | score={result.score.total} | phase={result.phase}")

    os.makedirs(os.path.dirname(SYNTHESIS_CACHE_PATH), exist_ok=True)
    with open(SYNTHESIS_CACHE_PATH, "w", encoding=ENCODING) as f:
        json.dump(results, f, ensure_ascii=JSON_ENSURE_ASCII, indent=2)

    print(f"\n✓ Кеш записан: {SYNTHESIS_CACHE_PATH} ({len(results)} кластеров)")


if __name__ == "__main__":
    main()
