"""
tests/conftest.py
Bitcoin Intel — глобальные pytest fixtures.

Автоматически применяется ко всем тестам (autouse=True).
Изолирует файловую систему: тесты не читают/пишут в реальные файлы проекта.

ВАЖНОЕ ПРАВИЛО (зафиксировано после B1 ARR v3):
isolated_environment ниже делает monkeypatch.chdir(tmp_path) для КАЖДОГО
теста без исключений. Это означает, что любой тест, который читает golden
fixture (или любой другой файл репозитория для чтения, не записи) по
ОТНОСИТЕЛЬНОМУ пути типа Path("tests/golden/fixtures/x.json"), всегда
получит несуществующий путь во временной песочнице — и либо упадёт, либо,
что хуже, молча pytest.skip(), создавая ложное впечатление прохождения теста.

Правило: тесты, которым нужно прочитать файл из репозитория (а не записать
во временную директорию), обязаны резолвить путь от Path(__file__), а не от
текущей рабочей директории:

    pairs_file = Path(__file__).parent / "fixtures" / "my_fixture.json"   # ПРАВИЛЬНО
    pairs_file = Path("tests/golden/fixtures/my_fixture.json")             # НЕПРАВИЛЬНО

Эталонный пример корректного паттерна — tests/golden/test_golden.py
(FIXTURES = Path(__file__).parent / "fixtures"). Пример бага, который этот
паттерн должен предотвратить — был в tests/unit/test_contradiction.py
(см. историю коммитов, B1 ARR v3): тест читал contradiction_pairs.json по
относительному пути, всегда получал "не найден" в песочнице и скипал —
включая в CI — много дней подряд, маскируя то, что precision алгоритма
не проходила архитектурный порог.
"""
import json
import os
import copy
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    """
    Изолирует каждый тест от реальных файлов проекта.
    Создаёт минимальный набор файлов во временной директории.
    Применяется автоматически ко всем тестам.
    """
    # Минимальные файлы для работы компонентов
    (tmp_path / "signals.json").write_text("[]", encoding="utf-8")
    (tmp_path / "ENTITIES.json").write_text("[]", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "events.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "synthesis_store").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "golden").mkdir()
    (tmp_path / "tests" / "golden" / "fixtures").mkdir()
    (tmp_path / "tests" / "golden" / "expected").mkdir()

    # Переключаем рабочую директорию
    monkeypatch.chdir(tmp_path)

    # Детерминизм
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    monkeypatch.setenv("ENVIRONMENT",    "test")

    yield tmp_path


@pytest.fixture
def sample_signal() -> dict:
    """Валидный тестовый сигнал для переиспользования в тестах."""
    return {
        "id":               "STR-2026-0101-001",
        "date":             "2026-01-01",
        "signal":           "Тестовый сигнал для unit-тестов",
        "cat":              "narrative",
        "catLabel":         "📰 Нарратив",
        "dir":              "pos",
        "horizon":          "mid",
        "theme":            "institutionalization",
        "weight":           "media",
        "actor":            "corporate",
        "flow":             "inflow",
        "tension":          "Тест vs контроль — проверка формулы",
        "macro_implication":"Unit-тест подтверждает корректность архитектуры и компонентов системы",
        "narrative_role":   "background",
        "cluster":          "test_cluster",
        "source":           "Test Suite (январь 2026)",
        "links":            {"confirms": [], "contradicts": [], "context_chain": []},
        "data":             [],
        "context":          "",
        "caveat":           "",
    }


@pytest.fixture
def sample_cluster_signals(sample_signal) -> list[dict]:
    """Набор из 3 сигналов для тестирования синтеза."""
    roles = [
        ("STR-2026-0101-001", "trigger",      "pos", []),
        ("STR-2026-0101-002", "complication", "neg", ["STR-2026-0101-001"]),
        ("STR-2026-0101-003", "background",   "neu", []),
    ]
    signals = []
    for sid, role, direction, contradicts in roles:
        s = copy.deepcopy(sample_signal)
        s["id"]             = sid
        s["narrative_role"] = role
        s["dir"]            = direction
        s["links"]["contradicts"] = contradicts
        signals.append(s)
    return signals


@pytest.fixture
def populated_signals_json(tmp_path, sample_signal):
    """Записывает sample_signal в signals.json во временной директории."""
    signals_path = tmp_path / "signals.json"
    signals_path.write_text(
        json.dumps([sample_signal], ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return signals_path


# ─── Общий JS-харнесс (2026-08-03) ───────────────────────────────────────
# До этой консолидации _extract_function (извлечение тела функции из
# app-main.js/app-early.js по балансу фигурных скобок, не regex — regex
# однажды уже обрезал synthesizeNarrativeAdvanced на первой вложенной
# '}' с совпадающим отступом, см. историю test_uncertainty_indicator.py)
# была независимо скопирована в 12 файлов tests/unit/*.py с косметическими
# отличиями (имена параметров, тексты ошибок) при идентичной логике.
# Отдельно, subprocess.run(["node", "-e", js], ...) - передача JS одним
# аргументом командной строки - несколько раз за 2026-08-03 упиралась в
# системный лимит ARG_MAX по мере роста THEORY_TOPICS.json/signals.json,
# каждый раз чинилась точечно в том файле, где всплыла. Обе проблемы -
# один и тот же класс (дублирование вместо общего места) - закрываются
# здесь один раз, а не при каждом следующем росте данных.
#
# Это ОБЫЧНЫЕ функции, не pytest-фикстуры - существующие тесты уже
# вызывают _extract_function() многократно с разными аргументами внутри
# своих собственных fixture/helper-методов (напр. `render_source`,
# `_run_popup`) - минимальная замена: одна строка импорта вместо
# копии определения, остальная структура каждого теста не тронута.

def extract_js_function(src: str, signature: str) -> str:
    """
    Извлекает тело `function <signature> {...}` из исходника JS по балансу
    фигурных скобок. signature может включать сигнатуру аргументов
    (`"foo(a, b)"`) - для поиска используется имя до первой `(`.
    """
    base_name = signature.split("(")[0].strip()
    start = src.find(f"function {base_name}")
    assert start != -1, f"Function '{signature}' not found in source — renamed or removed?"
    brace_open = src.find("{", start)
    assert brace_open != -1, f"No opening brace found for '{signature}'"
    depth = 0
    i = brace_open
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1] + "\n"
        i += 1
    raise AssertionError(f"Unbalanced braces extracting '{signature}'")


def run_node_js(js_code: str, timeout: int = 10):
    """
    Запускает JS через node БЕЗОПАСНО — временный файл вместо `node -e`
    (инлайн-аргумент командной строки). `node -e` несколько раз упиралась
    в ARG_MAX по мере роста встраиваемых JSON-данных (THEORY_TOPICS.json,
    BITCOIN_FUNCTIONS.json) — временный файл не имеет этого ограничения
    независимо от размера кода, поэтому не требует повторного лечения при
    дальнейшем росте данных.
    """
    import subprocess
    import tempfile
    import os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as tmp:
        tmp.write(js_code)
        tmp_path = tmp.name
    try:
        return subprocess.run(["node", tmp_path], capture_output=True, text=True, timeout=timeout)
    finally:
        os.unlink(tmp_path)
