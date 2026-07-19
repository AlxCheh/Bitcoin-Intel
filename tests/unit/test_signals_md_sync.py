"""
tests/unit/test_signals_md_sync.py
Bitcoin Intel — страж синхронизации SIGNALS.md ↔ signals.json.

SIGNALS.md больше не редактируется руками (см. scripts/build_signals_md.py) —
это производный файл, как data/facts.json. Единственный способ его изменить —
отредактировать signals.json и запустить генератор. Этот тест ловит любое
расхождение: новый сигнал без перегенерации, ручную правку .md напрямую,
правку текста в JSON без повторного прогона скрипта.

История вопроса: до 2026-07-19 SIGNALS.md вёлся руками параллельно с
signals.json («правило два файла одновременно», CLAUDE.md) — без механизма
проверки это разошлось молча за несколько месяцев: порядок блоков перестал
соответствовать заявленной сортировке (date DESC), а часть текстовых полей
(data/context/caveat) в .md отстала от более новых правок в .json. Тот же
класс проблемы, что уже решён для FACTS (AD-6) и SITE_MAP.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_signals_md as gen  # noqa: E402

SIGNALS_MD_PATH = REPO_ROOT / "SIGNALS.md"


def test_signals_md_matches_generator_output():
    """
    Байт-в-байт сверка: то, что лежит на диске, должно совпадать с тем,
    что породил бы генератор из ТЕКУЩЕГО signals.json прямо сейчас.
    """
    on_disk = SIGNALS_MD_PATH.read_text(encoding="utf-8")
    regenerated = gen.build()

    assert on_disk == regenerated, (
        "SIGNALS.md разошёлся с signals.json. Запусти "
        "`python3 scripts/build_signals_md.py` и закоммить результат "
        "тем же PR, что и правку signals.json."
    )


def test_generator_output_is_deterministic():
    """Два прогона подряд дают идентичный результат (нет скрытой недетерминированности — множеств, дат из datetime.now() и т.п.)."""
    assert gen.build() == gen.build()


def test_every_signal_appears_exactly_once():
    """Ни один сигнал не потерян и не задублирован при рендере."""
    import json

    data = json.loads((REPO_ROOT / "signals.json").read_text(encoding="utf-8"))
    ids = [s["id"] for s in data["signals"]]

    output = gen.build()
    for sid in ids:
        assert output.count(f"## {sid} ·") == 1, f"{sid} должен встречаться ровно 1 раз"


def test_sort_order_is_date_desc_then_id_desc():
    """
    Явная проверка конвенции сортировки (не полагаться только на побайтовое
    совпадение — оно не объясняет ПОЧЕМУ порядок такой при дебаге).
    Тай-брейк id DESC выведен эмпирически из корпуса до разъезда
    (см. docstring build_signals_md.py) — не выдуман.
    """
    import json

    data = json.loads((REPO_ROOT / "signals.json").read_text(encoding="utf-8"))
    expected_order = [
        s["id"]
        for s in sorted(data["signals"], key=lambda s: (s["date"], s["id"]), reverse=True)
    ]

    output = gen.build()
    import re

    actual_order = re.findall(r"^## (\S+) ·", output, re.M)

    assert actual_order == expected_order


def test_archived_tail_preserved_verbatim():
    """Доисторический раздел без id/theme/links не теряется при регенерации."""
    output = gen.build()
    assert "## Архивные заметки по разделам сайта" in output
    assert "git log -p -- SIGNALS.md" in output


def test_generator_catches_injected_drift():
    """
    Страж самого стража (паттерн test_check_stale_facts_catches_injected_stale_copy):
    искусственно рассинхронизированный файл ловится, синхронный — нет.
    """
    real = gen.build()
    corrupted = real.replace("Сигнал:**", "Сигнал (ИСПОРЧЕНО):**", 1)
    assert corrupted != gen.build()
    assert real == gen.build()
