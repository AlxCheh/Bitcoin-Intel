#!/usr/bin/env python3
"""
scripts/find_keyword_wiki_candidates.py
Bitcoin Intel — систематический поиск кандидатов на связь между
ENTITIES.json и THEORY_TOPICS.json/BITCOIN_FUNCTIONS.json по буквальным
ключевым словам. См. CLAUDE.md, раздел "LLM Wiki".

ИСТОРИЯ: первая попытка (2026-08-03) использовала TF-IDF по аналогии с
ADR-018 (find_similar_signals.py). На реальных данных провалилась
однозначно — подтверждённая вручную пара (Lightning Labs↔"Проблема
ликвидности") дала скор 0.032, заведомо нерелевантная пара — 0.046,
выше. Причина: корпус (72 сущности × 35 пунктов теории × 6 функций)
слишком мал, тексты слишком коротки для статистически осмысленного
TF-IDF (в отличие от signals.json, где 100+ содержательных документов
делают IDF нетривиальным).

Этот скрипт — не попытка исправить TF-IDF, а другой метод: буквальное
совпадение заранее заданных ключевых слов (не автовыведенных - авторы
контента сами вписывают отличительные термины в audit_keywords при
написании топика/функции, тот же принцип ручного курирования, что и
весь остальной контент проекта).

ПРОВЕРЕННЫЙ ПОТОЛОК МЕТОДА (2026-08-06, дважды перепроверено, не с
первой оценки): из 7 связей, найденных вручную при систематическом
аудите 2026-08-03, при первой прикидке казалось, что буквальное слово
есть только у 4 (Runes↔OP_RETURN, BitGo↔мультиподпись, Lightning
Labs↔ликвидность, Breez↔маршрутизация) - остальные 3 казались чисто
концептуальными. Построение и тестирование самого скрипта заставило
перепроверить буквальный текст внимательнее (не полагаясь на память о
смысле) - оказалось, что "governance" буквально есть в тексте $DOG Mode
("governance-споре"), а "консенсус"/"голосование" - в тексте Foundry.
Реальный счёт - 6 из 7 (~86%), при осознанном выборе ключевых слов
куратором. Единственная связь, для которой в тексте сущности
действительно нет ни одного подходящего слова - Tangem↔Multisig (связь
существует через рассуждение "конкурент Coinkite → та же логика
разнородности вендоров", не через явное упоминание мультиподписи).

Отсюда назначение этого скрипта - НЕ замена обязательного ручного/LLM-
прохода (см. CLAUDE.md, "Систематический аудит-чекпоинт для Пар 8/9"),
а его дешёвый первый фильтр: ловит подавляющее большинство случаев почти
бесплатно и детерминированно (объяснимо - "совпало, потому что текст
содержит X"), но не гарантированно все - относительно небольшая часть
связей (в проверенном образце - Tangem↔Multisig) существует только
через рассуждение о ОТНОШЕНИИ между сущностями (конкурент, альтернатива,
пример применения), а не через общий словарный запас текстов, и
принципиально не может быть поймана НИКАКИМ лексическим методом.

ТОЛЬКО генерация кандидатов - как и find_similar_signals.py, не решает
сама, честна ли связь. Каждый кандидат по-прежнему проверяется тем же
принципом: "добавляет ли понимание одного узла реальный, конкретный
контекст другому - не просто наличие слова".

РУКОВОДСТВО ДЛЯ КУРИРОВАНИЯ audit_keywords (найдено при сквозном тесте
на реальных данных, 2026-08-06): многозначные слова дают шум. "ликвидность"
как ключевое слово для панели про Lightning-каналы всплыло не только на
Lightning Labs (честная связь), но и на Strategy ("управление ликвидностью
и дивидендов" - корпоративный смысл) и Hyperliquid ("годами форы по
ликвидности" - биржевой смысл) - оба про СОВСЕМ другое значение того же
слова. Это не поломка механизма (кандидаты для отсева человеком, не
готовые решения) - но curator должен предпочитать специфичные словосочетания
там, где корень многозначен ("входящая ликвидность", "ликвидность канала"),
а не голый общий термин, чтобы не разводить лишний шум там, где это легко
избежать выбором более точной формулировки.

Использование:
    python3 scripts/find_keyword_wiki_candidates.py            # полный аудит
    python3 scripts/find_keyword_wiki_candidates.py --entity coinkite
"""
import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
ENTITIES_PATH = REPO_ROOT / "ENTITIES.json"
THEORY_TOPICS_PATH = REPO_ROOT / "THEORY_TOPICS.json"
BITCOIN_FUNCTIONS_PATH = REPO_ROOT / "BITCOIN_FUNCTIONS.json"

HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def strip_html(text: str) -> str:
    return HTML_TAG_PATTERN.sub(" ", text)


def entity_text(e: dict) -> str:
    parts = [
        e.get("summary", ""),
        e.get("profile", {}).get("what", ""),
        e.get("profile", {}).get("notable", ""),
    ]
    return " ".join(p for p in parts if p)


