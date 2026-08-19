"""
tests/unit/test_home_terminal_redesign.py
Bitcoin Intel — редизайн ОБЗОРА под терминал (Bloomberg/Arkham),
2026-08-19. Новые чистые (без DOM API) функции рендера карточки
нарратива и watchlist — тестируются через существующий Node-харнесс
(tests/conftest.py). DOM-сборка (renderNarrativeItem, renderWatchlist)
здесь не тестируется — использует document.createElement/querySelector,
недоступные в чистом Node; верифицируется вручную в браузере (см.
docs/superpowers/plans/2026-08-19-home-terminal-redesign.md).
"""
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def test_render_anchor_fields_html_shows_five_fields():
    import shutil
    import json as json_module
    from tests.conftest import extract_js_function, run_node_js
    if not shutil.which("node"):
        return
    src = (REPO_ROOT / "js" / "app-main.js").read_text(encoding="utf-8")
    fn = extract_js_function(src, "renderAnchorFieldsHtml")
    js = f"""
function sanitize(s) {{ return String(s == null ? '' : s); }}
{fn}
const anchor = {{ dir: 'neg', horizon: 'mid', weight: 'primary', narrative_role: 'complication', actor: 'government' }};
const html = renderAnchorFieldsHtml(anchor);
console.log(JSON.stringify({{
  hasDir: html.includes('NEG'),
  hasHorizon: html.includes('MID'),
  hasWeight: html.includes('PRIMARY'),
  hasRole: html.includes('COMPLICATION'),
  hasActor: html.includes('GOVERNMENT'),
  hasNegClass: html.includes('dash-anchor-field-value neg'),
  emptyWhenNoAnchor: renderAnchorFieldsHtml(null) === ''
}}));
"""
    result = run_node_js(js)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"
    out = json_module.loads(result.stdout)
    assert out["hasDir"] is True
    assert out["hasHorizon"] is True
    assert out["hasWeight"] is True
    assert out["hasRole"] is True
    assert out["hasActor"] is True
    assert out["hasNegClass"] is True
    assert out["emptyWhenNoAnchor"] is True


def test_render_anchor_links_html_shows_only_nonempty_link_types():
    import shutil
    import json as json_module
    from tests.conftest import extract_js_function, run_node_js
    if not shutil.which("node"):
        return
    src = (REPO_ROOT / "js" / "app-main.js").read_text(encoding="utf-8")
    fn = extract_js_function(src, "renderAnchorLinksHtml")
    js = f"""
{fn}
const anchor = {{ links: {{ confirms: ['A-1','A-2'], contradicts: [], context_chain: ['B-1'] }} }};
const html = renderAnchorLinksHtml(anchor);
console.log(JSON.stringify({{
  hasConfirms: html.includes('ПОДТВЕРЖДАЕТ') && html.includes('2'),
  hasContext: html.includes('КОНТЕКСТ') && html.includes('1'),
  hasContradicts: html.includes('ПРОТИВОРЕЧИТ'),
  emptyWhenNoLinks: renderAnchorLinksHtml({{}}) === '',
  emptyWhenNull: renderAnchorLinksHtml(null) === ''
}}));
"""
    result = run_node_js(js)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"
    out = json_module.loads(result.stdout)
    assert out["hasConfirms"] is True
    assert out["hasContext"] is True
    assert out["hasContradicts"] is False, "contradicts пуст — чип не должен рендериться"
    assert out["emptyWhenNoLinks"] is True
    assert out["emptyWhenNull"] is True


def test_render_anchor_entities_html_filters_by_signal_refs():
    import shutil
    import json as json_module
    from tests.conftest import extract_js_function, run_node_js
    if not shutil.which("node"):
        return
    src = (REPO_ROOT / "js" / "app-main.js").read_text(encoding="utf-8")
    fn = extract_js_function(src, "renderAnchorEntitiesHtml")
    js = f"""
function sanitize(s) {{ return String(s == null ? '' : s); }}
const ENTITIES = [
  {{ id: 'el_salvador', name: 'El Salvador', signal_refs: ['STR-2026-0701-002'] }},
  {{ id: 'strategy', name: 'Strategy', signal_refs: ['STR-2026-0720-001'] }}
];
{fn}
const anchor = {{ id: 'STR-2026-0701-002' }};
const html = renderAnchorEntitiesHtml(anchor);
console.log(JSON.stringify({{
  hasElSalvador: html.includes('El Salvador'),
  hasStrategy: html.includes('Strategy'),
  emptyWhenNoMatch: renderAnchorEntitiesHtml({{ id: 'NOPE-0000' }}) === '',
  emptyWhenNull: renderAnchorEntitiesHtml(null) === ''
}}));
"""
    result = run_node_js(js)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"
    out = json_module.loads(result.stdout)
    assert out["hasElSalvador"] is True
    assert out["hasStrategy"] is False, "сущность без совпадения signal_refs не должна попадать в карточку другого сигнала"
    assert out["emptyWhenNoMatch"] is True
    assert out["emptyWhenNull"] is True


def test_render_watchlist_row_shows_real_pos_neg_neu_ratio():
    import shutil
    import json as json_module
    from tests.conftest import extract_js_function, run_node_js
    if not shutil.which("node"):
        return
    src = (REPO_ROOT / "js" / "app-main.js").read_text(encoding="utf-8")
    fn = extract_js_function(src, "renderWatchlistRow")
    js = f"""
function sanitize(s) {{ return String(s == null ? '' : s); }}
const DIGEST_CLUSTER_LABELS = {{ btc_treasury_competition: '💰 КАЗНАЧЕЙСТВА' }};
{fn}
const cl = {{ signals: new Array(28), pos: 15, neg: 5, neu: 8 }};
const score = {{ total: 201 }};
const html = renderWatchlistRow('btc_treasury_competition', cl, score);
console.log(JSON.stringify({{
  hasLabel: html.includes('КАЗНАЧЕЙСТВА'),
  hasCount: html.includes('>28<'),
  hasDataCl: html.includes('data-cl=\\"btc_treasury_competition\\"'),
  hasPosSegment: html.includes('flex:15;background:var(--grn)'),
  hasNegSegment: html.includes('flex:5;background:var(--red)'),
  hasNeuSegment: html.includes('flex:8;background:var(--dim2)')
}}));
"""
    result = run_node_js(js)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"
    out = json_module.loads(result.stdout)
    assert out["hasLabel"] is True
    assert out["hasCount"] is True
    assert out["hasDataCl"] is True
    assert out["hasPosSegment"] is True
    assert out["hasNegSegment"] is True
    assert out["hasNeuSegment"] is True
