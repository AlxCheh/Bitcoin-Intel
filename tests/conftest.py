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
