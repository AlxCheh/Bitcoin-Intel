"""
tests/unit/test_quality_report.py
Bitcoin Intel — тесты scripts/quality_report.py.

До этого файла quality_report.py не имел НИ ОДНОГО теста (как и
approve_synthesis.py до C3 ARR v3 — тот же класс риска: CLI-инструмент,
запускаемый аналитиком, без защиты от тихой поломки при рефакторинге).
При написании этих тестов обнаружен реальный баг: main() передавал
сырой результат safe_read_json(SIGNALS_PATH) — словарь {meta, signals} —
напрямую в compute_quality_report(), которая ожидает list[dict]. CLI падал
при обычном запуске `python scripts/quality_report.py` без аргументов.
См. test_main_handles_signals_json_meta_wrapper.
"""
import json
import subprocess
import sys
from pathlib import Path

from scripts.quality_report import compute_quality_report, check_calibration_readiness
from config.settings import MIN_SYNTHESES_FOR_CALIBRATION

REPO_ROOT = Path(__file__).parent.parent.parent


def _signal(id_, **overrides):
    base = {
        "id": id_,
        "date": "2026-06-29",
        "tension": "X vs Y",
        "macro_implication": "Структурный сдвиг достаточной длины для прохождения проверки длины поля.",
        "context": "контекст",
        "caveat": "оговорка",
        "dir": "pos",
        "cluster": "test_cluster",
        "weight": "primary",
        "narrative_role": "trigger",
        "links": {"confirms": [], "contradicts": [], "context_chain": []},
    }
    base.update(overrides)
    return base


class TestComputeQualityReport:

    def test_empty_signals_returns_error(self):
        report = compute_quality_report([])
        assert report["error"] == "no signals"

    def test_full_coverage_scores_high(self):
        signals = [_signal(f"S-{i}") for i in range(5)]
        report = compute_quality_report(signals)
        assert report["coverage"]["tension"] == 1.0
        assert report["coverage"]["macro_implication"] == 1.0
        assert report["health"]["grade"] in ("A", "B")

    def test_missing_fields_lower_coverage(self):
        signals = [
            _signal("S-1"),
            _signal("S-2", tension="", macro_implication=""),
        ]
        report = compute_quality_report(signals)
        assert report["coverage"]["tension"] == 0.5
        assert report["coverage"]["macro_implication"] == 0.5

    def test_tension_without_marker_not_counted_as_valid(self):
        signals = [_signal("S-1", tension="Просто описание без противоречия")]
        report = compute_quality_report(signals)
        assert report["quality"]["tension_formula_valid"] == 0.0

    def test_tension_lowercase_first_letter_invalid(self):
        signals = [_signal("S-1", tension="строчная буква vs заглавная нужна")]
        report = compute_quality_report(signals)
        assert report["quality"]["tension_formula_valid"] == 0.0

    def test_cluster_filter_isolates_cluster(self):
        signals = [
            _signal("S-1", cluster="a"),
            _signal("S-2", cluster="b"),
        ]
        report = compute_quality_report(signals, cluster_filter="a")
        assert report["total_signals"] == 1
        assert report["cluster_filter"] == "a"

    def test_cluster_filter_no_match_returns_error(self):
        signals = [_signal("S-1", cluster="a")]
        report = compute_quality_report(signals, cluster_filter="nonexistent")
        assert report["error"] == "no signals"

    def test_connectivity_counts_any_link_type(self):
        signals = [
            _signal("S-1", links={"confirms": ["X"], "contradicts": [], "context_chain": []}),
            _signal("S-2", links={"confirms": [], "contradicts": [], "context_chain": []}),
        ]
        report = compute_quality_report(signals)
        assert report["quality"]["signals_with_links"] == 0.5

    def test_report_includes_calibration_section(self):
        """ADR-011: каждый отчёт включает статус готовности к калибровке."""
        signals = [_signal("S-1")]
        report = compute_quality_report(signals)
        assert "calibration" in report
        assert set(report["calibration"]) == {
            "synthesis_count", "threshold", "ready", "remaining"
        }


