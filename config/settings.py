"""
config/settings.py
Bitcoin Intel — централизованные настройки системы

Все константы, политики и пороги собраны здесь.
Импортировать: from config.settings import *
"""

import os

# ─── Политика дат ───────────────────────────────────────────────────────────
# Все даты хранятся в UTC, формат YYYY-MM-DD
DATE_POLICY = "UTC"
DATE_FORMAT  = "%Y-%m-%d"

# ─── Политика кодировки ──────────────────────────────────────────────────────
# Все файловые операции используют UTF-8, ensure_ascii=False при JSON
ENCODING          = "utf-8"
JSON_ENSURE_ASCII = False

# ─── Детерминизм ─────────────────────────────────────────────────────────────
# PYTHONHASHSEED=0 обязателен для воспроизводимости hash()-независимого кода.
# Проверка при старте синтезатора:
def assert_deterministic_env():
    """Вызывать в начале synthesizer.py перед любыми вычислениями."""
    seed = os.environ.get("PYTHONHASHSEED", "random")
    if seed == "random":
        raise RuntimeError(
            "PYTHONHASHSEED не задан. "
            "Запускай: PYTHONHASHSEED=0 python3 scripts/synthesizer.py"
        )

# ─── Score: максимально возможные баллы ──────────────────────────────────────
# Формула для одного сигнала:
#   freshness_score : max 3  (age <= 7 дней)
#   weight_score    : max 4  (onchain)
#   role_score      : max 4  (trigger)
#   contradiction   : +5 за каждый contradicts (бонус, не ограничен)
#
# MAX_PER_SIGNAL — без бонуса contradicts (базовый потолок):
MAX_PER_SIGNAL = 3 + 4 + 4   # = 11

def calculate_max_possible_score(n: int) -> int:
    """
    Теоретический потолок score для кластера из n сигналов.
    Не учитывает contradicts-бонус (он не ограничен сверху).
    Используется для нормализации confidence.

    >>> calculate_max_possible_score(1)
    11
    >>> calculate_max_possible_score(5)
    55
    """
    return max(n * MAX_PER_SIGNAL, 1)  # минимум 1 — защита от деления на ноль

def calculate_confidence(score_total: int, n_signals: int,
                          contradicts_share: float, all_stale: bool,
                          has_tension: bool) -> float:
    """
    Нормализованная уверенность синтеза [0.1, 1.0].

    Параметры:
        score_total    — суммарный score кластера
        n_signals      — число сигналов в кластере
        contradicts_share — доля сигналов кластера с хотя бы одним
                            contradicts-сигналом (0.0-1.0)
        all_stale      — все сигналы старше 30 дней
        has_tension    — у победителя есть tension (не fallback)

    >>> calculate_confidence(55, 5, 1.0, False, True)  # идеальный случай
    1.0

    НАХОДКА (2026-07-21, продолжение entity-aware экспериментов): было
    has_contradicts: bool — "есть хоть один сигнал с contradicts или нет".
    Реальные данные показали разброс от 0% (leverage_deleveraging_cycle) до
    54% (etf_institutional_flow) сигналов кластера с contradicts-связями —
    бинарный флаг не различал кластер с 1 связью из 5 и кластер с 7 из 13,
    хотя разница в фактической перекрёстной подтверждённости огромна.

    ОТЛИЧИЕ ОТ ADR-011 (docs/ADR-011-confidence-calibration-deferred.md,
    2026-06-30 — важно прочитать перед повторным изменением этой функции):
    та комиссия отклонила КАЛИБРОВКУ КОЭФФициентов формулы (0.8/0.7/0.6/0.5)
    под данные — на выборке 5-8 кластеров это было бы подгонкой под шум.
    Это изменение — НЕ калибровка коэффициентов: границы 0.8 (было at
    has_contradicts=False) и 1.0 (было at has_contradicts=True) сохранены
    буквально теми же, что уже были приняты и не пересчитаны заново —
    меняется только ВХОДНАЯ переменная (с бинарной на непрерывную долю),
    линейно интерполируя между уже существующими границами. Ни одно новое
    число не введено и не подобрано под текущие данные. См. также
    scripts/quality_report.py — счётчик MIN_SYNTHESES_FOR_CALIBRATION
    (порог калибровки коэффициентов) этим изменением не затронут и не
    закрыт — это разные вопросы: ЧТО формула получает на вход (это
    изменение) vs КАКИЕ веса она использует (по-прежнему ждёт 30 синтезов).
    """
    max_score = calculate_max_possible_score(n_signals)
    if max_score == 0:
        return 0.1

    raw = score_total / max_score

    # Снижающие модификаторы
    if n_signals == 1:
        raw *= 0.5
    raw *= (0.8 + 0.2 * contradicts_share)   # было: if not has_contradicts: raw *= 0.8
    if all_stale:
        raw *= 0.7
    if not has_tension:
        raw *= 0.6

    return max(0.1, min(1.0, raw))

