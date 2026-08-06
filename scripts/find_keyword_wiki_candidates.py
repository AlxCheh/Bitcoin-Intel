#!/usr/bin/env python3
"""
scripts/find_keyword_wiki_candidates.py
Bitcoin Intel — Уровень 1 систематической проверки связей LLM Wiki
(ENTITIES.json ↔ THEORY_TOPICS.json ↔ BITCOIN_FUNCTIONS.json).

ИСТОРИЯ: TF-IDF (scripts/find_missing_wiki_links.py, по аналогии с
ADR-018) был испробован и честно отклонён 2026-08-03 — на этом масштабе
корпуса (72 сущности × 35 пунктов теории × 6 функций, короткие тексты)
статистически ранжирует шум выше настоящих связей. Проверка на 7 уже
найденных вручную связях показала: 4 из 7 (Runes↔OP_RETURN, BitGo↔
Multisig, Lightning Labs↔ликвидность, Breez↔маршрутизация) содержат
БУКВАЛЬНОЕ ключевое слово в тексте сущности; оставшиеся 3 ($DOG Mode и
Foundry↔governance, Tangem↔Multisig) существуют только через
рассуждение о связи (альтернативные механизмы governance, разнородность
вендоров в мультисиг-кворуме) — никакой лексический метод их в принципе
не поймает.

ЭТО МЕНЯЕТ САМУ ЗАДАЧУ уровня 1: не "найти все связи" (TF-IDF пытался и
провалился), а "дёшево и объяснимо поймать ту половину, которая
ловится буквальным совпадением слов — не больше, не меньше". Уровень 2
(обязательный ручной/LLM-проход, см. CLAUDE.md) остаётся ОБЯЗАТЕЛЬНЫМ
независимо от результата этого скрипта - для оставшейся половины
концептуальных связей другого пути, кроме чтения и рассуждения, не
существует.

Метод: точное совпадение ключевых слов (audit_keywords, вручную
курируется при написании топика/функции - НЕ автогенерируется) в тексте
сущности, с границей слова СЛЕВА (regex \\b, учитывает кириллицу и
подчёркивания вроде OP_RETURN как часть "слова"; без границы справа -
русский язык сильно флективен, ключевые слова намеренно задаются как
корни/основы слов, рассчитанные на любое окончание), без учёта регистра.
Результат детерминирован и объясним ("совпало, потому что текст
содержит X") - в отличие от непрозрачного cosine-similarity скора,
который TF-IDF давал без внятного объяснения, ПОЧЕМУ пара совпала.

ТОЛЬКО генерация кандидатов - не решает, честна ли связь. Каждый
кандидат по-прежнему проверяется вручную тем же честным тестом, что и
для сигналов (Шаг 5): "добавляет ли понимание одного узла реальный,
конкретный контекст другому - не просто тематическая близость".

Использование:
    python3 scripts/find_keyword_wiki_candidates.py              # полный аудит
    python3 scripts/find_keyword_wiki_candidates.py --entity bitgo # только одна сущность
"""
import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
ENTITIES_PATH = REPO_ROOT / "ENTITIES.json"
THEORY_TOPICS_PATH = REPO_ROOT / "THEORY_TOPICS.json"
BITCOIN_FUNCTIONS_PATH = REPO_ROOT / "BITCOIN_FUNCTIONS.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def entity_text(e: dict) -> str:
    parts = [
        e.get("summary", ""),
        e.get("profile", {}).get("what", ""),
        e.get("profile", {}).get("notable", ""),
    ]
    return " ".join(p for p in parts if p)


def keyword_matches(text: str, keyword: str) -> bool:
    """
    Совпадение с границей слова ТОЛЬКО слева (\\bKEYWORD, без \\b справа).
    Изначально была граница с обеих сторон - сломалась на реальных данных:
    \\bмультиподпис\\b НЕ матчит "мультиподписных" (суффикс "-ных" сразу
    после корня, нет границы справа) - русский язык сильно флективен,
    ключевые слова намеренно задаются как корни/основы, рассчитанные на
    любое окончание. Граница слева всё ещё защищает от совпадения
    ключевого слова В СЕРЕДИНЕ постороннего слова (не в его начале).
    """
    pattern = r"\b" + re.escape(keyword)
    return re.search(pattern, text, re.IGNORECASE) is not None


def entity_has_theory_link(entity: dict, topic_id: str) -> bool:
    return topic_id in entity.get("theory_refs", [])


def entity_has_function_link(entity: dict, function_id: str) -> bool:
    return function_id in entity.get("function_refs", [])


def audit_entity_theory(entities: list, topics: list, entity_filter: str = None) -> list:
    candidates = [e for e in entities if entity_filter is None or e["id"] == entity_filter]
    results = []
    for e in candidates:
        text = entity_text(e)
        for topic in topics:
            if entity_has_theory_link(e, topic["id"]):
                continue
            for item in topic.get("items", []):
                for kw in item.get("audit_keywords", []):
                    if keyword_matches(text, kw):
                        results.append({
                            "entity_id": e["id"], "entity_name": e["name"],
                            "topic_id": topic["id"], "item_label": item["label"],
                            "matched_keyword": kw,
                        })
    return results


def audit_entity_function(entities: list, functions: list, entity_filter: str = None) -> list:
    candidates = [e for e in entities if entity_filter is None or e["id"] == entity_filter]
    results = []
    for e in candidates:
        text = entity_text(e)
        for fn in functions:
            if entity_has_function_link(e, fn["id"]):
                continue
            for kw in fn.get("audit_keywords", []):
                if keyword_matches(text, kw):
                    results.append({
                        "entity_id": e["id"], "entity_name": e["name"],
                        "function_id": fn["id"], "function_name": fn["name"],
                        "matched_keyword": kw,
                    })
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--entity", help="Ограничить аудит одной сущностью (id)")
    args = parser.parse_args()

    entities = load_json(ENTITIES_PATH)["entities"]
    topics = load_json(THEORY_TOPICS_PATH)["topics"]
    functions = load_json(BITCOIN_FUNCTIONS_PATH)["functions"]

    print("Уровень 1 (ключевые слова) — систематический аудит ENTITIES × THEORY_TOPICS × BITCOIN_FUNCTIONS")
    print("ТОЛЬКО генерация кандидатов, ловит примерно половину связей (буквальные, не концептуальные) — Уровень 2 (ручной проход) остаётся обязательным.\n")

    print("═══ ENTITIES ↔ THEORY_TOPICS ═══")
    et = audit_entity_theory(entities, topics, args.entity)
    if not et:
        print("  Кандидатов не найдено (или audit_keywords ещё не проставлены)")
    for r in et:
        print(f"  {r['entity_name']:20} ↔ {r['topic_id']}/{r['item_label']:35} — по слову «{r['matched_keyword']}»")

    print("\n═══ ENTITIES ↔ BITCOIN_FUNCTIONS ═══")
    ef = audit_entity_function(entities, functions, args.entity)
    if not ef:
        print("  Кандидатов не найдено (или audit_keywords ещё не проставлены)")
    for r in ef:
        print(f"  {r['entity_name']:20} ↔ {r['function_name']:35} — по слову «{r['matched_keyword']}»")


if __name__ == "__main__":
    main()
