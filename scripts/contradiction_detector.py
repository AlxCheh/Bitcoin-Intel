"""
scripts/contradiction_detector.py
Bitcoin Intel — детектор противоречий между сигналами

Предлагает кандидатов на links.contradicts на основе
семантического анализа macro_implication двух сигналов.

Запускать:
    PYTHONHASHSEED=0 python3 scripts/contradiction_detector.py signals.json

Алгоритм (два независимых режима):

  1. Текстовый режим — semantic_inverse_score(text_a, text_b):
     score = W_PAIR_TEXT × inverse_pair_score + W_POLARITY × polarity_divergence
     Используется когда доступен только текст macro_implication (без dir/actor
     метаданных сигнала) — например, при ручной проверке двух формулировок.
     Калибровка и обоснование выбора весов: docs/ADR-009-contradiction-scoring.md

  2. Полный режим — score_pair(sig_a, sig_b):
     score = W_INVERSE × text_score + W_SUBJECT × subject_score + W_DIR × dir_score
     Используется для реальных сигналов из signals.json, где actor/dir известны
     достоверно (заполнены аналитиком), а не выводятся из текста.

Эти два режима НЕ переиспользуют друг друга через фиктивные dir/actor —
см. docs/ADR-009-contradiction-scoring.md, раздел «Почему два режима».
"""

import os
import sys
import json
from dataclasses import dataclass
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    SIGNALS_PATH, ENCODING, JSON_ENSURE_ASCII,
    LEGACY_LINKS_ENABLED, CONTRADICTION_PROPOSAL_THRESHOLD,
)

# ─── INVERSE_PAIRS ────────────────────────────────────────────────────────────
# Пары понятий которые описывают несовместимые состояния BTC-системы.
# Формат: (термин_A, термин_B) — наличие A в одном macro и B в другом
# сигнализирует о потенциальном противоречии.
#
# Принцип: A и B не могут быть одновременно истинны для одного субъекта.

INVERSE_PAIRS: list[tuple[str, str]] = [
    # Капитал / потоки
    ("приток",          "отток"),
    ("inflow",          "outflow"),
    ("покупают",        "продают"),
    ("покупки",         "продажи"),
    ("накопление",      "распродажа"),
    ("накапливают",     "ликвидируют"),
    ("рост спроса",     "падение спроса"),
    ("структурный спрос", "структурное давление продаж"),

    # Оценка / цена
    ("премия",          "дисконт"),
    ("nav-премией",     "nav-дисконт"),
    ("nav-премия",      "nav-дисконт"),
    ("рост",            "падение"),
    ("укрепляется",     "ослабевает"),
    ("укрепляет",       "ослабляет"),
    ("максимум",        "минимум"),
    ("исчезает",        "появляется"),

    # Устойчивость модели
    ("платёжеспособ",   "неплатёжеспособ"),
    ("устойчив",        "уязвим"),
    ("надёжн",          "рискован"),
    ("долгосрочн",      "краткосрочн"),
    ("масштабирует",    "сворачивает"),
    ("требует паузы",   "продолжает работать"),

    # Институциональное доверие
    ("доверие",         "недоверие"),
    ("принятие",        "отторжение"),
    ("легитимн",        "нелегитимн"),
    ("регуляторное одобрение", "регуляторный запрет"),
    ("полноценный финансовый инструмент", "хрупкость"),
    ("открывает доступ", "ограничивает доступ"),

    # Предложение / дефицит
    ("дефицит",         "избыток"),
    ("сокращение предложения", "рост предложения"),
    ("потеряны навсегда", "возвращены в оборот"),

    # Инфраструктура
    ("масштабирование", "перегрузка"),
    ("рост сети",       "деградация сети"),
    ("хешрейт растёт",  "хешрейт падает"),

    # Макро
    ("ликвидность растёт", "ликвидность сжимается"),
    ("ставки снижаются",   "ставки повышаются"),
    ("риск-аппетит",       "бегство от риска"),
]

# ─── Polarity Lexicon ─────────────────────────────────────────────────────────
# Дополняет INVERSE_PAIRS: вместо точных пар терминов считает суммарный "знак"
# повествования в каждом тексте по словарю однонаправленных слов. Нужен потому
# что многие реальные contradicts-пары в базе не используют одну и ту же пару
# антонимов — у них структурно разная тональность изложения (одна сторона
# говорит "система укрепляется", другая — "система под давлением"), без общих
# лексических якорей для INVERSE_PAIRS.
#
# Группы соответствуют тем же доменным категориям что и INVERSE_PAIRS, чтобы
# словарь оставался объяснимым и не превращался в чёрный ящик.
# Калибровка весов и порога: docs/ADR-009-contradiction-scoring.md

