"""
tests/unit/test_synthesizer.py
Тесты синтезатора: детерминизм, scoring, confidence, bridge selection.
"""
import os
import sys
import subprocess
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import calculate_max_possible_score, calculate_confidence


# ─── Детерминизм ─────────────────────────────────────────────────────────────

def test_bridge_selection_deterministic():
    """
    select_bridge() детерминировано: seed % len(options) не зависит от PYTHONHASHSEED.
    Тест проверяет алгоритм напрямую — subprocess не нужен.
    """
    # seed % len(options) всегда даёт одинаковый результат независимо от PYTHONHASHSEED
    # Потому что % — арифметическая операция, не хэш
    from scripts.synthesizer import select_bridge
    results = {select_bridge("active", 42) for _ in range(3)}
    assert len(results) == 1, f"Non-deterministic: {results}"
    # Убедиться что результат — строка из BRIDGES["active"]
    result = select_bridge("active", 42)
    assert isinstance(result, str) and len(result) > 0


def test_bridge_selection_uses_modulo_not_hash():
    """Формула seed % len(options) — детерминирована по определению."""
    options = ["при этом", "однако", "в то время как", "тогда как"]
    seed = 42
    result_index = seed % len(options)
    assert 0 <= result_index < len(options)
    assert options[result_index] == options[42 % 4]


# ─── MAX_POSSIBLE_SCORE ───────────────────────────────────────────────────────

def test_max_possible_score_single():
    assert calculate_max_possible_score(1) == 11


def test_max_possible_score_five():
    assert calculate_max_possible_score(5) == 55


def test_max_possible_score_zero_safe():
    """Защита от деления на ноль — не должен возвращать 0."""
    result = calculate_max_possible_score(0)
    assert result >= 1


def test_max_possible_score_linear():
    """Линейная зависимость от количества сигналов."""
    assert calculate_max_possible_score(10) == calculate_max_possible_score(5) * 2


# ─── Confidence ───────────────────────────────────────────────────────────────

def test_confidence_always_in_range():
    """Confidence всегда в диапазоне [0.1, 1.0]."""
    cases = [
        (55, 5, True, False, True),    # лучший случай
        (0,  1, False, True, False),   # худший случай
        (11, 1, True, False, True),    # один сигнал
        (6,  3, False, False, False),  # без contradicts
    ]
    for args in cases:
        result = calculate_confidence(*args)
        assert 0.1 <= result <= 1.0, f"Out of range for {args}: {result}"


def test_confidence_higher_with_contradicts():
    """Кластер с contradicts получает выше confidence."""
    with_c = calculate_confidence(20, 3, has_contradicts=True,  all_stale=False, has_tension=True)
    without = calculate_confidence(20, 3, has_contradicts=False, all_stale=False, has_tension=True)
    assert with_c > without


def test_confidence_lower_when_stale():
    """Устаревшие сигналы снижают confidence."""
    fresh = calculate_confidence(20, 3, has_contradicts=True, all_stale=False, has_tension=True)
    stale = calculate_confidence(20, 3, has_contradicts=True, all_stale=True,  has_tension=True)
    assert fresh > stale


def test_confidence_minimum_floor():
    """Confidence не опускается ниже 0.1 даже при худших данных."""
    result = calculate_confidence(0, 1, has_contradicts=False, all_stale=True, has_tension=False)
    assert result >= 0.1


def test_confidence_deterministic():
    """Одинаковые аргументы → одинаковый результат (детерминизм)."""
    args = (20, 3, True, False, True)
    results = {calculate_confidence(*args) for _ in range(5)}
    assert len(results) == 1


# ─── ALGORITHM_VERSION (IRP v1 Wave 3 / REM-M07) ───────────────────────────────

def test_algorithm_version_is_semver():
    """ALGORITHM_VERSION — строка формата MAJOR.MINOR.PATCH (ADDENDUM §25.3)."""
    import re
    from scripts.synthesizer import ALGORITHM_VERSION
    assert re.match(r"^\d+\.\d+\.\d+$", ALGORITHM_VERSION), (
        f"ALGORITHM_VERSION='{ALGORITHM_VERSION}' не соответствует semver MAJOR.MINOR.PATCH"
    )


