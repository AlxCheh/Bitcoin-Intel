"""
tests/unit/test_uncertainty_indicator.py
Bitcoin Intel — тесты formatPhaseLabel() и buildUncertaintyWarnings() (N06, N04 ARR v3).

КОНТЕКСТ
--------
ARR v3 §N06 / N04: `phase` и `uncertainty` (из `handle_uncertainty()`,
scripts/synthesizer.py) присутствовали в `data/synthesis_cache.json`, но
нигде не отображались на UI — пользователь не мог отличить разрешённое
противоречие (phase=resolution) от активного конфликта, и не видел, что
confidence занижен из-за contested pos/neg баланса или устаревшего tension.

Извлекает реальный исходник из index.html (паттерн test_xss_sanitization.py).
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT  = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
NODE_AVAILABLE = shutil.which("node") is not None


def _extract_function(html: str, signature: str) -> str:
    """
    Извлекает полное тело function {signature}(...) {...} по балансу
    фигурных скобок — устойчиво к любому уровню отступа закрывающей скобки
    (в отличие от regex с фиксированным отступом, который однажды уже
    обрезал synthesizeNarrativeAdvanced на первой вложенной '}' с
    совпадающим отступом).
    """
    start_marker = f"function {signature}"
    start = html.find(start_marker)
    assert start != -1, f"Function '{signature}' not found in index.html"
    brace_open = html.find("{", start)
    assert brace_open != -1, f"No opening brace found for '{signature}'"
    depth = 0
    i = brace_open
    while i < len(html):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                return html[start:i + 1] + "\n"
        i += 1
    raise AssertionError(f"Unbalanced braces while extracting '{signature}'")


def _run(js_source: str, call: str):
    script = js_source + f"\nconsole.log(JSON.stringify({call}));"
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def phase_label_source() -> str:
    html = INDEX_HTML.read_text(encoding="utf-8")
    return _extract_function(html, "formatPhaseLabel")


@pytest.fixture(scope="module")
def uncertainty_warnings_source() -> str:
    html = INDEX_HTML.read_text(encoding="utf-8")
    return _extract_function(html, "buildUncertaintyWarnings")


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestFormatPhaseLabel:

    def test_resolution_phase_is_distinctly_labeled(self, phase_label_source):
        """N06: resolution должна визуально отличаться — отдельный цвет и текст."""
        result = _run(phase_label_source, "formatPhaseLabel('resolution')")
        assert result["label"] == "✓ РАЗРЕШЕНО"
        assert result["color"] == "var(--grn)"

    def test_active_phase_label(self, phase_label_source):
        result = _run(phase_label_source, "formatPhaseLabel('active')")
        assert result["label"]
        assert result["color"] != "var(--grn)"

    def test_tension_phase_label(self, phase_label_source):
        result = _run(phase_label_source, "formatPhaseLabel('tension')")
        assert result["label"]

    def test_structural_phase_label(self, phase_label_source):
        result = _run(phase_label_source, "formatPhaseLabel('structural')")
        assert result["label"]

    def test_all_four_phases_have_distinct_colors(self, phase_label_source):
        """N06: ни одна из 4 фаз не должна случайно совпасть цветом с другой."""
        phases = ["resolution", "active", "tension", "structural"]
        colors = [_run(phase_label_source, f"formatPhaseLabel('{p}')")["color"] for p in phases]
        assert len(set(colors)) == 4, f"Цвета фаз не уникальны: {dict(zip(phases, colors))}"

    def test_unknown_phase_does_not_crash(self, phase_label_source):
        result = _run(phase_label_source, "formatPhaseLabel('unknown_value')")
        assert result["label"] == ""

    def test_undefined_phase_does_not_crash(self, phase_label_source):
        result = _run(phase_label_source, "formatPhaseLabel(undefined)")
        assert result["label"] == ""


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestBuildUncertaintyWarnings:

    def test_no_uncertainty_returns_empty(self, uncertainty_warnings_source):
        result = _run(uncertainty_warnings_source, "buildUncertaintyWarnings({})")
        assert result == []

    def test_null_uncertainty_returns_empty(self, uncertainty_warnings_source):
        result = _run(uncertainty_warnings_source, "buildUncertaintyWarnings(null)")
        assert result == []

    def test_contested_direction_produces_warning(self, uncertainty_warnings_source):
        result = _run(
            uncertainty_warnings_source,
            'buildUncertaintyWarnings({direction: "contested"})',
        )
        assert len(result) == 1
        assert "ПРОТИВОРЕЧИВЫЕ" in result[0]

    def test_stale_tension_produces_warning_with_custom_label(self, uncertainty_warnings_source):
        result = _run(
            uncertainty_warnings_source,
            'buildUncertaintyWarnings({tension_stale: true, '
            '"tension_stale_label": "⚠ Кастомный текст устаревания"})',
        )
        assert result == ["⚠ Кастомный текст устаревания"]

    def test_stale_tension_without_custom_label_uses_default(self, uncertainty_warnings_source):
        result = _run(
            uncertainty_warnings_source, 'buildUncertaintyWarnings({tension_stale: true})'
        )
        assert len(result) == 1
        assert "устарел" in result[0]

    def test_both_contested_and_stale_produce_two_warnings(self, uncertainty_warnings_source):
        result = _run(
            uncertainty_warnings_source,
            'buildUncertaintyWarnings({direction: "contested", tension_stale: true})',
        )
        assert len(result) == 2

    def test_non_contested_direction_produces_no_warning(self, uncertainty_warnings_source):
        result = _run(
            uncertainty_warnings_source, 'buildUncertaintyWarnings({direction: "pos"})'
        )
        assert result == []


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestJSFallbackRationale:
    """N02 ARR v3: JS live-фоллбэк теперь тоже объясняет anchor-сигнал."""

    @pytest.fixture(scope="class")
    def synth_source(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        fresh = re.search(r"let FRESHNESS_FRESH_DAYS\s*=\s*(\d+);", html).group(1)
        recent = re.search(r"let FRESHNESS_RECENT_DAYS\s*=\s*(\d+);", html).group(1)
        globals_src = (
            f"const FRESHNESS_FRESH_DAYS = {fresh};\n"
            f"const FRESHNESS_RECENT_DAYS = {recent};\n"
        )
        return globals_src + _extract_function(html, "synthesizeNarrativeAdvanced")

    def test_rationale_present_and_mentions_anchor_id(self, synth_source):
        signals = [{
            "id": "TEST-001", "date": "2026-06-29", "weight": "primary",
            "narrative_role": "trigger", "tension": "X vs Y",
            "links": {"contradicts": []}, "dir": "pos", "cluster": "c",
        }]
        payload = json.dumps({"signals": signals})
        script = (
            synth_source
            + f"\nconst r = synthesizeNarrativeAdvanced('c', {payload});"
            + "\nconsole.log(JSON.stringify({rationale: r.rationale}));"
        )
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        parsed = json.loads(result.stdout)
        assert "TEST-001" in parsed["rationale"]
        assert "live-фоллбэк" in parsed["rationale"]
