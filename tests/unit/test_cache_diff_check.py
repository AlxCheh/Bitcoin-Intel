"""
tests/unit/test_cache_diff_check.py
Регрессионный тест для scripts/cache_diff_check.py (IRP v1 Wave 1 / M05
follow-up: предотвращение бесконечного цикла sync-PR из-за волатильных
timestamp-полей в synthesis_cache.json).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.cache_diff_check import has_meaningful_diff, normalize


def test_identical_dicts_no_diff():
    a = {"cluster": {"tension": "X vs Y"}}
    assert has_meaningful_diff(a, dict(a)) is False


def test_only_generated_at_differs_no_meaningful_diff():
    old = {"cluster": {"tension": "X vs Y", "generated_at": "2026-07-01T10:00:00+00:00"}}
    new = {"cluster": {"tension": "X vs Y", "generated_at": "2026-07-01T11:00:00+00:00"}}
    assert has_meaningful_diff(old, new) is False


def test_only_synthesis_id_differs_no_meaningful_diff():
    old = {"cluster": {"synthesis_id": "synthesis_x_20260701_100000"}}
    new = {"cluster": {"synthesis_id": "synthesis_x_20260701_110000"}}
    assert has_meaningful_diff(old, new) is False


def test_nested_detected_at_differs_no_meaningful_diff():
    old = {"cluster": {"phase_transition": {"detected": True, "detected_at": "2026-07-01T10:00:00+00:00"}}}
    new = {"cluster": {"phase_transition": {"detected": True, "detected_at": "2026-07-01T12:00:00+00:00"}}}
    assert has_meaningful_diff(old, new) is False


def test_all_volatile_fields_differ_simultaneously_no_meaningful_diff():
    old = {
        "cluster": {
            "generated_at": "t1",
            "synthesis_id": "id1",
            "phase_transition": {"detected_at": "t1a"},
        }
    }
    new = {
        "cluster": {
            "generated_at": "t2",
            "synthesis_id": "id2",
            "phase_transition": {"detected_at": "t2a"},
        }
    }
    assert has_meaningful_diff(old, new) is False


def test_tension_change_is_meaningful():
    old = {"cluster": {"tension": "A vs B"}}
    new = {"cluster": {"tension": "A vs C"}}
    assert has_meaningful_diff(old, new) is True


def test_new_cluster_is_meaningful():
    old = {"cluster_a": {"tension": "X"}}
    new = {"cluster_a": {"tension": "X"}, "cluster_b": {"tension": "Y"}}
    assert has_meaningful_diff(old, new) is True


def test_removed_cluster_is_meaningful():
    old = {"cluster_a": {"tension": "X"}, "cluster_b": {"tension": "Y"}}
    new = {"cluster_a": {"tension": "X"}}
    assert has_meaningful_diff(old, new) is True


def test_empty_old_treated_as_full_diff_if_new_nonempty():
    assert has_meaningful_diff({}, {"cluster": {"tension": "X"}}) is True


def test_both_empty_no_diff():
    assert has_meaningful_diff({}, {}) is False


def test_normalize_strips_all_volatile_keys_recursively():
    data = {
        "a": {
            "generated_at": "t1",
            "synthesis_id": "id1",
            "phase_transition": {"detected_at": "t2", "detected": True},
            "tension": "keep me",
        }
    }
    normalized = normalize(data)
    assert "generated_at" not in normalized["a"]
    assert "synthesis_id" not in normalized["a"]
    assert "detected_at" not in normalized["a"]["phase_transition"]
    assert normalized["a"]["tension"] == "keep me"
    assert normalized["a"]["phase_transition"]["detected"] is True


def test_normalize_does_not_mutate_input():
    data = {"a": {"generated_at": "t1", "tension": "X"}}
    normalize(data)
    assert "generated_at" in data["a"]  # original untouched
