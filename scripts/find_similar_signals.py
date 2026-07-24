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

ПОДПРАВЛЕНО 2026-07-25 (по итогам ручной инспекции весов на реальных
сигналах — см. обсуждение в чате): без обработки TF-IDF ловил два
источника шума, не относящихся к содержанию —
  1. Частые русские предлоги/союзы (через, на, же, vs) — получали
     ненулевой вес и вносили вклад в каждое сравнение вне зависимости
     от содержания.
  2. ID других сигналов, упомянутых внутри текста (напр. "NAR-2026-
     0711-001" в поле context) — выглядят как редкие токены с высоким
     IDF и завышают сходство с сигналами, где случайно встретился
     похожий числовой фрагмент.
Оба источника устранены здесь же, в Фазе 1 (без перехода к Фазе 3) —
дёшево, не требует новой инфраструктуры.

Использование:
    python3 scripts/find_similar_signals.py STR-2026-0716-002
    python3 scripts/find_similar_signals.py STR-2026-0716-002 --top 10
    python3 scripts/find_similar_signals.py STR-2026-0716-002 --same-cluster-ok
"""
import argparse
import json
import re
import sys
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

REPO_ROOT = Path(__file__).parent.parent
SIGNALS_PATH = REPO_ROOT / "signals.json"

# Паттерн ID сигнала, напр. "NAR-2026-0711-001" — встречается внутри текстовых
# полей (context ссылается на другие сигналы по id) и не несёт содержательного
# смысла для сравнения текстов; должен быть вырезан ДО векторизации.
SIGNAL_ID_PATTERN = re.compile(r"\b[A-Z]{2,4}-\d{4}-\d{4}-\d{3}\b")

# Небольшой список самых частых русских служебных слов (предлоги, союзы,
# частицы) — не исчерпывающий стоп-лист (для этого масштаба корпуса не нужен
# полноценный NLP-словарь), только те, что реально встречались как шум при
# ручной инспекции весов. Английские stop-words не нужны отдельно — корпус
# в основном русский, редкие английские связки (vs, and) добавлены явно.
RUSSIAN_STOP_WORDS = [
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то",
    "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за",
    "бы", "по", "только", "её", "мне", "было", "вот", "от", "меня", "ещё",
    "нет", "о", "из", "ему", "теперь", "когда", "даже", "ну", "вдруг", "ли",
    "если", "уже", "или", "быть", "был", "него", "до", "вас", "нибудь",
    "опять", "уж", "вам", "сказал", "ведь", "там", "потом", "себя", "ничего",
    "ей", "может", "они", "тут", "где", "есть", "надо", "ней", "для", "мы",
    "тебя", "их", "чем", "была", "сам", "чтоб", "без", "будто", "чего",
    "раз", "тоже", "себе", "под", "будет", "ж", "тогда", "кто", "этот",
    "того", "потому", "этого", "какой", "совсем", "ним", "здесь", "этом",
    "один", "почти", "мой", "тем", "чтобы", "нее", "сейчас", "были", "куда",
    "зачем", "всех", "никогда", "можно", "при", "об", "этой", "этих",
    "вся", "всё", "это", "также", "vs", "через",
]


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

    ID других сигналов, встречающиеся в этих полях (context часто
    ссылается на предшествующие сигналы по id), вырезаются — см.
    SIGNAL_ID_PATTERN и комментарий в шапке файла.
    """
    parts = [
        s.get("signal", ""),
        s.get("context", ""),
        s.get("tension", ""),
        s.get("macro_implication", ""),
    ]
    text = " ".join(p for p in parts if p)
    return SIGNAL_ID_PATTERN.sub(" ", text)


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
    vectorizer = TfidfVectorizer(stop_words=RUSSIAN_STOP_WORDS)
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