# ─── Трёхуровневая шкала уверенности (BAMS Р9) ───────────────────────────────
# docs/NIES.md AD-1, docs/ADR-020-ad1-blocker-decomposition.md.
#
# НЕ калибровка/замена calculate_confidence() выше — отдельная, дополнительная
# классификация. calculate_confidence() остаётся эвристикой для ранжирования
# и внутреннего rationale; classify_confidence_tier() — дискретная шкала,
# которую буквально требует BAMS Р9 и которой не было ни в каком виде
# (сам разрыв — предмет AD-1).
#
# weight ∈ {onchain, primary} — "прямое доказательство" по BAMS Р9. market/media
# — косвенное. Единственный runtime-источник этого деления (наравне с
# WEIGHT_SCORE ниже) — не дублировать по значению в другом месте (ADR-014).
DIRECT_EVIDENCE_WEIGHTS = frozenset({"onchain", "primary"})


def classify_confidence_tier(direct_evidence_count: int,
                              anchor_has_disputed_facts: bool,
                              all_stale: bool) -> str:
    """
    Дискретная уверенность по критериям BAMS Р9 ("Шкала уверенности") —
    high/medium/low. Критерии оценивают состояние доказательств кластера
    на момент синтеза, не предсказывают будущее (см. ADR-020).

    Параметры — уже агрегированные на уровне кластера, вычисляются вызывающей
    стороной (scripts/synthesizer.py, ШАГ 11):
        direct_evidence_count     — число активных сигналов кластера с
                                     weight ∈ DIRECT_EVIDENCE_WEIGHTS
        anchor_has_disputed_facts — есть ли непустой disputed_facts[] у
                                     anchor-сигнала (tension_source или
                                     anchor_trigger) — НЕ у любого сигнала
                                     кластера. Критерий Р9 — "противоречие
                                     в КЛЮЧЕВОМ факте", ключевой факт — тот,
                                     на котором держится вывод ЭТОГО кластера,
                                     не любой факт в его доказательной базе.
                                     Проверено эмпирически на реальном корпусе
                                     (2026-08-15): агрегация "любой сигнал
                                     кластера" систематически наказывает
                                     крупные, лучше всего обеспеченные
                                     кластеры — 1 спорный факт из 22-28
                                     сигналов топил весь кластер до low,
                                     тогда как однoсигнальные кластеры без
                                     единого спора получали high. Тот же
                                     класс инверсии, что уже пойман для
                                     links.contradicts в ADR-020.
        all_stale                 — все активные сигналы кластера старше
                                     STALE_THRESHOLD (та же величина, что
                                     already использует calculate_confidence)

    Критерий "исторический прецедент" (BAMS Р9) сюда сознательно не входит:
    BAMS v1.3 переформулировала его как опциональный бонус, не обязательное
    условие для high (см. ADR-020, разрешение открытого вопроса) — при
    текущем отсутствии Golden Dataset-матчинга (AD-3) он просто никогда не
    участвует, это не пробел данной функции.

    "Данных структурно недостаточно" (BAMS Р9, критерий low) отдельно не
    моделируется — покрывается direct_evidence_count == 0 и all_stale;
    вводить отдельный порог по числу сигналов без калибровки было бы той же
    "фиктивной точностью", которую ADR-011 уже отклонила для другой части
    формулы.

    >>> classify_confidence_tier(2, False, False)
    'high'
    >>> classify_confidence_tier(1, False, False)
    'medium'
    >>> classify_confidence_tier(0, False, False)
    'low'
    >>> classify_confidence_tier(5, True, False)
    'low'
    >>> classify_confidence_tier(5, False, True)
    'low'
    """
    if anchor_has_disputed_facts:
        return "low"
    if direct_evidence_count == 0:
        return "low"
    if all_stale:
        return "low"
    if direct_evidence_count >= 2:
        return "high"
    return "medium"

