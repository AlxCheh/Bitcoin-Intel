# Home Page Reorg + AEO Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn ОБЗОР (home tab) from a dense always-expanded dashboard into an editorial entry point (definition → top story → collapsed remaining narratives → 4 real-cluster portal tiles → compact ticker), relocating displaced blocks (price chart, cycle phase, latest blocks) to their thematic tabs instead of deleting them — plus a technical AEO foundation (`robots.txt`, `sitemap.xml`, Schema.org, and a CI-generated static narrative snapshot so non-JS crawlers see real content).

**Architecture:** Part 1 (Tasks 1-6) is pure frontend — HTML relocation across three tabs plus a refactor of the existing narrative-rendering loop inside `renderDashboard()` (js/app-main.js) to split "hero" (full card, reuses `renderNarrativeItem()` unchanged) from "mini rows" (new compact renderer, reuses existing `goToDigest()` for its click behavior) plus a new static tiles function reusing this session's `.toc-card` CSS. Part 2 (Tasks 7-9) is new static files plus one new Python build script wired into the existing `synthesize` CI job, which already recomputes `data/synthesis_cache.json` before every deploy. Full design: `docs/superpowers/specs/2026-08-16-home-page-reorg-design.md`.

**Tech Stack:** Vanilla JS (`js/app-main.js`), inline CSS (`index.html`), Python (`scripts/`), GitHub Actions (`.github/workflows/deploy.yml`), Python/pytest + Node harness for tests.

---

## Task 1: Relocate price chart, cycle phase, and latest-blocks panels

**Files:**
- Modify: `index.html` (cut three blocks from `tab-home`, paste into `tab-analytics` and `tab-pools`)
- Modify: `js/app-main.js` (`triggerTabData()`)
- Test: `tests/unit/test_home_page_reorg.py` (new)

> **Why first:** lowest-risk step — pure relocation, no new rendering logic. Confirms nothing breaks before adding new UI on top.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_home_page_reorg.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_home_page_reorg.py -v`
Expected: FAIL — all three tests fail (panels still on home, `triggerTabData` unchanged)

- [ ] **Step 3: Cut the three blocks from `tab-home` in index.html**

In `index.html`, find (inside `<section class="section active" id="tab-home">`):

```html
    <!-- Ключевые метрики (Production Cost / Realized Price) перенесены на
         вкладку МЕТРИКИ — здесь короткая ссылка + актуальный коэффициент -->
    <div class="dash-sum-link" onclick="showTab('analytics', null)" style="margin:0 0 12px">
      СЕБЕСТОИМОСТЬ И REALIZED PRICE → МЕТРИКИ <span>→</span>
    </div>

    <!-- ══ БЛОК 2.5: ГРАФИК ЦЕНЫ BTC ══ -->
    <div id="price-chart-wrap" style="margin:0 0 12px;border:1px solid var(--btc);overflow:hidden;display:none;">
      <div class="panel-head" style="margin:0">
        <span class="panel-title">График BTC / USD</span>
        <span class="chart-meta">ЦЕНА · ИСТОРИЯ</span>
      </div>
      <div id="terminal-price-chart"></div>
    </div>
```

Delete this whole block entirely (both the link and the chart wrap) — it moves to Step 5 below, not staying on home in any form (superseded by the ticker built in Task 2).

Then find:

```html
    <!-- ══ БЛОК 1: ЦИКЛОВОЙ ИНДИКАТОР ══ -->
    <div class="dash-cycle">
      <div class="panel-head" style="margin:-16px -16px 16px">
        <span class="panel-title">Фаза цикла</span>
        <div style="display:flex;align-items:center;gap:10px">
          <span id="dash-ratio" style="font-family:var(--mono);font-size:9px;color:var(--btc)">—</span>
          <span class="chart-meta">BITCOIN 2026</span>
        </div>
      </div>
      <div style="display:flex;align-items:baseline;gap:10px">
        <div class="dash-cycle-phase" id="dash-phase">НАКОПЛЕНИЕ</div>
      </div>
      <div class="dash-cycle-sub" id="dash-phase-sub">Цена у себестоимости добычи. Исторически — зона долгосрочных покупок перед ростом.</div>
      <div class="dash-cycle-track">
        <div class="dct-seg done"></div>
        <div class="dct-seg current"></div>
        <div class="dct-seg"></div>
        <div class="dct-seg"></div>
      </div>
      <div class="dash-cycle-labels">
        <span>ДНО</span>
        <span class="dct-active">▲ НАКОПЛЕНИЕ</span>
        <span>РОСТ</span>
        <span>ЭЙФОРИЯ</span>
      </div>
      <div style="margin-top:10px;padding-top:8px;border-top:1px solid var(--line);font-family:var(--mono);font-size:8px;color:var(--dim);line-height:1.6">
        <span id="dash-ratio-note">—</span> · Цена / Production Cost.
        <span style="opacity:0.7">Ниже ×1.0 — добыча убыточна. ×0.5–0.8 — исторически зона дна. ×2.5+ — зона перегрева.</span>
      </div>
    </div>
```

Delete this whole block too (moves to Step 5).

Then find:

```html
    <!-- ══ БЛОК 5: ПОСЛЕДНИЕ БЛОКИ ══ -->
    <div class="terminal" id="latest-blocks-panel" style="margin:0 0 16px;border:1px solid var(--btc)">
      <div class="panel-head" style="margin:-0px -0px 0px;border-bottom:none">
        <span class="panel-title">Последние блоки</span>
        <span class="terminal-title chart-meta" id="block-title">загрузка...</span>
      </div>
      <div class="terminal-body" style="padding:0">
        <div class="blk-head">
          <span>HEIGHT</span>
          <span>POOL</span>
          <span>TX</span>
          <span>AGE</span>
        </div>
        <div id="blocks-list">
          <div class="blk-row blk-loading">computing...</div>
        </div>
      </div>
    </div>
```

Delete this whole block too (moves to Step 6).

- [ ] **Step 4: Confirm the status bar block stays (will be restyled in Task 2, not touched here)**

Leave `<div id="dash-status-bar">...</div>` in place — Task 2 restyles it in place, no move needed.

- [ ] **Step 5: Paste the price chart + cycle phase blocks into `tab-analytics`**

In `index.html`, find:

```html
<section class="section" id="tab-analytics">
  <div class="page">

    <!-- VOLUME CHART — редизайн 2026-07-25:
