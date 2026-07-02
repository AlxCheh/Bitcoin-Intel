"""
tests/unit/test_migration_v1_to_v2.py
IRP v1 Wave 4 / MC05 — юнит-тесты stub-миграции.

Цель этих тестов не проверить логику миграции (её нет — это stub), а
зафиксировать поведенческий контракт stub'а: dry-run безопасен и
идемпотентен, --apply падает явно с NotImplementedError, а не тихо
делает вид что что-то мигрировал.
"""
import pytest

from migration.v1_to_v2 import migrate, _transform_record, TARGET_SCHEMA_EXISTS


def test_target_schema_does_not_exist_yet():
    """
    Фиксирует текущее состояние проекта явно: если этот тест начнёт падать
    (кто-то поменял флаг на True не заполнив миграцию) — это сигнал, что
    stub нужно либо доделать, либо флаг откатить.
    """
    assert TARGET_SCHEMA_EXISTS is False


def test_dry_run_is_safe_and_returns_zero_stats():
    stats = migrate(dry_run=True)
    assert stats["records_migrated"] == 0
    assert stats["records_skipped"] == 0
    assert stats["target_schema_exists"] is False


def test_dry_run_is_idempotent():
    """Повторный dry-run даёт тот же результат — не накапливает состояние."""
    first = migrate(dry_run=True)
    second = migrate(dry_run=True)
    assert first == second


def test_apply_raises_not_implemented_explicitly():
    """
    --apply на stub'е без target schema должен падать ЯВНО
    (NotImplementedError), а не тихо возвращать нулевую статистику как
    dry-run — иначе кто-то может принять stub за рабочую миграцию.
    """
    with pytest.raises(NotImplementedError):
        migrate(dry_run=False)


def test_transform_record_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        _transform_record({"id": "STR-2026-0101-001"})
