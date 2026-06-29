"""
tests/unit/test_contradiction.py
Тесты Contradiction Detector: semantic_inverse_score.
"""
import os
import sys
import json
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _import_detector():
    """Импортирует функции из contradiction_detector."""
    from scripts.contradiction_detector import (
        semantic_inverse_score,
        suggest_contradictions,
    )
    return semantic_inverse_score, suggest_contradictions


def make_signal(sid: str, macro_impl: str, direction: str = "pos") -> dict:
    return {
        "id": sid,
        "dir": direction,
        "macro_implication": macro_impl,
        "links": {"confirms": [], "contradicts": [], "context_chain": []},
    }


# ─── semantic_inverse_score ──────────────────────────────────────────────────

def test_obvious_contradiction_inflow_outflow():
    """ETF-приток vs ETF-отток — score >= 0.5."""
    score_fn, _ = _import_detector()
    a = "ETF-приток как структурный спрос создаёт давление покупки на рынке BTC"
    b = "ETF-отток сигнализирует о выходе институционального капитала из BTC-позиций"
    score = score_fn(a, b)
    assert score >= 0.5, f"Expected contradiction score >= 0.5, got {score}"


def test_same_direction_no_contradiction():
    """Два позитивных ETF сигнала — score < 0.5."""
    score_fn, _ = _import_detector()
    a = "ETF-приток как структурный спрос создаёт давление покупки"
    b = "Институциональный приток через ETF укрепляет позицию BTC как резервного актива"
    score = score_fn(a, b)
    assert score < 0.5, f"Expected no contradiction (score < 0.5), got {score}"


def test_empty_strings_return_zero():
    """Пустые строки → 0.0, не исключение."""
    score_fn, _ = _import_detector()
    assert score_fn("", "что угодно") == 0.0
    assert score_fn("что угодно", "") == 0.0
    assert score_fn("", "") == 0.0


def test_deterministic():
    """Одинаковые входы → одинаковый результат."""
    score_fn, _ = _import_detector()
    a = "BTC-накопление корпорациями как защита от инфляции"
    b = "Продажа BTC-резервов корпорациями под давлением долговой нагрузки"
    results = {score_fn(a, b) for _ in range(5)}
    assert len(results) == 1, f"Non-deterministic: {results}"


def test_score_in_range():
    """Score всегда в [0.0, 1.0]."""
    score_fn, _ = _import_detector()
    pairs = [
        ("рост накопления BTC институционалами", "падение и ликвидация BTC-позиций"),
        ("ETF приток", "ETF отток"),
        ("укрепление", "ослабление"),
        ("одно и то же", "одно и то же"),
    ]
    for a, b in pairs:
        score = score_fn(a, b)
        assert 0.0 <= score <= 1.0, f"Score out of range for ({a!r}, {b!r}): {score}"


def test_symmetry():
    """score(a, b) ≈ score(b, a) — симметричность."""
    score_fn, _ = _import_detector()
    a = "ETF-приток создаёт структурный спрос"
    b = "ETF-отток давит на цену BTC через ликвидацию"
    diff = abs(score_fn(a, b) - score_fn(b, a))
    assert diff < 0.15, f"Asymmetric score: {score_fn(a,b)} vs {score_fn(b,a)}"


# ─── suggest_contradictions (интеграция) ─────────────────────────────────────

def test_suggest_contradictions_returns_list():
    """suggest_contradictions возвращает список без исключений."""
    _, suggest_fn = _import_detector()
    signals = [
        make_signal("A", "ETF-приток создаёт структурный спрос на BTC", "pos"),
        make_signal("B", "ETF-отток давит на цену BTC через ликвидацию позиций", "neg"),
        make_signal("C", "Lightning Network достигла рекорда транзакций", "pos"),
    ]
    result = suggest_fn(signals)
    assert isinstance(result, list)


def test_suggest_no_self_contradictions():
    """Сигнал не предлагается как противоречие самому себе."""
    _, suggest_fn = _import_detector()
    signals = [
        make_signal("A", "ETF-приток создаёт структурный спрос", "pos"),
        make_signal("B", "ETF-отток давит на цену BTC", "neg"),
    ]
    result = suggest_fn(signals)
    for item in result:
        assert item.get("from_id") != item.get("to_id"), "Self-contradiction found"
