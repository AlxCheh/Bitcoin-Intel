"""
tests/unit/test_minority_anchor_badge.py
Bitcoin Intel — тесты buildMinorityAnchorWarning() (N07 ARR v3).

КОНТЕКСТ
--------
Фаза B (scripts/synthesizer.py, PR #399, 2026-07) добавила diagnostic-поля
entity_count / anchor_entity_share / is_minority_anchor в SynthesisResult —
но rebuild_synthesis.py их отбрасывал при записи data/synthesis_cache.json,
и index.html их нигде не отображал. Итог: победивший tension кластера мог
представлять периферийную сущность (напр. 2 сигнала из 21), а читатель об
этом не узнавал. buildMinorityAnchorWarning() — чистая функция, строящая
предупреждение из уже посчитанных полей; ничего не меняет в выборе
tension/anchor (Immutability Policy, docs/NIES.md AD-7 не затронут).

Извлекает реальный исходник из index.html (паттерн test_uncertainty_indicator.py).
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT  = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
NODE_AVAILABLE = shutil.which("node") is not None


def _extract_function(html: str, signature: str) -> str:
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
def minority_warning_source() -> str:
    html = INDEX_HTML.read_text(encoding="utf-8")
    return _extract_function(html, "buildMinorityAnchorWarning")


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestBuildMinorityAnchorWarning:

    def test_no_synthesis_returns_null(self, minority_warning_source):
        assert _run(minority_warning_source, "buildMinorityAnchorWarning(null)") is None

    def test_undefined_synthesis_returns_null(self, minority_warning_source):
        assert _run(minority_warning_source, "buildMinorityAnchorWarning(undefined)") is None

    def test_is_minority_anchor_false_returns_null(self, minority_warning_source):
        result = _run(
            minority_warning_source,
            'buildMinorityAnchorWarning({is_minority_anchor: false, anchor_entity_share: 0.867, entity_count: 2})',
        )
        assert result is None

    def test_missing_is_minority_anchor_field_returns_null(self, minority_warning_source):
        """JS live-фоллбэк не считает entity-diversity — отсутствие поля не должно падать."""
        result = _run(minority_warning_source, "buildMinorityAnchorWarning({tension: 'X vs Y'})")
        assert result is None

    def test_minority_anchor_true_produces_warning_with_percentage(self, minority_warning_source):
        """Воспроизводит реальный кейс btc_treasury_competition: 2 из 21 (≈9.5%), 13 сущностей."""
        result = _run(
            minority_warning_source,
            'buildMinorityAnchorWarning({is_minority_anchor: true, anchor_entity_share: 0.095, entity_count: 13})',
        )
        assert result is not None
        assert "10%" in result  # Math.round(9.5) == 10 в JS
        assert "13" in result

    def test_minority_anchor_true_without_entity_count_still_warns(self, minority_warning_source):
        result = _run(
            minority_warning_source,
            'buildMinorityAnchorWarning({is_minority_anchor: true, anchor_entity_share: 0.1})',
        )
        assert result is not None
        assert "10%" in result

    def test_warning_text_mentions_periphery(self, minority_warning_source):
        result = _run(
            minority_warning_source,
            'buildMinorityAnchorWarning({is_minority_anchor: true, anchor_entity_share: 0.095, entity_count: 13})',
        )
        assert "периферийная" in result
