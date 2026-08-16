# Theory Tab Card Reorg Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `theory-toc` into a grouped card grid (ОСНОВЫ / БЕЗОПАСНОСТЬ / МЕДИА) without breaking the two other tabs sharing `renderTOC()`, and turn Saylor Series into a real index→single-episode sub-hub instead of rendering all episodes inline on one long page.

**Architecture:** `renderTOC(containerId, items)` gets an optional grouped input shape (`[{group, items}]`) — flat-array callers (`macrocontext-toc`, `lightning-toc`) are auto-wrapped into one unnamed group internally, so their output only changes visually (grid instead of stacked rows), not structurally. `renderSaylorSeriesSection()` is split into `showSaylorSeriesIndex()` (card grid only) and `showSaylorEpisode(id)` (renders exactly one episode via the existing `renderTheoryTopic()`, plus a back link); `related_episodes` badges call a new `goToSaylorEpisode(id)` that renders-then-scrolls instead of a bare `scrollIntoView`. Full design: `docs/superpowers/specs/2026-08-16-theory-tab-card-reorg-design.md`.

**Tech Stack:** Vanilla JS (`js/app-main.js`), inline CSS (`index.html` `<style>`), Python/pytest + Node harness (`tests/conftest.py::extract_js_function`, `run_node_js`).

---

## Task 1: Card-grid CSS

**Files:**
- Modify: `index.html` (CSS block, near `.ep-fn-badge` definitions around line 948-962)

- [ ] **Step 1: Add the new classes**

In `index.html`, find:

```css
.ep-fn-badge {
  display: inline-flex; align-items: stretch; border-radius: 3px; overflow: hidden; cursor: pointer;
}
```

Insert immediately **before** that block:

```css
/* ── КАРТОЧНОЕ ОГЛАВЛЕНИЕ (2026-08-16) — общий визуальный язык для
   renderTOC() (theory-toc/macrocontext-toc/lightning-toc) и индекса
   эпизодов Saylor Series. Те же токены, что были у списка строк
   (var(--serif) italic заголовок, var(--dim) подзаголовок, var(--mono)
   var(--btc) номер) — просто в форме плитки, не новый визуальный язык. */
.toc-card-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px; margin-bottom: 16px;
}
.toc-card-grid:last-child { margin-bottom: 0; }
.toc-card {
  border: 1px solid var(--line); padding: 12px 14px; cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.toc-card:hover { border-color: var(--btc); background: var(--bg3); }
.toc-card-num { font-family: var(--mono); font-size: 10px; color: var(--btc); }
.toc-card-title {
  font-family: var(--serif); font-style: italic; font-weight: 500;
  font-size: 14px; color: var(--ivory); margin-top: 4px; line-height: 1.3;
}
.toc-card-subtitle { font-size: 10px; color: var(--dim); margin-top: 4px; line-height: 1.4; }
.toc-group-label {
  font-family: var(--mono); font-size: 10px; font-weight: 700; color: var(--btc);
  letter-spacing: 0.08em; margin: 0 0 8px;
}
```

- [ ] **Step 2: Verify it's valid CSS inside the existing `<style>` block**

