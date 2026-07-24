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

Метод: TF-IDF (уни+биграммы) + косинусное сходство (scikit-learn) —
намеренно простой, без нейросетей/моделей/сетевых вызовов. Проверяет сам
пайплайн "похожесть текста -> кандидаты для Шага 5" прежде чем
вкладываться в более тяжёлую инфраструктуру (Фазы 2-4 в ADR-018).

С 2026-07-25 запуск этого скрипта — ОБЯЗАТЕЛЬНАЯ часть Шага 5 для
каждого нового сигнала (не опциональный инструмент по запросу), см.
CLAUDE.md Шаг 5 и ADR-018 amendment.

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

ДОПОЛНЕНО 2026-07-25 (тот же день, следующий раунд обсуждения) — три
усиления, всё ещё в рамках Фазы 1 (структура/текст, не нейросети):

  1. Биграммы (ngram_range=(1,2)) — одиночные слова часто недостаточно
     специфичны ("порог", "данные"); словосочетания вроде "консенсусный
     порог"/"квантовая угроза" — гораздо более редкие и информативные
     признаки для сравнения.

  2. Пересечение по сущностям (ENTITIES.json.signal_refs) — ОТДЕЛЬНЫЙ от
     TF-IDF источник кандидатов, не замена: если два сигнала ссылаются
     на одну и ту же сущность (напр. оба упоминают 'strategy'), это
     конкретный, проверяемый факт (не категория с 5-7 значениями, как
     theme/actor — сущностей уже 45+, пространство гораздо более
     разреженное) — сильный кандидат, который TF-IDF мог не заметить,
     если тексты сформулированы разными словами.

  3. Флаг "противоположный dir + тот же theme" — дешёвый структурный
     намёк конкретно для contradicts-кандидатов (напр. pos vs neg по
     одной теме — стоит проверить в первую очередь). ТОЛЬКО намёк,
     аналитик по-прежнему обязан применить честный тест Шага 5 — сам
     по себе противоположный dir ничего не доказывает (см. обсуждение
     в чате про то, почему категориальные поля — плохая ЗАМЕНА тексту:
     92 сигнала дают всего 32 уникальные комбинации theme/actor/dir,
     слишком грубо для ранжирования, но годится как дополнительный
     флаг поверх текстового сравнения).

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
ENTITIES_PATH = REPO_ROOT / "ENTITIES.json"

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

# dir=pos и dir=neg считаются структурно противоположными для целей
# дешёвого contradicts-намёка; dir=neu намеренно не участвует (neu — "нет
# направления", а не "третья полярность", сравнивать не с чем).
DIR_OPPOSITES = {"pos": "neg", "neg": "pos"}


def load_signals(path: Path = SIGNALS_PATH) -> list:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("signals", raw) if isinstance(raw, dict) else raw


def load_entities(path: Path = ENTITIES_PATH) -> list:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("entities", raw) if isinstance(raw, dict) else raw


def build_signal_entity_map(entities: list) -> dict:
    """
    {signal_id: {entity_id, ...}} из ENTITIES.json[].signal_refs.
    Используется для поиска кандидатов по общей сущности — источник
    отдельный от TF-IDF-текста (см. пункт 2 в шапке файла).
    """
    m: dict[str, set[str]] = {}
    for e in entities:
        for sid in e.get("signal_refs", []):
            m.setdefault(sid, set()).add(e["id"])
    return m


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


def is_opposite_dir_same_theme(target: dict, candidate: dict) -> bool:
    """Дешёвый структурный намёк для contradicts-кандидатов — см. пункт 3
    в шапке файла. Не доказательство, только повод проверить в первую
    очередь честными тестами Шага 5."""
    t_dir = target.get("dir")
    return (
        target.get("theme") == candidate.get("theme")
        and t_dir in DIR_OPPOSITES
        and DIR_OPPOSITES[t_dir] == candidate.get("dir")
    )


