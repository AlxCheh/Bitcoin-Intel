"""
tests/unit/test_update_synthesis_history.py
Bitcoin Intel — тесты scripts/update_synthesis_history.py (ADR-011, заметка
2026-07-31: фикс calibration-счётчика, который был заморожен на synthesis_store/
с 2026-06-29, пока реальный пайплайн синтеза давно писал в
data/synthesis_cache.json).
"""
import json

from scripts.update_synthesis_history import update_history, DEFAULT_HISTORY


def test_first_run_no_existing_history_file_starts_from_zero(tmp_path):
    history_path = tmp_path / "synthesis_history_count.json"
    old = {}
    new = {"a": {"tension": "X"}}

    result = update_history(old, new, str(history_path))

    assert result["cluster_periods"] == 1
    assert json.loads(history_path.read_text())["cluster_periods"] == 1


def test_increments_existing_counter_by_number_of_changed_clusters(tmp_path):
    history_path = tmp_path / "synthesis_history_count.json"
    history_path.write_text(json.dumps({"cluster_periods": 191}))

    old = {"a": {"tension": "X"}, "b": {"tension": "Y"}}
    new = {"a": {"tension": "X2"}, "b": {"tension": "Y2"}}

    result = update_history(old, new, str(history_path))

    assert result["cluster_periods"] == 193
    assert result["last_run_changed_clusters"] == ["a", "b"]


def test_no_changed_clusters_does_not_rewrite_file(tmp_path):
    """
    Идемпотентность (см. докстринг модуля): прогон без единого содержательно
    изменившегося кластера не должен трогать файл на диске — иначе каждый
    прогон CI создавал бы шум в git diff даже без реального ресинтеза.
    """
    history_path = tmp_path / "synthesis_history_count.json"
    history_path.write_text(json.dumps({"cluster_periods": 50}))
    mtime_before = history_path.stat().st_mtime_ns

    old = {"a": {"tension": "X", "generated_at": "t1"}}
    new = {"a": {"tension": "X", "generated_at": "t2"}}  # только volatile

    result = update_history(old, new, str(history_path))

    assert result["cluster_periods"] == 50
    assert history_path.stat().st_mtime_ns == mtime_before


def test_cross_cluster_entities_only_change_does_not_increment(tmp_path):
    history_path = tmp_path / "synthesis_history_count.json"
    history_path.write_text(json.dumps({"cluster_periods": 191}))

    old = {"a": {"tension": "X"}, "_cross_cluster_entities": {"strategy": ["a"]}}
    new = {"a": {"tension": "X"}, "_cross_cluster_entities": {"strategy": ["a", "b"]}}

    result = update_history(old, new, str(history_path))

    assert result["cluster_periods"] == 191


def test_missing_history_file_degrades_to_default_not_crash(tmp_path):
    history_path = tmp_path / "does_not_exist.json"

    result = update_history({}, {"a": {"tension": "X"}}, str(history_path))

    assert result["cluster_periods"] == 1
    assert history_path.exists()


def test_corrupted_history_file_degrades_to_default(tmp_path):
    history_path = tmp_path / "synthesis_history_count.json"
    history_path.write_text("{not valid json")

    result = update_history({}, {"a": {"tension": "X"}}, str(history_path))

    assert result["cluster_periods"] == 1


def test_default_history_constant_starts_at_zero():
    assert DEFAULT_HISTORY["cluster_periods"] == 0
