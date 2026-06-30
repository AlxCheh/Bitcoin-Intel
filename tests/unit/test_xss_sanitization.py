"""
tests/unit/test_xss_sanitization.py
Bitcoin Intel — регрессионный тест XSS-защиты (B2 ARR v3, SECURITY.md T1).

index.html — единственный файл сайта (CLAUDE.md), поэтому sanitize() и
highlightEntities() живут как inline JS внутри index.html, а не как отдельный
импортируемый модуль. Этот тест извлекает РЕАЛЬНЫЙ исходный код этих функций
прямо из index.html (тем же способом, каким он будет исполняться в браузере)
и запускает его через Node.js — это проверяет именно то, что физически
задеплоено на сайт, а не отдельную копию логики, которая могла бы разойтись
с production-кодом.

Требует Node.js в PATH (доступен на GitHub Actions ubuntu-latest по умолчанию).
"""
import re
import json
import subprocess
import shutil
from pathlib import Path

import pytest

REPO_ROOT  = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"

NODE_AVAILABLE = shutil.which("node") is not None


def _extract_function(html: str, signature: str) -> str:
    """
    Извлекает тело функции `function <signature> {...}` из index.html по
    балансу фигурных скобок (устойчиво к любому уровню отступа закрывающей
    скобки — regex с фиксированным отступом однажды уже обрезал
    synthesizeNarrativeAdvanced на первой вложенной '}' с совпадающим
    отступом, см. tests/unit/test_uncertainty_indicator.py).
    """
    base_name = signature.split("(")[0].strip()
    start = html.find(f"function {base_name}")
    assert start != -1, f"Function '{signature}' not found in index.html — was it renamed or removed?"
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
                return html[start:i + 1]
        i += 1
    raise AssertionError(f"Unbalanced braces while extracting '{signature}'")


def _run_js(js_code: str) -> dict:
    """Запускает JS-сниппет через node и возвращает распарсенный JSON из stdout."""
    result = subprocess.run(
        ["node", "-e", js_code],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, f"Node execution failed:\n{result.stderr}"
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def sanitize_and_highlight_source() -> str:
    """Реальный исходник sanitize() + highlightEntities() из index.html."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    sanitize_fn   = _extract_function(html, "sanitize(str)")
    highlight_fn  = _extract_function(html, "highlightEntities(text)")
    return sanitize_fn + "\n\n" + highlight_fn


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestXSSSanitization:
    """B2 ARR v3: данные сигналов/сущностей не должны исполняться как HTML/JS."""

    def test_sanitize_escapes_script_payload(self, sanitize_and_highlight_source):
        """Классический XSS-payload полностью обезврежен."""
        js = sanitize_and_highlight_source + """
const out = sanitize('<img src=x onerror=alert(1)>');
console.log(JSON.stringify({ out }));
"""
        result = _run_js(js)
        assert "<img" not in result["out"]
        assert "&lt;img" in result["out"]
        assert "onerror" in result["out"]  # текст остаётся, но не как тег

    def test_sanitize_escapes_all_five_special_chars(self, sanitize_and_highlight_source):
        """&, <, >, \", ' — все пять экранируются."""
        js = sanitize_and_highlight_source + """
const out = sanitize(`&<>"'`);
console.log(JSON.stringify({ out }));
"""
        result = _run_js(js)
        assert result["out"] == "&amp;&lt;&gt;&quot;&#x27;"

    def test_sanitize_handles_null_and_undefined(self, sanitize_and_highlight_source):
        """null/undefined → пустая строка, не исключение."""
        js = sanitize_and_highlight_source + """
console.log(JSON.stringify({
    n: sanitize(null),
    u: sanitize(undefined),
    num: sanitize(123),
}));
"""
        result = _run_js(js)
        assert result["n"] == ""
        assert result["u"] == ""
        assert result["num"] == "123"

    def test_sanitize_idempotent_on_plain_text(self, sanitize_and_highlight_source):
        """Обычный текст без спецсимволов не искажается."""
        js = sanitize_and_highlight_source + """
const text = 'ETF-приток создаёт структурный спрос на BTC';
console.log(JSON.stringify({ out: sanitize(text), original: text }));
"""
        result = _run_js(js)
        assert result["out"] == result["original"]

    def test_highlight_entities_blocks_xss_while_preserving_entity_span(
        self, sanitize_and_highlight_source
    ):
        """
        Регрессия для T1 SECURITY.md: вредоносный payload в тексте сигнала не
        исполняется как HTML, а легитимное упоминание сущности (Strategy)
        всё ещё подсвечивается через <span data-entity-id>.
        """
        js = sanitize_and_highlight_source + """
const ENTITIES = [{ id: 'strategy', name: 'Strategy' }];
const payload = '<img src=x onerror=alert(1)> Strategy накапливает BTC';
const out = highlightEntities(payload);
console.log(JSON.stringify({ out }));
"""
        result = _run_js(js)
        assert "<img" not in result["out"], "XSS payload must not survive as a real tag"
        assert 'data-entity-id="strategy"' in result["out"], (
            "Legitimate entity highlighting must still work after sanitization"
        )
        assert "<span class=\"entity-link\"" in result["out"]

    def test_highlight_entities_sanitizes_even_without_entities(
        self, sanitize_and_highlight_source
    ):
        """Если ENTITIES пуст — highlightEntities всё равно обязана санитизировать (ранний return не должен пропускать XSS)."""
        js = sanitize_and_highlight_source + """
const ENTITIES = [];
const out = highlightEntities('<script>alert(1)</script>');
console.log(JSON.stringify({ out }));
"""
        result = _run_js(js)
        assert "<script>" not in result["out"]
        assert "&lt;script&gt;" in result["out"]


def test_all_signal_text_fields_pass_through_sanitize_or_highlight():
    """
    Статическая проверка: каждое поле сигнала, которое в index.html вставляется
    через innerHTML (signal, context, caveat, source, data, catLabel,
    theory_ref), обёрнуто либо sanitize(...), либо highlightEntities(...)
    (которая сама вызывает sanitize внутри).

    Эта проверка — защита от регрессии: если кто-то добавит новое поле сигнала
    в innerHTML без оборачивания, тест укажет на конкретную непрошедшую строку.
    """
    html = INDEX_HTML.read_text(encoding="utf-8")

    # Паттерны небезопасной прямой вставки — поле сигнала сразу после '+' без
    # sanitize(...)/highlightEntities(...) перед закрывающей кавычкой/конкатенацией.
    unsafe_patterns = [
        r"\+\s*s\.signal\s*\+",
        r"\+\s*s\.context\s*\+",
        r"\+\s*s\.caveat\s*\+",
        r"\+\s*s\.source\s*\+",
        r"\+\s*s\.catLabel\s*\+",
        r"\+\s*s\.theory_ref\s*\+",
        r"\+\s*e\.name\s*\+",
        r"\+\s*e\.summary\s*\+",
    ]
    violations = []
    for pattern in unsafe_patterns:
        if re.search(pattern, html):
            violations.append(pattern)

    assert not violations, (
        f"Found unwrapped signal/entity field(s) directly concatenated into "
        f"innerHTML-bound strings (must go through sanitize() or "
        f"highlightEntities()): {violations}"
    )