```

Replace with (inserting the two relocated blocks right after `<div class="page">`, before the existing volume-chart comment):

```html
<section class="section" id="tab-analytics">
  <div class="page">

    <!-- ══ ГРАФИК ЦЕНЫ BTC (перенесено с ОБЗОРА, 2026-08-16) ══ -->
    <div id="price-chart-wrap" style="margin:0 0 12px;border:1px solid var(--btc);overflow:hidden;display:none;">
      <div class="panel-head" style="margin:0">
        <span class="panel-title">График BTC / USD</span>
        <span class="chart-meta">ЦЕНА · ИСТОРИЯ</span>
      </div>
      <div id="terminal-price-chart"></div>
    </div>

    <!-- ══ ЦИКЛОВОЙ ИНДИКАТОР (перенесено с ОБЗОРА, 2026-08-16) ══ -->
    <div class="dash-cycle">
      <div class="panel-head" style="margin:-16px -16px 16px">
        <span class="panel-title">Фаза цикла</span>
        <div style="display:flex;align-items:center;gap:10px">
          <span id="dash-ratio" style="font-family:var(--mono);font-size:9px;color:var(--btc)">—</span>
          <span class="chart-meta">BITCOIN 2026</span>
        </div>
      </div>
      <div style="display:flex;align-items:baseline;gap:10px">
        <div class="dash-cycle-phase" id="dash-phase">НАКОПЛЕНИЕ</div>
      </div>
      <div class="dash-cycle-sub" id="dash-phase-sub">Цена у себестоимости добычи. Исторически — зона долгосрочных покупок перед ростом.</div>
      <div class="dash-cycle-track">
        <div class="dct-seg done"></div>
        <div class="dct-seg current"></div>
        <div class="dct-seg"></div>
        <div class="dct-seg"></div>
      </div>
      <div class="dash-cycle-labels">
        <span>ДНО</span>
        <span class="dct-active">▲ НАКОПЛЕНИЕ</span>
        <span>РОСТ</span>
        <span>ЭЙФОРИЯ</span>
      </div>
      <div style="margin-top:10px;padding-top:8px;border-top:1px solid var(--line);font-family:var(--mono);font-size:8px;color:var(--dim);line-height:1.6">
        <span id="dash-ratio-note">—</span> · Цена / Production Cost.
        <span style="opacity:0.7">Ниже ×1.0 — добыча убыточна. ×0.5–0.8 — исторически зона дна. ×2.5+ — зона перегрева.</span>
      </div>
    </div>

    <!-- VOLUME CHART — редизайн 2026-07-25:
```

- [ ] **Step 6: Paste the latest-blocks block into `tab-pools`**

In `index.html`, find:

```html
<section class="section" id="tab-pools">
  <div class="page">
    <div id="pool-summary"></div>
    <div id="pool-detail"></div>
  </div>
</section>
```

Replace with:

```html
<section class="section" id="tab-pools">
  <div class="page">
    <div id="pool-summary"></div>
    <div id="pool-detail"></div>

    <!-- ══ ПОСЛЕДНИЕ БЛОКИ (перенесено с ОБЗОРА, 2026-08-16) ══ -->
    <div class="terminal" id="latest-blocks-panel" style="margin:16px 0 0;border:1px solid var(--btc)">
      <div class="panel-head" style="margin:-0px -0px 0px;border-bottom:none">
        <span class="panel-title">Последние блоки</span>
        <span class="terminal-title chart-meta" id="block-title">загрузка...</span>
      </div>
      <div class="terminal-body" style="padding:0">
        <div class="blk-head">
          <span>HEIGHT</span>
          <span>POOL</span>
          <span>TX</span>
          <span>AGE</span>
        </div>
        <div id="blocks-list">
          <div class="blk-row blk-loading">computing...</div>
        </div>
      </div>
    </div>
  </div>
</section>
```

- [ ] **Step 7: Update `triggerTabData()` so ANALYTICS also fetches price/production-cost data**

In `js/app-main.js`, find:

```js
  if (id === 'home')      { fetchProdCost(); if (!LATEST_BLOCKS.length) fetchBlocks(); initPriceChart(); }
  if (id === 'analytics') { initCharts(); renderBip110Signaling(); }
```

Replace with:

```js
  if (id === 'home')      { fetchProdCost(); if (!LATEST_BLOCKS.length) fetchBlocks(); }
  // 2026-08-16: price-chart-wrap/dash-cycle перенесены с ОБЗОРА сюда — эта
  // вкладка теперь должна сама инициировать их данные, не полагаться на то,
  // что пользователь сначала посетил ОБЗОР. dashBtcPrice — простой глобал
  // без "уже гружу" guard, поэтому пропускаем повторный fetch если ОБЗОР
  // уже его выставил (тот же паттерн, что !LATEST_BLOCKS.length у fetchBlocks).
  if (id === 'analytics') { if (!dashBtcPrice) fetchProdCost(); initPriceChart(); initCharts(); renderBip110Signaling(); }
```

(`fetchBlocks()` stays home-only + the existing module-level `fetchBlocks(); setInterval(fetchBlocks, 60000);` already refreshes `LATEST_BLOCKS`/`#blocks-list` regardless of which tab is open — pools tab needs no extra wiring, `renderBlocks()` is already null-safe.)

- [ ] **Step 8: Run the new test to verify it passes**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_home_page_reorg.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 9: Run full suite**

Run: `python scripts/update_js_cache_bust.py && PYTHONHASHSEED=0 python -m pytest -q`
Expected: all passing

- [ ] **Step 10: Commit**

```bash
git add index.html js/app-main.js tests/unit/test_home_page_reorg.py
git commit -m "refactor: перенести график цены/фазу цикла на МЕТРИКИ, блоки на ПУЛЫ"
```

---

## Task 2: Site definition banner + compact ticker

**Files:**
- Modify: `index.html` (`tab-home`: add definition banner, restyle `#dash-status-bar` into a ticker, add `#dash-status-price`)
- Modify: `js/app-main.js` (`renderDashStatus()`)
- Test: `tests/unit/test_home_page_reorg.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_home_page_reorg.py`:

```python
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
renderDashStatus();
console.log(JSON.stringify({{ price: registry['dash-status-price'].textContent }}));
"""
    result = run_node_js(js)
    assert result.returncode == 0, f"Node failed:\n{{result.stderr}}"
    out = json_module.loads(result.stdout)
    assert "63" in out["price"], "Тикер обязан показать текущую цену BTC из dashBtcPrice"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_home_page_reorg.py -v`
