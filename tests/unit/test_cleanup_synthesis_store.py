"""
tests/unit/test_cleanup_synthesis_store.py
Bitcoin Intel — тесты scripts/cleanup_synthesis_store.py (M1 ARR v3).
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.cleanup_synthesis_store import find_expired, cleanup, _age_days
from domain.events import EventLog


def _make_synthesis_file(store: Path, name: str, status: str,
                          days_old: int, synthesis_id: str = None) -> Path:
    generated_at = (
        datetime.now(timezone.utc) - timedelta(days=days_old)
    ).isoformat()
    data = {
        "id": synthesis_id or name,
        "cluster": "test_cluster",
        "status": status,
        "generated_at": generated_at,
    }
    f = store / f"{name}.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return f


@pytest.fixture
def store(tmp_path):
    s = tmp_path / "synthesis_store"
    s.mkdir(exist_ok=True)
    return s


class TestAgeDays:

    def test_age_days_computes_correctly(self):
        ts = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        assert _age_days(ts) == 5

    def test_age_days_handles_naive_datetime(self):
        # generated_at без явного offset (на случай старых файлов / ручного ввода)
        ts = (datetime.now(timezone.utc) - timedelta(days=3)).replace(tzinfo=None).isoformat()
        assert _age_days(ts) in (2, 3)  # допуск на округление


class TestFindExpired:

    def test_generated_status_expires_after_30_days(self, store):
        _make_synthesis_file(store, "s1", "generated", days_old=31)
        expired, warnings = find_expired(str(store))
        assert len(expired) == 1
        assert expired[0]["id"] == "s1"
        assert not warnings

    def test_generated_status_not_expired_within_30_days(self, store):
        _make_synthesis_file(store, "s1", "generated", days_old=29)
        expired, warnings = find_expired(str(store))
        assert len(expired) == 0

    def test_approved_never_expires(self, store):
        _make_synthesis_file(store, "s1", "approved", days_old=10000)
        expired, warnings = find_expired(str(store))
        assert len(expired) == 0

    def test_published_never_expires(self, store):
        _make_synthesis_file(store, "s1", "published", days_old=10000)
        expired, warnings = find_expired(str(store))
        assert len(expired) == 0

    def test_archived_never_expires(self, store):
        _make_synthesis_file(store, "s1", "archived", days_old=10000)
        expired, warnings = find_expired(str(store))
        assert len(expired) == 0

    def test_superseded_expires_after_730_days(self, store):
        _make_synthesis_file(store, "s1", "superseded", days_old=731)
        _make_synthesis_file(store, "s2", "superseded", days_old=100)
        expired, warnings = find_expired(str(store))
        ids = {e["id"] for e in expired}
        assert ids == {"s1"}

    def test_missing_store_directory_returns_empty(self, tmp_path):
        expired, warnings = find_expired(str(tmp_path / "does_not_exist"))
        assert expired == []
        assert warnings == []

    def test_corrupted_json_file_warns_and_skips(self, store):
        (store / "broken.json").write_text("{not valid json", encoding="utf-8")
        _make_synthesis_file(store, "s1", "generated", days_old=31)
        expired, warnings = find_expired(str(store))
        assert len(expired) == 1  # s1 всё равно найден
        assert len(warnings) == 1
        assert "broken.json" in warnings[0]

    def test_missing_generated_at_warns_and_skips(self, store):
        f = store / "no_date.json"
        f.write_text(json.dumps({"id": "x", "status": "generated"}), encoding="utf-8")
        expired, warnings = find_expired(str(store))
        assert len(expired) == 0
        assert any("generated_at" in w for w in warnings)

    def test_unknown_status_defaults_to_generated_policy(self, store):
        # status отсутствует вовсе -> default "generated" по find_expired()
        f = store / "no_status.json"
        old_date = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
        f.write_text(json.dumps({"id": "x", "generated_at": old_date}), encoding="utf-8")
        expired, warnings = find_expired(str(store))
        assert len(expired) == 1


class TestCleanup:

    def test_dry_run_does_not_delete_files(self, store, monkeypatch):
        f = _make_synthesis_file(store, "s1", "generated", days_old=31)
        monkeypatch.setattr(
            "scripts.cleanup_synthesis_store.find_expired",
            lambda: find_expired(str(store)),
        )
        result = cleanup(apply=False)
        assert result["expired"] == 1
        assert result["deleted"] == 0
        assert f.exists(), "dry-run must never delete files"

    def test_apply_deletes_expired_files(self, store, monkeypatch):
        f = _make_synthesis_file(store, "s1", "generated", days_old=31)
        events_path = store.parent / "events.jsonl"
        monkeypatch.setattr(
            "scripts.cleanup_synthesis_store.find_expired",
            lambda: find_expired(str(store)),
        )
        monkeypatch.setattr(
            "scripts.cleanup_synthesis_store.EVENTS_LOG_PATH", str(events_path)
        )
        result = cleanup(apply=True)
        assert result["deleted"] == 1
        assert not f.exists(), "--apply must delete expired files"

    def test_apply_writes_audit_event_before_delete(self, store, monkeypatch):
        _make_synthesis_file(store, "s1", "generated", days_old=31)
        events_path = store.parent / "events.jsonl"
        monkeypatch.setattr(
            "scripts.cleanup_synthesis_store.find_expired",
            lambda: find_expired(str(store)),
        )
        monkeypatch.setattr(
            "scripts.cleanup_synthesis_store.EVENTS_LOG_PATH", str(events_path)
        )
        cleanup(apply=True)

        events = EventLog(str(events_path)).read_all()
        cleaned = [e for e in events if e.get("event_type") == "SynthesisStoreCleaned"]
        assert len(cleaned) == 1
        assert cleaned[0]["synthesis_id"] == "s1"
        assert cleaned[0]["status"] == "generated"

    def test_apply_preserves_non_expired_files(self, store, monkeypatch):
        f_keep = _make_synthesis_file(store, "keep", "approved", days_old=10000)
        f_del  = _make_synthesis_file(store, "del", "generated", days_old=31)
        events_path = store.parent / "events.jsonl"
        monkeypatch.setattr(
            "scripts.cleanup_synthesis_store.find_expired",
            lambda: find_expired(str(store)),
        )
        monkeypatch.setattr(
            "scripts.cleanup_synthesis_store.EVENTS_LOG_PATH", str(events_path)
        )
        cleanup(apply=True)
        assert f_keep.exists()
        assert not f_del.exists()

    def test_nothing_expired_is_safe_noop(self, store, monkeypatch):
        _make_synthesis_file(store, "s1", "approved", days_old=1)
        monkeypatch.setattr(
            "scripts.cleanup_synthesis_store.find_expired",
            lambda: find_expired(str(store)),
        )
        result = cleanup(apply=True)
        assert result == {"expired": 0, "deleted": 0, "warnings": 0}