# ─── Score: веса по полям ────────────────────────────────────────────────────
FRESHNESS_SCORE = {
    "fresh":   3,   # age <= 7 дней
    "recent":  1,   # age <= 30 дней
    "stale":   0,   # age > 30 дней
}

WEIGHT_SCORE = {
    # Единственный runtime-источник (ADR-014, IRP v1 Wave 3 / REM-M06).
    # ontology.json.weight_scores — display-only копия, помечена _note.
    "onchain": 4,
    "primary": 3,
    "market":  2,
    "media":   1,
}

ROLE_SCORE = {
    "trigger":       4,
    "complication":  3,
    "resolution":    2,
    "background":    0,
}

CONTRADICTION_BONUS = 5   # за каждый id в links.contradicts

# ─── Фаза B плана entity-aware усилений (2026-07-20) ────────────────────────
# Эксперимент на btc_treasury_competition: anchor-сигнал может представлять
# меньшинство сущностей кластера (найдено: anchor_entity_share=0.095 при
# entity_count=13 — El Salvador/МВФ стал единственной "золотой полосой"
# кластера, 86% которого про корпорации). Пороги — измеримые свойства
# кластера, не имя конкретного кластера, чтобы работать на любом будущем
# мульти-акторном кластере, не только на этом одном.
MULTI_ENTITY_THRESHOLD = 5      # кластер считается мульти-акторным от N уникальных сущностей
MINORITY_ANCHOR_SHARE  = 0.15   # anchor представляет <15% сигналов — подозрение на периферийность

# ─── Находка 3 плана entity-aware усилений — ADR-017 (2026-07-22) ───────────
# Диагностика кросс-кластерной центральности: сущность (напр. 'strategy')
# может одновременно быть центральной для двух разных нарративов, что
# синтезатор не фиксирует нигде (кластеры обрабатываются независимо, §17).
# Только измерение — не меняет выбор tension/anchor ни в одном кластере.
#
# Асимметричный порог (Вариант 2, ADR-017 amendment 2026-07-22): исходный
# план требовал >=2 сигналов В КАЖДОМ из >=2 кластеров — но реальный
# мотивирующий случай ('strategy': 16 сигналов в strategy_model_stress,
# 1 в bitcoin_governance_debate через NAR-2026-0711-001) сам не проходит
# этот порог. Симметричный порог отсекал бы находку, ради которой его
# вводили. Асимметрия: сущность нужна в >=2 разных кластерах (secondary),
# и хотя бы в ОДНОМ из них — весомое присутствие (primary), не разовое.
CROSS_CLUSTER_PRIMARY_MIN_SIGNALS   = 2   # весомое присутствие хотя бы в одном кластере
CROSS_CLUSTER_SECONDARY_MIN_SIGNALS = 1   # минимум для учёта присутствия в остальных кластерах

# ─── Contradiction Detector ──────────────────────────────────────────────────
# Порог score (semantic_inverse_score / score_pair) для предложения аналитику.
# Вынесен сюда из scripts/contradiction_detector.py (N2 ARR v3) — единая
# точка настройки порогов вместе с остальными.
# Целевая Precision на этом пороге = 60% (не 85% из BLUEPRINT §10) —
# см. docs/ADR-012-contradiction-precision-target.md. Пересмотр — при N>=150
# пар в tests/golden/fixtures/contradiction_pairs.json.
CONTRADICTION_PROPOSAL_THRESHOLD = 0.5

# ─── Кластер: пороги силы нарратива ─────────────────────────────────────────
SCORE_HOT      = 20   # 🔥 горячий нарратив
SCORE_STRONG   = 12   # strong
SCORE_MODERATE =  6   # moderate
# ниже SCORE_MODERATE → weak

