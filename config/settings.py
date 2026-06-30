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
                          has_contradicts: bool, all_stale: bool,
                          has_tension: bool) -> float:
    """
    Нормализованная уверенность синтеза [0.1, 1.0].

    Параметры:
        score_total    — суммарный score кластера
        n_signals      — число сигналов в кластере
        has_contradicts — есть ли хоть один сигнал с непустым contradicts
        all_stale      — все сигналы старше 30 дней
        has_tension    — у победителя есть tension (не fallback)

    >>> calculate_confidence(55, 5, True, False, True)  # идеальный случай
    1.0
    """
    max_score = calculate_max_possible_score(n_signals)
    if max_score == 0:
        return 0.1

    raw = score_total / max_score

    # Снижающие модификаторы
    if n_signals == 1:
        raw *= 0.5
    if not has_contradicts:
        raw *= 0.8
    if all_stale:
        raw *= 0.7
    if not has_tension:
        raw *= 0.6

    return max(0.1, min(1.0, raw))

# ─── Score: веса по полям ────────────────────────────────────────────────────
FRESHNESS_SCORE = {
    "fresh":   3,   # age <= 7 дней
    "recent":  1,   # age <= 30 дней
    "stale":   0,   # age > 30 дней
}

WEIGHT_SCORE = {
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

# ─── Contradiction Detector ──────────────────────────────────────────────────
# Порог score (semantic_inverse_score / score_pair) для предложения аналитику.
# Вынесен сюда из scripts/contradiction_detector.py (N2 ARR v3) — единая
# точка настройки порогов вместе с остальными.
CONTRADICTION_PROPOSAL_THRESHOLD = 0.5

# ─── Кластер: пороги силы нарратива ─────────────────────────────────────────
SCORE_HOT      = 20   # 🔥 горячий нарратив
SCORE_STRONG   = 12   # strong
SCORE_MODERATE =  6   # moderate
# ниже SCORE_MODERATE → weak

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

# ─── Переходный период: миграция links.* → relationships.json ────────────────
LEGACY_LINKS_ENABLED = True   # False после завершения миграции (конец Фазы 0)

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
UNCERTAINTY_RULES: dict = {
    "pos_neg_balance_threshold": 0.6,   # pos/(pos+neg) < 0.6 → contested
    "contested_strength_penalty": 0.7,  # score × 0.7
    "multiple_triggers_resolution": "most_recent",
    "tension_staleness_days": 90,
    "tension_stale_label": "⚠ Нарратив устарел — tension не обновлялся более 90 дней",
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
