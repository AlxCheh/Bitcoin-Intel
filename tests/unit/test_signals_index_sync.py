"""
tests/unit/test_signals_index_sync.py
Bitcoin Intel — страж синхронизации data/signals_index.json ↔ signals.json.

Зеркалирует tests/unit/test_signals_md_sync.py для нового производного
артефакта (см. scripts/build_signals_index.py). Тот же урок AD-6: процедура
без механизма проверки в этом проекте не держится — SIGNALS.md уже один раз
разошёлся с signals.json за несколько месяцев без такого теста.
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_signals_index as gen  # noqa: E402

INDEX_JSON_PATH = REPO_ROOT / "data" / "signals_index.json"
SIGNALS_JSON_PATH = REPO_ROOT / "signals.json"


def test_index_matches_generator_output():
    """
    Байт-в-байт сверка: то, что лежит на диске, должно совпадать с тем,
    что породил бы генератор из ТЕКУЩЕГО signals.json прямо сейчас.
    """
    on_disk = INDEX_JSON_PATH.read_text(encoding="utf-8")
    regenerated = gen.build_text()

    assert on_disk == regenerated, (
        "data/signals_index.json разошёлся с signals.json. Запусти "
        "`python3 scripts/build_signals_index.py` и закоммить результат "
        "тем же PR, что и правку signals.json."
    )


def test_generator_output_is_deterministic():
    """Два прогона подряд дают идентичный результат."""
    assert gen.build_text() == gen.build_text()


def test_every_signal_appears_exactly_once():
    """Ни один сигнал не потерян и не задублирован в индексе."""
    data = json.loads(SIGNALS_JSON_PATH.read_text(encoding="utf-8"))
    expected_ids = [s["id"] for s in data["signals"]]

    index = json.loads(gen.build_text())
    actual_ids = [entry["id"] for entry in index["signals"]]

    assert sorted(actual_ids) == sorted(expected_ids)
    assert len(actual_ids) == len(set(actual_ids)), "дубликаты id в индексе"


def test_sort_order_is_date_desc_then_id_desc():
    """Та же конвенция сортировки, что в build_signals_md.py — для согласованности."""
    data = json.loads(SIGNALS_JSON_PATH.read_text(encoding="utf-8"))
    expected_order = [
        s["id"]
        for s in sorted(data["signals"], key=lambda s: (s["date"], s["id"]), reverse=True)
    ]

    index = json.loads(gen.build_text())
    actual_order = [entry["id"] for entry in index["signals"]]

    assert actual_order == expected_order


def test_index_entry_has_only_declared_fields():
    """
    Узкий срез — намеренно. Если кто-то добавит поле в INDEX_FIELDS не
    понимая бюджет (docstring build_signals_index.py), тест не упадёт сам
    по себе, но эта проверка хотя бы фиксирует набор полей явно, чтобы
    расширение было осознанным, а не случайным импортом лишнего поля.
    """
    index = json.loads(gen.build_text())
    for entry in index["signals"]:
        assert set(entry.keys()) == set(gen.INDEX_FIELDS)


def test_index_is_no_more_than_a_fifth_of_signals_md_size():
    """
    Экономический смысл индекса — быть заметно легче полной проекции.
    Порог 20% — щедрый запас (текущее фактическое соотношение ~17%),
    ловит регресс, если кто-то по ошибке добавит тяжёлые поля вроде
    macro_implication/data/context в INDEX_FIELDS.
    """
    import build_signals_md as md_gen  # noqa: E402

    index_size = len(gen.build_text().encode("utf-8"))
    md_size = len(md_gen.build().encode("utf-8"))

    assert index_size < md_size * 0.2, (
        f"Индекс ({index_size} байт) занимает более 20% размера SIGNALS.md "
        f"({md_size} байт) — проверь, не добавлено ли в INDEX_FIELDS тяжёлое поле."
    )


def test_generator_catches_injected_drift():
    """Страж самого стража: искусственно рассинхронизированный файл ловится."""
    real = gen.build_text()
    corrupted = real.replace('"dir":', '"dir_CORRUPTED":', 1)
    assert corrupted != gen.build_text()
    assert real == gen.build_text()


def test_tension_field_not_truncated():
    """
    tension в индексе должен быть идентичен tension в signals.json — не
    обрезан/не пересказан. Индекс существует ЧТОБЫ читать tension дёшево;
    если он обрезан, весь смысл артефакта теряется молча.
    """
    data = json.loads(SIGNALS_JSON_PATH.read_text(encoding="utf-8"))
    by_id = {s["id"]: s["tension"] for s in data["signals"]}

    index = json.loads(gen.build_text())
    for entry in index["signals"]:
        assert entry["tension"] == by_id[entry["id"]]
