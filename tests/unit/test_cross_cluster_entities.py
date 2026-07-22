"""
tests/unit/test_cross_cluster_entities.py
Bitcoin Intel — тесты _find_cross_cluster_entities() (ADR-017 / находка 3
плана entity-aware усилений синтезатора).

КОНТЕКСТ
--------
Синтезатор обрабатывает каждый кластер независимо (§17, docs/NIES.md) —
если одна и та же сущность становится центральной сразу для двух разных
нарративов, это нигде не фиксируется. Функция — только измерение,
вызывается снаружи synthesize_cluster(), не меняет выбор tension/anchor.

Порог АСИММЕТРИЧНЫЙ (Вариант 2, ADR-017 amendment 2026-07-22): сущность
должна встречаться в >=2 разных кластерах (>=CROSS_CLUSTER_SECONDARY_MIN_
SIGNALS=1 сигнал каждый), и хотя бы в одном — весомо (>=CROSS_CLUSTER_
PRIMARY_MIN_SIGNALS=2). Исходный симметричный порог (>=2 в каждом) не
проходил сам мотивирующий случай ('strategy': 16 против 1) — см. ADR-017
amendment для полной истории обнаружения.
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.unit.test_synthesizer import _minimal_signal
from scripts.synthesizer import _find_cross_cluster_entities

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _signals_for(entity_cluster_counts: dict, entity_id: str) -> list[dict]:
    """Строит минимальные сигналы: {cluster: count} -> N сигналов в этом кластере."""
    signals = []
    i = 0
    for cluster, count in entity_cluster_counts.items():
        for _ in range(count):
            i += 1
            s = _minimal_signal(f"SIG-{entity_id}-{cluster}-{i}", "2026-07-01", "complication")
            s["cluster"] = cluster
            signals.append(s)
    return signals


class TestSyntheticThresholds:

    def test_entity_in_single_cluster_not_reported(self):
        """Сущность только в одном кластере — физически не кросс-кластерна."""
        signals = _signals_for({"cluster_a": 5}, "solo")
        emap = {s["id"]: "entity_solo" for s in signals}
        result = _find_cross_cluster_entities(signals, emap)
        assert "entity_solo" not in result

    def test_two_clusters_one_signal_each_not_reported(self):
        """1 и 1 — оба случайных упоминания, ни один не весомый (primary не пройден)."""
        signals = _signals_for({"cluster_a": 1, "cluster_b": 1}, "weak")
        emap = {s["id"]: "entity_weak" for s in signals}
        result = _find_cross_cluster_entities(signals, emap)
        assert "entity_weak" not in result

    def test_asymmetric_case_matches_real_strategy_pattern(self):
        """16 в одном, 1 в другом — реальный кейс 'strategy', должен пройти."""
        signals = _signals_for({"cluster_a": 16, "cluster_b": 1}, "strategy_like")
        emap = {s["id"]: "entity_strategy_like" for s in signals}
        result = _find_cross_cluster_entities(signals, emap)
        assert "entity_strategy_like" in result
        assert result["entity_strategy_like"] == {"cluster_a", "cluster_b"}

    def test_symmetric_strong_case_reported(self):
        """2 и 2 — оба весомых, тривиально должен пройти."""
        signals = _signals_for({"cluster_a": 2, "cluster_b": 2}, "both_strong")
        emap = {s["id"]: "entity_both_strong" for s in signals}
        result = _find_cross_cluster_entities(signals, emap)
        assert "entity_both_strong" in result

    def test_three_clusters_all_present_clusters_listed(self):
        """5/1/1 — весомый в одном, слабый в двух остальных: все три учтены."""
        signals = _signals_for({"cluster_a": 5, "cluster_b": 1, "cluster_c": 1}, "three")
        emap = {s["id"]: "entity_three" for s in signals}
        result = _find_cross_cluster_entities(signals, emap)
        assert result["entity_three"] == {"cluster_a", "cluster_b", "cluster_c"}

    def test_signal_without_entity_mapping_ignored(self):
        """Сигналы без entity_id (агрегатные) не создают ложных кросс-кластерных находок."""
        signals = _signals_for({"cluster_a": 5, "cluster_b": 5}, "unmapped")
        result = _find_cross_cluster_entities(signals, {})  # пустая карта — фолбэк
        assert result == {}

    def test_empty_signals_returns_empty_dict(self):
        assert _find_cross_cluster_entities([], {}) == {}


class TestRealDataConfirmsStrategyCase:
    """Подтверждает на реальных signals.json/ENTITIES.json мотивирующий кейс."""

    def test_strategy_entity_found_cross_cluster_in_production_data(self):
        signals_path = os.path.join(REPO_ROOT, "signals.json")
        entities_path = os.path.join(REPO_ROOT, "ENTITIES.json")
        if not (os.path.exists(signals_path) and os.path.exists(entities_path)):
            import pytest
            pytest.skip("Реальные данные недоступны в этом окружении")

        raw = json.loads(open(signals_path, encoding="utf-8").read())
        all_signals = raw.get("signals", raw) if isinstance(raw, dict) else raw

        eraw = json.loads(open(entities_path, encoding="utf-8").read())
        entities = eraw.get("entities", eraw) if isinstance(eraw, dict) else eraw
        signal_entity_map = {}
        for e in entities:
            for sid in e.get("signal_refs", []):
                signal_entity_map[sid] = e["id"]

        result = _find_cross_cluster_entities(all_signals, signal_entity_map)

        assert "strategy" in result, (
            "Мотивирующий кейс ADR-017 не найден на реальных данных — "
            "либо signals.json изменился настолько, что кейс исчез, либо "
            "регрессия в самой функции/порогах"
        )
        assert "strategy_model_stress" in result["strategy"]
        assert "bitcoin_governance_debate" in result["strategy"]
