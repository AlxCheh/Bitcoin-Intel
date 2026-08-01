"""
tests/unit/test_compare_contradiction_precision.py
Bitcoin Intel — тесты scripts/compare_contradiction_precision.py (методология
"до/после на фиксированном срезе", формализована 2026-07-31 — см.
docs/PLAN-open-initiatives.md (Часть 2)).
"""
import json
import types

import pytest

from scripts.compare_contradiction_precision import (
    compare_on_dataset,
    load_from_file,
    load_pairs,
    main,
    score_pairs,
)


def _fake_module(score_fn):
    """Имитирует загруженный модуль — только то, что использует скрипт."""
    m = types.SimpleNamespace()
    m.semantic_inverse_score = score_fn
    return m


def _write_pairs(tmp_path, name, pairs):
    path = tmp_path / name
    path.write_text(json.dumps({"_meta": {}, "pairs": pairs}), encoding="utf-8")
    return path


# ─── compare_on_dataset — логика сравнения на синтетических модулях ─────────

class TestCompareOnDataset:

    def test_identical_before_after_shows_zero_changes(self, tmp_path):
        same_fn = lambda a, b: 0.7  # noqa: E731
        before = _fake_module(same_fn)
        after = _fake_module(same_fn)
        pairs_path = _write_pairs(tmp_path, "p.json", [
            {"a": "x", "b": "y", "expected": True},
        ])

        result = compare_on_dataset(before, after, pairs_path)

        assert result["precision_before"] == result["precision_after"]
        assert result["changed"] == []

    def test_detects_fixed_prediction(self, tmp_path):
        before = _fake_module(lambda a, b: 0.0)   # всегда "не contradicts"
        after = _fake_module(lambda a, b: 0.9)    # всегда "contradicts"
        pairs_path = _write_pairs(tmp_path, "p.json", [
            {"a": "x", "b": "y", "expected": True, "signal_a": "A", "signal_b": "B"},
        ])

        result = compare_on_dataset(before, after, pairs_path)

        assert result["precision_before"] == 0.0
        assert result["precision_after"] == 1.0
        assert len(result["changed"]) == 1
        assert result["changed"][0]["verdict"] == "FIXED"
        assert result["changed"][0]["signal_a"] == "A"

    def test_detects_broke_prediction(self, tmp_path):
        before = _fake_module(lambda a, b: 0.9)
        after = _fake_module(lambda a, b: 0.0)
        pairs_path = _write_pairs(tmp_path, "p.json", [
            {"a": "x", "b": "y", "expected": True},
        ])

        result = compare_on_dataset(before, after, pairs_path)

        assert result["precision_before"] == 1.0
        assert result["precision_after"] == 0.0
        assert result["changed"][0]["verdict"] == "BROKE"

    def test_changed_prediction_that_stays_wrong_not_labeled_fixed_or_broke(self, tmp_path):
        """Скор поменялся, предсказание изменилось, но было и осталось неверным — CHANGED, не FIXED/BROKE."""
        before = _fake_module(lambda a, b: 0.6)   # предсказывает True, expected False -> неверно
        after = _fake_module(lambda a, b: 0.9)    # тоже True, тоже неверно — но раз score разный,
        pairs_path = _write_pairs(tmp_path, "p.json", [               # предсказание (bool) НЕ поменялось
            {"a": "x", "b": "y", "expected": False},
        ])
        result = compare_on_dataset(before, after, pairs_path)
        # bool-предсказание не изменилось (True->True) -> changed пуст, не тестируем verdict
        assert result["changed"] == []

    def test_mixed_pairs_correct_precision_math(self, tmp_path):
        def fn(a, b):
            return {"p1": 0.9, "p2": 0.1}[a]
        before = _fake_module(lambda a, b: 0.9)  # всегда contradicts
        after = _fake_module(fn)
        pairs_path = _write_pairs(tmp_path, "p.json", [
            {"a": "p1", "b": "y", "expected": True},
            {"a": "p2", "b": "y", "expected": False},
        ])
        result = compare_on_dataset(before, after, pairs_path)
        assert result["precision_before"] == 0.5   # p1 верно, p2 неверно (0.9>=0.5)
        assert result["precision_after"] == 1.0     # p1 верно (0.9), p2 верно (0.1<0.5)
        assert len(result["changed"]) == 1
        assert result["changed"][0]["verdict"] == "FIXED"


# ─── load_from_file / load_pairs — реальная механика загрузки ───────────────

class TestModuleLoading:

    def test_load_from_file_executes_and_exposes_function(self, tmp_path):
        src = (
            "import sys, os\n"
            "def semantic_inverse_score(a, b):\n"
            "    return 1.0 if a == b else 0.0\n"
        )
        path = tmp_path / "fake_detector.py"
        path.write_text(src, encoding="utf-8")

        module = load_from_file(path, "test_module_unique_name")

        assert module.semantic_inverse_score("x", "x") == 1.0
        assert module.semantic_inverse_score("x", "y") == 0.0

    def test_load_from_file_real_contradiction_detector_works(self):
        """
        Регрессия на реальный файл (не синтетику) — ловит поломку __file__/
        sys.path трюка, если contradiction_detector.py когда-нибудь изменит
        способ вычисления REPO_ROOT.
        """
        from pathlib import Path
        from scripts.compare_contradiction_precision import REPO_ROOT, DETECTOR_REL_PATH

        module = load_from_file(REPO_ROOT / DETECTOR_REL_PATH, "test_real_detector")
        score = module.semantic_inverse_score("ETF-приток растёт", "ETF-отток растёт")
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_load_pairs_reads_pairs_key(self, tmp_path):
        path = _write_pairs(tmp_path, "p.json", [{"a": "1", "b": "2", "expected": True}])
        pairs = load_pairs(path)
        assert len(pairs) == 1
        assert pairs[0]["a"] == "1"


# ─── main() — exit codes ─────────────────────────────────────────────────────

class TestMainExitCode:

    def test_blocking_regression_causes_exit_1(self, tmp_path, monkeypatch, capsys):
        import scripts.compare_contradiction_precision as mod

        monkeypatch.setattr(
            mod, "load_from_git_ref",
            lambda ref, name: _fake_module(lambda a, b: 0.9),  # "до" — всегда contradicts (верно)
        )
        monkeypatch.setattr(
            mod, "load_from_file",
            lambda path, name: _fake_module(lambda a, b: 0.0),  # "после" — регресс
        )
        blocking_path = _write_pairs(tmp_path, "blocking.json", [
            {"a": "x", "b": "y", "expected": True},
        ])
        monkeypatch.setattr(mod, "DATASETS", {"blocking": blocking_path})
        monkeypatch.setattr("sys.argv", ["compare_contradiction_precision.py"])

        exit_code = mod.main()

        assert exit_code == 1
        assert "РЕГРЕСС" in capsys.readouterr().out

    def test_no_regression_returns_exit_0(self, tmp_path, monkeypatch, capsys):
        import scripts.compare_contradiction_precision as mod

        monkeypatch.setattr(mod, "load_from_git_ref", lambda ref, name: _fake_module(lambda a, b: 0.9))
        monkeypatch.setattr(mod, "load_from_file", lambda path, name: _fake_module(lambda a, b: 0.9))
        blocking_path = _write_pairs(tmp_path, "blocking.json", [
            {"a": "x", "b": "y", "expected": True},
        ])
        monkeypatch.setattr(mod, "DATASETS", {"blocking": blocking_path})
        monkeypatch.setattr("sys.argv", ["compare_contradiction_precision.py"])

        assert mod.main() == 0
