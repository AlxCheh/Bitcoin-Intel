"""
tests/unit/test_render_acc_item_lists.py
Bitcoin Intel — regression: renderAccItem() must support a bulleted list as
one element of item.paragraphs, alongside plain string paragraphs. Needed
for Saylor Series episode 1 ("Рим: система важнее героя" has a real 4-item
bulleted list in the user's source draft — see
docs/superpowers/specs/2026-08-16-saylor-series-theory-section-design.md).
Existing string-paragraph behavior must stay unchanged (backward compat —
every other THEORY_TOPICS.json/THEORY_ESSAYS.json item uses plain strings).
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
def render_acc_item_source() -> str:
    src = APP_MAIN_JS.read_text(encoding="utf-8")
    funcs = [
        extract_js_function(src, "sanitize"),
        extract_js_function(src, "sanitizeStrong"),
        extract_js_function(src, "renderAccItem"),
    ]
    return "\n\n".join(funcs)


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestRenderAccItemLists:

    def test_string_paragraph_still_renders_as_p(self, render_acc_item_source):
        js = render_acc_item_source + """
const item = { icon: '01', label: 'X', paragraphs: ['Обычный абзац'] };
console.log(JSON.stringify({ html: renderAccItem(item) }));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert '<p>Обычный абзац</p>' in html

    def test_list_paragraph_renders_as_ul_li(self, render_acc_item_source):
        js = render_acc_item_source + """
const item = {
  icon: '05', label: 'Рим',
  paragraphs: [
    'Вступление перед списком:',
    { list: ['<strong>Первый</strong> пункт.', '<strong>Второй</strong> пункт.'] },
    'Вывод после списка.'
  ]
};
console.log(JSON.stringify({ html: renderAccItem(item) }));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert '<ul' in html and '</ul>' in html
        assert html.count('<li') == 2
        assert '<strong>Первый</strong> пункт.' in html
        assert '<strong>Второй</strong> пункт.' in html
        intro_pos = html.find('Вступление перед списком')
        list_pos = html.find('<ul')
        outro_pos = html.find('Вывод после списка')
        assert intro_pos < list_pos < outro_pos

    def test_list_items_go_through_sanitize_strong(self, render_acc_item_source):
        """Список — не лазейка мимо экранирования: <script> в пункте списка обязан быть обезврежен."""
        js = render_acc_item_source + """
const item = { icon: '01', label: 'X', paragraphs: [{ list: ['<script>alert(1)</script>текст'] }] };
console.log(JSON.stringify({ html: renderAccItem(item) }));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert '<script>' not in html
