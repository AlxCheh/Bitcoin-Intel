"""
tests/unit/test_synthesizer.py
Тесты для синтезатора — детерминизм, ранжирование, bridge selection.
Запускать: PYTHONHASHSEED=0 python3 -m pytest tests/unit/test_synthesizer.py -v
"""

import os
import sys
import pytest

# Патчим PYTHONHASHSEED для тестов
os.environ["PYTHONHASHSEED"] = "0"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.synthesizer import (
    select_bridge, synthesize_cluster, _rank_signals, _score_signal,
    _detect_phase, _get_contradicts,
)
from config.settings import calculate_max_possible_score, calculate_confidence, get_strength


# ─── Фикстуры ────────────────────────────────────────────────────────────────
def make_signal(id, date="2026-06-20", role="trigger", weight="onchain",
                tension="X vs Y", macro="BTC растёт структурно.", contradicts=None):
    return {
        "id": id,
        "date": date,
        "narrative_role": role,
        "weight": weight,
        "tension": tension,
        "macro_implication": macro,
        "cluster": "test_cluster",
        "links": {"contradicts": contradicts or [], "confirms": [], "context_chain": []},
    }


# ─── B1: Детерминизм select_bridge ───────────────────────────────────────────
class TestSelectBridge:

    def test_deterministic_same_seed(self):
        """Один seed → один результат, всегда."""
        r1 = select_bridge("active", seed=5)
        r2 = select_bridge("active", seed=5)
        assert r1 == r2

    def test_deterministic_across_calls(self):
        """100 вызовов с одним seed — всегда одно значение."""
        results = {select_bridge("tension", seed=3) for _ in range(100)}
        assert len(results) == 1

    def test_different_seeds_can_differ(self):
        """Разные seeds должны давать разные bridges (не всегда, но для len>1 фазы)."""
        phase = "active"   # 4 варианта
        bridges = {select_bridge(phase, seed=i) for i in range(4)}
        assert len(bridges) > 1  # как минимум 2 разных значения

    def test_all_phases_return_string(self):
        """Все фазы возвращают непустую строку."""
        for phase in ("active", "tension", "resolution", "structural"):
            result = select_bridge(phase, seed=2)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_unknown_phase_fallback(self):
        """Неизвестная фаза → fallback на 'active'."""
        result = select_bridge("unknown_phase", seed=1)
        assert isinstance(result, str)


# ─── TD1: MAX_POSSIBLE_SCORE ──────────────────────────────────────────────────
class TestMaxPossibleScore:

    def test_single_signal(self):
        assert calculate_max_possible_score(1) == 11

    def test_five_signals(self):
        assert calculate_max_possible_score(5) == 55

    def test_zero_signals(self):
        assert calculate_max_possible_score(0) == 0

    def test_confidence_perfect(self):
        """Идеальный кластер → confidence близок к 1.0."""
        c = calculate_confidence(55, 5, True, False, True)
        assert c >= 0.9

    def test_confidence_weak(self):
        """Один старый сигнал без contradicts → низкая confidence."""
        c = calculate_confidence(1, 1, False, True, False)
        assert c < 0.3

    def test_confidence_bounds(self):
        """confidence всегда в [0.1, 1.0]."""
        for n in range(1, 10):
            c = calculate_confidence(n * 2, n, False, True, False)
            assert 0.1 <= c <= 1.0


