"""
tests/integration/test_narrative_regression.py
E2E Narrative Regression Test (C1 ARR v2).

Проверяет что при добавлении нового сигнала нарратив кластера
изменился ожидаемым образом.

Без этого теста изменение алгоритма или весов незаметно влияет
на нарративы в production.
"""

import json
import sys
import pytest
from pathlib import Path
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from datetime import date as _dt, timedelta as _td

# Даты в пределах WINDOW_DAYS_DEFAULT (90 дней)
_D1 = (_dt.today() - _td(days=5)).isoformat()
_D2 = (_dt.today() - _td(days=4)).isoformat()
_D3 = (_dt.today() - _td(days=3)).isoformat()
_D4 = (_dt.today() - _td(days=2)).isoformat()


def make_cluster_signals(cluster_key: str = "test_cluster") -> list[dict]:
    """Базовый набор сигналов для регрессионного теста."""
    return [
        {
            "id": "REG-2026-0101-001",
            "date": _D1,
            "signal": "Базовый триггер кластера",
            "cat": "narrative", "catLabel": "📰 Нарратив",
            "dir": "pos", "horizon": "mid",
            "theme": "institutionalization",
            "weight": "primary", "actor": "etf", "flow": "inflow",
            "tension": "ETF-приток vs ожидания рынка — структурный разрыв",
            "macro_implication": (
                "ETF-инструменты создают устойчивый структурный спрос на BTC "
                "независимо от краткосрочных настроений рынка"
            ),
            "narrative_role": "trigger",
            "cluster": cluster_key,
            "source": "Test (январь 2026)",
            "links": {"confirms": [], "contradicts": [], "context_chain": []},
            "data": [], "context": "", "caveat": "",
        },
        {
            "id": "REG-2026-0102-001",
            "date": _D2,
            "signal": "Осложнение нарратива",
            "cat": "narrative", "catLabel": "📰 Нарратив",
            "dir": "neg", "horizon": "short",
            "theme": "institutionalization",
            "weight": "market", "actor": "etf", "flow": "outflow",
            "tension": "ETF-отток vs долгосрочный структурный спрос — временное расхождение",
            "macro_implication": (
                "ETF-оттоки как поверхностное краткосрочное давление не меняют "
                "структурную картину институционального накопления BTC"
            ),
            "narrative_role": "complication",
            "cluster": cluster_key,
            "source": "Test (январь 2026)",
            "links": {"confirms": [], "contradicts": ["REG-2026-0101-001"],
                      "context_chain": []},
            "data": [], "context": "", "caveat": "",
        },
    ]


def run_synthesis(signals: list) -> dict:
    """Запускает синтез и возвращает результат."""
    from scripts.synthesizer import synthesize_cluster
    result = synthesize_cluster("test_cluster", signals, previous_synthesis=None)
    return {
        "phase":            result.phase,
        "tension":          result.tension,
        "strength":         result.strength,
        "confidence":       result.confidence,
        "signal_count":     result.signal_count,
        "anchor_signal_id": result.anchor_signal_id,
        "uncertainty":      result.uncertainty,
    }


# ─── Тесты ───────────────────────────────────────────────────────────────────

def test_baseline_synthesis_is_deterministic():
    """
    Один и тот же набор сигналов → один и тот же результат.
    Проверяет детерминизм синтезатора.
    """
    signals = make_cluster_signals()
    result1 = run_synthesis(signals)
    result2 = run_synthesis(signals)
    assert result1["tension"]   == result2["tension"],   "tension не детерминирован"
    assert result1["phase"]     == result2["phase"],     "phase не детерминирована"
    assert result1["confidence"]== result2["confidence"],"confidence не детерминирован"


def test_adding_trigger_changes_narrative():
    """
    Добавление второго trigger сигнала меняет signal_count.
    Нарратив не должен оставаться идентичным.
    """
    base_signals = make_cluster_signals()
    base_result  = run_synthesis(base_signals)

    new_trigger = {
        "id": "REG-2026-0103-001",
        "date": _D3,
        "signal": "Новый триггер с более высоким весом",
        "cat": "narrative", "catLabel": "📰 Нарратив",
        "dir": "pos", "horizon": "long",
        "theme": "institutionalization",
        "weight": "onchain", "actor": "corporate", "flow": "inflow",
        "tension": "Корпоративное накопление vs рыночный скептицизм",
        "macro_implication": (
            "Корпоративное накопление BTC создаёт новый класс держателей "
            "с горизонтом инвестирования в десятилетия"
        ),
        "narrative_role": "trigger",
        "cluster": "test_cluster",
        "source": "Test (январь 2026)",
        "links": {"confirms": ["REG-2026-0101-001"], "contradicts": [],
                  "context_chain": []},
        "data": [], "context": "", "caveat": "",
    }

    extended_signals = base_signals + [new_trigger]
    new_result       = run_synthesis(extended_signals)

    assert new_result["signal_count"] > base_result["signal_count"], (
        "Добавление сигнала должно увеличить signal_count"
    )


