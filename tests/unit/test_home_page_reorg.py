"""
tests/unit/test_home_page_reorg.py
Bitcoin Intel — regression: price chart, cycle phase, and latest-blocks
panels must live on their thematic tabs (МЕТРИКИ/ПУЛЫ), not on ОБЗОР —
2026-08-16 home page reorg. These elements are NOT duplicated anywhere
(confirmed via grep before this change — earlier design draft wrongly
assumed duplication) — relocating, not deleting, is required or the
features are lost from the site entirely.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _section_range(html: str, tab_id: str) -> tuple[int, int]:
    start = html.find(f'id="{tab_id}"')
    assert start != -1, f'Секция id="{tab_id}" не найдена'
    end = html.find("</section>", start)
    assert end != -1, f"Закрывающий </section> для {tab_id} не найден"
    return start, end


def test_price_chart_and_cycle_phase_live_on_analytics_not_home():
    html = INDEX_HTML.read_text(encoding="utf-8")
    home_start, home_end = _section_range(html, "tab-home")
    analytics_start, analytics_end = _section_range(html, "tab-analytics")

    assert 'id="price-chart-wrap"' not in html[home_start:home_end]
    assert 'class="dash-cycle"' not in html[home_start:home_end]
    assert 'id="price-chart-wrap"' in html[analytics_start:analytics_end]
    assert 'class="dash-cycle"' in html[analytics_start:analytics_end]


def test_latest_blocks_panel_lives_on_pools_not_home():
    html = INDEX_HTML.read_text(encoding="utf-8")
    home_start, home_end = _section_range(html, "tab-home")
    pools_start, pools_end = _section_range(html, "tab-pools")

    assert 'id="latest-blocks-panel"' not in html[home_start:home_end]
    assert 'id="latest-blocks-panel"' in html[pools_start:pools_end]


def test_trigger_tab_data_still_populates_relocated_panels():
    """
    fetchProdCost()/initPriceChart() must fire when opening МЕТРИКИ (not
    just ОБЗОР) now that the panels they populate live there — otherwise
    a user landing directly on analytics (e.g. restored last-active-tab
    from localStorage) sees empty panels until they visit home first.
    """
    src = (REPO_ROOT / "js" / "app-main.js").read_text(encoding="utf-8")
    marker = "function triggerTabData(id) {"
    start = src.find(marker)
    assert start != -1
    end = src.find("\n}", start)
    body = src[start:end]

    analytics_line_start = body.find("if (id === 'analytics')")
    analytics_line_end = body.find("\n", analytics_line_start)
    analytics_line = body[analytics_line_start:analytics_line_end]

    assert "fetchProdCost" in analytics_line, (
        "triggerTabData() для 'analytics' обязан вызывать fetchProdCost() — "
        "график цены и фаза цикла теперь монтируются на этой вкладке"
    )
    assert "initPriceChart" in analytics_line


def test_home_has_definition_banner():
    html = INDEX_HTML.read_text(encoding="utf-8")
    home_start, home_end = _section_range(html, "tab-home")
    home_html = html[home_start:home_end]
    assert 'id="dash-definition"' in home_html
    assert "Bitcoin Intel" in home_html
    assert "нарративного анализа" in home_html


def test_ticker_has_price_span():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="dash-status-price"' in html


def test_render_dash_status_updates_price_span():
    import shutil
    import json as json_module
    from tests.conftest import extract_js_function, run_node_js
    if not shutil.which("node"):
        return
    src = (REPO_ROOT / "js" / "app-main.js").read_text(encoding="utf-8")
    fn = extract_js_function(src, "renderDashStatus")
    js = f"""
{fn}
var dashBtcPrice = 63224;
var dashProdCost = 81000;
const SIGNALS = [{{dir:'pos'}}, {{dir:'neg'}}];
const registry = {{
  'dash-status-phase': {{ textContent: '' }},
  'dash-status-ratio': {{ textContent: '' }},
  'dash-status-price': {{ textContent: '' }},
  'dash-status-pos': {{ textContent: '' }},
  'dash-status-neg': {{ textContent: '' }},
  'dash-status-neu': {{ textContent: '' }},
  'dash-phase': {{ textContent: '' }},
  'dash-ratio': {{ textContent: '' }},
  'dash-top3-list': {{ innerHTML: '' }}
}};
const document = {{ getElementById: function(id) {{ return registry[id] || null; }} }};
function calcCyclePhase(price, cost) {{ return {{ phase: 'ДНО' }}; }}
function renderDashTop3() {{}}
renderDashStatus();
console.log(JSON.stringify({{ price: registry['dash-status-price'].textContent }}));
"""
    result = run_node_js(js)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"
    out = json_module.loads(result.stdout)
    assert "63" in out["price"], "Тикер обязан показать текущую цену BTC из dashBtcPrice"


def test_mini_list_container_exists_in_home():
    html = INDEX_HTML.read_text(encoding="utf-8")
    home_start, home_end = _section_range(html, "tab-home")
    home_html = html[home_start:home_end]
    assert 'id="dash-narratives-mini-list"' in home_html


def test_render_narrative_mini_row_returns_html_string(tmp_path):
    import shutil
    import json as json_module
    from tests.conftest import extract_js_function, run_node_js
    if not shutil.which("node"):
        return
    src = (REPO_ROOT / "js" / "app-main.js").read_text(encoding="utf-8")
    fn = extract_js_function(src, "renderNarrativeMiniRow")
    js = f"""
function sanitize(s) {{ return String(s == null ? '' : s); }}
const CLUSTER_LABELS = {{ etf_institutional_flow: '📊 ETF: ИНСТИТУЦИОНАЛЬНЫЙ ПОТОК' }};
{fn}
const cl = {{ signals: [1,2,3], pos: 2, neg: 1, neu: 0 }};
const score = {{ total: 213 }};
const html = renderNarrativeMiniRow('etf_institutional_flow', cl, score);
console.log(JSON.stringify({{
  isString: typeof html === 'string',
  hasLabel: html.includes('ETF'),
  hasScore: html.includes('213'),
  hasCount: html.includes('3'),
  hasDataCl: html.includes('data-cl=\\"etf_institutional_flow\\"')
}}));
"""
    result = run_node_js(js)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"
    out = json_module.loads(result.stdout)
    assert out["isString"] is True
    assert out["hasLabel"] is True
    assert out["hasScore"] is True
    assert out["hasCount"] is True
    assert out["hasDataCl"] is True


def test_explore_tiles_container_exists_in_home():
    html = INDEX_HTML.read_text(encoding="utf-8")
    home_start, home_end = _section_range(html, "tab-home")
    assert 'id="dash-explore-tiles"' in html[home_start:home_end]


def test_render_explore_tiles_covers_all_four_real_clusters():
    import shutil
    import json as json_module
    from tests.conftest import extract_js_function, run_node_js
    if not shutil.which("node"):
        return
    src = (REPO_ROOT / "js" / "app-main.js").read_text(encoding="utf-8")
    fn = extract_js_function(src, "renderExploreTiles")
    js = f"""
{fn}
console.log(JSON.stringify({{ html: renderExploreTiles() }}));
"""
    result = run_node_js(js)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"
    html = json_module.loads(result.stdout)["html"]
    for cluster_key in ["live", "knowledge", "macro", "analysis"]:
        assert "selectCluster('" + cluster_key + "')" in html, (
            f"Плитка для кластера '{cluster_key}' отсутствует или не вызывает selectCluster()"
        )
    assert "toc-card-grid" in html
    assert "toc-card" in html
