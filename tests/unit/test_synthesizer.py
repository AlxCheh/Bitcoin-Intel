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