POSITIVE_TERMS: list[str] = [
    # Потоки / накопление
    "приток", "накоплен", "накаплива", "структурный спрос", "покупк",
    "обязательная покупка", "автоматический спрос", "поглощают",
    "структурный покупатель", "держатели не выходят",
    # Оценка / доверие
    "премия", "укрепля", "устойчив", "надёжн", "легитимн", "доверие",
    "полноценный финансовый инструмент", "открывает доступ",
    # Инфраструктура / сеть
    "масштабирует", "масштабирование", "рост сети", "рекорд",
    "комиссионный доход", "операционн",
    # Общая динамика
    "рост ", "растёт", "разворот вверх", "защищ",
]

NEGATIVE_TERMS: list[str] = [
    # Потоки / распродажа
    "отток", "распродажа", "ликвидаци", "продают", "выход капитала",
    "давление продаж", "слабые руки продают", "структурный продавец",
    # Оценка / риск
    "дисконт", "хрупкость", "неопределённост", "недоверие", "нелегитимн",
    "не верит", "расхождение", "под давлением", "давление", "сжимает",
    "сжатие", "испытывает давление", "капитуляция", "уязвим", "барьер",
    "несовместим",
    # Инфраструктура / деградация
    "перегрузка", "деградация сети", "сворачивает",
    # Общая динамика
    "падение", "падает", "разворот вниз", "пауза", "требует паузы",
    "ограничивает доступ",
]

# Веса компонент текстового (semantic_inverse_score) режима.
# Откалиброваны на Golden Dataset (73 пары, tests/golden/fixtures/contradiction_pairs.json)
# с целью максимизации accuracy при пороге классификации = CONTRADICTION_PROPOSAL_THRESHOLD.
# Подробности и альтернативы, рассмотренные при калибровке: docs/ADR-009.
W_PAIR_TEXT     = 0.2
W_POLARITY      = 0.8
POLARITY_DIVNORM = 1.5   # нормирующий делитель для |net_a - net_b|

# Веса компонент полного (score_pair) режима — для реальных сигналов
W_INVERSE  = 0.6
W_SUBJECT  = 0.2
W_DIR      = 0.2

# Пороги нормализации числа сработавших INVERSE_PAIRS (для текстового score)
HIT_THRESHOLDS = {1: 0.55, 2: 0.85, 3: 1.0}

# Порог предложения аналитику и порог классификации в semantic_inverse_score
PROPOSAL_THRESHOLD = CONTRADICTION_PROPOSAL_THRESHOLD


# ─── Dataclass результата ─────────────────────────────────────────────────────
@dataclass
class ContradictionCandidate:
    signal_a_id:   str
    signal_b_id:   str
    score:         float
    hits:          list[tuple[str, str]]   # сработавшие пары
    inverse_score: float
    subject_score: float
    dir_score:     float
    explanation:   str


# ─── Вспомогательные функции ─────────────────────────────────────────────────
def _normalize(text: str) -> str:
    """Нижний регистр, без лишних пробелов."""
    return " ".join(text.lower().split()) if text else ""


def _inverse_pair_hits(macro_a: str, macro_b: str) -> list[tuple[str, str]]:
    """Возвращает список сработавших INVERSE_PAIRS между двумя текстами."""
    a = _normalize(macro_a)
    b = _normalize(macro_b)

    hits = []
    for term_pos, term_neg in INVERSE_PAIRS:
        ab = (term_pos in a and term_neg in b)
        ba = (term_neg in a and term_pos in b)
        if ab or ba:
            hits.append((term_pos, term_neg))
    return hits


def _inverse_pair_score(macro_a: str, macro_b: str) -> tuple[float, list[tuple[str, str]]]:
    """
    Нормализует число сработавших INVERSE_PAIRS в score [0, 1].
    1 hit → 0.55, 2 hits → 0.85, 3+ hits → 1.0.
    """
    hits = _inverse_pair_hits(macro_a, macro_b)
    n = len(hits)
    if n == 0:
        return 0.0, []
    score = HIT_THRESHOLDS.get(n, 1.0)
    return score, hits