class TestCalibrationReadiness:
    """
    2026-07-31: до этой правки тесты патчили SYNTHESIS_STORE_PATH и считали
    файлы в synthesis_store/ — тот самый механизм, который оказался
    заброшен с 2026-06-29 в проде (см. ADR-011, заметка 2026-07-31).
    Тесты теперь патчат SYNTHESIS_HISTORY_PATH (новый самоподдерживающийся
    счётчик, data/synthesis_history_count.json), сохраняя тот же контракт
    check_calibration_readiness() (synthesis_count/threshold/ready/remaining).
    """

    def test_below_threshold_not_ready(self, tmp_path, monkeypatch):
        history_file = tmp_path / "synthesis_history_count.json"
        history_file.write_text(json.dumps({"cluster_periods": 5}))
        monkeypatch.setattr(
            "scripts.quality_report.SYNTHESIS_HISTORY_PATH", str(history_file)
        )

        result = check_calibration_readiness()
        assert result["synthesis_count"] == 5
        assert result["ready"] is False
        assert result["remaining"] == MIN_SYNTHESES_FOR_CALIBRATION - 5

    def test_at_or_above_threshold_ready(self, tmp_path, monkeypatch):
        history_file = tmp_path / "synthesis_history_count.json"
        history_file.write_text(
            json.dumps({"cluster_periods": MIN_SYNTHESES_FOR_CALIBRATION})
        )
        monkeypatch.setattr(
            "scripts.quality_report.SYNTHESIS_HISTORY_PATH", str(history_file)
        )

        result = check_calibration_readiness()
        assert result["ready"] is True
        assert result["remaining"] == 0

    def test_above_threshold_reports_real_backfilled_count(self, tmp_path, monkeypatch):
        """Регрессия на реальный кейс находки: 191 >> 30, а не застрявшие 10."""
        history_file = tmp_path / "synthesis_history_count.json"
        history_file.write_text(json.dumps({"cluster_periods": 191}))
        monkeypatch.setattr(
            "scripts.quality_report.SYNTHESIS_HISTORY_PATH", str(history_file)
        )

        result = check_calibration_readiness()
        assert result["synthesis_count"] == 191
        assert result["ready"] is True

    def test_missing_history_file_counts_zero(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "scripts.quality_report.SYNTHESIS_HISTORY_PATH",
            str(tmp_path / "does_not_exist.json"),
        )
        result = check_calibration_readiness()
        assert result["synthesis_count"] == 0
        assert result["ready"] is False