def find_keyword_match(text: str, keywords: list) -> str | None:
    """
    Возвращает ПЕРВОЕ совпавшее ключевое слово (для объяснимости в
    выводе) или None. Регистронезависимо, граница слова ТОЛЬКО СЛЕВА
    (\\b перед словом, без \\b после) — намеренно, не недосмотр:

    Русский язык сильно флективен (падежи, числа) - "ликвидность"
    встречается в тексте как "ликвидности", "ликвидностью" и т.д.
    Граница с ОБЕИХ сторон (\\bликвидност\\b) не совпадёт ни с одной
    флективной формой, только с "ликвидност" как отдельным словом,
    которого не бывает - куратор вписывает КОРЕНЬ (audit_keywords:
    ["ликвидност"]), не полную словоформу, и ожидает совпадения со
    всеми падежами.

    Компромисс, найденный тестами (2026-08-06): короткие акронимы-корни
    ("BIP" как отдельное слово) могут случайно совпасть с началом
    несвязанного слова (\\bbip совпадёт с началом "Biplanet", поскольку
    начало слова - тоже граница). Это не решается регулярным выражением
    - решение на стороне куратора: выбирать достаточно специфичные
    ключевые слова ("BIP-360", "BIP-361", не голое "BIP"), тот же
    принцип осознанного ручного курирования, что и весь остальной
    контент в этом проекте.
    """
    text_lower = text.lower()
    for kw in keywords:
        pattern = r"\b" + re.escape(kw.lower())
        if re.search(pattern, text_lower):
            return kw
    return None


def entity_has_theory_link(entity: dict, topic_id: str) -> bool:
    return topic_id in entity.get("theory_refs", [])


def entity_has_function_link(entity: dict, function_id: str) -> bool:
    return function_id in entity.get("function_refs", [])


def audit_entity_theory(entities: list, topics: list, entity_filter: str = None):
    candidates = entities
    if entity_filter:
        candidates = [e for e in candidates if e["id"] == entity_filter]

    results = []
    for e in candidates:
        text = entity_text(e)
        for topic in topics:
            if entity_has_theory_link(e, topic["id"]):
                continue
            for item in topic.get("items", []):
                keywords = item.get("audit_keywords", [])
                if not keywords:
                    continue
                match = find_keyword_match(text, keywords)
                if match:
                    results.append({
                        "entity_id": e["id"], "entity_name": e["name"],
                        "topic_id": topic["id"], "item_label": item["label"],
                        "matched_keyword": match,
                    })
    return results


def audit_entity_function(entities: list, functions: list, entity_filter: str = None):
    candidates = entities
    if entity_filter:
        candidates = [e for e in candidates if e["id"] == entity_filter]

    results = []
    for e in candidates:
        text = entity_text(e)
        for fn in functions:
            if entity_has_function_link(e, fn["id"]):
                continue
            keywords = fn.get("audit_keywords", [])
            if not keywords:
                continue
            match = find_keyword_match(text, keywords)
            if match:
                results.append({
                    "entity_id": e["id"], "entity_name": e["name"],
                    "function_id": fn["id"], "function_name": fn["name"],
                    "matched_keyword": match,
                })
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--entity", help="Ограничить аудит одной сущностью (id)")
    args = parser.parse_args()

    entities = load_json(ENTITIES_PATH)["entities"]
    topics = load_json(THEORY_TOPICS_PATH)["topics"]
    functions = load_json(BITCOIN_FUNCTIONS_PATH)["functions"]

    topics_with_kw = sum(1 for t in topics for i in t.get("items", []) if i.get("audit_keywords"))
    functions_with_kw = sum(1 for f in functions if f.get("audit_keywords"))
    print("Поиск кандидатов ENTITIES ↔ THEORY_TOPICS/BITCOIN_FUNCTIONS по ключевым словам")
    print(f"Пунктов теории с audit_keywords: {topics_with_kw}, функций: {functions_with_kw}")
    print("ТОЛЬКО генерация кандидатов — каждый требует честной проверки вручную.")
    print("Ловит подавляющее большинство буквальных совпадений — но не все: связи через отношение (не текст) требуют полного прохода.\n")

    print("═══ ENTITIES ↔ THEORY_TOPICS ═══")
    et = audit_entity_theory(entities, topics, args.entity)
    if not et:
        print("  Кандидатов не найдено")
    for r in et:
        print(f"  [{r['matched_keyword']}]  {r['entity_name']:20} ↔ {r['topic_id']}/{r['item_label']}")

    print("\n═══ ENTITIES ↔ BITCOIN_FUNCTIONS ═══")
    ef = audit_entity_function(entities, functions, args.entity)
    if not ef:
        print("  Кандидатов не найдено")
    for r in ef:
        print(f"  [{r['matched_keyword']}]  {r['entity_name']:20} ↔ {r['function_name']}")


if __name__ == "__main__":
    main()
