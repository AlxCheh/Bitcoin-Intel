"""
tests/unit/test_claude_md_schema_sync.py
Bitcoin Intel — страж против дрейфа CLAUDE.md ↔ schemas/signal/v1.json (AD-6, docs/NIES.md).

КОНТЕКСТ
--------
AD-6 (docs/NIES.md, Часть XI): дважды подряд поле добавлялось в пример схемы
сигнала CLAUDE.md версией (v7.6 — `alternatives_considered`; v7.7 —
`alternative_scenario`), а `schemas/signal/v1.json` не обновлялась в том же
PR. Оба раза расхождение обнаруживалось не на PR со спекой, а постфактум —
Contract Tests падали на первом реальном сигнале с новым полем (например,
INF-2026-0702-001, PR #130), когда откатывать уже сложнее, чем просто
дополнить схему.

Этот тест — не разовая проверка, а страж против повторного дрейфа: любое
будущее изменение примера схемы в CLAUDE.md («## Сигнал: схема объекта»)
без синхронного добавления поля в `schemas/signal/v1.json` теперь падает в
CI на PR со спекой, а не остаётся незамеченным до первого сигнала с новым
полем (тот же класс риска, что и M3 в test_ontology_settings_consistency.py).

НАПРАВЛЕНИЕ ПРОВЕРКИ
---------------------
Односторонне: каждое поле из примера в CLAUDE.md должно существовать в
`properties` схемы. Обратное не требуется — схема может легитимно содержать
поля, которых нет в примере CLAUDE.md (`cluster_label`, `theory_ref` —
задокументированные в самой схеме исключения, встречающиеся в
production-данных до того как решение "оставить/убрать" принято, см.
AD-2/AD-4 в docs/NIES.md). Пример CLAUDE.md — не обязан быть исчерпывающим
переч­нем всех когда-либо встречавшихся полей, но обязан быть подмножеством
того, что схема разрешает.
"""
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
CLAUDE_MD_PATH = REPO_ROOT / "CLAUDE.md"
SCHEMA_PATH = REPO_ROOT / "schemas" / "signal" / "v1.json"


def _load_claude_md_example_fields() -> set[str]:
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"## Сигнал: схема объекта.*?```json\n(.*?)\n```",
        text,
        re.S,
    )
    assert match, (
        "Не найден блок примера схемы сигнала в CLAUDE.md "
        "(секция '## Сигнал: схема объекта' с ```json блоком) — "
        "структура файла изменилась, тест нужно обновить вручную"
    )
    example = json.loads(match.group(1))
    return set(example.keys())


def _load_schema_properties() -> set[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return set(schema["properties"].keys())


def test_claude_md_example_fields_all_exist_in_schema():
    """
    Каждое поле из примера схемы сигнала в CLAUDE.md должно быть разрешено
    в schemas/signal/v1.json. Если это падает — CLAUDE.md обновили (добавили
    поле в пример), но забыли синхронно обновить схему. Исправление: добавить
    поле в `properties` схемы в том же PR, что и правку CLAUDE.md (см. AD-6).
    """
    claude_md_fields = _load_claude_md_example_fields()
    schema_fields = _load_schema_properties()

    missing_in_schema = claude_md_fields - schema_fields
    assert not missing_in_schema, (
        "Поля документированы в примере CLAUDE.md, но отсутствуют в "
        f"schemas/signal/v1.json: {sorted(missing_in_schema)}. "
        "CLAUDE.md — это спека, схема — производное (S12, docs/NIES.md): "
        "обновите schemas/signal/v1.json тем же коммитом, что и CLAUDE.md."
    )


def test_schema_required_fields_all_documented_in_claude_md():
    """
    Обратная сторона той же проверки: всё, что схема требует (`required`),
    должно быть в примере CLAUDE.md — иначе пример вводит в заблуждение,
    выглядя как полный, но не показывая обязательное поле.
    """
    claude_md_fields = _load_claude_md_example_fields()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    required_fields = set(schema.get("required", []))

    missing_in_example = required_fields - claude_md_fields
    assert not missing_in_example, (
        "Схема требует поля, которых нет в примере CLAUDE.md: "
        f"{sorted(missing_in_example)}. Обновите пример в секции "
        "'## Сигнал: схема объекта'."
    )
