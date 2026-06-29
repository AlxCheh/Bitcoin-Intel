"""
tests/golden/test_golden.py
Регрессионные тесты нарративного движка на Golden Dataset.
Тестируют СМЫСЛ результата, не только формат.
"""
import json
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED = Path(__file__).parent / "expected"

TENSION_MARKERS = ["vs", "несмотря на", "при условии", "вопреки", " — ", "—"]


def load_golden_signals() -> list:
    f = FIXTURES / "golden_signals.json"
    if not f.exists():
        pytest.skip("golden_signals.json not found")
    data = json.loads(f.read_text(encoding="utf-8"))
    # Поддержка форматов: {meta, signals:[...]} и просто [...]
    if isinstance(data, dict):
        return data.get("signals", [])
    return data


def load_expected_synthesis() -> dict:
    f = EXPECTED / "golden_synthesis.json"
    if not f.exists():
        pytest.skip("golden_synthesis.json not found — create it first (G2)")
    return json.loads(f.read_text(encoding="utf-8"))


# ─── Структурные тесты (не требуют синтезатора) ──────────────────────────────

def test_golden_dataset_minimum_size():
    """Golden Dataset содержит минимум 15 сигналов."""
    signals = load_golden_signals()
    assert len(signals) >= 15, (
        f"Golden Dataset has {len(signals)} signals, need >= 15"
    )


def test_golden_covers_minimum_clusters():
    """Golden Dataset покрывает минимум 3 кластера."""
    signals  = load_golden_signals()
    clusters = {s.get("cluster") for s in signals if s.get("cluster")}
    assert len(clusters) >= 3, (
        f"Only {len(clusters)} clusters: {clusters}. Need >= 3."
    )


def test_golden_signal_ids_unique():
    """Все ID уникальны."""
    signals = load_golden_signals()
    ids     = [s["id"] for s in signals]
    dupes   = [i for i in ids if ids.count(i) > 1]
    assert not dupes, f"Duplicate IDs: {set(dupes)}"


def test_required_fields_present():
    """Каждый сигнал содержит обязательные поля."""
    signals  = load_golden_signals()
    required = ["id", "date", "signal", "tension", "macro_implication",
                "narrative_role", "cluster", "weight", "dir"]
    for s in signals:
        for field in required:
            assert field in s, (
                f"Signal {s.get('id','?')} missing required field: '{field}'"
            )


def test_tension_starts_with_capital():
    """Tension начинается с заглавной буквы (правило CLAUDE.md)."""
    signals = load_golden_signals()
    for s in signals:
        tension = s.get("tension", "")
        if tension:
            assert tension[0].isupper(), (
                f"Signal {s['id']}: tension must start with capital: '{tension}'"
            )


def test_tension_has_opposition_marker():
    """Непустой tension содержит конструкцию противоречия."""
    signals = load_golden_signals()
    for s in signals:
        tension = s.get("tension", "")
        if not tension:
            continue
        has_marker = any(m.lower() in tension.lower() for m in TENSION_MARKERS)
        assert has_marker, (
            f"Signal {s['id']}: tension has no opposition marker: '{tension}'"
        )


def test_macro_implication_not_too_short():
    """
    macro_implication описывает структурное изменение, не пересказ события.
    Минимальная длина 50 символов.
    """
    signals = load_golden_signals()
    for s in signals:
        impl = s.get("macro_implication", "")
        if impl:
            assert len(impl) >= 50, (
                f"Signal {s['id']}: macro_implication too short "
                f"({len(impl)} chars): '{impl}'"
            )


def test_narrative_roles_valid():
    """narrative_role принимает только допустимые значения."""
    signals = load_golden_signals()
    valid   = {"trigger", "complication", "resolution", "background"}
    for s in signals:
        role = s.get("narrative_role", "")
        assert role in valid, (
            f"Signal {s['id']}: invalid narrative_role '{role}'. Must be: {valid}"
        )


def test_dir_values_valid():
    """dir принимает только pos / neg / neu."""
    signals = load_golden_signals()
    valid   = {"pos", "neg", "neu"}
    for s in signals:
        d = s.get("dir", "")
        assert d in valid, (
            f"Signal {s['id']}: invalid dir '{d}'. Must be: {valid}"
        )


def test_weight_values_valid():
    """weight принимает только допустимые значения."""
    signals = load_golden_signals()
    valid   = {"onchain", "primary", "market", "media"}
    for s in signals:
        w = s.get("weight", "")
        assert w in valid, (
            f"Signal {s['id']}: invalid weight '{w}'. Must be: {valid}"
        )


# ─── Регрессионные тесты (требуют golden_synthesis.json) ─────────────────────

def test_expected_synthesis_file_exists():
    """golden_synthesis.json существует (создать если нет — G2)."""
    f = EXPECTED / "golden_synthesis.json"
    assert f.exists(), (
        "tests/golden/expected/golden_synthesis.json not found. "
        "Create it per ARCH_GAP_SPEC G2."
    )


def test_expected_synthesis_valid_json():
    """golden_synthesis.json валидный JSON."""
    f = EXPECTED / "golden_synthesis.json"
    if not f.exists():
        pytest.skip("golden_synthesis.json not found")
    data = json.loads(f.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "golden_synthesis.json must be a dict"
    assert "_meta" in data, "golden_synthesis.json must have _meta section"
