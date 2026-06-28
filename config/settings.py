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
    return n * MAX_PER_SIGNAL

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
