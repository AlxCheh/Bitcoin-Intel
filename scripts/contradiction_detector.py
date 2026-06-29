"""
scripts/contradiction_detector.py
Bitcoin Intel — детектор противоречий между сигналами

Предлагает кандидатов на links.contradicts на основе
семантического анализа macro_implication двух сигналов.

Запускать:
    PYTHONHASHSEED=0 python3 scripts/contradiction_detector.py signals.json

Алгоритм:
    score = 0.6 × inverse_score + 0.2 × subject_score + 0.2 × dir_conflict_score
    Порог предложения: score >= 0.5
"""

import os
import sys
import json
from dataclasses import dataclass
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    SIGNALS_PATH, ENCODING, JSON_ENSURE_ASCII,
    LEGACY_LINKS_ENABLED,
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
    ("накопление",      "распродажа"),
    ("рост спроса",     "падение спроса"),

    # Оценка / цена
    ("премия",          "дисконт"),
    ("nav-премией",     "nav-дисконт"),
    ("nav-премия",      "nav-дисконт"),
    ("рост",            "падение"),
    ("укрепляется",     "ослабевает"),
    ("максимум",        "минимум"),

    # Устойчивость модели
    ("платёжеспособ",   "неплатёжеспособ"),
    ("устойчив",        "уязвим"),
    ("надёжн",          "рискован"),
    ("долгосрочн",      "краткосрочн"),
    ("масштабирует",    "сворачивает"),

    # Институциональное доверие
    ("доверие",         "недоверие"),
    ("принятие",        "отторжение"),
    ("легитимн",        "нелегитимн"),
    ("регуляторное одобрение", "регуляторный запрет"),

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

# Веса компонент
W_INVERSE  = 0.6
W_SUBJECT  = 0.2
W_DIR      = 0.2

# Пороги хитов
HIT_THRESHOLDS = {1: 0.4, 2: 0.7, 3: 1.0}

# Порог предложения аналитику
PROPOSAL_THRESHOLD = 0.5


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


def _inverse_score(macro_a: str, macro_b: str) -> tuple[float, list[tuple[str, str]]]:
    """
    Проверяет сколько INVERSE_PAIRS сработало между двумя macro_implication.

    Returns:
        (score, hit_pairs)
    """
    a = _normalize(macro_a)
    b = _normalize(macro_b)

    hits = []
    for term_pos, term_neg in INVERSE_PAIRS:
        # Пара срабатывает если: A содержит term_pos и B содержит term_neg
        # ИЛИ A содержит term_neg и B содержит term_pos
        ab = (term_pos in a and term_neg in b)
        ba = (term_neg in a and term_pos in b)
        if ab or ba:
            hits.append((term_pos, term_neg))

    n = len(hits)
    if n == 0:
        return 0.0, []
    # Нормализуем: 1 hit → 0.4, 2 hits → 0.7, 3+ hits → 1.0
    score = HIT_THRESHOLDS.get(n, 1.0)
    return score, hits


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


def score_pair(sig_a: dict, sig_b: dict) -> ContradictionCandidate:
    """
    Вычисляет semantic_inverse_score для пары сигналов.

    score = W_INVERSE × inverse + W_SUBJECT × subject + W_DIR × dir
    """
    macro_a = sig_a.get("macro_implication", "")
    macro_b = sig_b.get("macro_implication", "")

    inv_score, hits = _inverse_score(macro_a, macro_b)
    sub_score = _subject_score(sig_a, sig_b)
    dir_score = _dir_conflict_score(sig_a, sig_b)

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
# Эти функции — тонкие обёртки над внутренними score_pair / find_contradiction_candidates.

def semantic_inverse_score(impl_a: str, impl_b: str) -> float:
    """
    Публичный API: оценка семантической несовместимости двух macro_implication.
    Диапазон: 0.0 (совместимы) → 1.0 (прямое противоречие).
    Threshold для предложения в contradicts: >= PROPOSAL_THRESHOLD (0.5).
    """
    if not impl_a or not impl_b:
        return 0.0
    sig_a = {"id": "_a", "macro_implication": impl_a, "dir": "pos", "actor": ""}
    sig_b = {"id": "_b", "macro_implication": impl_b, "dir": "neg", "actor": ""}
    candidate = score_pair(sig_a, sig_b)
    return candidate.score


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
            "rationale": c.rationale,
        }
        for c in candidates
    ]