Run: `grep -c "toc-card-grid" index.html` — expect `2` (one in the new CSS block, one will appear later once Task 2/4 use it in JS-generated markup — for now just confirm the CSS rule itself is present once).

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat: CSS для карточного оглавления (toc-card-grid)"
```

---

## Task 2: `renderTOC()` — grouped input, card-grid render

**Files:**
- Modify: `js/app-main.js` (`renderTOC()`, currently at line 3213)
- Test: `tests/unit/test_render_toc_grouping.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_render_toc_grouping.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_render_toc_grouping.py -v`
Expected: FAIL — current `renderTOC()` has no `toc-card-grid`/`toc-group-label` output, renders rows not cards.

- [ ] **Step 3: Rewrite `renderTOC()`**

In `js/app-main.js`, replace the entire current function body (lines 3213-3243, from `function renderTOC(containerId, items) {` through its closing `}`):

```js
function renderTOC(containerId, items) {
  const el = document.getElementById(containerId);
  if (!el) return;

  // 2026-08-16: items может быть либо плоским массивом записей
  // ({target,title,subtitle}, как раньше — macrocontext-toc/lightning-toc),
  // либо массивом групп ({group, items:[...]}, как теперь theory-toc).
  // Приводим плоский случай к одной безымянной группе — дальше один и тот
  // же путь рендера, не два параллельных куска кода.
  const groups = (items.length && items[0].group !== undefined)
    ? items
    : [{ group: null, items: items }];

  const n = groups.reduce(function(sum, g) { return sum + g.items.length; }, 0);
  let counter = 0;

  let html = '<div style="margin-top:12px;border:1px solid var(--btc);background:var(--bg2)">';
  html += '<div style="display:flex;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid var(--btc);background:var(--bg3)">'
    + '<span>📑</span>'
    + '<span style="font-family:var(--mono);font-size:11px;font-weight:700;color:var(--btc);letter-spacing:0.08em">СОДЕРЖАНИЕ</span>'
    + '<span style="margin-left:auto;font-family:var(--mono);font-size:9px;color:var(--btc);border:1px solid rgba(247,147,26,0.4);padding:2px 7px;border-radius:2px">' + n + '</span>'
    + '</div>';

  html += '<div style="padding:12px 14px">';
  html += groups.map(function(g) {
    let groupHtml = g.group ? '<div class="toc-group-label">' + sanitize(g.group) + '</div>' : '';
    groupHtml += '<div class="toc-card-grid">';
    groupHtml += g.items.map(function(item) {
      counter++;
      const num = String(counter).padStart(2, '0');
      return '<div class="toc-card" onclick="uncollapseAndScrollTo(\'' + item.target + '\')">'
        + '<span class="toc-card-num">' + num + '</span>'
        + '<div class="toc-card-title">' + sanitize(item.title) + '</div>'
        + '<div class="toc-card-subtitle">' + sanitize(item.subtitle) + '</div>'
        + '</div>';
    }).join('');
    groupHtml += '</div>';
    return groupHtml;
  }).join('');
  html += '</div>';

  html += '</div>';
  el.innerHTML = html;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_render_toc_grouping.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Run full suite to check no regressions**

Run: `python scripts/update_js_cache_bust.py && PYTHONHASHSEED=0 python -m pytest -q`
Expected: all passing — pay attention to `tests/unit/test_theory_toc_completeness.py` specifically (regex-based scan of the `renderTOC('theory-toc', [...])` literal must still find it correctly once Task 3 changes its shape; this task alone doesn't change the `theory-toc` call site yet, so it must already pass unchanged here)

- [ ] **Step 6: Commit**

```bash
git add js/app-main.js index.html tests/unit/test_render_toc_grouping.py
git commit -m "feat: renderTOC() — карточная сетка + опциональная группировка"
```

---

## Task 3: Group `theory-toc`

**Files:**
- Modify: `js/app-main.js` (`renderTOC('theory-toc', [...])` call, currently lines 3245-3255)

- [ ] **Step 1: Replace the flat array with grouped data**

Replace:

```js
renderTOC('theory-toc', [
  { target: 'theory-money', title: 'Что такое деньги', subtitle: 'Функции, свойства, история от бартера до Bitcoin' },
  { target: 'theory-network', title: 'Семь сетевых эффектов', subtitle: 'Почему Bitcoin побеждает структурно' },
  { target: 'theory-governance', title: 'Bitcoin Governance', subtitle: 'Как принимаются решения без центральной власти' },
  { target: 'theory-dca', title: 'Стратегия DCA', subtitle: 'Как накапливать без эмоций и таймирования' },
  { target: 'theory-passphrase', title: 'Насколько надёжна ваша парольная фраза?', subtitle: 'Diceware, математика взлома, Trezor Trusted Display' },
  { target: 'theory-hashrate-units', title: 'Хешрейт и сложность: единицы измерения', subtitle: 'TH/s vs T — почему их путают' },
  { target: 'theory-dice-seed', title: 'Сид на костях: как создать ключ, не доверяя генератору', subtitle: 'Энтропия костью вместо доверия закрытому генератору кошелька' },
  { target: 'theory-quantum', title: 'Квантовая угроза: подготовка началась', subtitle: 'Подготовка к угрозе, которой формально ещё нет' },
  { target: 'theory-saylor-series-mount', title: 'Saylor Series', subtitle: 'Роберт Бридлав и Майкл Сэйлор — 17 эпизодов о деньгах и цивилизации' }
]);
```

With:

```js
renderTOC('theory-toc', [
  { group: 'ОСНОВЫ', items: [
    { target: 'theory-money', title: 'Что такое деньги', subtitle: 'Функции, свойства, история от бартера до Bitcoin' },
    { target: 'theory-network', title: 'Семь сетевых эффектов', subtitle: 'Почему Bitcoin побеждает структурно' },
    { target: 'theory-governance', title: 'Bitcoin Governance', subtitle: 'Как принимаются решения без центральной власти' },
    { target: 'theory-dca', title: 'Стратегия DCA', subtitle: 'Как накапливать без эмоций и таймирования' },
    { target: 'theory-hashrate-units', title: 'Хешрейт и сложность: единицы измерения', subtitle: 'TH/s vs T — почему их путают' }
  ]},
  { group: 'БЕЗОПАСНОСТЬ', items: [
    { target: 'theory-passphrase', title: 'Насколько надёжна ваша парольная фраза?', subtitle: 'Diceware, математика взлома, Trezor Trusted Display' },
    { target: 'theory-dice-seed', title: 'Сид на костях: как создать ключ, не доверяя генератору', subtitle: 'Энтропия костью вместо доверия закрытому генератору кошелька' },
    { target: 'theory-quantum', title: 'Квантовая угроза: подготовка началась', subtitle: 'Подготовка к угрозе, которой формально ещё нет' }
  ]},
  { group: 'МЕДИА', items: [
    { target: 'theory-saylor-series-mount', title: 'Saylor Series', subtitle: 'Роберт Бридлав и Майкл Сэйлор — 17 эпизодов о деньгах и цивилизации' }
  ]}
]);
```

- [ ] **Step 2: Run TOC completeness + grouping tests**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_theory_toc_completeness.py tests/unit/test_render_toc_grouping.py -v`
Expected: PASS — `test_theory_toc_completeness.py` extracts `target:` values via regex regardless of nesting depth, so grouping doesn't break it; confirms no panel silently dropped during the data move

- [ ] **Step 3: Update cache-bust, run full suite**

Run: `python scripts/update_js_cache_bust.py && PYTHONHASHSEED=0 python -m pytest -q`
Expected: all passing

- [ ] **Step 4: Commit**

```bash
git add js/app-main.js index.html
git commit -m "feat: сгруппировать theory-toc — ОСНОВЫ / БЕЗОПАСНОСТЬ / МЕДИА"
```

---

## Task 4: Saylor Series as index→episode sub-hub

**Files:**
- Modify: `js/app-main.js` (`renderSaylorSeriesSection()` at line 849, and the `related_episodes` block inside `renderTheoryTopic()`)
- Modify: `tests/unit/test_saylor_series_section.py` (rewrite the now-outdated index+panel test, update related-episodes onclick assertion)

- [ ] **Step 1: Write the failing tests**

In `tests/unit/test_saylor_series_section.py`, replace the existing `test_render_saylor_series_section_builds_index_and_episode_panels` function (and its preceding `render_saylor_source` fixture stays, just add `showSaylorSeriesIndex`/`showSaylorEpisode`/`goToSaylorEpisode` to the extracted functions list) with:

```python
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
        extract_js_function(src, "showSaylorSeriesIndex"),
        extract_js_function(src, "showSaylorEpisode"),
        extract_js_function(src, "goToSaylorEpisode"),
    ]
    return "\n\n".join(funcs)


_TWO_EPISODES_JS = """
const THEORY_TOPICS = [
  {
    id: 'saylor-series-01', target_group: 'saylor-series', episode_number: 1,
    panel_title: 'Огонь, праща и Рим', panel_tag: 'SAYLOR SERIES · 01',
    items: [{ icon: '01', label: 'Огонь', paragraphs: ['текст огня'] }]
  },
  {
    id: 'saylor-series-02', target_group: 'saylor-series', episode_number: 2,
    panel_title: 'Империи, сталь и антибиотики', panel_tag: 'SAYLOR SERIES · 02',
    related_episodes: ['saylor-series-01'],
    items: [{ icon: '01', label: 'Империя', paragraphs: ['текст империи'] }]
  }
];
const registry = {};
function makeMount(id) { return { innerHTML: '' }; }
registry['theory-saylor-series-mount'] = makeMount('theory-saylor-series-mount');
const document = { getElementById: function(id) { return registry[id] || null; } };
"""


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
def test_render_saylor_series_section_shows_index_only_not_full_episodes(render_saylor_source):
    js = render_saylor_source + _TWO_EPISODES_JS + """
renderSaylorSeriesSection();
const html = registry['theory-saylor-series-mount'].innerHTML;
console.log(JSON.stringify({
  hasIndexTitles: html.includes('Огонь, праща и Рим') && html.includes('Империи, сталь и антибиотики'),
  hasFullEpisodeBody: html.includes('текст огня') || html.includes('текст империи')
}));
"""
    result = run_node_js(js)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"
    out = json.loads(result.stdout)
    assert out["hasIndexTitles"] is True
    assert out["hasFullEpisodeBody"] is False, (
        "После renderSaylorSeriesSection() в DOM не должно быть полного тела "
        "ни одного эпизода — только карточки индекса, до клика"
    )


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
def test_show_saylor_episode_renders_exactly_one_episode_with_back_link(render_saylor_source):
    js = render_saylor_source + _TWO_EPISODES_JS + """
showSaylorEpisode('saylor-series-01');
const html = registry['theory-saylor-series-mount'].innerHTML;
console.log(JSON.stringify({
  hasEpisode1Body: html.includes('текст огня'),
  hasEpisode2Body: html.includes('текст империи'),
  hasBackLink: html.includes('showSaylorSeriesIndex()')
}));
"""
    result = run_node_js(js)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"
    out = json.loads(result.stdout)
    assert out["hasEpisode1Body"] is True
    assert out["hasEpisode2Body"] is False, "Только показанный эпизод должен быть в DOM, не оба сразу"
    assert out["hasBackLink"] is True


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
def test_show_saylor_series_index_returns_from_episode_view(render_saylor_source):
    js = render_saylor_source + _TWO_EPISODES_JS + """
showSaylorEpisode('saylor-series-01');
showSaylorSeriesIndex();
const html = registry['theory-saylor-series-mount'].innerHTML;
console.log(JSON.stringify({
  hasIndexTitles: html.includes('Огонь, праща и Рим') && html.includes('Империи, сталь и антибиотики'),
  hasFullEpisodeBody: html.includes('текст огня')
}));
"""
    result = run_node_js(js)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"
    out = json.loads(result.stdout)
    assert out["hasIndexTitles"] is True
    assert out["hasFullEpisodeBody"] is False, "Возврат к индексу не должен оставлять старую панель эпизода в DOM"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
def test_go_to_saylor_episode_renders_target_if_not_already_shown(render_saylor_source):
    js = render_saylor_source + _TWO_EPISODES_JS + """
// Сейчас показан индекс (ничего не отрендерено) — related_episodes-бейдж
// эпизода 2 должен сначала отрендерить эпизод 1, затем "проскроллить"
// (в мини-DOM без layout scrollIntoView просто не существует — не мокаем,
// раз не вызывается ни в одном из путей теста; если бы вызывался — упал бы
// с понятной ошибкой "not a function", а не молча прошёл).
goToSaylorEpisode('saylor-series-01');
const html = registry['theory-saylor-series-mount'].innerHTML;
console.log(JSON.stringify({ hasEpisode1Body: html.includes('текст огня') }));
"""
    result = run_node_js(js)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"
    out = json.loads(result.stdout)
    assert out["hasEpisode1Body"] is True
```

Delete the now-outdated `test_render_saylor_series_section_builds_index_and_episode_panels` test entirely (it asserted the old "everything inline at once" behavior — superseded by the four tests above).

Then update `TestRelatedEpisodes::test_related_episode_renders_clickable_link_with_looked_up_title` — replace its last assertion line:

```python
        assert "onclick=\"document.getElementById('saylor-series-01').scrollIntoView" in html
```

with:

```python
        assert "onclick=\"goToSaylorEpisode('saylor-series-01')\"" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_saylor_series_section.py -v`
Expected: FAIL on the new tests (`showSaylorSeriesIndex`/`showSaylorEpisode`/`goToSaylorEpisode` not defined yet) and on the updated related-episodes onclick assertion (still emits the old `scrollIntoView` form)

- [ ] **Step 3: Rewrite `renderSaylorSeriesSection()` and add the three new functions**

In `js/app-main.js`, replace the entire current function (from the comment block starting `// Эпизоды — топики THEORY_TOPICS.json с target_group: 'saylor-series',` through the closing `}` of `renderSaylorSeriesSection()`, i.e. through what's currently line 879) with:

```js
// Эпизоды — топики THEORY_TOPICS.json с target_group: 'saylor-series',
// пропущенные generic-сканером renderTheoryTopics() (см. правку там же).
// 2026-08-16: раньше renderSaylorSeriesSection() рендерила индекс + ВСЕ
// полные панели эпизодов разом (episodes.map(renderTheoryTopic).join(''))
// — при 17 эпизодах это очень длинная страница. Теперь — index→detail:
// по умолчанию показывается только сетка карточек (showSaylorSeriesIndex),
// клик по карточке рендерит РОВНО один эпизод (showSaylorEpisode), кнопка
// "назад" возвращает к сетке. Панель эпизода — тот же renderTheoryTopic(),
// что у theory-dice-seed/theory-quantum, без дублирования кода.
function renderSaylorSeriesSection() {
  const el = document.getElementById('theory-saylor-series-mount');
  if (!el) return;
  const episodes = THEORY_TOPICS.filter(function(t) { return t.target_group === 'saylor-series'; });
  if (!episodes.length) return;
  showSaylorSeriesIndex();
}

function showSaylorSeriesIndex() {
  const el = document.getElementById('theory-saylor-series-mount');
  if (!el) return;
  const episodes = THEORY_TOPICS.filter(function(t) { return t.target_group === 'saylor-series'; });

  let html = '<div class="panel" style="margin-top:12px">';
  html += '<div class="panel-head"><span class="panel-title">Saylor Series</span>'
    + '<span class="panel-tag">BREEDLOVE × SAYLOR</span></div>';
  html += '<div style="padding:12px 14px;border-bottom:1px solid var(--line)">'
    + '<div style="font-family:var(--sans);font-size:12px;color:var(--dim);line-height:1.6">'
    + 'Роберт Бридлав и Майкл Сэйлор — 17 эпизодов о деньгах, энергии и цивилизации. Разбор по одному эпизоду за раз.'
    + '</div></div>';

  html += '<div style="padding:12px 14px"><div class="toc-card-grid">';
  html += episodes.map(function(ep) {
    const num = String(ep.episode_number || '').padStart(2, '0');
    return '<div class="toc-card" onclick="showSaylorEpisode(\'' + sanitize(ep.id) + '\')">'
      + '<span class="toc-card-num">' + num + '</span>'
      + '<div class="toc-card-title">' + sanitize(ep.panel_title) + '</div>'
      + '</div>';
  }).join('');
  html += '</div></div>';

  html += '</div>';
  el.innerHTML = html;
}

function showSaylorEpisode(id) {
  const el = document.getElementById('theory-saylor-series-mount');
  if (!el) return;
  const episode = THEORY_TOPICS.find(function(t) { return t.id === id && t.target_group === 'saylor-series'; });
  if (!episode) return;

  let html = '<div style="margin-top:12px">';
  html += '<div onclick="showSaylorSeriesIndex()" '
    + 'style="cursor:pointer;font-family:var(--mono);font-size:10px;color:var(--btc);padding:8px 0;display:flex;align-items:center;gap:6px">'
    + '<span>←</span><span>Ко всем эпизодам Saylor Series</span>'
    + '</div>';
  html += renderTheoryTopic(episode);
  html += '</div>';
  el.innerHTML = html;
}

// related_episodes-бейджи (см. renderTheoryTopic()) вызывают ЭТУ функцию,
// не голый scrollIntoView — целевой эпизод может быть сейчас не в DOM
// (показан индекс или другой эпизод), его сперва нужно отрендерить.
function goToSaylorEpisode(id) {
  if (!document.getElementById(id)) {
    showSaylorEpisode(id);
  }
  const target = document.getElementById(id);
  if (target) target.scrollIntoView({ behavior: 'smooth' });
}
```

- [ ] **Step 4: Update the `related_episodes` badge onclick**

In `js/app-main.js`, inside `renderTheoryTopic()`, find the `related_episodes` block (the `.map(function(rid) { ... })` that builds `.ep-fn-badge` markup) and change:

```js
          return '<div class="ep-fn-badge" onclick="document.getElementById(\'' + sanitize(rid) + '\').scrollIntoView({behavior:\'smooth\'})">'
```

to:

```js
          return '<div class="ep-fn-badge" onclick="goToSaylorEpisode(\'' + sanitize(rid) + '\')">'
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_saylor_series_section.py -v`
Expected: PASS (all tests, including the four new ones and the updated related-episodes assertion)

- [ ] **Step 6: Run full suite**

Run: `python scripts/update_js_cache_bust.py && PYTHONHASHSEED=0 python -m pytest -q`
Expected: all passing

- [ ] **Step 7: Commit**

```bash
git add js/app-main.js index.html tests/unit/test_saylor_series_section.py
git commit -m "feat: Saylor Series — индекс/эпизод вместо одной длинной страницы"
```

---

## Task 5: Manual verification in browser

**Files:** none (verification only)

- [ ] **Step 1: Serve the site locally**

```bash
cd "D:\Claude\Bitcoin-Intel" && python -m http.server 8794
```

- [ ] **Step 2: Open ТЕОРИЯ tab, confirm grouped card grid**

Navigate to `http://localhost:8794/index.html`, run in console (or via browser automation): `showTab('theory', null)`. Confirm «📑 СОДЕРЖАНИЕ» now shows three labeled groups (ОСНОВЫ, БЕЗОПАСНОСТЬ, МЕДИА) as card grids, count badge still shows 9. Click a card from each group — confirm it still scrolls to the right panel on the long page (unchanged behavior for the 8 non-Saylor panels).

- [ ] **Step 3: Confirm Saylor Series index→episode flow**

Click the МЕДИА → Saylor Series card. Confirm it scrolls to a panel showing only episode index cards (no long episode bodies visible). Click episode 1's card — confirm only episode 1's full panel renders (not both episodes), with a "← Ко всем эпизодам Saylor Series" link above it. Click that link — confirm it returns to the index grid, and episode 1's body is gone from the DOM (not just visually hidden — check via `document.getElementById('saylor-series-01')` returning `null` after returning to index).

- [ ] **Step 4: Confirm related_episodes badge works across the index/detail split**

From episode 2's panel, click its "ЭПИЗОД 01" related-episode badge. Confirm episode 1 renders and the page scrolls to it (this exercises `goToSaylorEpisode()` rendering on demand, since episode 1 wasn't already in the DOM).

