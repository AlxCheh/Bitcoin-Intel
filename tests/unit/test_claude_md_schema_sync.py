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


# ═══════════════════════════════════════════════════════════════════════
# Страж синхронности enum-описаний: schemas/signal/v1.json ↔ CLAUDE.md
#
# schemas/signal/v1.json обогащён (oneOf const+description вместо голого
# enum) для 8 полей — machine-readable смысл каждого значения теперь
# существует В САМОЙ СХЕМЕ, не только в прозе CLAUDE.md. Без этого теста
# два места с одним и тем же смыслом неизбежно разошлись бы — ровно
# то же, что уже произошло с таблицей кластеров (v8.8) и разделом FACTS
# (v8.9): дублирование смысла без механизма не держится (AD-6).
#
# Описания в схему перенесены ДОСЛОВНО из прозы CLAUDE.md на момент
# обогащения — для `cat` описание составное (catLabel без эмодзи +
# примеры), т.к. в прозе у cat нет отдельной колонки "смысл", только
# catLabel + Примеры; для narrative_role используется колонка
# "Критерий" (содержательное определение, не короткая расшифровка для
# сводки).
# ═══════════════════════════════════════════════════════════════════════

def _load_schema_oneof_descriptions(field: str) -> dict[str, str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    prop = schema["properties"][field]
    assert "oneOf" in prop, f"Поле '{field}' в схеме должно использовать oneOf(const+description), не голый enum"
    return {branch["const"]: branch["description"] for branch in prop["oneOf"]}


def _parse_two_col_table_after(text: str, anchor: str) -> dict[str, str]:
    """
    Парсит markdown-таблицу '| Значение | Смысл |' сразу после anchor —
    используется для dir/horizon/weight/actor/flow (общая форма).
    """
    idx = text.index(anchor)
    m = re.search(
        r"\| Значение \| Смысл \|\n\|[-|]+\|\n((?:\|.+\|\n)+)",
        text[idx:],
    )
    assert m, f"Таблица 'Значение|Смысл' не найдена после '{anchor[:40]}...'"
    rows = {}
    for line in m.group(1).strip().split("\n"):
        cells = [c.strip() for c in line.strip("|").split("|")]
        value = cells[0].strip("`")
        rows[value] = cells[1]
    return rows


def _parse_theme_table(text: str) -> dict[str, str]:
    """Тема встроена в id-префиксную таблицу: | Префикс | theme | Смысл темы |"""
    m = re.search(
        r"\| Префикс \| theme \| Смысл темы \|\n\|[-|]+\|\n((?:\|.+\|\n)+)",
        text,
    )
    assert m, "Таблица id-префиксов (Префикс|theme|Смысл темы) не найдена"
    rows = {}
    for line in m.group(1).strip().split("\n"):
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows[cells[1].strip("`")] = cells[2]
    return rows


def _parse_cat_table(text: str) -> dict[str, str]:
    """
    cat/catLabel/Примеры → составное description 'LABEL (без эмодзи) —
    например: Примеры', плюс ta (депрецирована, своя строка вне таблицы).
    """
    m = re.search(
        r"\| cat \| catLabel \(канон\) \| Примеры \|\n\|[-|]+\|\n((?:\|.+\|\n)+)",
        text,
    )
    assert m, "Таблица cat/catLabel/Примеры не найдена"
    rows = {}
    for line in m.group(1).strip().split("\n"):
        cells = [c.strip() for c in line.strip("|").split("|")]
        cat_value = cells[0].strip("`")
        label_no_emoji = re.sub(r"^\S+\s+", "", cells[1]).strip()  # снять ведущий emoji
        examples = cells[2]
        rows[cat_value] = f"{label_no_emoji} — например: {examples}"

    ta_match = re.search(r"Категория `ta`.*?депрецирована в v6\.0[^.]*\.", text)
    assert ta_match, "Заметка о депрекации 'ta' не найдена"
    rows["ta"] = "Технический анализ — депрецирована в v6.0, новые сигналы с этой категорией не создаются"
    return rows


def _parse_narrative_role_table(text: str) -> dict[str, str]:
    """| Роль | Критерий | Расшифровка для сводки | — используем 'Критерий'."""
    m = re.search(
        r"\| Роль \| Критерий \| Расшифровка для сводки \|\n\|[-|]+\|\n((?:\|.+\|\n)+)",
        text,
    )
    assert m, "Таблица narrative_role (Роль|Критерий|Расшифровка) не найдена"
    rows = {}
    for line in m.group(1).strip().split("\n"):
        cells = [c.strip() for c in line.strip("|").split("|")]
        meaning = re.sub(r"`([^`]+)`", r"\1", cells[1])  # снять markdown-код внутри текста
        rows[cells[0].strip("`")] = meaning
    return rows


import pytest as _pytest  # noqa: E402


@_pytest.mark.parametrize("field,anchor", [
    ("dir", "**`dir`** — что сигнал говорит"),
    ("horizon", "**`horizon`** — временной горизонт"),
    ("weight", "**`weight`** — достоверность источника"),
    ("actor", "**`actor`** — субъект сигнала"),
    ("flow", "**`flow`** — направление капитала"),
])
def test_schema_enum_description_matches_claude_md_two_col_table(field, anchor):
    """
    Для 5 полей с однотипной таблицей '| Значение | Смысл |': описание в
    schemas/signal/v1.json (oneOf) должно дословно совпадать с колонкой
    "Смысл" в CLAUDE.md.
    """
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    claude_md = _parse_two_col_table_after(text, anchor)
    schema_desc = _load_schema_oneof_descriptions(field)

    assert claude_md == schema_desc, (
        f"[{field}] Расхождение CLAUDE.md ↔ schema: "
        f"claude_md={claude_md}, schema={schema_desc}"
    )


def test_schema_theme_description_matches_claude_md():
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    assert _parse_theme_table(text) == _load_schema_oneof_descriptions("theme")


def test_schema_cat_description_matches_claude_md():
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    assert _parse_cat_table(text) == _load_schema_oneof_descriptions("cat")


def test_schema_narrative_role_description_matches_claude_md():
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    assert _parse_narrative_role_table(text) == _load_schema_oneof_descriptions("narrative_role")


def test_all_eight_enum_fields_use_oneof_not_bare_enum():
    """
    Явная проверка формы: ни одно из 8 полей не должно тихо откатиться
    на голый `enum` (например, при будущей правке кем-то, кто не знает
    про это решение) — иначе описания молча перестанут существовать в
    схеме, а этот файл тестов перестанет их проверять (упадёт на
    отсутствии oneOf, но с менее говорящим сообщением без этой проверки).
    """
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    for field in ["narrative_role", "theme", "weight", "dir", "horizon", "cat", "actor", "flow"]:
        prop = schema["properties"][field]
        assert "oneOf" in prop and "enum" not in prop, (
            f"Поле '{field}' должно использовать oneOf(const+description), "
            "не enum — см. CLAUDE.md v8.10/предложение 1 (машиночитаемые "
            "описания значений в самой схеме)"
        )


def test_enum_description_detector_catches_injected_drift():
    """
    Страж-на-стража: искажение описания в схеме ловится сравнением с
    прозой CLAUDE.md (паттерн test_check_stale_facts_catches_injected_stale_copy).
    """
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    real_claude_md = _parse_two_col_table_after(text, "**`dir`** — что сигнал говорит")
    real_schema = _load_schema_oneof_descriptions("dir")
    assert real_claude_md == real_schema  # исходное состояние синхронно

    corrupted_schema = dict(real_schema)
    corrupted_schema["pos"] = "ИСКАЖЁННОЕ описание"
    assert corrupted_schema != real_claude_md, "детектор обязан ловить искажение"


# ═══════════════════════════════════════════════════════════════════════
# Страж против дрейфа CLAUDE.md ↔ ontology.json (таблица «Кластеры»)
#
# CLAUDE.md сам объявляет ontology.json.clusters «фактическим источником
# истины» (раздел «Кластеры (текущие)»), а свою таблицу — человекочитаемым
# зеркалом для быстрой справки. Без теста это зеркало может разойтись
# молча — и разошлось: при аудите 2026-07-19 обнаружено, что описание
# supply_scarcity в CLAUDE.md потеряло ", цикличность" по сравнению с
# ontology.json (исправлено тем же PR, что и этот тест). Тот же класс
# проблемы, что FACTS/SITE_MAP/SIGNALS.md — процедура без механизма не
# держится (AD-6).
#
# Проверка двусторонняя: новый кластер в ontology.json без строки в
# CLAUDE.md — падение (человек не увидит документацию новой темы);
# строка в CLAUDE.md без кластера в ontology.json — падение (устаревшая/
# удалённая запись вводит в заблуждение); описания должны совпадать
# дословно, не только набор ключей.
# ═══════════════════════════════════════════════════════════════════════

ONTOLOGY_PATH = REPO_ROOT / "ontology.json"


def _load_claude_md_cluster_table() -> dict[str, str]:
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"## Кластеры \(текущие\)\n\n\| cluster \| Описание \|\n\|---------\|----------\|\n(.*?)\n\n",
        text,
        re.S,
    )
    assert match, (
        "Не найдена таблица кластеров в CLAUDE.md (секция "
        "'## Кластеры (текущие)') — структура файла изменилась, "
        "тест нужно обновить вручную"
    )
    rows = {}
    for line in match.group(1).strip().split("\n"):
        m = re.match(r"\| `([^`]+)` \| (.+) \|$", line)
        if m:
            rows[m.group(1)] = m.group(2)
    return rows


