"""
tests/unit/test_generate_dashboard.py
MON05 — юнит-тесты render_dashboard_markdown().

Тестирует чистую функцию dict → str напрямую, не запускает
compute_quality_report() и не трогает файлы — быстро, изолированно.
"""
from scripts.generate_dashboard import render_dashboard_markdown

VALID_REPORT = {
    "generated_at": "2026-07-02",
    "cluster_filter": None,
    "total_signals": 10,
    "coverage": {"tension": 1.0, "macro_implication": 0.9, "context": 1.0, "caveat": 0.8},
    "freshness": {"last_30_days": 0.7, "last_90_days": 1.0},
    "quality": {"tension_formula_valid": 0.95, "signals_with_links": 0.6},
    "distribution": {
        "by_dir": {"pos": 5, "neg": 3, "neu": 2},
        "by_cluster": {"cluster_a": 6, "cluster_b": 4},
        "by_weight": {"primary": 8, "media": 2},
        "by_narrative_role": {"trigger": 2, "complication": 5, "background": 3},
    },
    "health": {"score": 87.5, "grade": "A", "max": 100},
    "calibration": {"synthesis_count": 12, "threshold": 30, "ready": False, "remaining": 18},
}


def test_error_report_renders_warning():
    result = render_dashboard_markdown({"error": "no signals", "total": 0, "cluster": "x"})
    assert "⚠" in result
    assert "no signals" in result


def test_valid_report_contains_health_score():
    result = render_dashboard_markdown(VALID_REPORT)
    assert "87.5/100" in result
    assert "Grade A" in result


def test_valid_report_contains_signal_count():
    result = render_dashboard_markdown(VALID_REPORT)
    assert "10" in result
    assert "2026-07-02" in result


def test_calibration_not_ready_shows_remaining():
    result = render_dashboard_markdown(VALID_REPORT)
    assert "18 до порога" in result


def test_calibration_ready_shows_checkmark():
    report = dict(VALID_REPORT)
    report["calibration"] = {"synthesis_count": 30, "threshold": 30, "ready": True, "remaining": 0}
    result = render_dashboard_markdown(report)
    assert "✅ готово" in result


def test_distribution_clusters_present():
    result = render_dashboard_markdown(VALID_REPORT)
    assert "cluster_a: 6" in result
    assert "cluster_b: 4" in result


def test_grade_emoji_varies_by_grade():
    for grade, expected_emoji in [("A", "🟢"), ("B", "🟡"), ("C", "🟠"), ("D", "🔴")]:
        report = dict(VALID_REPORT)
        report["health"] = {"score": 50.0, "grade": grade, "max": 100}
        result = render_dashboard_markdown(report)
        assert expected_emoji in result


def test_output_ends_with_newline():
    result = render_dashboard_markdown(VALID_REPORT)
    assert result.endswith("\n")