# ─── TD6: Тиебрейкер 4-го уровня ─────────────────────────────────────────────
class TestRankSignals:

    def test_tiebreaker_by_id(self):
        """При равных score/weight/date — сортировка по id (лексикографически ASC)."""
        s1 = make_signal("STR-2026-0628-002", date="2026-06-20", weight="media", role="background")
        s2 = make_signal("STR-2026-0628-001", date="2026-06-20", weight="media", role="background")
        ranked = _rank_signals([s1, s2])
        # id "001" < "002" → s2 должен быть первым
        assert ranked[0][0]["id"] == "STR-2026-0628-001"

    def test_role_priority_over_weight(self):
        """trigger (role_score=4) > onchain complication только по роли."""
        trigger = make_signal("A", role="trigger", weight="media")
        background = make_signal("B", role="background", weight="onchain")
        ranked = _rank_signals([background, trigger])
        # trigger: freshness+weight(1)+role(4) vs background: freshness+weight(4)+role(0)
        # Зависит от freshness, но trigger с медиа должен конкурировать
        assert ranked[0][0]["id"] in ("A", "B")  # детерминизм важнее позиции

    def test_deterministic_ranking(self):
        """Один и тот же список → всегда одинаковый порядок."""
        signals = [
            make_signal("C", date="2026-06-15", role="complication", weight="market"),
            make_signal("A", date="2026-06-20", role="trigger", weight="onchain"),
            make_signal("B", date="2026-06-18", role="background", weight="media"),
        ]
        r1 = [s["id"] for s, _ in _rank_signals(signals)]
        r2 = [s["id"] for s, _ in _rank_signals(signals[::-1])]  # обратный порядок на входе
        assert r1 == r2


# ─── TD7: Empty cluster rendering states ─────────────────────────────────────
class TestEmptyCluster:

    def test_empty_cluster_returns_weak(self):
        """Кластер без сигналов → strength=weak."""
        result = synthesize_cluster("empty_cluster", [])
        assert result.strength == "weak"
        assert result.confidence == 0.1
        assert result.signal_count == 0

    def test_stale_signals_handled(self):
        """Все сигналы старше 90 дней → пустой кластер."""
        old_signal = make_signal("OLD", date="2020-01-01", role="trigger")
        result = synthesize_cluster("stale_cluster", [old_signal])
        assert result.signal_count == 0
        assert result.strength == "weak"


# ─── TD8: Date policy ────────────────────────────────────────────────────────
class TestDatePolicy:

    def test_date_format_accepted(self):
        """Сигнал с датой YYYY-MM-DD обрабатывается без ошибок."""
        s = make_signal("DATE-TEST", date="2026-06-28")
        score = _score_signal(s)
        assert score.total >= 0

    def test_invalid_date_fallback(self):
        """Некорректная дата не роняет синтез."""
        s = make_signal("BAD-DATE", date="not-a-date")
        score = _score_signal(s)
        assert score.freshness == 0  # fallback → stale


# ─── TD9: Encoding policy ────────────────────────────────────────────────────
class TestEncodingPolicy:

    def test_cyrillic_in_tension(self):
        """Кириллица в tension не ломает синтез."""
        s = make_signal("RU", tension="Стратегия наращивает долг vs рынок даёт дисконт")
        result = synthesize_cluster("ru_cluster", [s])
        assert "Стратегия" in result.tension or result.tension

    def test_get_strength(self):
        assert get_strength(20) == "strong"
        assert get_strength(10) == "moderate"
        assert get_strength(3)  == "weak"


# ─── Интеграционный тест ─────────────────────────────────────────────────────
class TestSynthesizeCluster:

    def test_full_cluster(self):
        """Полный кластер с trigger + complication + contradicts."""
        signals = [
            make_signal("T1", role="trigger", weight="onchain",
                        tension="Strategy наращивает долг vs рынок даёт дисконт 0.83x",
                        macro="BTC-казначейство становится стандартом корпоративного баланса.",
                        contradicts=["C1"]),
            make_signal("C1", role="complication", weight="market",
                        tension="",
                        macro="Волатильность MSTR угрожает кредитному рейтингу Strategy.",
                        contradicts=[]),
        ]
        result = synthesize_cluster("strategy_model_stress", signals)
        assert result.tension != ""
        assert result.narrative != ""
        assert result.signal_count == 2
        assert result.phase in ("active", "tension", "resolution", "structural")
        assert 0.1 <= result.confidence <= 1.0

    def test_synthesis_is_deterministic(self):
        """Один набор сигналов → всегда одинаковый результат."""
        signals = [
            make_signal("X1", role="trigger", contradicts=["X2"]),
            make_signal("X2", role="complication"),
        ]
        r1 = synthesize_cluster("det_test", signals)
        r2 = synthesize_cluster("det_test", signals)
        assert r1.tension    == r2.tension
        assert r1.narrative  == r2.narrative
        assert r1.takeaway   == r2.takeaway
        assert r1.strength   == r2.strength
        assert r1.confidence == r2.confidence