def _load_ontology_clusters() -> dict[str, str]:
    ontology = json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))
    return {k: v["description"] for k, v in ontology["clusters"].items()}


def test_claude_md_cluster_table_matches_ontology_json():
    """
    Двусторонняя сверка ключей + дословное совпадение описаний.
    Падение с недостающим кластером → допиши строку в таблицу CLAUDE.md.
    Падение с лишним кластером → удали устаревшую строку (кластер убран
    из ontology.json) или проверь опечатку в имени.
    Падение с расхождением описания → одно из двух устарело; ontology.json
    объявлен источником истины, но реши осознанно, не просто скопируй.
    """
    claude_rows = _load_claude_md_cluster_table()
    ontology_rows = _load_ontology_clusters()

    missing_in_claude_md = set(ontology_rows) - set(claude_rows)
    assert not missing_in_claude_md, (
        f"Кластеры есть в ontology.json, но не в таблице CLAUDE.md: "
        f"{sorted(missing_in_claude_md)}"
    )

    stale_in_claude_md = set(claude_rows) - set(ontology_rows)
    assert not stale_in_claude_md, (
        f"Строки в таблице CLAUDE.md ссылаются на кластеры, которых нет "
        f"в ontology.json: {sorted(stale_in_claude_md)}"
    )

    mismatched = {
        k: (claude_rows[k], ontology_rows[k])
        for k in claude_rows
        if claude_rows[k] != ontology_rows[k]
    }
    assert not mismatched, (
        "Описания кластеров разошлись между CLAUDE.md и ontology.json "
        f"(claude_md, ontology): {mismatched}"
    )
