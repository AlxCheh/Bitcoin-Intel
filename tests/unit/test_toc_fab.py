"""
tests/unit/test_toc_fab.py
Bitcoin Intel — regression: плавающая кнопка «↑ К содержанию» (js/app-early.js).
Показывается только на вкладках с оглавлением (theory/macrocontext/lightning)
после скролла ниже порога; клик скроллит к {currentTabId}-toc. См. запрос
пользователя 2026-08-16 — кнопка нужна после карточной реорганизации ТЕОРИИ,
где панели (особенно детальный вид эпизода Saylor Series) стали снова длинными.
"""
import json
import re
import shutil
from pathlib import Path

import pytest
from tests.conftest import extract_js_function, run_node_js

REPO_ROOT = Path(__file__).parent.parent.parent
APP_EARLY_JS = REPO_ROOT / "js" / "app-early.js"
NODE_AVAILABLE = shutil.which("node") is not None


@pytest.fixture(scope="module")
def toc_fab_source() -> str:
    src = APP_EARLY_JS.read_text(encoding="utf-8")
    # updateTocFabVisibility() читает эти два module-level var — extract_js_function
    # вытаскивает только тела function {...}, не соседние var-объявления.
    consts_match = re.search(
        r"var TOC_FAB_TABS = \[.*?\];\nvar TOC_FAB_SCROLL_THRESHOLD = \d+;",
        src, re.DOTALL,
    )
    assert consts_match, "TOC_FAB_TABS/TOC_FAB_SCROLL_THRESHOLD не найдены в app-early.js — переименованы?"
    funcs = [
        consts_match.group(0),
        extract_js_function(src, "updateTocFabVisibility"),
        extract_js_function(src, "scrollToActiveToc"),
    ]
    return "\n\n".join(funcs)


def _mock_dom(current_tab_id: str, scroll_top: int) -> str:
    return f"""
var currentTabId = {json.dumps(current_tab_id)};
const fab = {{ style: {{ display: '' }} }};
const scrollEl = {{ scrollTop: {scroll_top} }};
const registry = {{ 'toc-fab': fab, '.app-scroll': scrollEl }};
const document = {{
  getElementById: function(id) {{ return registry[id] || null; }},
  querySelector: function(sel) {{ return registry[sel] || null; }}
}};
"""


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestUpdateTocFabVisibility:

    @pytest.mark.parametrize("tab_id", ["theory", "macrocontext", "lightning"])
    def test_shows_on_toc_tabs_past_threshold(self, toc_fab_source, tab_id):
        js = toc_fab_source + _mock_dom(tab_id, 500) + """
updateTocFabVisibility();
console.log(JSON.stringify({ display: fab.style.display }));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        assert json.loads(result.stdout)["display"] == "flex"

    @pytest.mark.parametrize("tab_id", ["theory", "macrocontext", "lightning"])
    def test_hides_on_toc_tabs_before_threshold(self, toc_fab_source, tab_id):
        js = toc_fab_source + _mock_dom(tab_id, 50) + """
updateTocFabVisibility();
console.log(JSON.stringify({ display: fab.style.display }));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        assert json.loads(result.stdout)["display"] == "none"

    @pytest.mark.parametrize("tab_id", ["home", "market", "tech", "pools", "signals"])
    def test_hides_on_non_toc_tabs_even_past_threshold(self, toc_fab_source, tab_id):
        """Скролл далеко вниз на вкладке без оглавления не должен показывать кнопку."""
        js = toc_fab_source + _mock_dom(tab_id, 900) + """
updateTocFabVisibility();
console.log(JSON.stringify({ display: fab.style.display }));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        assert json.loads(result.stdout)["display"] == "none"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestScrollToActiveToc:

    def test_scrolls_to_toc_matching_current_tab(self, toc_fab_source):
        js = toc_fab_source + """
var currentTabId = 'macrocontext';
let scrolledCalls = [];
const toc = { scrollIntoView: function(opts) { scrolledCalls.push(opts); } };
const registry = { 'macrocontext-toc': toc };
const document = { getElementById: function(id) { return registry[id] || null; } };
scrollToActiveToc();
console.log(JSON.stringify({ calls: scrolledCalls }));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        calls = json.loads(result.stdout)["calls"]
        assert len(calls) == 1
        assert calls[0]["behavior"] == "smooth"

    def test_does_not_crash_if_toc_missing(self, toc_fab_source):
        js = toc_fab_source + """
var currentTabId = 'home';
const document = { getElementById: function(id) { return null; } };
scrollToActiveToc();
console.log(JSON.stringify({ ok: true }));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        assert json.loads(result.stdout)["ok"] is True
