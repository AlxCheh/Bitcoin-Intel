"""
tests/unit/test_saylor_series_section.py
Bitcoin Intel — regression: topics with target_group must NOT be picked up
by the generic renderTheoryTopics() scanner (they'd otherwise fall into
theory-topics-container, which physically lives on the MACROCONTEXT tab —
see docs/superpowers/specs/2026-08-16-saylor-series-theory-section-design.md).
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
def render_topics_source() -> str:
    src = APP_MAIN_JS.read_text(encoding="utf-8")
    funcs = [
        extract_js_function(src, "sanitize"),
        extract_js_function(src, "sanitizeStrong"),
        extract_js_function(src, "sourceFooterHtml"),
        extract_js_function(src, "renderAccItem"),
        extract_js_function(src, "renderTheoryTopic"),
        extract_js_function(src, "renderTheoryTopics"),
    ]
    return "\n\n".join(funcs)


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
def test_target_group_topic_is_not_mounted_by_generic_scanner(render_topics_source):
    js = render_topics_source + """
const THEORY_TOPICS = [
  { id: 'saylor-series-01', target_group: 'saylor-series', panel_title: 'X', panel_tag: 'Y' },
  { id: 'theory-example', panel_title: 'Обычный топик', panel_tag: 'Z' }
];

const registry = {};
function makeMount(id) { return { innerHTML: '' }; }
const containerEl = { set innerHTML(html) {
  this._html = html;
  const re = /id="([\\w-]+)"/g;
  let m;
  while ((m = re.exec(html))) { if (!registry[m[1]]) registry[m[1]] = makeMount(m[1]); }
}, get innerHTML() { return this._html || ''; } };
registry['theory-topics-container'] = containerEl;

const document = { getElementById: function(id) { return registry[id] || null; } };
renderTheoryTopics();
console.log(JSON.stringify({
  saylorMounted: !!registry['saylor-series-01'],
  exampleMounted: !!registry['theory-example']
}));
"""
    result = run_node_js(js)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"
    out = json.loads(result.stdout)
    assert out["saylorMounted"] is False, (
        "Топик с target_group не должен попадать в общий контейнер "
        "theory-topics-container — он физически лежит на вкладке MACROCONTEXT"
    )
    assert out["exampleMounted"] is True, (
        "Обычный топик без target_group должен по-прежнему рендериться "
        "generic-сканером — регрессия не должна ломать существующее поведение"
    )


@pytest.fixture(scope="module")
def render_saylor_source() -> str:
    src = APP_MAIN_JS.read_text(encoding="utf-8")
    funcs = [
        extract_js_function(src, "sanitize"),
        extract_js_function(src, "sanitizeStrong"),
        extract_js_function(src, "sourceFooterHtml"),
        extract_js_function(src, "renderAccItem"),
        extract_js_function(src, "renderTheoryTopic"),
        extract_js_function(src, "renderSaylorSeriesSection"),
    ]
    return "\n\n".join(funcs)


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
def test_render_saylor_series_section_builds_index_and_episode_panels(render_saylor_source):
    js = render_saylor_source + """
const THEORY_TOPICS = [
  {
    id: 'saylor-series-01', target_group: 'saylor-series', episode_number: 1,
    panel_title: 'Эпизод про огонь', panel_tag: 'SAYLOR SERIES · 01',
    intro: 'Интро', items: [{ icon: '01', label: 'Огонь', paragraphs: ['текст'] }]
  },
  { id: 'theory-example', panel_title: 'Не эпизод', panel_tag: 'X' }
];

const registry = {};
function makeMount(id) { return { innerHTML: '' }; }
registry['theory-saylor-series-mount'] = makeMount('theory-saylor-series-mount');
const document = { getElementById: function(id) { return registry[id] || null; } };
renderSaylorSeriesSection();
const html = registry['theory-saylor-series-mount'].innerHTML;
console.log(JSON.stringify({
  hasIndexCard: html.includes('Эпизод про огонь'),
  hasEpisodePanel: html.includes('id=\\"saylor-series-01\\"'),
  hasEpisodeBody: html.includes('Огонь') && html.includes('текст'),
  excludesNonEpisode: !html.includes('Не эпизод')
}));
"""
    result = run_node_js(js)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"
    out = json.loads(result.stdout)
    assert out["hasIndexCard"] is True
    assert out["hasEpisodePanel"] is True
    assert out["hasEpisodeBody"] is True
    assert out["excludesNonEpisode"] is True
