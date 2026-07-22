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

# IRP v1 Wave 3 / REM-M07: версия алгоритма синтеза (MAJOR.MINOR.PATCH).
# Семантика — ADDENDUM §25.3:
#   MAJOR — изменение алгоритма выбора tension/causal chain (ревью approved синтезов)
#   MINOR — новые мосты, новые scoring modifiers (ревью для STRUCTURAL кластеров)
#   PATCH — bugfix без изменения логики (ревью не требуется)
# Хранится в каждой записи synthesis_store/*.json и synthesis_cache.json
# как поле algorithm_version.
ALGORITHM_VERSION = "2.1.1"

from config.settings import (
    assert_deterministic_env,
    assert_required_files_exist,
    calculate_max_possible_score,
    calculate_confidence,
    get_strength,
    FRESHNESS_SCORE, WEIGHT_SCORE, ROLE_SCORE, CONTRADICTION_BONUS,
    SCORE_HOT, WINDOW_DAYS_DEFAULT, STALE_THRESHOLD, ARCHIVE_THRESHOLD,
    MULTI_ENTITY_THRESHOLD, MINORITY_ANCHOR_SHARE,
    COMPLICATION_DOMINANCE_RATIO,
    CROSS_CLUSTER_PRIMARY_MIN_SIGNALS, CROSS_CLUSTER_SECONDARY_MIN_SIGNALS,
    SIGNALS_PATH, SYNTHESIS_CACHE_PATH, SYNTHESIS_STORE_PATH, RELATIONSHIPS_PATH,
    ENTITIES_PATH,
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
    uncertainty:       dict  = field(default_factory=dict)
    signals_used:      list  = field(default_factory=list)
    signals_ignored:   list  = field(default_factory=list)
    generated_at:      str   = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    algorithm_version: str   = ALGORITHM_VERSION
    # Фаза B плана entity-aware усилений (2026-07-20) — чисто диагностические
    # поля, не меняют tension/anchor/narrative. См. _compute_entity_diversity().
    entity_count:        int   = 0
    anchor_entity_share: float = 1.0
    is_minority_anchor:  bool  = False


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


def _load_contradicts_map() -> dict:
    """
    Строит {signal_id: {id сигналов с которыми противоречит}} из relationships.json.

    Тот же фильтр, что scripts/validate_relationships.py (§6 Contradiction cycles):
    type == "contradicts" и status != "retracted".

    Вызывается ОДИН РАЗ в main() и передаётся в synthesize_cluster() как параметр —
    §17: synthesize_cluster() не читает файлы сам. DEGRADE GRACEFULLY: файл
    отсутствует/повреждён → safe_read_json возвращает [], map пустой — синтез
    продолжается с contradiction_bonus=0 для всех, не падает.
    """
    relationships = safe_read_json(RELATIONSHIPS_PATH, default=[])
    contradicts_map: dict = {}
    for rel in relationships:
        if rel.get("type") == "contradicts" and rel.get("status") != "retracted":
            from_id = rel.get("from_id", "")
            to_id   = rel.get("to_id", "")
            if from_id and to_id:
                contradicts_map.setdefault(from_id, set()).add(to_id)
    return contradicts_map


def _load_signal_entity_map() -> dict:
    """
    Строит {signal_id: entity_id} из ENTITIES.json.entities[].signal_refs[].

    Фаза A плана entity-aware усилений синтезатора (2026-07-20, эксперимент на
    btc_treasury_competition). Используется deduplicate_signals() для более
    точного ключа дедупликации в мульти-акторных кластерах — см. докстринг
    deduplicate_signals() для полного обоснования.

    Вызывается ОДИН РАЗ в main() и передаётся в synthesize_cluster() как
    параметр — §17: synthesize_cluster() не читает файлы сам, тот же паттерн,
    что _load_contradicts_map(). DEGRADE GRACEFULLY: файл отсутствует/повреждён
    → safe_read_json возвращает {}, map пустой — дедупликация продолжает
    работать по старому ключу (actor) для всех сигналов, не падает.

    Сигнал, не упомянутый ни в одной сущности (агрегатные сигналы вроде
    «Топ-100 компаний», не про одну конкретную компанию), в map не попадает —
    deduplicate_signals() для него использует actor как раньше.
    """
    raw = safe_read_json(ENTITIES_PATH, default={})
    entities = raw.get("entities", []) if isinstance(raw, dict) else raw
    signal_entity_map: dict = {}
    for entity in entities:
        entity_id = entity.get("id", "")
        for sid in entity.get("signal_refs", []):
            signal_entity_map[sid] = entity_id
    return signal_entity_map


def _compute_entity_diversity(
    active_signals: list[dict],
    anchor_id: str,
    signal_entity_map: dict,
) -> tuple[int, float]:
    """
    Фаза B плана entity-aware усилений (2026-07-20). Только измерение —
    не влияет на выбор tension/anchor/narrative (это осталось в Шаге 6,
    не тронуто). Использует ту же identity-логику, что deduplicate_signals()
    (Фаза A): entity_id из signal_entity_map, фолбэк на actor.

    Returns:
        (entity_count, anchor_entity_share)
        entity_count — число уникальных identity среди active_signals
        anchor_entity_share — доля active_signals с той же identity, что anchor
    """
    def identity(s: dict) -> str:
        return signal_entity_map.get(s.get("id", ""), s.get("actor", ""))

    identities = [identity(s) for s in active_signals]
    entity_count = len(set(identities))

    if not active_signals:
        return entity_count, 1.0

    anchor_signal = next((s for s in active_signals if s.get("id") == anchor_id), None)
    if anchor_signal is None:
        return entity_count, 1.0

    anchor_identity = identity(anchor_signal)
    matching = sum(1 for ident in identities if ident == anchor_identity)
    anchor_entity_share = matching / len(active_signals)
    return entity_count, anchor_entity_share


def _find_cross_cluster_entities(
    all_signals: list[dict],
    signal_entity_map: dict,
    primary_min: int = CROSS_CLUSTER_PRIMARY_MIN_SIGNALS,
    secondary_min: int = CROSS_CLUSTER_SECONDARY_MIN_SIGNALS,
) -> dict[str, set[str]]:
    """
    ADR-017 / находка 3 плана entity-aware усилений (2026-07-20/22). Только
    измерение — вызывается СНАРУЖИ synthesize_cluster(), после того как все
    кластеры уже синтезированы независимо (контракт §17, docs/NIES.md, не
    нарушается: ни один кластер не узнаёт о существовании других изнутри
    своего синтеза). Не меняет выбор tension/anchor/narrative ни в одном
    кластере.

    Находит сущности с общей центральностью сразу для >= 2 независимых
    нарративов, которую сейчас никто не фиксирует (подтверждённый случай:
    'strategy' в strategy_model_stress И bitcoin_governance_debate).

    ПОРОГ — асимметричный (Вариант 2, ADR-017 amendment 2026-07-22).
    Изначальный план требовал >= primary_min сигналов В КАЖДОМ из >= 2
    кластеров — но реальный мотивирующий случай ('strategy': 16 сигналов
    в strategy_model_stress, 1 в bitcoin_governance_debate через
    NAR-2026-0711-001) сам не проходит симметричный порог. Отсекать
    находку порогом, введённым ради неё же, — внутреннее противоречие.
    Асимметрия: сущность должна встречаться в >= 2 разных кластерах
    (secondary_min сигналов достаточно для учёта присутствия), и хотя бы
    в ОДНОМ из них иметь весомое присутствие (>= primary_min) — так
    отсекается случай "1 сигнал и там, и там" (шумное совпадение), но не
    отсекается "много в одном, один вскользь в другом" (реальный кейс).

    Args:
        all_signals: ПОЛНЫЙ список сигналов (не отфильтрованный по одному
            кластеру) — иначе кросс-кластерность физически не обнаружить.
        signal_entity_map: {signal_id: entity_id} из _load_signal_entity_map(),
            та же идентичность, что использует Фаза A/B.
        primary_min: минимум сигналов хотя бы в одном кластере (весомое
            присутствие, не разовое упоминание).
        secondary_min: минимум сигналов, чтобы засчитать присутствие
            сущности в остальных кластерах отчёта.

    Returns:
        {entity_id: {кластеры, где у сущности >= secondary_min сигналов}}
        — только для сущностей, у которых таких кластеров >= 2 И хотя бы
        один из них проходит primary_min. Сигналы без entity_id (не в
        signal_entity_map — агрегатные сигналы) не участвуют, тот же
        фолбэк-принцип, что в остальных Фазах.
    """
    entity_cluster_counts: dict[str, dict[str, int]] = {}
    for s in all_signals:
        eid = signal_entity_map.get(s.get("id", ""))
        cluster = s.get("cluster")
        if not eid or not cluster:
            continue
        counts = entity_cluster_counts.setdefault(eid, {})
        counts[cluster] = counts.get(cluster, 0) + 1

    result: dict[str, set[str]] = {}
    for eid, counts in entity_cluster_counts.items():
        present = {c for c, n in counts.items() if n >= secondary_min}
        if len(present) < 2:
            continue
        if not any(counts[c] >= primary_min for c in present):
            continue
        result[eid] = present
    return result


def _get_contradicts(signal: dict, contradicts_map: dict) -> list:
    """
    Возвращает id сигналов, с которыми signal противоречит.

    LEGACY_LINKS_ENABLED=True  → links.contradicts сигнала (путь до Фазы 0)
    LEGACY_LINKS_ENABLED=False → contradicts_map из relationships.json (текущий
                                   путь; миграция IRP v1 Wave 1 / REM-B2 завершена
                                   2026-07-01)

    ИСПРАВЛЕННЫЙ БАГ (2026-07-04): до этой правки функция при
    LEGACY_LINKS_ENABLED=False безусловно возвращала [] — relationships.json уже
    существовал (156 записей после миграции), но никогда не читался. Contradiction
    bonus в score был равен 0 для всех сигналов с 2026-07-01 — anchor/tension
    selection по MAX(contradicts) фактически не работал ни для одного кластера,
    молча деградировав до freshness+weight+role. Риск был предугадан заранее (см.
    ALGORITHM.md, «Чувствительные места», запись до миграции) но не устранён
    синхронно с флагом. Тестового покрытия на эту комбинацию не было — обнаружено
    вручную при инженерной сверке (IRP Wave 2-5), не автоматикой.
    """
    if LEGACY_LINKS_ENABLED:
        return (signal.get("links") or {}).get("contradicts", []) or []
    return sorted(contradicts_map.get(signal.get("id", ""), set()))


def _score_signal(signal: dict, contradicts_map: dict) -> SignalScore:
    age         = _age_days(signal.get("date", "2000-01-01"))
    contradicts = _get_contradicts(signal, contradicts_map)
    return SignalScore(
        freshness=_freshness(age),
        weight=_weight_score(signal.get("weight", "media")),
        role=_role_score(signal.get("narrative_role", "background")),
        contradiction=len(contradicts) * CONTRADICTION_BONUS,
    )


def _rank_signals(signals: list[dict], contradicts_map: dict) -> list[tuple[dict, SignalScore]]:
    """
    Ранжирует сигналы по importance DESC.
    4-уровневый tiebreaker (TD6):
      1. score.total DESC
      2. weight_score DESC
      3. date DESC
      4. id ASC — гарантирует детерминизм
    """
    scored = [(s, _score_signal(s, contradicts_map)) for s in signals]
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
    """
    ШАГ 3: определяет фазу кластера по распределению narrative_role.

    Фаза C плана entity-aware усилений (2026-07-20). До этой правки условие
    "trigger>0 И complication>0 → active" срабатывало независимо от
    СООТНОШЕНИЯ — кластер с 5 trigger/15 complication читался неотличимо
    от кластера с 1 trigger/1 complication, хотя первый явно "утяжелился"
    осложнениями. Добавлена проверка: если complication перевешивает
    trigger в COMPLICATION_DOMINANCE_RATIO раз и более — фаза "tension",
    даже при наличии хотя бы одного trigger. Resolution по-прежнему
    побеждает безусловно и первым — эта проверка её не касается.

    Порог — измеримое свойство распределения ролей внутри кластера, не
    имя кластера — работает одинаково для любого кластера, который в
    будущем накопит похожий перевес.
    """
    roles  = [s.get("narrative_role", "background") for s in signals]
    counts = {r: roles.count(r) for r in set(roles)}
    if counts.get("resolution", 0) > 0:
        return "resolution"
    trigger_count      = counts.get("trigger", 0)
    complication_count = counts.get("complication", 0)
    if trigger_count > 0 and complication_count > 0:
        if complication_count >= COMPLICATION_DOMINANCE_RATIO * trigger_count:
            return "tension"
        return "active"
    if complication_count > trigger_count:
        return "tension"
    return "structural"


def _select_tension_source(signals: list[dict], contradicts_map: dict) -> Optional[dict]:
    """
    ШАГ 6: выбирает сигнал-источник tension.

    Приоритет:
      1. Resolution signal (самый свежий) — закрывает цикл кластера,
         его tension должен звучать первым, перекрывая открытые complications.
      2. MAX(contradicts) → MAX(weight) → MAX(date) — для active/tension фаз
         где явного разрешения ещё нет.

    Rationale: если кластер достиг фазы resolution, показывать старый
    complication-tension вводит пользователя в заблуждение — вопрос
    уже закрыт, но карточка продолжает заявлять что он открыт.
    """
    candidates = [s for s in signals if s.get("tension")]
    if not candidates:
        return None

    # Приоритет 1: resolution всегда побеждает (самый свежий если их несколько)
    resolutions = [s for s in candidates if s.get("narrative_role") == "resolution"]
    if resolutions:
        resolutions.sort(
            key=lambda s: datetime.strptime(
                s.get("date", "2000-01-01"), DATE_FORMAT
            ).toordinal(),
            reverse=True,
        )
        return resolutions[0]

    # Приоритет 2: обычная логика MAX(contradicts) → MAX(weight) → MAX(date)
    candidates.sort(key=lambda s: (
        -len(_get_contradicts(s, contradicts_map)),
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


def deduplicate_signals(
    signals: list[dict],
    signal_entity_map: Optional[dict] = None,
) -> tuple[list[dict], list[str]]:
    """
    §16: Удаляет дублирующие сигналы перед синтезом.
    Дубликат = одинаковый (date, entity_or_actor, cluster, dir).

    Фаза A плана entity-aware усилений (2026-07-20). Раньше ключ был
    (date, actor, cluster, dir) — слишком груб для мульти-акторного кластера:
    в btc_treasury_competition (9+ компаний, все actor='corporate') это ложно
    схлопывало сигналы РАЗНЫХ компаний в один день в "дубликаты" и роняло их
    из синтеза. Подтверждено на реальных данных: 3 пары сигналов о разных
    компаниях (Strive/H100, OranjeBTC/Strive, Q2-агрегат/CRYL) ошибочно
    считались дублями только из-за совпадения date+actor+dir.

    signal_entity_map (опционально, {signal_id: entity_id} из
    _load_signal_entity_map(), §17 — передаётся вызывающим, не читается
    здесь) уточняет ключ до конкретной сущности там, где сигнал с ней связан.
    Сигнал без записи в map (агрегатные сигналы не про одну компанию, либо
    map не передан вовсе — None по умолчанию) использует actor как раньше —
    100% обратная совместимость для однокомпонентных кластеров и для любого
    вызова без нового параметра.

    Из группы оставляет сигнал с наибольшим weight_score.

    Returns:
        (deduplicated, ignored_ids)
    """
    signal_entity_map = signal_entity_map or {}
    seen:        dict[tuple, dict] = {}
    ignored_ids: list[str]         = []

    for signal in signals:
        entity_or_actor = signal_entity_map.get(signal.get("id", ""), signal.get("actor", ""))
        key = (
            signal.get("date", ""),
            entity_or_actor,
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


def handle_uncertainty(
    signals: list[dict],
    phase: str,
    ranked: list[tuple],
    contradicts_map: dict,
) -> dict:
    """
    B3 ARR v2: Обрабатывает неопределённые ситуации перед финальным синтезом.

    Три критических ситуации из UNCERTAINTY_RULES (settings.py):
      1. 50/50 pos/neg → direction = "contested", score penalty 0.7
      2. Два+ trigger → выбрать более свежий (most_recent)
      3. Устаревший tension (победитель > 90 дней) → метка STALE

    Возвращает dict с корректировками которые synthesize_cluster применяет.
    Пустой dict = неопределённости не обнаружено.
    """
    from datetime import date as _date
    from config.settings import UNCERTAINTY_RULES

    adjustments: dict = {}

    # ── 1. Баланс pos/neg → contested ─────────────────────────────────────
    threshold = UNCERTAINTY_RULES.get("pos_neg_balance_threshold", 0.6)
    penalty   = UNCERTAINTY_RULES.get("contested_strength_penalty", 0.7)

    pos_count = sum(1 for s in signals if s.get("dir") == "pos")
    neg_count = sum(1 for s in signals if s.get("dir") == "neg")
    total_dir = pos_count + neg_count

    if total_dir >= 2:
        ratio = pos_count / total_dir
        if (1 - threshold) <= ratio <= threshold:
            adjustments["direction"]        = "contested"
            adjustments["score_multiplier"] = penalty
            logger.info(
                f"Uncertainty: pos/neg balance {pos_count}/{neg_count} "
                f"→ contested (penalty ×{penalty})"
            )

    # ── 2. Несколько trigger → выбрать самый свежий ────────────────────────
    resolution = UNCERTAINTY_RULES.get("multiple_triggers_resolution", "most_recent")
    triggers = [s for s in signals if s.get("narrative_role") == "trigger"]

    if len(triggers) > 1 and resolution == "most_recent":
        triggers_sorted = sorted(
            triggers,
            key=lambda s: s.get("date", "1970-01-01"),
            reverse=True
        )
        adjustments["anchor_trigger"]    = triggers_sorted[0]["id"]
        adjustments["ignored_triggers"]  = [s["id"] for s in triggers_sorted[1:]]
        logger.info(
            f"Uncertainty: {len(triggers)} triggers → "
            f"using most recent {triggers_sorted[0]['id']}, "
            f"ignoring {adjustments['ignored_triggers']}"
        )

    # ── 3. Устаревший tension ─────────────────────────────────────────────
    staleness_days = UNCERTAINTY_RULES.get("tension_staleness_days", 90)
    stale_label    = UNCERTAINTY_RULES.get(
        "tension_stale_label",
        "⚠ Нарратив устарел — tension не обновлялся более 90 дней"
    )

    # Победитель tension = сигнал с MAX(contradicts)
    winner = None
    max_contra = -1
    for s in signals:
        n = len(_get_contradicts(s, contradicts_map))
        if n > max_contra and s.get("tension"):
            max_contra = n
            winner     = s

    if winner:
        try:
            age = (_date.today() - _date.fromisoformat(winner.get("date", "1970-01-01"))).days
            if age > staleness_days:
                adjustments["tension_stale"]       = True
                adjustments["tension_stale_label"] = stale_label
                adjustments["tension_age_days"]    = age
                logger.warning(
                    f"Uncertainty: tension winner {winner['id']} "
                    f"is {age} days old → STALE label applied"
                )
        except ValueError:
            pass

    return adjustments


@measure_performance("synthesize_cluster")
def synthesize_cluster(
    cluster_key:        str,
    signals:            list[dict],
    previous_synthesis: Optional[dict] = None,   # §17: передаётся снаружи
    contradicts_map:    Optional[dict] = None,    # §17: передаётся снаружи, см. _load_contradicts_map()
    signal_entity_map:  Optional[dict] = None,    # §17: передаётся снаружи, см. _load_signal_entity_map()
) -> SynthesisResult:
    """
    12-шаговый алгоритм синтеза нарратива для кластера.

    §17: previous_synthesis, contradicts_map и signal_entity_map передаются
    как параметры — synthesizer не читает файлы сам. Это гарантирует
    соблюдение архитектурного контракта: Delivery Context не записывает,
    Synthesis Context не читает файлы напрямую.

    Args:
        cluster_key:        ключ кластера
        signals:            список сигналов кластера
        previous_synthesis: dict предыдущего синтеза или None (загружает caller)
        contradicts_map:    dict {signal_id: {ids противоречий}} из
                             relationships.json или None → {} (загружает caller
                             через _load_contradicts_map(), см. main())
        signal_entity_map:  dict {signal_id: entity_id} из ENTITIES.json или
                             None → {} (загружает caller через
                             _load_signal_entity_map(), см. main()) — Фаза A
                             плана entity-aware усилений, уточняет ключ
                             дедупликации в мульти-акторных кластерах

    Raises:
        EmptyClusterError: если нет активных сигналов в окне WINDOW_DAYS_DEFAULT
    """
    if contradicts_map is None:
        contradicts_map = {}
    signal_entity_map = signal_entity_map or {}

    logger.debug(
        f"Synthesizing cluster '{cluster_key}' ({len(signals)} signals)",
        extra={"cluster": cluster_key}
    )

    # §16: Дедупликация перед синтезом
    signals, ignored_ids = deduplicate_signals(signals, signal_entity_map)

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
    ranked         = _rank_signals(active_signals, contradicts_map)
    ranked_signals = [s for s, _ in ranked]
    signals_used   = [s.get("id", "") for s in ranked_signals]

    # ШАГ 3: Фаза
    phase = _detect_phase(ranked_signals)

    # ШАГ 3.5: Обработка неопределённости (B3 ARR v2)
    uncertainty = handle_uncertainty(active_signals, phase, ranked, contradicts_map)

    # ШАГ 4: Разбивка по ролям
    triggers       = [s for s in ranked_signals if s.get("narrative_role") == "trigger"]
    complications  = [s for s in ranked_signals if s.get("narrative_role") == "complication"]
    resolutions    = [s for s in ranked_signals if s.get("narrative_role") == "resolution"]

    anchor_trigger      = triggers[0]      if triggers      else ranked_signals[0]
    anchor_complication = complications[0] if complications else None
    anchor_resolution   = resolutions[0]   if resolutions   else None

    # ШАГ 5: Contradiction weighting (учтён в _score_signal)

    # ШАГ 6: Tension
    tension_source = _select_tension_source(ranked_signals, contradicts_map)
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
    # Находка 2026-07-21: было has_contradicts=any(...) — бинарный флаг не
    # различал кластер с 1 contradicts-связью из 5 и с 7 из 13 сигналов.
    # См. обоснование отличия от ADR-011 в докстринге calculate_confidence().
    contradicts_share = (
        sum(1 for s in active_signals if _get_contradicts(s, contradicts_map)) / len(active_signals)
        if active_signals else 0.0
    )
    all_stale    = all(
        _age_days(s.get("date", "2000-01-01")) > STALE_THRESHOLD
        for s in active_signals
    )
    confidence = calculate_confidence(
        score_total=total_score,
        n_signals=len(active_signals),
        contradicts_share=contradicts_share,
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

    # Применить uncertainty adjustments к score_multiplier
    if uncertainty.get('score_multiplier'):
        cluster_score.freshness = int(
            cluster_score.freshness * uncertainty['score_multiplier']
        )

    # ШАГ 12: Rationale
    anchor_id  = (tension_source or anchor_trigger).get("id", "?")
    anchor_obj = tension_source or anchor_trigger

    # Фаза B: диагностика периферийности anchor — только измерение, не влияет
    # ни на что выше (tension/anchor уже выбраны на Шаге 6, не переопределяются)
    entity_count, anchor_entity_share = _compute_entity_diversity(
        active_signals, anchor_id, signal_entity_map
    )
    is_minority_anchor = (
        entity_count >= MULTI_ENTITY_THRESHOLD
        and anchor_entity_share < MINORITY_ANCHOR_SHARE
    )

    rationale  = (
        f"Tension from {anchor_id} "
        f"(contradicts: {len(_get_contradicts(anchor_obj, contradicts_map))}, "
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
        uncertainty=uncertainty,
        entity_count=entity_count,
        anchor_entity_share=anchor_entity_share,
        is_minority_anchor=is_minority_anchor,
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
        "uncertainty":      result.uncertainty,
        "entity_count":        result.entity_count,
        "anchor_entity_share": round(result.anchor_entity_share, 3),
        "is_minority_anchor":  result.is_minority_anchor,
        "generated_at":     result.generated_at,
        "algorithm_version":result.algorithm_version,
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

    # §17: загружаем relationships вне synthesize_cluster(), один раз на весь прогон
    contradicts_map = _load_contradicts_map()
    # §17: то же для карты сущностей — Фаза A плана entity-aware усилений
    signal_entity_map = _load_signal_entity_map()

    for cluster_key, signals in clusters.items():
        try:
            # §17: загружаем previous_synthesis вне synthesize_cluster()
            previous = _load_previous_synthesis(cluster_key)

            result = synthesize_cluster(
                cluster_key, signals,
                previous_synthesis=previous,
                contradicts_map=contradicts_map,
                signal_entity_map=signal_entity_map,
            )

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
                "entity_count":        result.entity_count,
                "anchor_entity_share": round(result.anchor_entity_share, 3),
                "is_minority_anchor":  result.is_minority_anchor,
                "generated_at":     result.generated_at,
                "algorithm_version":result.algorithm_version,
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
    # ADR-017: top-level ключ, не per-cluster — про отношение между
    # кластерами, а не свойство одного. Считается на ПОЛНОМ all_signals,
    # не на отфильтрованном подмножестве.
    cross_cluster = _find_cross_cluster_entities(all_signals, signal_entity_map)
    results["_cross_cluster_entities"] = {
        eid: sorted(clusters) for eid, clusters in cross_cluster.items()
    }

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