# ─── Фаза C плана entity-aware усилений (2026-07-20) ────────────────────────
# Найдено на эксперименте: _detect_phase() при ЛЮБОМ trigger>0 И complication>0
# безусловно возвращает "active", независимо от соотношения — кластер с
# 5 trigger/15 complication (btc_treasury_competition, реальные данные)
# читается неотличимо от кластера с 1 trigger/1 complication. Порог ниже —
# явное соотношение "во сколько раз complication должен перевесить trigger,
# чтобы считать кластер утяжелившимся осложнениями, а не просто активным".
COMPLICATION_DOMINANCE_RATIO = 3   # complication >= 3x trigger → phase="tension", не "active"

def get_strength(score_total: int) -> str:
    if score_total >= SCORE_STRONG:
        return "strong"
    if score_total >= SCORE_MODERATE:
        return "moderate"
    return "weak"

# ─── Временные окна ──────────────────────────────────────────────────────────
WINDOW_DAYS_DEFAULT = 90    # сигналы старше не влияют на score
STALE_THRESHOLD     = 30    # дней до снижения freshness
ARCHIVE_THRESHOLD   = 180   # дней до авто-архивации сигнала

# ─── Файловые пути ───────────────────────────────────────────────────────────
SIGNALS_PATH         = "signals.json"
ENTITIES_PATH        = "ENTITIES.json"
SYNTHESIS_CACHE_PATH = "data/synthesis_cache.json"
EVENTS_LOG_PATH      = "data/events.jsonl"
RELATIONSHIPS_PATH   = "data/relationships.json"

# Счётчик реальных "кластеро-периодов" (ADR-011) — см. заметку 2026-07-31
# в docs/ADR-011-confidence-calibration-deferred.md. НЕ путать с
# SYNTHESIS_STORE_PATH ниже (устаревший, не обновлялся с 2026-06-29).
SYNTHESIS_HISTORY_PATH = "data/synthesis_history_count.json"

# ─── Переходный период: миграция links.* → relationships.json ────────────────
LEGACY_LINKS_ENABLED = False  # Фаза 0 завершена 2026-07-01: миграция выполнена (156 relationships), IRP v1 Wave 1 / B2

# ─── Рендер: UI контракты для пустых кластеров ───────────────────────────────
# Три состояния карточки нарратива (используется в index.html renderNarrativeItem):
#   "empty"    → кластер есть, сигналов нет или все stale → renderWeakSignalPlaceholder
#   "tension"  → есть tension, нет полного narrative      → renderTensionOnly
#   "full"     → все поля заполнены                       → renderFullCard
NARRATIVE_RENDER_STATES = ("empty", "tension", "full")

# ─── Error Handling Philosophy (P1 §1) ───────────────────────────────────────
#
# FAIL LOUD (raise исключение) когда:
#   - Входные данные нарушают инвариант (невалидный ID, отсутствует обязательное поле)
#   - Системная ошибка без обхода (disk full, lock timeout)
#   - Нарушение архитектурного контракта
#
# DEGRADE GRACEFULLY (log WARNING + return default) когда:
#   - Один сигнал из кластера повреждён → пропустить, синтезировать без него
#   - synthesis_cache устарел → перестроить на лету
#   - relationships.json отсутствует → работать с links.* (LEGACY_LINKS_ENABLED)
#   - Одно необязательное поле невалидно → логировать, использовать NULL_DEFAULT
#
# НИКОГДА:
#   - except: pass  (молчаливое поглощение исключений)
#   - продолжать запись если файл повреждён при чтении

ERROR_PHILOSOPHY = "fail_loud_on_boundary__degrade_gracefully_inside"
LOCK_TIMEOUT_SECONDS = 5

# ─── Component Initialization Order (P1 §4) ──────────────────────────────────
#
# При запуске любого скрипта соблюдать порядок:
#   1. assert_deterministic_env()      — проверить PYTHONHASHSEED
#   2. assert_required_files_exist()   — signals.json, ENTITIES.json
#   3. load ontology через параметр    — передавать в функции, не singleton
#   4. Инициализировать компонент
#   5. EventLog(EVENTS_LOG_PATH)       — готов к записи
#
# DEPENDENCY INJECTION RULE:
#   ✅ def synthesize(cluster, signals, ontology: dict)  — тестируемо
#   ❌ ontology = json.load(open("ontology.json"))       — глобальный singleton

INITIALIZATION_ORDER = [
    "assert_deterministic_env",
    "assert_required_files_exist",
    "load_ontology_via_parameter",
    "init_component",
    "init_event_log",
]

SYNTHESIS_STORE_PATH = "synthesis_store"

