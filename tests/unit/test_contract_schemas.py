"""
tests/unit/test_contract_schemas.py
Bitcoin Intel — Contract Tests (IRP v1 Wave 2 / REM-B3, MC01-04, MT01).

Валидирует реальные данные (signals.json, data/relationships.json,
synthesis_store/*.json) против JSON Schema в schemas/. Ловит невалидные
поля/значения до того, как они попадут в продакшн-данные незамеченными.

Схемы отражают текущую реализацию, а не всегда дословно ADDENDUM §17 —
расхождения задокументированы в самих схемах и в ADR-013 (для synthesis).
synthesis_cache.json НЕ валидируется этим schema — его форма (keyed by
cluster, без id/status) отличается от synthesis_store; это осознанное
решение, не пробел.
"""
import glob
import json
import os

import pytest
from jsonschema import Draft7Validator

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_schema(name: str) -> Draft7Validator:
    path = os.path.join(ROOT, "schemas", name, "v1.json")
    with open(path, encoding="utf-8") as f:
        return Draft7Validator(json.load(f))


def _load_signals() -> list[dict]:
    path = os.path.join(ROOT, "signals.json")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("signals", raw) if isinstance(raw, dict) else raw


def _load_relationships() -> list[dict]:
    path = os.path.join(ROOT, "data", "relationships.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_synthesis_store() -> list[tuple[str, dict]]:
    pattern = os.path.join(ROOT, "synthesis_store", "*.json")
    out = []
    for filepath in glob.glob(pattern):
        with open(filepath, encoding="utf-8") as f:
            out.append((os.path.basename(filepath), json.load(f)))
    return out


# ─── Signal Schema ─────────────────────────────────────────────────────────

def test_signal_schema_is_valid_json_schema():
    schema = _load_schema("signal")
    schema.check_schema(schema.schema)


def test_all_signals_conform_to_schema():
    validator = _load_schema("signal")
    signals = _load_signals()
    assert signals, "signals.json пуст или не прочитан"

    failures = []
    for s in signals:
        errors = list(validator.iter_errors(s))
        if errors:
            failures.append((s.get("id", "?"), [e.message for e in errors]))

    assert not failures, "Невалидные сигналы:\n" + "\n".join(
        f"  {sid}: {errs}" for sid, errs in failures
    )


def test_signal_schema_rejects_unknown_field():
    validator = _load_schema("signal")
    bad = {
        "id": "STR-2026-0101-001", "date": "2026-01-01",
        "signal": "x" * 25, "tension": "X vs Y" + " padding text here",
        "macro_implication": "x" * 45, "narrative_role": "trigger",
        "cluster": "test", "theme": "macro", "weight": "media",
        "dir": "pos", "horizon": "short", "cat": "macro",
        "catLabel": "test", "source": "test source",
        "totally_unknown_field": "should fail",
    }
    errors = list(validator.iter_errors(bad))
    assert errors, "Схема должна отклонять неизвестные поля (additionalProperties: false)"


# ─── Relationship Schema ───────────────────────────────────────────────────

def test_relationship_schema_is_valid_json_schema():
    schema = _load_schema("relationship")
    schema.check_schema(schema.schema)


def test_all_relationships_conform_to_schema():
    validator = _load_schema("relationship")
    rels = _load_relationships()
    if not rels:
        pytest.skip("data/relationships.json пуст или отсутствует (legacy режим)")

    failures = []
    for r in rels:
        errors = list(validator.iter_errors(r))
        if errors:
            failures.append((r.get("id", "?"), [e.message for e in errors]))

    assert not failures, "Невалидные relationships:\n" + "\n".join(
        f"  {rid}: {errs}" for rid, errs in failures
    )


# ─── Synthesis Schema ──────────────────────────────────────────────────────

def test_synthesis_schema_is_valid_json_schema():
    schema = _load_schema("synthesis")
    schema.check_schema(schema.schema)


def test_all_synthesis_store_records_conform_to_schema():
    validator = _load_schema("synthesis")
    records = _load_synthesis_store()
    if not records:
        pytest.skip("synthesis_store/ пуст")

    failures = []
    for name, rec in records:
        errors = list(validator.iter_errors(rec))
        if errors:
            failures.append((name, [e.message for e in errors]))

    assert not failures, "Невалидные synthesis-записи:\n" + "\n".join(
        f"  {name}: {errs}" for name, errs in failures
    )