- [ ] **Step 5: Confirm `macrocontext-toc`/`lightning-toc` still work**

Switch to MACROCONTEXT and LIGHTNING tabs, confirm their «📑 СОДЕРЖАНИЕ» now render as card grids too (visual-only change), all cards still click through to the right panel, no group labels appear (flat data, no `group` field).

If any check fails, stop and diagnose before proceeding — do not push to `main`.

---

## Task 6: Push and open PR

**Files:** none (git/gh operations only)

- [ ] **Step 1: Confirm all commits are in place**

Run: `git log --oneline main..HEAD`
Expected: 5 commits — CSS (Task 1), renderTOC() rewrite (Task 2), theory-toc grouping (Task 3), Saylor Series sub-hub (Task 4), plus the earlier design-doc commit already on this branch (`feat/theory-card-reorg`) from the brainstorming step

- [ ] **Step 2: Push the branch**

```bash
git push -u origin feat/theory-card-reorg
```

- [ ] **Step 3: Open the PR**

```bash
gh pr create --title "feat: карточное оглавление ТЕОРИИ + Saylor Series как под-хаб" --body "$(cat <<'EOF'
## Summary
- renderTOC() — карточная сетка вместо списка строк, с опциональной группировкой (обратная совместимость: плоский массив, как у macrocontext-toc/lightning-toc, оборачивается в одну безымянную группу)
- theory-toc сгруппирован: ОСНОВЫ / БЕЗОПАСНОСТЬ / МЕДИА
- Saylor Series переведён с "индекс + все 17 панелей разом" на "индекс → клик → ровно один эпизод + кнопка назад" (showSaylorSeriesIndex/showSaylorEpisode)
- related_episodes-бейджи теперь вызывают goToSaylorEpisode() — рендерят целевой эпизод по требованию, если его нет в DOM, потом скроллят
- Design doc: docs/superpowers/specs/2026-08-16-theory-tab-card-reorg-design.md

## Test plan
- [x] PYTHONHASHSEED=0 python -m pytest -q — все тесты зелёные
- [x] Ручная проверка в браузере (Task 5 плана реализации) — группировка, index→episode переход, related_episodes-бейдж между непоказанными эпизодами, macrocontext/lightning TOC не сломаны
EOF
)"
```

- [ ] **Step 4: Report the PR URL to the user and wait for merge instruction**

Do not merge without explicit user confirmation (established pattern this session).