def find_similar(
    target_id: str,
    signals: list,
    top_n: int = 5,
    same_cluster_ok: bool = False,
) -> list[tuple[dict, float]]:
    """
    Возвращает до top_n сигналов, ранжированных по косинусному сходству
    TF-IDF-векторов (уни+биграммы) с целевым сигналом (убывание). По
    умолчанию исключает сигналы того же cluster, что у target — та часть
    пространства кандидатов уже покрывается обычным Шагом 5, дублировать
    незачем; --same-cluster-ok включает их обратно (напр. для отладки).

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
    vectorizer = TfidfVectorizer(stop_words=RUSSIAN_STOP_WORDS, ngram_range=(1, 2))
    tfidf = vectorizer.fit_transform(corpus)
    sims = cosine_similarity(tfidf[0:1], tfidf[1:]).flatten()

    ranked = sorted(zip(candidates, sims), key=lambda pair: pair[1], reverse=True)
    return ranked[:top_n]


def find_shared_entity_candidates(
    target_id: str,
    signals: list,
    signal_entity_map: dict,
    same_cluster_ok: bool = False,
) -> list[tuple[dict, set]]:
    """
    Кандидаты, разделяющие хотя бы одну сущность (ENTITIES.json) с
    target — источник, ОТДЕЛЬНЫЙ от TF-IDF-текста. Возвращает
    (signal, shared_entity_ids), отсортировано по числу общих сущностей.
    """
    by_id = {s["id"]: s for s in signals}
    target = by_id.get(target_id)
    if target is None:
        raise ValueError(f"Сигнал {target_id} не найден в signals.json")

    target_entities = signal_entity_map.get(target_id, set())
    if not target_entities:
        return []

    results = []
    for s in signals:
        if s["id"] == target_id:
            continue
        if not same_cluster_ok and s.get("cluster") == target.get("cluster"):
            continue
        shared = target_entities & signal_entity_map.get(s["id"], set())
        if shared:
            results.append((s, shared))

    results.sort(key=lambda pair: len(pair[1]), reverse=True)
    return results


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
        target = next(s for s in signals if s["id"] == args.signal_id)
    except StopIteration:
        print(f"✗ Сигнал {args.signal_id} не найден в signals.json")
        sys.exit(1)

    try:
        results = find_similar(args.signal_id, signals, args.top, args.same_cluster_ok)
    except ValueError as e:
        print(f"✗ {e}")
        sys.exit(1)

    entities = load_entities()
    signal_entity_map = build_signal_entity_map(entities)
    shown_ids = {s["id"] for s, _ in results}

    print(f"Кандидаты для {args.signal_id} (TF-IDF уни+биграммы, Фаза 1 — ADR-018)")
    print("НЕ являются автоматическими confirms/contradicts — только кандидаты для честной проверки по Шагу 5.\n")

    if not results:
        print("Текстовых кандидатов не найдено (недостаточно сигналов вне кластера для сравнения)")
    for s, score in results:
        title = s.get("signal", "")[:80]
        flags = []
        shared = signal_entity_map.get(args.signal_id, set()) & signal_entity_map.get(s["id"], set())
        if shared:
            flags.append(f"★ ОБЩАЯ СУЩНОСТЬ: {', '.join(sorted(shared))}")
        if is_opposite_dir_same_theme(target, s):
            flags.append("⚡ ПРОТИВОПОЛОЖНЫЙ dir, та же theme — проверить на contradicts в первую очередь")
        flag_str = "  " + " | ".join(flags) if flags else ""
        print(f"  {score:.3f}  {s['id']}  [{s.get('cluster')}]  {title}{flag_str}")

    entity_candidates = find_shared_entity_candidates(
        args.signal_id, signals, signal_entity_map, args.same_cluster_ok
    )
    entity_candidates = [(s, shared) for s, shared in entity_candidates if s["id"] not in shown_ids]
    if entity_candidates:
        print("\nДополнительно — общая сущность, но вне топа по тексту:")
        for s, shared in entity_candidates:
            title = s.get("signal", "")[:80]
            print(f"  ★ {s['id']}  [{s.get('cluster')}]  ({', '.join(sorted(shared))})  {title}")


if __name__ == "__main__":
    main()
