"""
tests/unit/test_check_synthesis_freshness.py
IRP v1 Wave 4 / OP05 — юнит-тесты чистых функций проверки freshness.

check_absolute_staleness и check_signal_cache_desync намеренно принимают
dict/list напрямую (не читают файлы сами) — это делает их тестируемыми без
файлового I/O и без конфликта с autouse isolated_environment (см.
tests/conftest.py) из tests/performance/test_synthesizer_perf.py.
"""
from datetime import datetime, timedelta, timezone

from scripts.check_synthesis_freshness import (
    check_absolute_staleness,
    check_signal_cache_desync,
)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def test_absolute_staleness_no_problems_when_fresh():
    now = datetime.now(timezone.utc)
    cache = {
        "cluster_a": {"generated_at": _iso(now - timedelta(days=1))},
        "cluster_b": {"generated_at": _iso(now - timedelta(days=5))},
    }
    assert check_absolute_staleness(cache, threshold_days=14) == []


def test_absolute_staleness_flags_old_cluster():
    now = datetime.now(timezone.utc)
    cache = {
        "cluster_a": {"generated_at": _iso(now - timedelta(days=1))},
        "cluster_b": {"generated_at": _iso(now - timedelta(days=30))},
    }
    problems = check_absolute_staleness(cache, threshold_days=14)
    assert len(problems) == 1
    assert "cluster_b" in problems[0]


def test_absolute_staleness_flags_missing_generated_at():
    cache = {"cluster_a": {}}
    problems = check_absolute_staleness(cache, threshold_days=14)
    assert len(problems) == 1
    assert "generated_at" in problems[0]


def test_desync_no_problems_when_signal_older_than_cache():
    now = datetime.now(timezone.utc)
    cache = {"cluster_a": {"generated_at": _iso(now)}}
    signals = [{"id": "STR-2026-0101-001", "cluster": "cluster_a", "date": "2026-01-01"}]
    assert check_signal_cache_desync(signals, cache) == []


def test_desync_flags_signal_newer_than_cache():
    old_cache_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    cache = {"cluster_a": {"generated_at": _iso(old_cache_time)}}
    signals = [{"id": "STR-2026-0630-001", "cluster": "cluster_a", "date": "2026-06-30"}]
    problems = check_signal_cache_desync(signals, cache)
    assert len(problems) == 1
    assert "STR-2026-0630-001" in problems[0]


def test_desync_ignores_signal_in_uncached_cluster():
    """
    Кластер, который ещё ни разу не синтезировался (нет в cache), не должен
    считаться рассинхронизацией — это не деградация, а ожидаемое состояние
    для только что созданного кластера до первого прогона synthesizer.py.
    """
    cache = {"cluster_a": {"generated_at": _iso(datetime.now(timezone.utc))}}
    signals = [{"id": "NEW-2026-0630-001", "cluster": "brand_new_cluster", "date": "2026-06-30"}]
    assert check_signal_cache_desync(signals, cache) == []


def test_desync_ignores_signal_with_malformed_date():
    """Сигнал с некорректной датой не должен ронять проверку с исключением."""
    cache = {"cluster_a": {"generated_at": _iso(datetime.now(timezone.utc))}}
    signals = [{"id": "BAD-2026-0630-001", "cluster": "cluster_a", "date": "not-a-date"}]
    assert check_signal_cache_desync(signals, cache) == []