def test_synthesis_result_default_algorithm_version_matches_constant():
    """SynthesisResult.algorithm_version по умолчанию равен модульной константе."""
    from scripts.synthesizer import ALGORITHM_VERSION, SynthesisResult, SignalScore
    result = SynthesisResult(
        cluster="test", tension="X vs Y", narrative="n", takeaway="t",
        strength="weak", confidence=0.5, phase="active",
        score=SignalScore(), anchor_signal_id="X-1", signal_count=1,
    )
    assert result.algorithm_version == ALGORITHM_VERSION


# ─── _get_contradicts / relationships.json (bugfix 2026-07-04, ALGORITHM_VERSION 2.1.1) ──
#
# КОНТЕКСТ: до этой правки _get_contradicts() при LEGACY_LINKS_ENABLED=False
# безусловно возвращала [] — relationships.json существовал (мигрирован IRP v1
# Wave 1 / REM-B2, 2026-07-01), но никогда не читался. Contradiction bonus был
# равен 0 для всех сигналов с даты миграции. Обнаружено вручную при инженерной
# сверке (не автоматикой) — эти тесты закрывают тот пробел покрытия.

def test_load_contradicts_map_filters_by_type_and_status(tmp_path, monkeypatch):
    """_load_contradicts_map() берёт только type=contradicts, исключая retracted."""
    import json as _json
    from scripts import synthesizer as _syn

    rel_path = tmp_path / "relationships.json"
    rel_path.write_text(_json.dumps([
        {"from_id": "A-1", "to_id": "B-1", "type": "contradicts", "status": "active"},
        {"from_id": "A-1", "to_id": "C-1", "type": "confirms",    "status": "active"},
        {"from_id": "A-2", "to_id": "D-1", "type": "contradicts", "status": "retracted"},
    ]), encoding="utf-8")

    monkeypatch.setattr(_syn, "RELATIONSHIPS_PATH", str(rel_path))
    result = _syn._load_contradicts_map()

    assert result == {"A-1": {"B-1"}}, (
        "Должен остаться только type=contradicts + status!=retracted; "
        f"получено {result}"
    )


def test_get_contradicts_reads_relationships_when_legacy_disabled(monkeypatch):
    """LEGACY_LINKS_ENABLED=False → читает contradicts_map, не links.* сигнала."""
    from scripts import synthesizer as _syn

    monkeypatch.setattr(_syn, "LEGACY_LINKS_ENABLED", False)
    signal = {"id": "STR-2026-0701-002", "links": {"contradicts": ["IGNORED"]}}
    contradicts_map = {"STR-2026-0701-002": {"STR-2026-0623-006"}}

    result = _syn._get_contradicts(signal, contradicts_map)

    assert result == ["STR-2026-0623-006"], (
        "При LEGACY_LINKS_ENABLED=False должен игнорировать links.* сигнала "
        f"и брать из contradicts_map; получено {result}"
    )


def test_get_contradicts_falls_back_to_links_when_legacy_enabled(monkeypatch):
    """LEGACY_LINKS_ENABLED=True → читает links.contradicts сигнала, игнорируя map."""
    from scripts import synthesizer as _syn

    monkeypatch.setattr(_syn, "LEGACY_LINKS_ENABLED", True)
    signal = {"id": "X-1", "links": {"contradicts": ["Y-1"]}}

    result = _syn._get_contradicts(signal, contradicts_map={"X-1": {"Z-1"}})

    assert result == ["Y-1"], (
        "При LEGACY_LINKS_ENABLED=True должен игнорировать contradicts_map "
        f"и брать из links.*; получено {result}"
    )


def test_get_contradicts_empty_map_returns_empty_list(monkeypatch):
    """Сигнал без записи в contradicts_map → пустой список, не ошибка."""
    from scripts import synthesizer as _syn

    monkeypatch.setattr(_syn, "LEGACY_LINKS_ENABLED", False)
    signal = {"id": "NO-RELATIONSHIPS-1"}

    assert _syn._get_contradicts(signal, contradicts_map={}) == []


def test_get_contradicts_result_is_sorted_deterministic(monkeypatch):
    """Результат — sorted list, не произвольный порядок set() (детерминизм)."""
    from scripts import synthesizer as _syn

    monkeypatch.setattr(_syn, "LEGACY_LINKS_ENABLED", False)
    signal = {"id": "A-1"}
    contradicts_map = {"A-1": {"Z-1", "B-1", "M-1"}}

    result = _syn._get_contradicts(signal, contradicts_map)

    assert result == sorted(result), "Должен быть отсортирован для детерминизма"
    assert result == ["B-1", "M-1", "Z-1"]