# ─── Confidence Calibration Gate (ADR-011, C2 ARR v3) ────────────────────────
# Калибровка confidence на статистически значимой выборке откладывается до
# накопления этого числа исторических "кластеро-периодов" — см.
# SYNTHESIS_HISTORY_PATH (data/synthesis_history_count.json), обновляется
# scripts/update_synthesis_history.py на каждый прогон CI-синтеза (см.
# .github/workflows/deploy.yml). До 2026-07-31 счётчик считал файлы в
# synthesis_store/ — механизм не обновлялся с 2026-06-29, пока реальный
# пайплайн синтеза давно переехал в data/synthesis_cache.json (заметка
# 2026-07-31 в ADR-011 — полная история находки и честный backfill).
# До достижения порога calculate_confidence() остаётся объяснённой
# эвристикой, проверяемой property-тестами
# (tests/unit/test_confidence_properties.py), а не статистической моделью.
MIN_SYNTHESES_FOR_CALIBRATION = 30


def assert_required_files_exist() -> None:
    """Проверяет наличие критических файлов перед запуском."""
    missing = [p for p in [SIGNALS_PATH, ENTITIES_PATH] if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError(
            f"Required files missing: {missing}. "
            f"Run from project root or check file paths in config/settings.py"
        )


# ─── Duplicate Signal Policy (P1 §6) ─────────────────────────────────────────
#
# Дубликат по ID → DuplicateSignalError (FAIL LOUD, блокирует запись)
# Похожий сигнал (date + actor + cluster) → WARNING (не блокирует)
#
# Два сигнала про одно событие с разными источниками — ЛЕГАЛЬНЫ.
# Аналитик осознанно добавляет оба для кросс-верификации.

DUPLICATE_WARNING_FIELDS = ["date", "actor", "cluster"]

# ─── Null Handling Rules (P2 §12) ────────────────────────────────────────────
#
# Правило в коде:
#   signal.get("tension") or ""      — текстовые поля
#   signal.get("data") or []         — списки
#   signal.get("confidence") or 0.5  — числа
#   signal.get("actor") or "unknown" — enum необязательные

NULL_DEFAULTS: dict = {
    "tension":           "",
    "context":           "",
    "caveat":            "",
    "macro_implication": "",
    "data":              [],
    "links": {
        "confirms":      [],
        "contradicts":   [],
        "context_chain": [],
    },
    "confidence": 0.5,
    "actor":      "unknown",
    "flow":       "neutral",
    "rationale":  "",
}

# ─── Data Retention Policy (P2 §11) ──────────────────────────────────────────
RETAIN_SYNTHESIS_DAYS  = 730   # 2 года — superseded синтезы
RETAIN_EVENTS_DAYS     = 365   # 1 год — events.jsonl ротация
RETAIN_SNAPSHOTS_COUNT = 7     # локальных backup снапшотов

SYNTHESIS_RETENTION: dict = {
    "generated":  30,    # дней; неутверждённые удалять через 30 дней
    "reviewed":   30,
    "approved":   None,  # бессрочно
    "published":  None,  # бессрочно
    "superseded": RETAIN_SYNTHESIS_DAYS,
    "archived":   None,  # бессрочно
}

# ─── Schema Versioning (P2 §14) ──────────────────────────────────────────────
SIGNAL_SCHEMA_VERSION = "1.0"

# Backward Compatibility:
#   PATCH: добавить необязательное поле → signal.get("new_field", default)
#   MINOR: переименование → читать оба: signal.get("new") or signal.get("old")
#   MAJOR: полная миграция всех файлов перед деплоем

SCHEMA_BACKWARD_COMPAT: dict = {
    "deprecated_fields": {
        "links": {
            "replaced_by": "relationships.json",
            "flag":        "LEGACY_LINKS_ENABLED",
        }
    }
}

# ─── Uncertainty Handling Rules (P3 §18) ─────────────────────────────────────
# tension_staleness_days ИСПРАВЛЕН с 90 → 60 (2026-07-31, ADR-019): при 90 флаг
# был структурно недостижим — active_signals в synthesize_cluster() уже
# отфильтрован по WINDOW_DAYS_DEFAULT=90 ДО вызова handle_uncertainty(),
# поэтому возраст победителя внутри неё математически не мог превысить 90.
# ИНВАРИАНТ (проверяется tests/unit/test_uncertainty_indicator.py::
# test_tension_staleness_days_below_synthesis_window): tension_staleness_days
# ДОЛЖЕН быть строго меньше WINDOW_DAYS_DEFAULT, иначе тот же баг повторится
# при любом будущем изменении одной из констант без другой.
#
# tension_staleness_signal_count (новое) — независимый, velocity-aware
# критерий: победитель считается устаревшим, если с его даты в кластер
# добавлено >= N новых сигналов, ДАЖЕ если по дням он моложе
# tension_staleness_days. Найдено на реальных данных (2026-07-31, разбор
# масштабирования): в двух самых быстрых кластерах (btc_treasury_competition,
# etf_institutional_flow) tension был "жив" по дням (30-42 дня), но за это
# время накопилось 12-14 новых сигналов без единого обновления заголовка —
# фиксированный день-порог для быстрого кластера практически бесполезен,
# т.к. кластер успевает архивировать/переросинтезировать раньше, чем
# набежит 60-90 дней. N=8 — эмпирически: на 11 реальных кластерах чётко
# разделяет 4 быстрых (8-14 новых сигналов) от 7 медленных (1-3) — не
# теоретическая оценка, реальный разрыв в распределении. Полная методология
# и honest caveat про произвольность конкретного N → ADR-019.
UNCERTAINTY_RULES: dict = {
    "pos_neg_balance_threshold": 0.6,   # pos/(pos+neg) < 0.6 → contested
    "contested_strength_penalty": 0.7,  # score × 0.7
    "multiple_triggers_resolution": "most_recent",
    "tension_staleness_days": 60,
    "tension_staleness_signal_count": 8,
    "tension_stale_label": "⚠ Нарратив устарел — tension не обновлялся более 60 дней",
    "tension_stale_label_velocity": "⚠ Нарратив устарел — уже {n} новых сигналов кластера с момента этого tension",
}

# ─── Idempotency Matrix (P2 §15) ─────────────────────────────────────────────
# validator.py                → ✅ идемпотентен
# synthesizer.py              → ✅ идемпотентен (не пишет, только возвращает)
# synthesis_cache_builder.py  → ✅ идемпотентен (temp→rename)
# contradiction_detector.py  → ✅ идемпотентен
# add_signal.py               → ⚠ НЕ идемпотентен (side effect = ожидаемо)
# history_query.py            → ✅ идемпотентен
# migrate_relationships.py    → ✅ идемпотентен (пропускает дубликаты)
# validate_relationships.py   → ✅ идемпотентен
# quality_report.py           → ✅ идемпотентен
# backup.py                   → ⚠ создаёт новый снапшот (side effect = ожидаемо)

# ─── Error Exit Codes (P2 §9) ────────────────────────────────────────────────
ERROR_EXIT_CODES: dict = {
    "success":              0,
    "business_logic_error": 1,   # ValidationError, DuplicateSignalError
    "system_error":         2,   # непредвиденное исключение
    "data_integrity_error": 3,   # CorruptedFileError, OrphanRelationshipError
}


# ─── Business Rules (D11) ────────────────────────────────────────────────────
# Явные бизнес-правила системы. Нарушение → ValidationError.

BUSINESS_RULES = {
    # Сигнал
    "signal_id_format":        r"^[A-Z]{2,5}-\d{4}-\d{4}-\d{3}$",
    "tension_must_start_upper": True,   # tension[0].isupper()
    "tension_must_have_marker": True,   # содержит vs / несмотря на / при условии
    "macro_implication_min_len": 50,    # не пересказ события
    "date_format":             "%Y-%m-%d",

    # Синтез
    "max_clusters_in_overview": 4,      # MAX_SHOWN
    "min_score_for_overview":   0,      # SCORE_MIN
    "window_days":              90,     # WINDOW_DAYS_DEFAULT

    # Связи
    "contradiction_threshold":  0.5,    # semantic_inverse_score >= 0.5
    "duplicate_warning_fields": ["date", "actor", "cluster"],

    # Golden Dataset
    "golden_dataset_min_signals": 15,
    "golden_dataset_min_clusters": 3,
}
ONTOLOGY_PATH = "ontology.json"   # B1: онтология нарративного движка