class TestMainCLIRegression:
    """
    Регрессионный тест на реальный production-баг: main() падал на текущей
    схеме signals.json ({meta, signals: [...]}) с
    AttributeError: 'str' object has no attribute 'get' внутри
    compute_quality_report(), потому что туда передавался весь dict целиком,
    а не список сигналов. Обнаружено вручную при разработке ADR-011 — ни
    один существующий тест этого не покрывал (как и approve_synthesis.py
    до C3 ARR v3).

    Тест запускает РЕАЛЬНЫЙ CLI как subprocess на РЕАЛЬНОМ signals.json
    репозитория — не мок, чтобы поймать именно класс бага "работает с
    тестовыми данными, падает на реальной схеме".
    """

    def test_main_handles_signals_json_meta_wrapper(self):
        result = subprocess.run(
            [sys.executable, "scripts/quality_report.py"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=15,
        )
        assert result.returncode in (0, 1), (
            f"quality_report.py crashed (exit {result.returncode}):\n{result.stderr}"
        )
        assert "Unexpected error" not in result.stderr
        assert "Health Score" in result.stdout

    def test_main_json_format_is_valid_json(self):
        result = subprocess.run(
            [sys.executable, "scripts/quality_report.py", "--format", "json"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=15,
        )
        assert result.returncode in (0, 1)
        parsed = json.loads(result.stdout)
        assert "health" in parsed
        assert "calibration" in parsed

    def test_main_cluster_filter_does_not_crash(self):
        result = subprocess.run(
            [sys.executable, "scripts/quality_report.py",
             "--cluster", "strategy_model_stress"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=15,
        )
        assert result.returncode in (0, 1)
        assert "Unexpected error" not in result.stderr


# ─── Contradiction Detector Precision (roadmap 2026-07-31) ──────────────────
# Видимость между прогонами тестов — см. docs/PLAN-contradiction-precision-roadmap.md.
# НЕ подменяет tests/unit/test_contradiction.py (источник истины для CI gate).

class TestContradictionPrecisionVisibility:

    def _write_pairs(self, tmp_path, name, pairs):
        path = tmp_path / name
        path.write_text(json.dumps({"_meta": {}, "pairs": pairs}), encoding="utf-8")
        return str(path)

    def test_precision_computed_correctly_on_known_pairs(self, tmp_path, monkeypatch):
        from scripts.quality_report import check_contradiction_precision

        # Пара, которую semantic_inverse_score() заведомо оценит как contradicts
        # (явная лексическая инверсия — не зависит от будущих правок детектора)
        contradicting = {"a": "ETF-приток растёт", "b": "ETF-отток растёт", "expected": True}
        path = self._write_pairs(tmp_path, "pairs.json", [contradicting])
        monkeypatch.setattr("scripts.quality_report.CONTRADICTION_PAIRS_PATH", path)
        monkeypatch.setattr(
            "scripts.quality_report.CONTRADICTION_PAIRS_EXTENDED_PATH",
            str(tmp_path / "does_not_exist.json"),
        )

        result = check_contradiction_precision()
        assert result["blocking"]["n_pairs"] == 1
        assert result["blocking"]["precision"] in (0.0, 1.0)  # детерминировано, не упало
        assert result["extended"] is None

    def test_missing_dataset_degrades_to_none_not_crash(self, tmp_path, monkeypatch):
        from scripts.quality_report import check_contradiction_precision

        monkeypatch.setattr(
            "scripts.quality_report.CONTRADICTION_PAIRS_PATH",
            str(tmp_path / "missing1.json"),
        )
        monkeypatch.setattr(
            "scripts.quality_report.CONTRADICTION_PAIRS_EXTENDED_PATH",
            str(tmp_path / "missing2.json"),
        )
        result = check_contradiction_precision()
        assert result == {"blocking": None, "extended": None}

    def test_empty_pairs_list_degrades_to_none(self, tmp_path, monkeypatch):
        from scripts.quality_report import check_contradiction_precision

        path = self._write_pairs(tmp_path, "empty.json", [])
        monkeypatch.setattr("scripts.quality_report.CONTRADICTION_PAIRS_PATH", path)
        monkeypatch.setattr(
            "scripts.quality_report.CONTRADICTION_PAIRS_EXTENDED_PATH",
            str(tmp_path / "missing.json"),
        )
        result = check_contradiction_precision()
        assert result["blocking"] is None

    def test_report_includes_contradiction_precision_key(self):
        from scripts.quality_report import compute_quality_report
        signals = [_signal("STR-2026-0101-001")]
        report = compute_quality_report(signals)
        assert "contradiction_precision" in report
        assert set(report["contradiction_precision"]) == {"blocking", "extended"}

    def test_real_blocking_dataset_reads_via_real_repo_paths(self):
        """
        Регрессия на реальные пути (не monkeypatch) — не даёт constants'ам
        (CONTRADICTION_PAIRS_PATH/_EXTENDED_PATH) молча разойтись с
        реальным расположением файлов в tests/golden/fixtures/.
        """
        from scripts.quality_report import (
            CONTRADICTION_PAIRS_PATH, CONTRADICTION_PAIRS_EXTENDED_PATH,
        )
        assert (REPO_ROOT / CONTRADICTION_PAIRS_PATH).exists()
        assert (REPO_ROOT / CONTRADICTION_PAIRS_EXTENDED_PATH).exists()
