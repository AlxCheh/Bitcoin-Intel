"""
tests/unit/test_check_signals_size.py
IRP v1 Wave 4 / OP06 — юнит-тесты check_size().

check_size() принимает Path и порог явно, не читает глобальный SIGNALS_PATH
константу — тестируется через tmp_path без конфликта с autouse
isolated_environment (см. tests/conftest.py; тот же паттерн, что в
tests/unit/test_check_synthesis_freshness.py и tests/performance/).
"""
import json

from scripts.check_signals_size import check_size


def _write_signals(tmp_path, n_signals: int, filler: str = "x") -> "Path":  # noqa: F821
    path = tmp_path / "signals.json"
    signals = [
        {"id": f"STR-2026-0101-{i:03d}", "cluster": "test", "filler": filler * 100}
        for i in range(n_signals)
    ]
    path.write_text(
        json.dumps({"meta": {}, "signals": signals}, ensure_ascii=False),
        encoding="utf-8"
    )
    return path


def test_under_threshold_not_flagged(tmp_path):
    path = _write_signals(tmp_path, n_signals=5)
    result = check_size(path, threshold_mb=4.0)
    assert result["over_threshold"] is False
    assert result["signal_count"] == 5


def test_over_threshold_flagged(tmp_path):
    path = _write_signals(tmp_path, n_signals=100)
    # Порог заведомо ниже реального размера файла
    result = check_size(path, threshold_mb=0.0001)
    assert result["over_threshold"] is True


def test_avg_bytes_per_signal_computed(tmp_path):
    path = _write_signals(tmp_path, n_signals=10)
    result = check_size(path, threshold_mb=4.0)
    assert result["avg_bytes_per_signal"] > 0
    assert result["size_bytes"] == path.stat().st_size


def test_projected_signals_at_threshold_is_positive(tmp_path):
    path = _write_signals(tmp_path, n_signals=10)
    result = check_size(path, threshold_mb=4.0)
    assert result["projected_signals_at_threshold"] is not None
    assert result["projected_signals_at_threshold"] > 0


def test_empty_signals_list_does_not_crash(tmp_path):
    path = tmp_path / "signals.json"
    path.write_text(json.dumps({"meta": {}, "signals": []}), encoding="utf-8")
    result = check_size(path, threshold_mb=4.0)
    assert result["signal_count"] == 0
    assert result["avg_bytes_per_signal"] == 0
    assert result["projected_signals_at_threshold"] is None
