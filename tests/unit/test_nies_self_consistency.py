"""
tests/unit/test_nies_self_consistency.py
Bitcoin Intel — страж внутренней согласованности docs/NIES.md (AD-9, случай 4).

КОНТЕКСТ
--------
AD-9 (docs/NIES.md, Часть XI) зарегистрировал четыре случая, где проверка
целостности держится на процедурной дисциплине сессии, а не на тесте.
Случай (4) — согласованность прозы самого NIES.md — единственный из четырёх
**структурный**, не семантический: его можно проверить механически, в отличие
от «значимости сущности» или «честности связи», где нужно суждение человека.

Дрейф не гипотетический — он реально произошёл дважды подряд при регистрации
AD-8 (v2.3, PR #867): обновлены шапка, «История» и таблица долга, но НЕ
обновлены «Вердикт» (остался «Семь пунктов», хотя их стало восемь) и футер
(остался «Версия 2.2»). Поймано вручную при подготовке объяснения документа,
закрыто отдельным PR #868 — то есть реактивно, как и предсказывает AD-9.
Третий случай того же класса найден при написании этого теста: абзац статусов
озаглавлен «Статус на v2.1», хотя перечисляет записи из v2.3 и v2.4.

ЧТО ПРОВЕРЯЕТСЯ
---------------
Четыре инварианта, каждый — ровно тот вид дрейфа, который уже случался:

1. Версия в шапке == версия в футере.
2. Числительное в «Вердикте» == фактическое число строк AD-N в таблице.
3. Каждый AD-N из таблицы упомянут в абзаце статусов (не забыт при добавлении).
4. «Статус на vX» == версия в шапке (абзац описывает актуальное состояние).

Тест НЕ проверяет содержательную корректность формулировок долга — только то,
что документ не противоречит сам себе в проверяемых механически местах.
Тот же класс стража, что test_claude_md_schema_sync.py для AD-6.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
NIES_PATH = REPO_ROOT / "docs" / "NIES.md"

# Числительные прописью, встречающиеся в «Вердикте». Диапазон с запасом:
# документ рос 7 → 8 → 9, следующие значения понадобятся при AD-10+.
RU_NUMERALS = {
    "Пять": 5, "Шесть": 6, "Семь": 7, "Восемь": 8, "Девять": 9,
    "Десять": 10, "Одиннадцать": 11, "Двенадцать": 12, "Тринадцать": 13,
    "Четырнадцать": 14, "Пятнадцать": 15,
}


def _read_nies() -> str:
    return NIES_PATH.read_text(encoding="utf-8")


def _header_version(text: str) -> str:
    match = re.search(r"^\*\*Версия:\*\*\s*([\d.]+)\s*$", text, re.M)
    assert match, (
        "Не найдена версия в шапке NIES.md (строка вида '**Версия:** 2.4') — "
        "структура документа изменилась, тест нужно обновить вручную"
    )
    return match.group(1)


def _footer_version(text: str) -> str:
    match = re.search(r"\*Конец документа\.\s*Версия\s*([\d.]+)\.", text)
    assert match, (
        "Не найдена версия в футере NIES.md (строка вида "
        "'*Конец документа. Версия 2.4. ...*') — структура изменилась"
    )
    return match.group(1)


def _debt_table_ids(text: str) -> list[str]:
    """ID строк таблицы «Архитектурный долг» в порядке появления."""
    ids = re.findall(r"^\|\s*(AD-\d+)\s*\|", text, re.M)
    assert ids, "Не найдено ни одной строки AD-N в таблице архитектурного долга"
    return ids


def _verdict_count(text: str) -> int:
    match = re.search(r"(\w+)\s+пунктов архитектурного долга", text)
    assert match, (
        "Не найдена фраза 'N пунктов архитектурного долга' в «Вердикте» — "
        "формулировка изменилась, тест нужно обновить вручную"
    )
    word = match.group(1)
    assert word in RU_NUMERALS, (
        f"Числительное '{word}' в «Вердикте» не распознано — "
        f"допиши его в RU_NUMERALS (известные: {sorted(RU_NUMERALS)})"
    )
    return RU_NUMERALS[word]


def _status_paragraph(text: str) -> str:
    match = re.search(r"Долг зафиксирован сознательно:.*?(?=\n\n)", text, re.S)
    assert match, (
        "Не найден абзац статусов ('Долг зафиксирован сознательно: …') — "
        "структура изменилась"
    )
    return match.group(0)


def _status_paragraph_version(text: str) -> str:
    match = re.search(r"Статус на v([\d.]+):", _status_paragraph(text))
    assert match, (
        "Не найден маркер 'Статус на vX:' в абзаце статусов — "
        "формулировка изменилась"
    )
    return match.group(1)


def test_header_version_matches_footer_version():
    """
    Ровно тот дрейф, что случился в PR #867: шапка обновлена на 2.3,
    футер остался 2.2 (поймано вручную, закрыто реактивно в PR #868).
    """
    text = _read_nies()
    header, footer = _header_version(text), _footer_version(text)
    assert header == footer, (
        f"Версия в шапке NIES.md ({header}) не совпадает с версией в футере "
        f"({footer}). При обновлении версии документа правятся ОБА места — "
        "см. AD-9, случай 4."
    )


def test_verdict_count_matches_debt_table_rows():
    """
    Второй дрейф из PR #867: в таблицу добавлен AD-8, «Вердикт» остался
    с «Семь пунктов».
    """
    text = _read_nies()
    declared, actual = _verdict_count(text), len(_debt_table_ids(text))
    assert declared == actual, (
        f"«Вердикт» заявляет {declared} пунктов архитектурного долга, а в "
        f"таблице фактически {actual} строк AD-N. Добавили запись в таблицу — "
        "обновите числительное в «Вердикте» тем же коммитом (AD-9, случай 4)."
    )


def test_every_debt_id_is_mentioned_in_status_paragraph():
    """
    Новая запись в таблице обязана получить статус в сводном абзаце —
    иначе читатель видит пункт в таблице, но не понимает, в какой он
    стадии (закрыт / принят / открыт с триггером).
    """
    text = _read_nies()
    paragraph = _status_paragraph(text)
    missing = [ad for ad in _debt_table_ids(text) if ad not in paragraph]
    assert not missing, (
        f"Записи {missing} есть в таблице архитектурного долга, но не "
        "упомянуты в абзаце статусов ('Долг зафиксирован сознательно: …') — "
        "допишите их статус тем же коммитом (AD-9, случай 4)."
    )


def test_status_paragraph_version_matches_header():
    """
    Третий случай того же класса, найденный при написании этого теста:
    абзац озаглавлен «Статус на v2.1», хотя перечисляет записи из v2.3/v2.4.
    Маркер версии обязан описывать актуальное состояние документа.
    """
    text = _read_nies()
    header, stated = _header_version(text), _status_paragraph_version(text)
    assert header == stated, (
        f"Абзац статусов озаглавлен «Статус на v{stated}», а текущая версия "
        f"документа — v{header}. Абзац описывает актуальное состояние долга, "
        "значит маркер обновляется вместе с версией (AD-9, случай 4)."
    )


def test_detectors_catch_injected_drift():
    """
    Страж-на-стража (паттерн test_enum_description_detector_catches_injected_drift):
    убедиться, что проверки выше падают на искажённом документе, а не
    проходят вхолостую из-за неудачной регулярки.
    """
    text = _read_nies()

    # исходное состояние согласовано
    assert _header_version(text) == _footer_version(text)
    assert _verdict_count(text) == len(_debt_table_ids(text))

    corrupted_footer = text.replace(
        f"*Конец документа. Версия {_footer_version(text)}.",
        "*Конец документа. Версия 0.1.",
    )
    assert _footer_version(corrupted_footer) == "0.1", (
        "детектор футера обязан читать искажённое значение, а не исходное"
    )
    assert _header_version(text) != _footer_version(corrupted_footer)

    # искажение таблицы: убрать последнюю строку AD-N
    ids = _debt_table_ids(text)
    last_id = ids[-1]
    corrupted_table = re.sub(rf"^\|\s*{last_id}\s*\|.*$", "", text, flags=re.M)
    assert len(_debt_table_ids(corrupted_table)) == len(ids) - 1, (
        "детектор таблицы обязан заметить удалённую строку"
    )
    assert _verdict_count(corrupted_table) != len(_debt_table_ids(corrupted_table))
