"""
scripts/build_signals_index.py
Bitcoin Intel — детерминированный генератор data/signals_index.json из signals.json.

ПРОБЛЕМА, КОТОРУЮ РЕШАЕТ ЭТОТ СКРИПТ: и signals.json (539 КБ на 115 сигналов),
и его читаемая проекция SIGNALS.md (492 КБ) слишком тяжелы, чтобы читать
целиком ради панорамного вопроса («какие tension сейчас в базе», обзор по
кластерам) — на 300 сигналах это ~350K токенов на файл, риск случайно
выжрать контекстное окно одним Read(). Целевого чтения (`grep` по id/
кластеру/теме) это не заменяет и не должно — для точечной работы по
Шагу 5 CLAUDE.md `grep` был и остаётся правильным инструментом, независимо
от размера файла.

РЕШЕНИЕ: узкий производный индекс — только те поля, что нужны для панорамного
обзора корпуса (id, date, cluster, dir, narrative_role, signal, tension), без
data/context/caveat/alternatives/facts/links. На 115 сигналах это на порядок
легче SIGNALS.md; проекция на 300 сигналов — низкие десятки тысяч токенов,
безопасно для полного Read().

Тот же принцип, что уже применён для SIGNALS.md (2026-07-19) и data/facts.json:
производный файл не редактируется руками, регенерируется этим скриптом,
тест-страж (tests/unit/test_signals_index_sync.py) проверяет байт-в-байт
синхронность с signals.json на каждом прогоне — процедура без механизма
в этом проекте исторически не держится (AD-6).

Запускать после КАЖДОГО изменения signals.json (нового сигнала, правки
существующего), тем же коммитом, что и build_signals_md.py:
    python3 scripts/build_signals_index.py

Сортировка (date DESC, при равенстве — id DESC) — та же конвенция, что в
build_signals_md.py, для согласованности между производными артефактами.

Полностью детерминирован намеренно: никакого generated_at на date.today()
(в отличие от build_facts.py) — иначе байт-в-байт тест синхронности ловил
бы ложное расхождение на следующий день после генерации без единой правки
signals.json.
"""
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIGNALS_JSON_PATH = os.path.join(REPO_ROOT, "signals.json")
INDEX_JSON_PATH = os.path.join(REPO_ROOT, "data", "signals_index.json")

# Поля индекса — узкий срез, достаточный для панорамного обзора корпуса.
# НЕ включает: data, context, caveat, alternatives_considered,
# alternative_scenario, facts, links, macro_implication (по отдельности
# доступны через grep по id — точечное чтение остаётся дешёвым).
INDEX_FIELDS = ["id", "date", "cluster", "dir", "narrative_role", "signal", "tension"]


def build_index_entry(s: dict) -> dict:
    return {field: s[field] for field in INDEX_FIELDS}


def build() -> dict:
    with open(SIGNALS_JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    signals = sorted(
        data["signals"],
        key=lambda s: (s["date"], s["id"]),
        reverse=True,
    )

    return {
        "_generated_by": "scripts/build_signals_index.py — не редактировать руками",
        "_source": "signals.json (узкий срез полей — см. INDEX_FIELDS)",
        "_purpose": "Панорамное чтение корпуса целиком без риска исчерпать контекст; для точечной работы по конкретному сигналу использовать grep по signals.json",
        "signals": [build_index_entry(s) for s in signals],
    }


def build_text() -> str:
    """Сериализованный вывод — то, что реально пишется на диск и сверяется тестом."""
    return json.dumps(build(), ensure_ascii=False, indent=2) + "\n"


def main():
    output = build_text()
    os.makedirs(os.path.dirname(INDEX_JSON_PATH), exist_ok=True)
    with open(INDEX_JSON_PATH, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"OK: data/signals_index.json перегенерирован ({INDEX_JSON_PATH})")


if __name__ == "__main__":
    sys.exit(main())