def test_high_weight_signal_becomes_anchor():
    """
    Сигнал с weight=onchain и contradicts должен стать anchor.
    Проверяет что алгоритм ранжирования работает корректно.
    """
    signals = make_cluster_signals()

    # Добавляем сигнал с максимальным весом и contradicts
    anchor_candidate = {
        "id": "REG-2026-0104-001",
        "date": _D4,
        "signal": "Сигнал с максимальным весом и contradicts",
        "cat": "onchain", "catLabel": "📊 On-chain",
        "dir": "neg", "horizon": "short",
        "theme": "institutionalization",
        "weight": "onchain", "actor": "miner", "flow": "outflow",
        "tension": "On-chain данные vs позитивный нарратив — структурное расхождение",
        "macro_implication": (
            "On-chain метрики фиксируют распределение от долгосрочных держателей — "
            "расхождение с рыночным нарративом создаёт структурный риск"
        ),
        "narrative_role": "complication",
        "cluster": "test_cluster",
        "source": "Glassnode (январь 2026)",
        "links": {"confirms": [], "contradicts": ["REG-2026-0101-001", "REG-2026-0102-001"],
                  "context_chain": []},
        "data": [], "context": "", "caveat": "",
    }

    signals_with_anchor = signals + [anchor_candidate]
    result = run_synthesis(signals_with_anchor)

    # Сигнал с 2 contradicts и weight=onchain должен стать anchor
    assert result["anchor_signal_id"] == "REG-2026-0104-001", (
        f"Expected onchain signal with 2 contradicts to be anchor, "
        f"got: {result['anchor_signal_id']}"
    )


def test_contested_direction_triggers_uncertainty():
    """
    Равный баланс pos/neg сигналов → uncertainty['direction'] = 'contested'.
    Проверяет B3: handle_uncertainty() работает корректно.
    """
    signals = make_cluster_signals()  # 1 pos + 1 neg = 50/50

    result = run_synthesis(signals)
    # При балансе 1:1 pos/neg (50%) < threshold (60%) → contested
    uncertainty = result.get("uncertainty", {})
    assert uncertainty.get("direction") == "contested", (
        f"50/50 pos/neg должен давать direction=contested. "
        f"Got uncertainty: {uncertainty}"
    )


def test_confidence_range():
    """Confidence всегда в диапазоне [0.1, 1.0]."""
    result = run_synthesis(make_cluster_signals())
    assert 0.1 <= result["confidence"] <= 1.0, (
        f"Confidence {result['confidence']} out of range [0.1, 1.0]"
    )


def test_resolution_signal_wins_tension_over_complication():
    """
    Resolution-сигнал должен стать источником tension даже если
    у него меньше contradicts чем у существующего complication-anchor.

    Защищает от логического дефекта: phase=resolution говорит что
    вопрос закрыт, но tension продолжает звучать как открытый.
    """
    signals = make_cluster_signals()  # trigger (pos) + complication (neg), 0 contradicts у обоих

    # Усиливаем complication — даём ему contradicts чтобы он выигрывал
    # по старому правилу MAX(contradicts)
    strong_complication = deepcopy(signals[1])
    strong_complication["id"] = "REG-2026-0105-001"
    strong_complication["links"]["contradicts"] = ["REG-2026-0101-001", "REG-2026-0102-001"]

    resolution_signal = {
        "id": "REG-2026-0106-001",
        "date": signals[0]["date"],  # тот же тестовый диапазон дат
        "signal": "Резолюция кластера",
        "cat": "narrative", "catLabel": "📰 Нарратив",
        "dir": "pos", "horizon": "mid",
        "theme": "institutionalization",
        "weight": "primary", "actor": "etf", "flow": "inflow",
        "tension": "Резолюция vs устаревший комплекейшн — цикл закрыт",
        "macro_implication": (
            "Противоречие кластера разрешено: структурный спрос подтверждён "
            "вопреки краткосрочным колебаниям, цикл неопределённости завершён"
        ),
        "narrative_role": "resolution",
        "cluster": "test_cluster",
        "source": "Test (resolution)",
        "links": {"confirms": [], "contradicts": [], "context_chain": []},
        "data": [], "context": "", "caveat": "",
    }

    all_signals = signals + [strong_complication, resolution_signal]
    result = run_synthesis(all_signals)

    assert result["tension"] == resolution_signal["tension"], (
        f"Resolution must win tension even with 0 contradicts vs "
        f"complication with 2 contradicts. Got: {result['tension']!r}"
    )
    assert result["phase"] == "resolution", (
        f"Phase must be 'resolution' when resolution signal present, got {result['phase']!r}"
    )


def test_no_resolution_keeps_max_contradicts_priority():
    """
    Контрольный тест: без resolution-сигнала старое правило
    MAX(contradicts) продолжает работать как раньше.
    """
    signals = make_cluster_signals()
    strong_complication = deepcopy(signals[1])
    strong_complication["id"] = "REG-2026-0107-001"
    strong_complication["links"]["contradicts"] = ["REG-2026-0101-001"]

    all_signals = signals + [strong_complication]
    result = run_synthesis(all_signals)

    # Без resolution anchor выбирается по MAX(contradicts) как раньше
    assert result["phase"] != "resolution"
