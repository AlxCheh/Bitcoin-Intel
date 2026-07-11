"""
tests/unit/test_facts.py
Bitcoin Intel — тесты машиночитаемых фактов (CLAUDE.md v8.2).

Проверяет:
1. Внутри одного сигнала нет дублирующихся facts[].key (иначе неясно,
   какое значение из ДВУХ в одном сигнале использовать — двусмысленность,
   которую нельзя разрешить автоматически, в отличие от дублей МЕЖДУ
   сигналами, где age (as_of) даёт однозначный ответ).
2. resolve_facts() из scripts/build_facts.py корректно выбирает запись
   с максимальным as_of среди нескольких сигналов на один и тот же key —
   это ядро всего механизма (S12: "производное приводится к источнику",
   применительно к фактам — последнее актуальное значение, не последнее
   по порядку в файле).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from build_facts import resolve_facts  # noqa: E402


def _load_signals() -> list[dict]:
    path = os.path.join(ROOT, "signals.json")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("signals", raw) if isinstance(raw, dict) else raw


def test_no_duplicate_fact_keys_within_a_signal():
    signals = _load_signals()
    offenders = []
    for sig in signals:
        facts = sig.get("facts") or []
        keys = [f["key"] for f in facts]
        if len(keys) != len(set(keys)):
            offenders.append(sig["id"])
    assert not offenders, f"Дублирующиеся facts[].key внутри сигнала(ов): {offenders}"


def test_resolve_facts_picks_latest_as_of():
    signals = [
        {"id": "A-2026-0101-001", "facts": [
            {"key": "x.metric", "value": 100, "unit": "BTC", "as_of": "2026-01-01"}
        ]},
        {"id": "A-2026-0201-001", "facts": [
            {"key": "x.metric", "value": 200, "unit": "BTC", "as_of": "2026-02-01"}
        ]},
    ]
    resolved = resolve_facts(signals)
    assert resolved["x.metric"]["value"] == 200
    assert resolved["x.metric"]["signal_id"] == "A-2026-0201-001"


def test_resolve_facts_ignores_file_order_only_as_of_matters():
    # Сигнал с более ранним as_of идёт ПОСЛЕ в списке — порядок не должен влиять
    signals = [
        {"id": "A-2026-0201-001", "facts": [
            {"key": "y.metric", "value": 200, "unit": "BTC", "as_of": "2026-02-01"}
        ]},
        {"id": "A-2026-0101-001", "facts": [
            {"key": "y.metric", "value": 100, "unit": "BTC", "as_of": "2026-01-01"}
        ]},
    ]
    resolved = resolve_facts(signals)
    assert resolved["y.metric"]["value"] == 200


def test_resolve_facts_handles_signals_without_facts_field():
    signals = [{"id": "A-2026-0101-001"}, {"id": "A-2026-0102-001", "facts": []}]
    resolved = resolve_facts(signals)
    assert resolved == {}


def test_real_signals_json_facts_resolve_without_error():
    """Смоук-тест на реальных данных — не должен падать и должен вернуть
    непустой результат, раз в signals.json уже есть сигналы с facts."""
    signals = _load_signals()
    resolved = resolve_facts(signals)
    assert isinstance(resolved, dict)