def _polarity_counts(text: str) -> tuple[int, int]:
    """Считает сырые вхождения POSITIVE_TERMS / NEGATIVE_TERMS в тексте."""
    t = _normalize(text)
    pos = sum(1 for term in POSITIVE_TERMS if term in t)
    neg = sum(1 for term in NEGATIVE_TERMS if term in t)
    return pos, neg


def _polarity_score(macro_a: str, macro_b: str) -> float:
    """
    Оценивает расхождение тональности между двумя текстами в [0, 1].

    net(text) = pos_count - neg_count (целое, может быть отрицательным).
    Чем больше |net_a - net_b|, тем сильнее тексты расходятся по тональности.
    Если знаки net_a и net_b совпадают и оба не нулевые — тексты, скорее всего,
    говорят об одном направлении в одних и тех же терминах — ослабляем score,
    чтобы не давать ложный высокий результат на двух текстах с одинаковой
    общей тональностью, но разным набором конкретных слов.
    """
    pos_a, neg_a = _polarity_counts(macro_a)
    pos_b, neg_b = _polarity_counts(macro_b)
    net_a = pos_a - neg_a
    net_b = pos_b - neg_b

    diff = net_a - net_b
    score = min(1.0, abs(diff) / POLARITY_DIVNORM)

    if net_a != 0 and net_b != 0 and (net_a > 0) == (net_b > 0):
        score *= 0.3

    return score


def _subject_score(sig_a: dict, sig_b: dict) -> float:
    """
    Субъекты должны совпадать или быть в одном домене
    чтобы противоречие было реальным, а не сравнением разных систем.

    Логика:
      actor совпадает точно → 1.0
      theme совпадает → 0.5
      ничего общего → 0.0
    """
    if sig_a.get("actor") and sig_a.get("actor") == sig_b.get("actor"):
        return 1.0
    if sig_a.get("theme") and sig_a.get("theme") == sig_b.get("theme"):
        return 0.5
    return 0.0


def _dir_conflict_score(sig_a: dict, sig_b: dict) -> float:
    """
    pos vs neg → явный конфликт направлений → 1.0
    neu vs любой → слабый сигнал → 0.3
    одинаковые → 0.0 (не противоречие)
    """
    da = sig_a.get("dir", "neu")
    db = sig_b.get("dir", "neu")

    if da == db:
        return 0.0
    if "neu" in (da, db):
        return 0.3
    # pos vs neg или neg vs pos
    return 1.0


def _already_linked(sig_a: dict, sig_b: dict) -> bool:
    """Проверяет существующие links чтобы не предлагать дубли."""
    if not LEGACY_LINKS_ENABLED:
        return False
    a_contradicts = sig_a.get("links", {}).get("contradicts", [])
    b_contradicts = sig_b.get("links", {}).get("contradicts", [])
    return (sig_b.get("id") in a_contradicts or sig_a.get("id") in b_contradicts)


def _text_score(macro_a: str, macro_b: str) -> tuple[float, list[tuple[str, str]]]:
    """
    Чистый текстовый score без актёра/направления.
    score = W_PAIR_TEXT × inverse_pair_score + W_POLARITY × polarity_score
    """
    pair_score, hits = _inverse_pair_score(macro_a, macro_b)
    pol_score         = _polarity_score(macro_a, macro_b)
    total = W_PAIR_TEXT * pair_score + W_POLARITY * pol_score
    return min(1.0, total), hits


def score_pair(sig_a: dict, sig_b: dict) -> ContradictionCandidate:
    """
    Вычисляет полный score для пары реальных сигналов (с actor/dir).

    score = W_INVERSE × inverse_pair_score + W_SUBJECT × subject_score + W_DIR × dir_score

    Намеренно использует ТОЛЬКО _inverse_pair_score (лексические пары), а не
    _text_score / polarity: для реальных сигналов направление уже достоверно
    известно из поля `dir`, заполненного аналитиком. Добавление polarity
    (текстовой оценки тональности, нужной только когда dir неизвестен) сюда
    задваивало бы один и тот же сигнал дважды — через dir_score и через текст —
    и завышало бы score для почти любой pos/neg-пары независимо от реального
    лексического конфликта. См. docs/ADR-009-contradiction-scoring.md.
    """
    macro_a = sig_a.get("macro_implication", "")
    macro_b = sig_b.get("macro_implication", "")

    inv_score, hits = _inverse_pair_score(macro_a, macro_b)
    sub_score        = _subject_score(sig_a, sig_b)
    dir_score        = _dir_conflict_score(sig_a, sig_b)

    total = W_INVERSE * inv_score + W_SUBJECT * sub_score + W_DIR * dir_score

    if hits:
        hit_str = ", ".join(f"«{a}» ↔ «{b}»" for a, b in hits[:3])
        explanation = f"Конфликтующие концепции: {hit_str}"
    elif dir_score == 1.0:
        explanation = "Противоположные направления (pos vs neg) без явных лексических хитов"
    else:
        explanation = "Слабый сигнал — общая тема, нет явного лексического конфликта"

    return ContradictionCandidate(
        signal_a_id=sig_a.get("id", "?"),
        signal_b_id=sig_b.get("id", "?"),
        score=round(total, 3),
        hits=hits,
        inverse_score=round(inv_score, 3),
        subject_score=round(sub_score, 3),
        dir_score=round(dir_score, 3),
        explanation=explanation,
    )