Expected: FAIL — definition banner missing, price span missing, `renderDashStatus()` doesn't write it

- [ ] **Step 3: Add the definition banner and restyle the status bar into a ticker**

In `index.html`, find (inside `tab-home`, this is now the first content block after Task 1's cuts):

```html
    <!-- ══ БЛОК 0: СТАТУС ══ -->
    <!-- ══ БЛОК 0: СТАТУС ══ -->
    <div id="dash-status-bar" style="margin:12px 0;border:1px solid var(--btc);background:var(--bg2)">
      <div style="display:flex;align-items:center;gap:8px;padding:10px 14px;flex-wrap:wrap">
        <span style="font-family:var(--mono);font-size:9px;letter-spacing:0.12em;color:var(--dim)">СТАТУС</span>
        <span style="font-family:var(--mono);font-size:9px;color:var(--line2)">·</span>
        <span style="font-family:var(--mono);font-size:13px;font-weight:700;color:var(--btc)" id="dash-status-phase">—</span>
        <span style="font-family:var(--mono);font-size:10px;color:var(--dim)" id="dash-status-ratio">—</span>
        <span style="font-family:var(--mono);font-size:9px;color:var(--line2)">·</span>
        <span style="font-family:var(--mono);font-size:13px;font-weight:700;color:var(--grn)" id="dash-status-pos">—↑</span>
        <span style="font-family:var(--mono);font-size:13px;font-weight:700;color:var(--red)" id="dash-status-neg">—↓</span>
        <span style="font-family:var(--mono);font-size:13px;font-weight:700;color:var(--dim)" id="dash-status-neu">—→</span>
      </div>
    </div>
```

Replace with:

```html
    <!-- ══ ОПРЕДЕЛЕНИЕ САЙТА (2026-08-16) ══ -->
    <div id="dash-definition" style="margin:12px 0;border:1px solid var(--btc);background:var(--bg2);padding:10px 12px;font-family:var(--sans);font-size:11px;line-height:1.5;color:var(--dim)">
      <b style="color:var(--txt)">Bitcoin Intel</b> — платформа нарративного анализа Bitcoin: сталкивает противоречивые сигналы рынка и институтов, показывает где правда ещё не решена.
    </div>

    <!-- ══ ТИКЕР ЖИВЫХ ДАННЫХ (2026-08-16, ранее — БЛОК 0: СТАТУС) ══ -->
    <div id="dash-status-bar" style="margin:0 0 12px;border:1px solid var(--line);background:var(--bg2)">
      <div style="display:flex;align-items:center;gap:8px;padding:8px 14px;flex-wrap:wrap;font-family:var(--mono);font-size:11px">
        <span style="font-weight:700;color:var(--txt)" id="dash-status-price">—</span>
        <span style="color:var(--line2)">·</span>
        <span style="font-weight:700;color:var(--btc)" id="dash-status-phase">—</span>
        <span style="color:var(--dim)" id="dash-status-ratio">—</span>
        <span style="color:var(--line2)">·</span>
        <span style="font-weight:700;color:var(--grn)" id="dash-status-pos">—↑</span>
        <span style="font-weight:700;color:var(--red)" id="dash-status-neg">—↓</span>
        <span style="font-weight:700;color:var(--dim)" id="dash-status-neu">—→</span>
      </div>
    </div>
```

- [ ] **Step 4: Update `renderDashStatus()` to write the price span**

In `js/app-main.js`, find:

```js
  const statusPhase = document.getElementById('dash-status-phase');
  const statusRatio = document.getElementById('dash-status-ratio');
  if (statusPhase) {
```

Replace with:

```js
  const statusPhase = document.getElementById('dash-status-phase');
  const statusRatio = document.getElementById('dash-status-ratio');
  // 2026-08-16: тикер на ОБЗОРЕ теперь показывает и цену — раньше цена
  // была видна только в полном графике (перенесён на МЕТРИКИ, Task 1).
  const statusPrice = document.getElementById('dash-status-price');
  if (statusPrice && typeof dashBtcPrice === 'number' && dashBtcPrice > 0) {
    statusPrice.textContent = '$' + dashBtcPrice.toLocaleString('en-US', { maximumFractionDigits: 0 });
  }
  if (statusPhase) {
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_home_page_reorg.py -v`
Expected: PASS (all tests so far)

- [ ] **Step 6: Run full suite**

Run: `python scripts/update_js_cache_bust.py && PYTHONHASHSEED=0 python -m pytest -q`
Expected: all passing

- [ ] **Step 7: Commit**

```bash
git add index.html js/app-main.js tests/unit/test_home_page_reorg.py
git commit -m "feat: определение сайта + компактный тикер вместо статус-бара"
```

---

## Task 3: Hero + mini-row narrative split

**Files:**
- Modify: `index.html` (`tab-home`: add `#dash-narratives-mini-list` container + section label)
- Modify: `js/app-main.js` (`renderDashboard()` — the `shown.forEach` loop; new `renderNarrativeMiniRow()`)
- Test: `tests/unit/test_home_page_reorg.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_home_page_reorg.py`:

```python
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
    assert result.returncode == 0, f"Node failed:\n{{result.stderr}}"
    out = json_module.loads(result.stdout)
    assert out["isString"] is True
    assert out["hasLabel"] is True
    assert out["hasScore"] is True
    assert out["hasCount"] is True
    assert out["hasDataCl"] is True
```

(`renderNarrativeMiniRow()` returns an HTML **string**, not a DOM node — same style as `renderNarrativeItem()`'s siblings elsewhere in this file, e.g. `renderTOC()`/`renderTheoryTopic()`. This repo's Node test harness has no DOM implementation, so string-returning functions are what's testable — see Step 4's implementation.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_home_page_reorg.py -v`
Expected: FAIL — container missing, function doesn't exist

- [ ] **Step 3: Add `#dash-narratives-mini-list` container in index.html**

In `index.html`, find:

```html
    <!-- ══ БЛОК 3: ГЛАВНЫЕ НАРРАТИВЫ ══ -->
    <div class="dash-narratives" id="dash-narratives-wrap">
      <div class="panel-head" style="margin:0">
        <span class="panel-title">Главные нарративы</span>
        <span id="dash-narratives-total" class="chart-meta"></span>
      </div>
      <div id="dash-narratives-list"></div>
    </div>
```

Replace with:

```html
    <!-- ══ ГЛАВНАЯ ИСТОРИЯ (2026-08-16, ранее БЛОК 3: ГЛАВНЫЕ НАРРАТИВЫ) ══ -->
    <div class="dash-narratives" id="dash-narratives-wrap">
      <div class="panel-head" style="margin:0">
        <span class="panel-title">Главная история</span>
        <span id="dash-narratives-total" class="chart-meta"></span>
      </div>
      <div id="dash-narratives-list"></div>
    </div>

    <!-- ══ ЕЩЁ НАРРАТИВЫ (2026-08-16) ══ -->
    <div id="dash-narratives-mini-wrap" style="margin-top:12px">
      <div id="dash-narratives-mini-label" style="font-family:var(--mono);font-size:9px;color:var(--dim2);letter-spacing:0.1em;margin-bottom:6px"></div>
      <div id="dash-narratives-mini-list"></div>
    </div>
```

(`dash-narratives-mini-label` starts empty and is filled by JS only when there's at least one mini row — see Step 4's `weak` empty-case handling from the design doc.)

- [ ] **Step 4: Add `renderNarrativeMiniRow()` and wire it into the `shown.forEach` loop**

In `js/app-main.js`, find the `renderNarrativeItem` function's closing brace and the loop right after it:

```js
    item.querySelector('[data-cl]').addEventListener('click', function() { goToDigest(this.dataset.cl); });
    item.querySelector('[data-bd]').addEventListener('click', function() { document.getElementById(this.dataset.bd).classList.toggle('open'); });
    return item;
  }

  // Путь 3: используем Python-синтез из synthesis_cache.json
  // Fallback на браузерный синтез если кеш недоступен или кластер не найден
  shown.forEach(({ key, cl, score, weak }, idx) => {
    const cached = SYNTHESIS_CACHE[key];
    const synthesis = (cached && cached.tension)
      ? cached
      : synthesizeNarrativeAdvanced(key, cl);
    const item = renderNarrativeItem(key, cl, score, weak, idx, synthesis);
    listEl.appendChild(item);
  });
```

Replace with:

```js
    item.querySelector('[data-cl]').addEventListener('click', function() { goToDigest(this.dataset.cl); });
    item.querySelector('[data-bd]').addEventListener('click', function() { document.getElementById(this.dataset.bd).classList.toggle('open'); });
    return item;
  }

  // 2026-08-16: компактная строка для "ещё нарративы" на ОБЗОРЕ — только
  // топ-1 (idx===0) идёт полной карточкой через renderNarrativeItem(),
  // остальные сюда. Возвращает HTML-строку (не DOM-узел), тот же стиль,
  // что у renderTOC()/renderTheoryTopic() в этом файле — не ради
  // единообразия ради единообразия, а потому что клик вешается ПОСЛЕ
  // вставки в DOM через querySelectorAll (см. вызов ниже), как и для
  // остальных .innerHTML-based рендеров.
  function renderNarrativeMiniRow(key, cl, score) {
    const dirCls = cl.neg > cl.pos ? 'neg' : cl.pos > cl.neg ? 'pos' : 'neu';
    const dotColor = dirCls === 'pos' ? 'var(--grn)' : dirCls === 'neg' ? 'var(--red)' : 'var(--dim)';
    const label = CLUSTER_LABELS[key] || sanitize(key).toUpperCase();
    return '<div class="dash-narrative-mini" data-cl="' + sanitize(key) + '" '
      + 'style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--line);cursor:pointer;font-size:11px">'
      + '<span style="width:6px;height:6px;border-radius:50%;flex-shrink:0;background:' + dotColor + '"></span>'
      + '<span style="flex:1;color:var(--txt)">' + label + '</span>'
      + '<span style="font-family:var(--mono);font-size:9px;color:var(--dim)">' + cl.signals.length + ' · ' + score.total + '</span>'
      + '<span style="color:var(--dim);font-size:12px">›</span>'
      + '</div>';
  }

  // Путь 3: используем Python-синтез из synthesis_cache.json
  // Fallback на браузерный синтез если кеш недоступен или кластер не найден
  const miniListEl = document.getElementById('dash-narratives-mini-list');
  const miniLabelEl = document.getElementById('dash-narratives-mini-label');
  let miniHtml = '';
  shown.forEach(({ key, cl, score, weak }, idx) => {
    const cached = SYNTHESIS_CACHE[key];
    const synthesis = (cached && cached.tension)
      ? cached
      : synthesizeNarrativeAdvanced(key, cl);
    if (idx === 0) {
      const item = renderNarrativeItem(key, cl, score, weak, idx, synthesis);
      listEl.appendChild(item);
    } else {
      miniHtml += renderNarrativeMiniRow(key, cl, score);
    }
  });
  if (miniListEl) {
    miniListEl.innerHTML = miniHtml;
    if (miniHtml) {
      if (miniLabelEl) miniLabelEl.textContent = 'ЕЩЁ НАРРАТИВЫ';
      miniListEl.querySelectorAll('[data-cl]').forEach(function(el) {
        el.addEventListener('click', function() { goToDigest(this.dataset.cl); });
      });
    } else if (miniLabelEl) {
      miniLabelEl.textContent = '';
    }
  }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_home_page_reorg.py -v`
Expected: PASS

- [ ] **Step 6: Run full suite**

Run: `python scripts/update_js_cache_bust.py && PYTHONHASHSEED=0 python -m pytest -q`
Expected: all passing

- [ ] **Step 7: Commit**

```bash
git add index.html js/app-main.js tests/unit/test_home_page_reorg.py
git commit -m "feat: главная история полной карточкой, остальные — свёрнутыми строками"
```

---

## Task 4: Explore tiles (4 real clusters)

**Files:**
- Modify: `index.html` (`tab-home`: add `#dash-explore-tiles` container)
- Modify: `js/app-main.js` (new `renderExploreTiles()`, called once)
- Test: `tests/unit/test_home_page_reorg.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_home_page_reorg.py`:

```python
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
    assert result.returncode == 0, f"Node failed:\n{{result.stderr}}"
    html = json_module.loads(result.stdout)["html"]
    for cluster_key in ["live", "knowledge", "macro", "analysis"]:
        assert "selectCluster('" + cluster_key + "')" in html, (
            f"Плитка для кластера '{{cluster_key}}' отсутствует или не вызывает selectCluster()"
        )
    assert "toc-card-grid" in html
    assert "toc-card" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_home_page_reorg.py -v`
Expected: FAIL — container and function don't exist

- [ ] **Step 3: Add the container in index.html**

In `index.html`, find (the mini-narratives block added in Task 3, Step 3):

```html
    <!-- ══ ЕЩЁ НАРРАТИВЫ (2026-08-16) ══ -->
    <div id="dash-narratives-mini-wrap" style="margin-top:12px">
      <div id="dash-narratives-mini-label" style="font-family:var(--mono);font-size:9px;color:var(--dim2);letter-spacing:0.1em;margin-bottom:6px"></div>
      <div id="dash-narratives-mini-list"></div>
    </div>
```

Replace with (adding the tiles section right after):

```html
    <!-- ══ ЕЩЁ НАРРАТИВЫ (2026-08-16) ══ -->
    <div id="dash-narratives-mini-wrap" style="margin-top:12px">
      <div id="dash-narratives-mini-label" style="font-family:var(--mono);font-size:9px;color:var(--dim2);letter-spacing:0.1em;margin-bottom:6px"></div>
      <div id="dash-narratives-mini-list"></div>
    </div>

    <!-- ══ ИССЛЕДОВАТЬ ГЛУБЖЕ (2026-08-16) ══ -->
    <div style="margin-top:16px">
      <div style="font-family:var(--mono);font-size:9px;color:var(--dim2);letter-spacing:0.1em;margin-bottom:6px">ИССЛЕДОВАТЬ ГЛУБЖЕ</div>
      <div id="dash-explore-tiles"></div>
    </div>
```

- [ ] **Step 4: Add `renderExploreTiles()` and call it once**

In `js/app-main.js`, find `function goToDigest(clusterKey) {` (this sits right before the "ANALYSIS → ВСЕ НАРРАТИВЫ" comment block, a natural neighbor). Insert **before** it:

```js
// 2026-08-16: плитки-порталы на ОБЗОРЕ — реальные 4 кластера навигации
// (CLUSTERS ниже), не придуманная отдельная таксономия. Переиспользует
// .toc-card-grid/.toc-card/.toc-card-title/.toc-card-subtitle — тот же
// визуальный язык, что карточное оглавление ТЕОРИИ (эта же сессия,
// 2026-08-16). Статична (не зависит от данных) — рендерится один раз.
function renderExploreTiles() {
  const tiles = [
    { key: 'live', icon: '📡', title: 'LIVE', sub: 'Цена · Дайджест · Метрики · Пулы' },
    { key: 'knowledge', icon: '⚙️', title: 'Ecosystem', sub: 'Технологии · Lightning · Инструменты' },
    { key: 'macro', icon: '📖', title: 'Fundamental', sub: 'Теория · Макроконтекст · Эмиссия' },
    { key: 'analysis', icon: '🔬', title: 'Analysis', sub: 'Анализатор · Холдеры · Все нарративы' }
  ];
  return '<div class="toc-card-grid">'
    + tiles.map(function(t) {
        return '<div class="toc-card" onclick="selectCluster(\'' + t.key + '\')">'
          + '<span style="font-size:16px">' + t.icon + '</span>'
          + '<div class="toc-card-title">' + t.title + '</div>'
          + '<div class="toc-card-subtitle">' + t.sub + '</div>'
          + '</div>';
      }).join('')
    + '</div>';
}

function goToDigest(clusterKey) {
```

Then find (inside `triggerTabData()`, the `home` branch already touched in Task 1):

```js
  if (id === 'home')      { fetchProdCost(); if (!LATEST_BLOCKS.length) fetchBlocks(); }
```

Replace with:

```js
  if (id === 'home')      { fetchProdCost(); if (!LATEST_BLOCKS.length) fetchBlocks(); renderExploreTilesOnce(); }
```

Then, right after the `renderExploreTiles()` function definition added above, add a tiny idempotency wrapper (the tiles are static — no need to re-render every time the home tab is revisited):

```js
let exploreTilesRendered = false;
function renderExploreTilesOnce() {
  if (exploreTilesRendered) return;
  const el = document.getElementById('dash-explore-tiles');
  if (!el) return;
  el.innerHTML = renderExploreTiles();
  exploreTilesRendered = true;
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_home_page_reorg.py -v`
Expected: PASS

- [ ] **Step 6: Run full suite**

Run: `python scripts/update_js_cache_bust.py && PYTHONHASHSEED=0 python -m pytest -q`
Expected: all passing

- [ ] **Step 7: Commit**

```bash
git add index.html js/app-main.js tests/unit/test_home_page_reorg.py
git commit -m "feat: плитки-порталы на реальные 4 кластера навигации"
```

---

## Task 5: Manual verification in browser (Part 1 complete)

**Files:** none (verification only)

- [ ] **Step 1: Serve locally**

```bash
cd "D:\Claude\Bitcoin-Intel" && python -m http.server 8800
```

- [ ] **Step 2: Confirm ОБЗОР matches the approved mockup**

Navigate to `http://localhost:8800/index.html`. Confirm order top to bottom: definition banner → ticker (price/phase/pos/neg/neu) → главная история (full card) → ещё нарративы (mini rows, if any pass `SCORE_MIN`) → исследовать глубже (4 tiles) — no price chart, no cycle-phase panel, no blocks table on this page.

- [ ] **Step 3: Confirm relocated panels work**

Switch to МЕТРИКИ (`showTab('analytics', null)`): confirm the price chart and cycle-phase panel render with real data (not stuck on placeholder `—`/`НАКОПЛЕНИЕ`). Switch to ПУЛЫ (`showTab('pools', null)`): confirm the latest-blocks table renders with real block data.

- [ ] **Step 4: Confirm interactions**

Click a mini-row narrative — confirm it navigates to ДАЙДЖЕСТ filtered to that cluster. Click each of the 4 explore tiles — confirm each opens the correct cluster's first tab (LIVE→ОБЗОР already active is fine to re-click; ECOSYSTEM→ТЕХНОЛОГИИ; FUNDAMENTAL→ТЕОРИЯ; ANALYSIS→АНАЛИЗАТОР).

If any check fails, stop and diagnose before proceeding to Part 2.

---

## Task 6: `robots.txt`, `sitemap.xml`, Schema.org JSON-LD

**Files:**
- Create: `robots.txt`
- Create: `sitemap.xml`
- Modify: `index.html` (`<head>`)
- Test: `tests/unit/test_aeo_foundation.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_aeo_foundation.py`:

```python
"""
tests/unit/test_aeo_foundation.py
Bitcoin Intel — regression: robots.txt/sitemap.xml/Schema.org present and
well-formed. Part of the 2026-08-16 AEO foundation — see
docs/superpowers/specs/2026-08-16-home-page-reorg-design.md Часть 2.
"""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def test_robots_txt_exists_and_allows_ai_crawlers():
    robots = (REPO_ROOT / "robots.txt").read_text(encoding="utf-8")
    for bot in ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot"]:
        assert bot in robots, f"{bot} не упомянут в robots.txt"
    assert "Sitemap:" in robots
    assert "Disallow: /" not in robots.split("User-agent: *")[1].split("User-agent:")[0], (
        "User-agent: * не должен блокировать сайт целиком"
    )


def test_sitemap_xml_is_valid_xml_with_root_url():
    sitemap_path = REPO_ROOT / "sitemap.xml"
    tree = ET.parse(sitemap_path)
    root = tree.getroot()
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = root.findall("sm:url/sm:loc", ns)
    assert len(urls) >= 1
    assert "alxcheh.github.io/Bitcoin-Intel" in urls[0].text


def test_index_html_has_schema_org_website_jsonld():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    start = html.find('application/ld+json')
    assert start != -1, "Schema.org JSON-LD блок не найден в index.html"
    script_start = html.find(">", start) + 1
    script_end = html.find("</script>", script_start)
    payload = json.loads(html[script_start:script_end])
    assert payload["@type"] == "WebSite"
    assert payload["name"] == "Bitcoin Intel"
    assert "url" in payload
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_aeo_foundation.py -v`
Expected: FAIL — files don't exist yet

- [ ] **Step 3: Create `robots.txt`**

Create `D:\Claude\Bitcoin-Intel\robots.txt`:

```
User-agent: *
Allow: /

User-agent: GPTBot
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: anthropic-ai
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Perplexity-User
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: CCBot
Allow: /

Sitemap: https://alxcheh.github.io/Bitcoin-Intel/sitemap.xml
```

- [ ] **Step 4: Create `sitemap.xml`**

Create `D:\Claude\Bitcoin-Intel\sitemap.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://alxcheh.github.io/Bitcoin-Intel/</loc>
    <changefreq>hourly</changefreq>
  </url>
</urlset>
```

- [ ] **Step 5: Add Schema.org JSON-LD to index.html `<head>`**

In `index.html`, find:

```html
<title>BITCOIN INTEL</title>
<script>
// 2026-08-01: отключаем нативное восстановление скролла браузером —
```

Replace with:

```html
<title>BITCOIN INTEL</title>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "Bitcoin Intel",
  "url": "https://alxcheh.github.io/Bitcoin-Intel/",
  "description": "Платформа нарративного анализа Bitcoin: сталкивает противоречивые сигналы рынка и институтов, показывает где правда ещё не решена.",
  "inLanguage": "ru"
}
</script>
<script>
// 2026-08-01: отключаем нативное восстановление скролла браузером —
```

(Placed before the scroll-restoration script, not after — that script's own test, `test_scroll_restoration_is_the_first_script_tag`, checks it's the first **executable** `<script>` without a `type` attribute; a `type="application/ld+json"` block is not JS and won't be picked up by that check, but confirm in Step 7 anyway.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_aeo_foundation.py -v`
Expected: PASS

- [ ] **Step 7: Run full suite (confirms the JSON-LD placement didn't break the scroll-restoration guard)**

Run: `PYTHONHASHSEED=0 python -m pytest -q`
Expected: all passing — pay attention to `tests/unit/test_scroll_restoration.py` specifically

- [ ] **Step 8: Commit**

```bash
git add robots.txt sitemap.xml index.html tests/unit/test_aeo_foundation.py
git commit -m "feat: robots.txt, sitemap.xml, Schema.org WebSite"
```

---

## Task 7: `scripts/prerender_home.py` — static narrative snapshot

**Files:**
- Create: `scripts/prerender_home.py`
- Modify: `index.html` (add `<!-- PRERENDER:HOME:START -->`/`<!-- PRERENDER:HOME:END -->` markers inside `#dash-narratives-list`)
- Test: `tests/unit/test_prerender_home.py` (new)

- [ ] **Step 1: Add the marker comments in index.html**

In `index.html`, find (inside `tab-home`, from Task 3):

```html
      <div id="dash-narratives-list"></div>
```

Replace with:

```html
      <div id="dash-narratives-list"><!-- PRERENDER:HOME:START --><!-- PRERENDER:HOME:END --></div>
```

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_prerender_home.py`:

```python
"""
tests/unit/test_prerender_home.py
Bitcoin Intel — regression: scripts/prerender_home.py must inject a real,
readable snapshot of the top narrative between the PRERENDER:HOME markers
in index.html, so a crawler that doesn't execute JS still sees content —
see docs/superpowers/specs/2026-08-16-home-page-reorg-design.md Часть 2.4.
Same marker-replace principle as scripts/update_js_cache_bust.py.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def _write_fixture_files(tmp_path):
    synthesis_cache = {
        "btc_treasury_competition": {
            "tension": "трекер показывает рост баланса vs МВФ заявляет консолидацию",
            "narrative": "Казначейства эволюционируют от пассивного баланса к операционному движку.",
            "strength": "strong",
            "phase": "active",
            "generated_at": "2026-08-16T10:00:00Z"
        }
    }
    signals = [
        {"id": "STR-2026-0801-001", "cluster": "btc_treasury_competition", "dir": "pos",
         "date": "2026-08-15", "weight": "primary", "narrative_role": "trigger",
         "links": {"contradicts": ["STR-2026-0801-002"]}, "tension": "x"},
        {"id": "STR-2026-0801-002", "cluster": "btc_treasury_competition", "dir": "neg",
         "date": "2026-08-15", "weight": "media", "narrative_role": "complication",
         "links": {}, "tension": ""},
    ]
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "synthesis_cache.json").write_text(json.dumps(synthesis_cache), encoding="utf-8")
    (tmp_path / "signals.json").write_text(json.dumps({"signals": signals}), encoding="utf-8")
    index_html = tmp_path / "index.html"
    index_html.write_text(
        '<div id="dash-narratives-list">'
        '<!-- PRERENDER:HOME:START --><!-- PRERENDER:HOME:END -->'
        '</div>',
        encoding="utf-8",
    )
    return index_html


def test_prerender_writes_top_narrative_text_between_markers(tmp_path, monkeypatch):
    _write_fixture_files(tmp_path)
    monkeypatch.chdir(tmp_path)
    script = REPO_ROOT / "scripts" / "prerender_home.py"
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert result.returncode == 0, f"prerender_home.py failed:\n{result.stderr}"

    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    start = html.find("PRERENDER:HOME:START")
    end = html.find("PRERENDER:HOME:END")
    snapshot = html[start:end]
    assert "трекер показывает рост" in snapshot or "Казначейства" in snapshot, (
        "Снимок обязан содержать реальный текст топ-нарратива, не пустой"
    )


def test_prerender_is_idempotent_no_duplication_on_rerun(tmp_path, monkeypatch):
    _write_fixture_files(tmp_path)
    monkeypatch.chdir(tmp_path)
    script = REPO_ROOT / "scripts" / "prerender_home.py"
    subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=True)
    first = (tmp_path / "index.html").read_text(encoding="utf-8")
    subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=True)
    second = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert first == second, "Повторный прогон не должен дублировать/менять контент при неизменных данных"
    assert second.count("PRERENDER:HOME:START") == 1, "Маркер не должен задваиваться"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_prerender_home.py -v`
Expected: FAIL — `scripts/prerender_home.py` doesn't exist

- [ ] **Step 4: Write `scripts/prerender_home.py`**

Create `D:\Claude\Bitcoin-Intel\scripts\prerender_home.py`:

```python
"""
scripts/prerender_home.py
Bitcoin Intel — генерирует статический текстовый снимок топ-нарратива
между маркерами <!-- PRERENDER:HOME:START/END --> в index.html, чтобы
краулер без исполнения JS видел реальный контент вместо пустого
<div id="dash-narratives-list">.

Запускается в CI (deploy.yml, job "synthesize") сразу после synthesizer.py,
на том же актуальном data/synthesis_cache.json — коммитится тем же sync-PR.
Тот же принцип маркер-замены, что scripts/update_js_cache_bust.py.

Дублирует ТОЛЬКО отбор топ-1 кластера (сортировка по тому же полю score,
что и клиентский renderDashboard() в js/app-main.js) — не весь алгоритм
скоринга (freshness/weight/tension/roles), который живёт только в JS и
scripts/synthesizer.py. Снимок читает уже готовый tension/narrative из
synthesis_cache.json, вычисляет только счётчик сигналов и грубую
сортировку по числу сигналов кластера (прокси для score.total, который
в остальном требует SIGNALS-специфичных данных недоступных здесь без
дублирования всей клиентской формулы — приемлемое упрощение: снимок
существует для краулеров, не для точного паритета с длиной live UI).
"""
import json
import re
import sys
from pathlib import Path

START_MARKER = "<!-- PRERENDER:HOME:START -->"
END_MARKER = "<!-- PRERENDER:HOME:END -->"


def build_snapshot_html(synthesis_cache: dict, signals: list) -> str:
    clusters = {}
    for s in signals:
        cl = s.get("cluster") or s.get("theme") or "narrative"
        clusters.setdefault(cl, []).append(s)

    if not clusters:
        return ""

    top_key = max(clusters, key=lambda k: len(clusters[k]))
    synthesis = synthesis_cache.get(top_key, {})
    tension = synthesis.get("tension", "")
    narrative = synthesis.get("narrative", "")
    n = len(clusters[top_key])

    if not tension and not narrative:
        return ""

    parts = ['<div class="dash-narrative-item">']
    if tension:
        parts.append('<div class="dash-narrative-tension">' + tension + "</div>")
    if narrative:
        parts.append('<div class="dash-narrative-macro">' + narrative + "</div>")
    parts.append('<div style="font-size:10px;color:var(--dim)">' + str(n) + " сигналов</div>")
    parts.append("</div>")
    return "".join(parts)


def main() -> int:
    synthesis_cache_path = Path("data/synthesis_cache.json")
    signals_path = Path("signals.json")
    index_path = Path("index.html")

    synthesis_cache = json.loads(synthesis_cache_path.read_text(encoding="utf-8")) if synthesis_cache_path.exists() else {}
    signals_data = json.loads(signals_path.read_text(encoding="utf-8")) if signals_path.exists() else {"signals": []}
    signals = signals_data.get("signals", signals_data) if isinstance(signals_data, dict) else signals_data

    snapshot = build_snapshot_html(synthesis_cache, signals)

    html = index_path.read_text(encoding="utf-8")
    pattern = re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER)
    replacement = START_MARKER + snapshot + END_MARKER
    if not re.search(pattern, html, flags=re.DOTALL):
        print("PRERENDER:HOME маркеры не найдены в index.html — пропущено", file=sys.stderr)
        return 1
    new_html = re.sub(pattern, replacement, html, count=1, flags=re.DOTALL)
    index_path.write_text(new_html, encoding="utf-8")
    print("OK: prerender_home.py — снимок обновлён (" + str(len(snapshot)) + " символов)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_prerender_home.py -v`
Expected: PASS

- [ ] **Step 6: Run the script against the real repo data once, confirm output looks right, then revert**

```bash
cd "D:\Claude\Bitcoin-Intel" && python scripts/prerender_home.py && git diff index.html
```

Expected: diff shows real narrative text injected between the markers. Then discard this local run (the real commit happens in CI, not here — this repo's `index.html` should stay marker-only in git, matching how `?v=hash` in cache-bust is also CI/local-script-generated, not manually maintained):

```bash
git checkout -- index.html
```

- [ ] **Step 7: Run full suite**

Run: `PYTHONHASHSEED=0 python -m pytest -q`
Expected: all passing

- [ ] **Step 8: Commit**

```bash
git add index.html scripts/prerender_home.py tests/unit/test_prerender_home.py
git commit -m "feat: scripts/prerender_home.py — статический снимок нарратива для краулеров"
```

(This commits the marker comments in `index.html` — empty between them, exactly as in Step 1 — the actual snapshot content is only ever written by CI, never committed from a dev machine.)

---

## Task 8: Wire `prerender_home.py` into CI

**Files:**
- Modify: `.github/workflows/deploy.yml`

- [ ] **Step 1: Add the prerender step to the `synthesize` job**

In `.github/workflows/deploy.yml`, find:

```yaml
      - name: Run synthesizer
        # ENVIRONMENT=production — structured JSON logs (infrastructure/logger.py
        # StructuredFormatter), не HumanFormatter. До этого CI работал с
        # ENVIRONMENT по умолчанию ("local") — цветной текст в raw логе раннера,
        # который никто не парсит. См. scripts/check_error_rate.py (MON07).
        run: ENVIRONMENT=production PYTHONHASHSEED=0 python3 scripts/synthesizer.py 2> /tmp/synth.log; cat /tmp/synth.log
```

Replace with:

```yaml
      - name: Run synthesizer
        # ENVIRONMENT=production — structured JSON logs (infrastructure/logger.py
        # StructuredFormatter), не HumanFormatter. До этого CI работал с
        # ENVIRONMENT по умолчанию ("local") — цветной текст в raw логе раннера,
        # который никто не парсит. См. scripts/check_error_rate.py (MON07).
        run: ENVIRONMENT=production PYTHONHASHSEED=0 python3 scripts/synthesizer.py 2> /tmp/synth.log; cat /tmp/synth.log

      - name: Prerender home page snapshot for crawlers (AEO)
        # 2026-08-16: index.html целиком рендерится JS — краулер без его
        # исполнения (историческая практика части AI-краулеров) видит пустые
        # <div>. Дописывает статический текст топ-нарратива между маркерами
        # PRERENDER:HOME:START/END, используя ТОЛЬКО ЧТО пересчитанный
        # data/synthesis_cache.json выше — снимок никогда не расходится с
        # реальным состоянием синтеза. Коммитится тем же sync-PR, что и
        # synthesis_cache.json (см. шаг "Commit synthesis cache via PR" ниже).
        run: python3 scripts/prerender_home.py
```

- [ ] **Step 2: Include `index.html` in the sync-PR commit**

In the same file, find:

```yaml
          git add data/synthesis_cache.json
          # data/synthesis_history_count.json: no-op add если update_synthesis_history.py
          # выше не тронул файл (0 реально изменившихся кластеров, см. его докстринг) —
          # git add на неизменённый файл безопасен и ничего не коммитит.
          git add data/synthesis_history_count.json
```

Replace with:

```yaml
          git add data/synthesis_cache.json
          # data/synthesis_history_count.json: no-op add если update_synthesis_history.py
          # выше не тронул файл (0 реально изменившихся кластеров, см. его докстринг) —
          # git add на неизменённый файл безопасен и ничего не коммитит.
          git add data/synthesis_history_count.json
          # 2026-08-16: index.html — снимок для краулеров (prerender_home.py
          # выше), меняется только между PRERENDER:HOME маркерами, тот же
          # no-op-safe git add, что и для synthesis_history_count.json.
          git add index.html
```

- [ ] **Step 3: Confirm the diff-check step doesn't get confused by an index.html-only change**

Read `scripts/cache_diff_check.py` to confirm it only compares `data/synthesis_cache.json` content (not `index.html`) — if the underlying narrative data is unchanged but `prerender_home.py` still ran (idempotent, see Task 7 Step 6's idempotency test), `index.html` should end up byte-identical too, so `git add index.html` stages no actual change and the "meaningful diff" check (which gates the whole commit-and-PR step) is unaffected either way.

Run: `grep -n "def " scripts/cache_diff_check.py`

Confirm the function only reads/diffs `data/synthesis_cache.json` paths passed as arguments — it does not scan working-tree changes generally, so `index.html` being staged-but-unchanged has no effect on its logic. No code change needed here, this step is verification only.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "feat: встроить prerender_home.py в CI synthesize job"
```

---

## Task 9: Final verification and PR

**Files:** none (verification only)

- [ ] **Step 1: Run the complete test suite one more time**

Run: `python scripts/update_js_cache_bust.py && PYTHONHASHSEED=0 python -m pytest -q`
Expected: all passing, no skips beyond the pre-existing Node-unavailable skip

- [ ] **Step 2: Manual browser check of the full redesigned home page (repeat of Task 5, now with Part 2 files present)**

```bash
cd "D:\Claude\Bitcoin-Intel" && python -m http.server 8801
```

Open `http://localhost:8801/robots.txt` — confirm it serves as plain text with the expected User-agent blocks. Open `http://localhost:8801/sitemap.xml` — confirm it renders as valid XML in the browser. View-source on `http://localhost:8801/index.html` — confirm the JSON-LD `<script type="application/ld+json">` block is present and the `PRERENDER:HOME` markers exist (empty, since this is the dev copy — real content only appears after a CI run).

- [ ] **Step 3: Confirm commits are in place**

Run: `git log --oneline main..HEAD`
Expected: 8 commits — Tasks 1-4 (Part 1) + Tasks 6-8 (Part 2), plus the earlier design-doc commit from the brainstorming step already on this branch (`feat/home-page-reorg`). (Task 5 and this task have no commits — verification only.)

- [ ] **Step 4: Push and open the PR**

```bash
git push -u origin feat/home-page-reorg
gh pr create --title "feat: реорганизация ОБЗОРА + AEO-фундамент" --body "$(cat <<'EOF'
## Summary
- ОБЗОР: определение сайта → главная история (полная карточка) → ещё нарративы (свёрнутые строки → ДАЙДЖЕСТ по кластеру) → 4 плитки-портала на реальные кластеры навигации → компактный тикер (цена/фаза/сигналы)
- График цены, фаза цикла, таблица последних блоков — перенесены (не удалены) на МЕТРИКИ и ПУЛЫ, где тематически и место
- AEO-фундамент: robots.txt (явно пускает GPTBot/ClaudeBot/PerplexityBot/Google-Extended/CCBot), sitemap.xml, Schema.org WebSite JSON-LD
- scripts/prerender_home.py — встроен в существующий CI synthesize job, пишет статический снимок топ-нарратива в index.html при каждом content-значимом изменении сигналов, коммитится тем же sync-PR что и synthesis_cache.json — краулеры без JS теперь видят реальный текст
- Design doc: docs/superpowers/specs/2026-08-16-home-page-reorg-design.md
- Plan: docs/superpowers/plans/2026-08-16-home-page-reorg.md

## Test plan
- [x] PYTHONHASHSEED=0 python -m pytest -q — все тесты зелёные
- [x] Ручная проверка в браузере (Tasks 5, 9) — редизайн ОБЗОРА соответствует утверждённому макету, перенесённые панели работают на новых вкладках, robots.txt/sitemap.xml/JSON-LD валидны
EOF
)"
```

- [ ] **Step 5: Report the PR URL to the user and wait for merge instruction**

Do not merge without explicit user confirmation (established pattern this session).
