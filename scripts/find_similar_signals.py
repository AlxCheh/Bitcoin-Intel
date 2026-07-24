#!/usr/bin/env python3
"""
scripts/find_similar_signals.py
Bitcoin Intel — Фаза 1 плана расширения кандидатов для Шага 5 (связывание
сигналов). См. docs/ADR-018-signal-similarity-candidate-expansion.md.

ТОЛЬКО генерация кандидатов — не решает, является ли связь confirms/
contradicts/context_chain. Это по-прежнему делает аналитик (Шаг 5,
CLAUDE.md) вручную, честными тестами, как и раньше. Скрипт лишь
расширяет пул кандидатов за пределы одного theme/cluster, куда Шаг 5
сейчас не смотрит вообще (тот же класс слепого пятна, что находка 3 /
ADR-017, только для текстовой похожести сигналов, а не общих сущностей).

Метод: TF-IDF + косинусное сходство (scikit-learn) — самый простой из
возможных методов, без нейросетей/моделей/сетевых вызовов. Проверяет
сам пайплайн "похожесть текста -> кандидаты для Шага 5" прежде чем
вкладываться в более тяжёлую инфраструктуру (Фазы 2-4 в ADR-018).

Использование:
    python3 scripts/find_similar_signals.py STR-2026-0716-002
    python3 scripts/find_similar_signals.py STR-2026-0716-002 --top 10
    python3 scripts/find_similar_signals.py STR-2026-0716-002 --same-cluster-ok
"""
import argparse
import json
import sys
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

REPO_ROOT = Path(__file__).parent.parent
SIGNALS_PATH = REPO_ROOT / "signals.json"


def load_signals(path: Path = SIGNALS_PATH) -> list:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("signals", raw) if isinstance(raw, dict) else raw


def signal_text(s: dict) -> str:
    """
    Поля, формирующие смысловое содержание сигнала для сравнения.
    tension/macro_implication — смысловое ядро синтеза (Шаг 6), signal/
    context — описание самого события. Намеренно НЕ включаем caveat/
    alternatives_considered/alternative_scenario — это оговорки и
    контрфактические ветки, не про "о чём сигнал по существу", их
    включение размыло бы сравнение шумом отклонённых альтернатив.
    """
    parts = [
        s.get("signal", ""),
        s.get("context", ""),
        s.get("tension", ""),
        s.get("macro_implication", ""),
    ]
    return " ".join(p for p in parts if p)


def find_similar(
    target_id: str,
    signals: list,
    top_n: int = 5,
    same_cluster_ok: bool = False,
) -> list[tuple[dict, float]]:
    """
    Возвращает до top_n сигналов, ранжированных по косинусному сходству
    TF-IDF-векторов с целевым сигналом (убывание). По умолчанию исключает
    сигналы того же cluster, что у target — та часть пространства
    кандидатов уже покрывается обычным Шагом 5, дублировать незачем;
    --same-cluster-ok включает их обратно (напр. для отладки/сравнения).

    Raises:
        ValueError: если target_id не найден в signals.
    """
    by_id = {s["id"]: s for s in signals}
    if target_id not in by_id:
        raise ValueError(f"Сигнал {target_id} не найден в signals.json")
    target = by_id[target_id]

    candidates = [s for s in signals if s["id"] != target_id]
    if not same_cluster_ok:
        candidates = [s for s in candidates if s.get("cluster") != target.get("cluster")]

    if not candidates:
        return []

    corpus = [signal_text(target)] + [signal_text(s) for s in candidates]
    vectorizer = TfidfVectorizer()
    tfidf = vectorizer.fit_transform(corpus)
    sims = cosine_similarity(tfidf[0:1], tfidf[1:]).flatten()

    ranked = sorted(zip(candidates, sims), key=lambda pair: pair[1], reverse=True)
    return ranked[:top_n]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("signal_id", help="ID сигнала, для которого ищем кандидатов")
    parser.add_argument("--top", type=int, default=5, help="Сколько кандидатов показать (по умолчанию 5)")
    parser.add_argument(
        "--same-cluster-ok", action="store_true",
        help="Не исключать сигналы того же кластера (по умолчанию исключены — уже покрыты Шагом 5)",
    )
    args = parser.parse_args()

    signals = load_signals()
    try:
        results = find_similar(args.signal_id, signals, args.top, args.same_cluster_ok)
    except ValueError as e:
        print(f"✗ {e}")
        sys.exit(1)

    if not results:
        print("Кандидатов не найдено (недостаточно сигналов вне кластера для сравнения)")
        return

    print(f"Кандидаты для {args.signal_id} (TF-IDF cosine similarity, Фаза 1 — ADR-018)")
    print("НЕ являются автоматическими confirms/contradicts — только кандидаты для честной проверки по Шагу 5.\n")
    for s, score in results:
        title = s.get("signal", "")[:80]
        print(f"  {score:.3f}  {s['id']}  [{s.get('cluster')}]  {title}")


if __name__ == "__main__":
    main()
