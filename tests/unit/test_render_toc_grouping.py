"""
tests/unit/test_render_toc_grouping.py
Bitcoin Intel — regression: renderTOC() must accept BOTH its original flat
array shape ([{target,title,subtitle}], used by macrocontext-toc and
lightning-toc) and a new grouped shape ([{group, items:[...]}], used by
theory-toc after the 2026-08-16 card reorg) — without the flat callers
needing any data changes. See
docs/superpowers/specs/2026-08-16-theory-tab-card-reorg-design.md.
"""
import json
import shutil
from pathlib import Path

import pytest
from tests.conftest import extract_js_function, run_node_js

REPO_ROOT = Path(__file__).parent.parent.parent
APP_MAIN_JS = REPO_ROOT / "js" / "app-main.js"
NODE_AVAILABLE = shutil.which("node") is not None


@pytest.fixture(scope="module")
def render_toc_source() -> str:
    src = APP_MAIN_JS.read_text(encoding="utf-8")
    funcs = [
        extract_js_function(src, "sanitize"),
        extract_js_function(src, "renderTOC"),
    ]
    return "\n\n".join(funcs)


def _mini_dom_js() -> str:
    return """
const registry = {};
function makeMount(id) { return { innerHTML: '' }; }
registry['toc-container'] = makeMount('toc-container');
const document = { getElementById: function(id) { return registry[id] || null; } };
"""


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestRenderTOCGrouping:

    def test_flat_array_renders_without_group_labels(self, render_toc_source):
        js = render_toc_source + _mini_dom_js() + """
renderTOC('toc-container', [
  { target: 'a', title: 'Alpha', subtitle: 'x' },
  { target: 'b', title: 'Beta', subtitle: 'y' }
]);
console.log(JSON.stringify({ html: registry['toc-container'].innerHTML }));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert 'toc-card-grid' in html
        assert 'toc-group-label' not in html
        assert 'Alpha' in html and 'Beta' in html
        assert '>2<' in html, "Счётчик СОДЕРЖАНИЕ должен показать 2 для плоского массива из 2 записей"

    def test_grouped_array_renders_group_labels_and_correct_total_count(self, render_toc_source):
        js = render_toc_source + _mini_dom_js() + """
renderTOC('toc-container', [
  { group: 'ОСНОВЫ', items: [
    { target: 'a', title: 'Alpha', subtitle: 'x' },
    { target: 'b', title: 'Beta', subtitle: 'y' }
  ]},
  { group: 'БЕЗОПАСНОСТЬ', items: [
    { target: 'c', title: 'Gamma', subtitle: 'z' }
  ]}
]);
console.log(JSON.stringify({ html: registry['toc-container'].innerHTML }));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert 'ОСНОВЫ' in html and 'БЕЗОПАСНОСТЬ' in html
        assert 'Alpha' in html and 'Beta' in html and 'Gamma' in html
        assert '>3<' in html, "Счётчик СОДЕРЖАНИЕ должен быть суммой items всех групп (2+1=3), не числом групп (2)"

    def test_grouped_array_numbers_cards_sequentially_across_groups(self, render_toc_source):
        js = render_toc_source + _mini_dom_js() + """
renderTOC('toc-container', [
  { group: 'A', items: [{ target: 'a', title: 'Alpha', subtitle: '' }] },
  { group: 'B', items: [{ target: 'b', title: 'Beta', subtitle: '' }] }
]);
console.log(JSON.stringify({ html: registry['toc-container'].innerHTML }));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        alpha_pos = html.find('Alpha')
        beta_pos = html.find('Beta')
        num01_pos = html.find('>01<')
        num02_pos = html.find('>02<')
        assert num01_pos != -1 and num02_pos != -1
        assert num01_pos < alpha_pos, "01 должен относиться к первой карточке (Alpha)"
        assert num02_pos < beta_pos, "02 должен относиться ко второй карточке (Beta), не начинаться заново с 01 в новой группе"

    def test_card_click_still_calls_uncollapse_and_scroll_to(self, render_toc_source):
        """Поведение клика не меняется — тот же uncollapseAndScrollTo(target), что был у строк."""
        js = render_toc_source + _mini_dom_js() + """
renderTOC('toc-container', [{ target: 'theory-money', title: 'X', subtitle: 'y' }]);
console.log(JSON.stringify({ html: registry['toc-container'].innerHTML }));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert "onclick=\"uncollapseAndScrollTo('theory-money')\"" in html
