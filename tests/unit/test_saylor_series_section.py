"""
tests/unit/test_saylor_series_section.py
Bitcoin Intel — regression: topics with target_group must NOT be picked up
by the generic renderTheoryTopics() scanner (they'd otherwise fall into
theory-topics-container, which physically lives on the MACROCONTEXT tab —
see docs/superpowers/specs/2026-08-16-saylor-series-theory-section-design.md).

Also covers related_episodes rendering (added 2026-08-16 with episode 2 —
deliberately deferred in the original design until a real second episode
existed to link to, per the "honest test only" discipline used elsewhere
in this project).
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


@pytest.fixture(scope="module")
def render_topic_source() -> str:
    src = APP_MAIN_JS.read_text(encoding="utf-8")
    funcs = [
        extract_js_function(src, "sanitize"),
        extract_js_function(src, "sanitizeStrong"),
        extract_js_function(src, "sourceFooterHtml"),
        extract_js_function(src, "renderAccItem"),
        extract_js_function(src, "renderTheoryTopic"),
    ]
    return "\n\n".join(funcs)


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestRelatedEpisodes:

    def test_topic_without_related_episodes_has_no_block(self, render_topic_source):
        js = render_topic_source + """
const THEORY_TOPICS = [{ id: 'saylor-series-01', panel_title: 'Эпизод 1', panel_tag: 'X' }];
console.log(JSON.stringify({ html: renderTheoryTopic(THEORY_TOPICS[0]) }));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert "СВЯЗАННЫЕ ЭПИЗОДЫ" not in html

    def test_related_episode_renders_clickable_link_with_looked_up_title(self, render_topic_source):
        js = render_topic_source + """
const THEORY_TOPICS = [
  { id: 'saylor-series-01', panel_title: 'Огонь, праща и Рим', panel_tag: 'X' },
  { id: 'saylor-series-02', panel_title: 'Империи, сталь и антибиотики', panel_tag: 'Y', related_episodes: ['saylor-series-01'] }
];
console.log(JSON.stringify({ html: renderTheoryTopic(THEORY_TOPICS[1]) }));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert "СВЯЗАННЫЕ ЭПИЗОДЫ" in html
        assert "Огонь, праща и Рим" in html, "Заголовок связанного эпизода должен подтягиваться по id из THEORY_TOPICS, не показывать голый id"
        assert "onclick=\"document.getElementById('saylor-series-01').scrollIntoView" in html

    def test_related_episode_uses_established_badge_pattern(self, render_topic_source):
        """
        2026-08-16, найдено пользователем визуально ("оформлено криво"):
        .crosslink-arrow/.crosslink-text/.crosslink-target — старый паттерн
        БЕЗ единого правила CSS в текущей вёрстке (в index.html есть только
        .crosslink/.crosslink-text-col/.crosslink-cta). Прецедент, выбранный
        пользователем — .ep-fn-badge/-label/-cta (та же плашка, что
        "СВЯЗАННЫЕ ПАНЕЛИ ТЕОРИИ"/"СВЯЗАННЫЕ ФУНКЦИИ" в попапе сущности,
        js/app-main.js showEntityPopup()). Полный panel_title, без обрезки —
        так же, как в этих двух прецедентах.
        """
        js = render_topic_source + """
const THEORY_TOPICS = [
  { id: 'saylor-series-01', panel_title: 'Огонь, праща и Рим', panel_tag: 'X', episode_number: 1 },
  { id: 'saylor-series-02', panel_title: 'Империи, сталь и антибиотики', panel_tag: 'Y', related_episodes: ['saylor-series-01'] }
];
console.log(JSON.stringify({ html: renderTheoryTopic(THEORY_TOPICS[1]) }));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert 'class="ep-fn-badge"' in html
        assert 'class="ep-fn-badge-label">ЭПИЗОД 01<' in html
        assert 'class="ep-fn-badge-cta">Огонь, праща и Рим →<' in html
        assert "crosslink-arrow" not in html
        assert "crosslink-text" not in html
        assert "crosslink-target" not in html

    def test_related_episode_falls_back_to_raw_id_if_not_found(self, render_topic_source):
        """Не должно падать, если ссылка на ещё не существующий эпизод — просто некрасивый fallback, не краш."""
        js = render_topic_source + """
const THEORY_TOPICS = [
  { id: 'saylor-series-02', panel_title: 'Y', panel_tag: 'Y', related_episodes: ['saylor-series-03'] }
];
console.log(JSON.stringify({ html: renderTheoryTopic(THEORY_TOPICS[0]) }));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert "saylor-series-03" in html

    def test_related_episodes_block_positioned_before_essays_mount(self, render_topic_source):
        js = render_topic_source + """
const THEORY_TOPICS = [
  { id: 'saylor-series-01', panel_title: 'X', panel_tag: 'X' },
  {
    id: 'saylor-series-02', panel_title: 'Y', panel_tag: 'Y',
    items: [{ icon: '01', label: 'Пункт', paragraphs: ['текст'] }],
    related_episodes: ['saylor-series-01'],
    source_footer: 'ИСТОЧНИК: тест'
  }
];
console.log(JSON.stringify({ html: renderTheoryTopic(THEORY_TOPICS[1]) }));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        items_pos = html.find("Пункт")
        related_pos = html.find("СВЯЗАННЫЕ ЭПИЗОДЫ")
        mount_pos = html.find('id="saylor-series-02-essays"')
        footer_pos = html.find("ИСТОЧНИК: тест")
        assert items_pos < related_pos < mount_pos < footer_pos