# ─── Основная функция ─────────────────────────────────────────────────────────
def find_contradiction_candidates(
    signals: list[dict],
    threshold: float = PROPOSAL_THRESHOLD,
    same_cluster_only: bool = False,
) -> list[ContradictionCandidate]:
    """
    Перебирает все пары сигналов и возвращает кандидатов на contradicts.

    Args:
        signals:           список сигналов из signals.json
        threshold:         минимальный score для предложения (default 0.5)
        same_cluster_only: искать только внутри одного кластера

    Returns:
        Список ContradictionCandidate отсортированный по score DESC
    """
    candidates = []

    pairs = list(combinations(signals, 2))
    for sig_a, sig_b in pairs:
        # Фильтр по кластеру
        if same_cluster_only:
            if sig_a.get("cluster") != sig_b.get("cluster"):
                continue

        # Пропускаем уже связанные
        if _already_linked(sig_a, sig_b):
            continue

        result = score_pair(sig_a, sig_b)
        if result.score >= threshold:
            candidates.append(result)

    candidates.sort(key=lambda c: -c.score)
    return candidates


# ─── CLI ──────────────────────────────────────────────────────────────────────
def main():
    path = sys.argv[1] if len(sys.argv) > 1 else SIGNALS_PATH

    with open(path, encoding=ENCODING) as f:
        data = json.load(f)

    signals = data["signals"] if isinstance(data, dict) else data

    print(f"Анализируем {len(signals)} сигналов...\n")

    candidates = find_contradiction_candidates(signals, threshold=PROPOSAL_THRESHOLD)

    if not candidates:
        print("Новых кандидатов на contradicts не найдено.")
        return

    print(f"Найдено {len(candidates)} кандидатов (score >= {PROPOSAL_THRESHOLD}):\n")
    print(f"{'Score':>6}  {'Сигнал A':<25} {'Сигнал B':<25}  Объяснение")
    print("-" * 100)

    for c in candidates[:20]:
        print(f"{c.score:>6.3f}  {c.signal_a_id:<25} {c.signal_b_id:<25}  {c.explanation[:50]}")

    print(f"\n{'—' * 60}")
    print("Тест совместимости (можно ли A и B быть правыми одновременно?):")
    print("Если нет → добавить в links.contradicts. Финальное решение — аналитик.")


if __name__ == "__main__":
    main()


# ─── Публичный API для тестов ────────────────────────────────────────────────
# Тесты импортируют semantic_inverse_score и suggest_contradictions.

def semantic_inverse_score(impl_a: str, impl_b: str) -> float:
    """
    Публичный API: оценка семантической несовместимости двух macro_implication
    на основе ТОЛЬКО текста (без actor/dir — они здесь неизвестны и не
    фабрикуются искусственно, см. ADR-009).

    Диапазон: 0.0 (совместимы) → 1.0 (прямое противоречие).
    Threshold для предложения в contradicts: >= PROPOSAL_THRESHOLD (0.5).
    """
    if not impl_a or not impl_b:
        return 0.0
    score, _ = _text_score(impl_a, impl_b)
    return round(score, 3)


def suggest_contradictions(signals: list) -> list:
    """
    Публичный API: предлагает пары сигналов как кандидаты на links.contradicts.
    Возвращает список dict с from_id, to_id, score, rationale.
    """
    candidates = find_contradiction_candidates(signals, threshold=PROPOSAL_THRESHOLD)
    return [
        {
            "from_id":   c.signal_a_id,
            "to_id":     c.signal_b_id,
            "score":     c.score,
            "rationale": c.explanation,
        }
        for c in candidates
    ]
