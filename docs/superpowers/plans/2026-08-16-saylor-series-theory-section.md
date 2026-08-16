# Saylor Series Theory Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Saylor Series" mini-section inside the ТЕОРИЯ tab — one TOC row → episode-index cards → full per-episode panels — starting with episode 1, reusing `THEORY_TOPICS.json`/`renderTheoryTopic()` so entity/signal cross-link mechanisms work with zero duplication.

**Architecture:** Episodes are `THEORY_TOPICS.json` topics tagged `target_group: "saylor-series"`. `renderTheoryTopics()` (the generic scanner) skips them. A new `renderSaylorSeriesSection()` renders an index card list plus, for each episode, a full panel via the existing `renderTheoryTopic()` — into one static mount `<div id="theory-saylor-series-mount"></div>` inside the ТЕОРИЯ tab. One new row in `renderTOC('theory-toc', [...])`. Full design: `docs/superpowers/specs/2026-08-16-saylor-series-theory-section-design.md`.

**Tech Stack:** Vanilla JS (`js/app-main.js`), static JSON data (`THEORY_TOPICS.json`, `THEORY_ESSAYS.json`), Python/pytest + Node harness for tests (`tests/conftest.py::extract_js_function`, `run_node_js`).

---

## Task 1: Add `saylor-series-01` topic data to THEORY_TOPICS.json

**Files:**
- Modify: `js/app-main.js` (`renderAccItem()`, starting at `function renderAccItem(item) {`)
- Modify: `THEORY_TOPICS.json`
- Test: `tests/unit/test_render_acc_item_lists.py` (new)

> **Context (added after user review of this plan):** the user's original episode-1 draft has a real bulleted list in the "Рим" section (4 items with bold lead words). The original plan flattened it into one semicolon-joined paragraph because `renderAccItem()` only supports plain `<p>` paragraphs. The user chose to extend the renderer instead of losing the list structure — do that first, then use it in the episode data below.

- [ ] **Step 1: Write the failing test for list support**

Create `tests/unit/test_render_acc_item_lists.py`:

```python
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
        import json
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
        import json
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert '<ul' in html and '</ul>' in html
        assert html.count('<li') == 2
        assert '<strong>Первый</strong> пункт.' in html
        assert '<strong>Второй</strong> пункт.' in html
        # порядок: вступление -> список -> вывод
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
        import json
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert '<script>' not in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_render_acc_item_lists.py -v`
Expected: FAIL — `test_list_paragraph_renders_as_ul_li` and `test_list_items_go_through_sanitize_strong` fail (no `<ul>` emitted, list object gets passed straight into `sanitizeStrong()` as `[object Object]` or similar); `test_string_paragraph_still_renders_as_p` should already PASS (documents current behavior before the change)

- [ ] **Step 3: Extend `renderAccItem()` to support list paragraphs**

In `js/app-main.js`, find:

```js
  if (item.paragraphs && item.paragraphs.length) {
    html += item.paragraphs.map(function(p){ return '<p>' + sanitizeStrong(p) + '</p>'; }).join('');
  }
```

Replace with:

```js
  if (item.paragraphs && item.paragraphs.length) {
    // 2026-08-16: элемент paragraphs может быть либо строкой (обычный
    // абзац, как раньше), либо { list: [...] } — маркированный список.
    // Добавлено для Saylor Series (секция "Рим" эпизода 1 — реальный
    // список в исходном тексте пользователя, не искусственно навязанная
    // структура). sanitizeStrong() применяется к каждому пункту списка
    // тем же путём, что и к обычным абзацам — не отдельная лазейка мимо
    // экранирования.
    html += item.paragraphs.map(function(p){
      if (p && typeof p === 'object' && p.list) {
        return '<ul style="margin:8px 0 8px 18px;padding:0;display:flex;flex-direction:column;gap:6px">'
          + p.list.map(function(li){ return '<li style="font-size:12px;color:var(--dim);line-height:1.6">' + sanitizeStrong(li) + '</li>'; }).join('')
          + '</ul>';
      }
      return '<p>' + sanitizeStrong(p) + '</p>';
    }).join('');
  }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_render_acc_item_lists.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Run full suite to check no regressions**

Run: `PYTHONHASHSEED=0 python -m pytest -q`
Expected: all passing — `renderAccItem()` is shared by every existing THEORY_TOPICS.json/THEORY_ESSAYS.json item, all of which use plain string paragraphs, so this must not change their output

- [ ] **Step 6: Commit the renderer change separately from the data**

```bash
git add js/app-main.js tests/unit/test_render_acc_item_lists.py
git commit -m "feat: поддержать маркированные списки в renderAccItem()"
```

- [ ] **Step 7: Append the episode 1 topic to the `topics` array**

Add this object as the last element of `topics` (keep valid JSON — comma after the previous topic's closing `}`):

```json
    {
      "id": "saylor-series-01",
      "target_group": "saylor-series",
      "episode_number": 1,
      "panel_title": "Огонь, праща и Рим: чему Майкл Сэйлор учит нас об энергии и цивилизации",
      "panel_tag": "SAYLOR SERIES · 01",
      "intro": "Когда Майкл Сэйлор говорит о Биткоине, он редко начинает с графиков и халвингов. Вместо этого — с огня, пращи и римских акведуков. В первом эпизоде подкаста Роберта Бридлава он выстраивает почти двухчасовую аргументацию «от первых принципов»: чтобы понять, зачем человечеству нужны деньги нового типа, сначала нужно понять, зачем человечеству вообще нужна цивилизация. Разбираем главные мысли разговора.",
      "items": [
        {
          "icon": "01",
          "label": "Главный тезис: цивилизация — это управление энергией",
          "paragraphs": [
            "Через весь разговор проходит одна идея: выживают не самые сильные, а те, кто эффективнее направляет энергию природы в нужное русло. Не борьба с природой напролом, а умение канализировать её силу — химическую, кинетическую, гравитационную — с минимальными потерями. Сэйлор называет прямое силовое противостояние с враждебной вселенной «глупым героизмом»: стратегия, которая почти всегда проигрывает более энергоэффективной альтернативе."
          ]
        },
        {
          "icon": "02",
          "label": "Огонь: первая технология направления энергии",
          "paragraphs": [
            "Огонь в разговоре — не просто удобство, а поворотный момент эволюции. Это первый инструмент, которым человек начал сознательно перенаправлять химическую энергию под свои задачи — от готовки пищи до защиты и производства. Сэйлор придаёт этому и духовное измерение: способность «играть с огнём» — то, что в буквальном смысле уникально для человечества среди всех видов."
          ]
        },
        {
          "icon": "03",
          "label": "Праща и стрела: оружие как канал кинетической энергии",
          "paragraphs": [
            "Тот же принцип — но для энергии движения. Метательное оружие позволило человеку поражать цель на расстоянии, не расходуя силы на прямой контакт. В подкасте приводится пример: во Вторую Пуническую войну римские пращники превосходили физически более сильные галльские племена — потому что технология направления энергии оказалась эффективнее грубой силы."
          ]
        },
        {
          "icon": "04",
          "label": "Вода: богатство, санитария и инженерия",
          "paragraphs": [
            "Следующий блок — вода как ресурс, без которого невозможна ни жизнь, ни цивилизация («три минуты без воздуха, три дня без воды, три месяца без еды»). Сэйлор приводит бобра как «инженера природы» — животное, которое в буквальном смысле строит инфраструктуру для управления водным потоком. А для человеческих городов вода — это не только питьё, но и санитария: без нормальной канализации даже развитая цивилизация (в разговоре упоминается Санторини) обречена на болезни и упадок."
          ]
        },
        {
          "icon": "05",
          "label": "Рим: система важнее героя",
          "paragraphs": [
            "Самая объёмная часть разговора — Рим как высшая точка «энергоэффективной» организации общества до Нового времени. Здесь несколько идей сплетаются вместе:",
            {
              "list": [
                "<strong>Ограничение сроков полномочий</strong> и ротация власти — защита от концентрации силы в одних руках.",
                "<strong>Меритократия</strong>, показанная на примере карьерного пути в армии — путь наверх открыт по заслугам, а не по происхождению.",
                "<strong>Децентрализация возможностей</strong> — распределённая, а не централизованная структура власти делает систему устойчивее («антихрупкой»).",
                "<strong>Стандартизация</strong> — римские дороги как единый «протокол логистики», акведуки как инженерия воды в масштабе целой империи. Именно стандартизация, по Сэйлору, даёт системе дарвиновское конкурентное преимущество перед соседями."
              ]
            },
            "Вывод из этого блока простой: побеждают не отдельные герои, а системы с работающими, устойчивыми протоколами."
          ],
          "crosslinks": [
            {
              "target_panel": "theory-network",
              "target_label": "Мировая резервная валюта · 07",
              "text": "Рим победил не силой, а тем что одновременно превзошёл соседей во всех своих протоколах — дороги, право, меритократия, акведуки. Та же логика структурной непобедимости — у Bitcoin как резервного протокола: нужно превзойти его сразу во всех семи сетевых эффектах."
            }
          ]
        },
        {
          "icon": "06",
          "label": "Крах протокола: как рушится Рим",
          "paragraphs": [
            "Если Рим — пример работающей системы, то его закат — пример того, что происходит, когда протоколы начинают ломаться. В разговоре крах связывается с порчей монеты и разрастанием политического и юридического аппарата — то есть с разрушением тех самых правил, на которых система держалась."
          ]
        },
        {
          "icon": "07",
          "label": "Боль как сигнал",
          "paragraphs": [
            "Разговор завершается неожиданно личной метафорой: боль — это сигнал, а не враг. Попытки заглушить сигнал — обезболить симптом вместо того, чтобы решить причину — опасны как для организма, так и для целой цивилизации."
          ]
        },
        {
          "icon": "08",
          "label": "При чём тут Биткоин",
          "paragraphs": [
            "Прямо в этом эпизоде о Биткоине почти не говорят — и это осознанный ход. Смысл первой серии подкаста — построить понятийный фундамент: деньги, как и огонь, праща или римские дороги, — это тоже протокол направления энергии (в данном случае — энергии человеческого труда и доверия). А значит, история о том, как рушатся протоколы Рима из-за порчи монеты и разрастания бюрократии, — это заодно и история о том, почему, по мнению Сэйлора, современным деньгам нужен более устойчивый стандарт."
          ]
        }
      ],
      "source_footer": "ИСТОЧНИК: подкаст Роберта Бридлава «What is Money?» с Майклом Сэйлором, эпизод 1 — «The Rise of Man through the Stone and Iron Ages» · 2020-11-20 · <a href=\"https://www.youtube.com/watch?v=4rvTppy1qLI\" target=\"_blank\" style=\"color:var(--btc);text-decoration:none\">оригинал на YouTube</a> · русский перевод — <a href=\"https://www.youtube.com/watch?v=vvB3amDxMFg\" target=\"_blank\" style=\"color:var(--btc);text-decoration:none\">канал BitKorn</a>"
    }
```

> **Found during execution:** a pre-existing test, `tests/unit/test_theory_dice_seed_mount_location.py::test_all_theory_tab_topics_have_explicit_mounts`, asserts every `THEORY_TOPICS.json` topic has either an explicit `{id}-mount` or is in an `INTENTIONAL_MACROCONTEXT_FALLBACK` set — it didn't know about the new `target_group` category (topics deliberately handled by a dedicated renderer, no `{id}-mount` of their own). Fixed by adding a `topic.get("target_group")` skip to that test, with a docstring note explaining the third category. File: `tests/unit/test_theory_dice_seed_mount_location.py`.

- [ ] **Step 8: Validate JSON**

Run: `python -c "import json; json.load(open('THEORY_TOPICS.json', encoding='utf-8'))" && echo OK`
Expected: `OK`

- [ ] **Step 9: Update `meta.last_updated`**

In `THEORY_TOPICS.json`, set `"last_updated": "2026-08-16"` in the `meta` block.

- [ ] **Step 10: Commit**

```bash
git add THEORY_TOPICS.json
git commit -m "signal: добавить эпизод 1 Saylor Series в THEORY_TOPICS.json"
```

(Note: this is data-only; JS to render it lands in Task 3. Committing separately keeps the diff reviewable — this step is still local, not pushed yet.)

---

## Task 2: Skip `target_group` topics in the generic scanner

**Files:**
- Modify: `js/app-main.js` (`renderTheoryTopics()`, currently starting at the line containing `function renderTheoryTopics() {`)
- Test: `tests/unit/test_saylor_series_section.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_saylor_series_section.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_saylor_series_section.py -v`
Expected: FAIL — `saylorMounted` is `True` (scanner doesn't yet skip `target_group` topics)

- [ ] **Step 3: Implement the skip in `renderTheoryTopics()`**

In `js/app-main.js`, find `function renderTheoryTopics() {` and the line `THEORY_TOPICS.forEach(function(topic) {`. Immediately after the existing idempotency check (`if (document.getElementById(topic.id)) return;`), add:

```js
    // 2026-08-16: топики с target_group рендерятся отдельным конвейером
    // (renderSaylorSeriesSection() и аналогичные в будущем) — не через
    // generic-сканер. Без этого пропуска они падают в общий контейнер
    // theory-topics-container, который физически лежит на вкладке
    // MACROCONTEXT, не ТЕОРИЯ (см. design doc 2026-08-16).
    if (topic.target_group) return;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_saylor_series_section.py -v`
Expected: PASS

- [ ] **Step 5: Run full suite to check no regressions**

Run: `PYTHONHASHSEED=0 python -m pytest -q`
Expected: all passing (no new failures)

- [ ] **Step 6: Commit**

```bash
git add js/app-main.js tests/unit/test_saylor_series_section.py
git commit -m "feat: пропускать target_group топики в generic-сканере renderTheoryTopics()"
```

---

## Task 3: `renderSaylorSeriesSection()` — index cards + per-episode panels

**Files:**
- Modify: `js/app-main.js` (add new function near `renderTheoryTopics()`; call it from the same place `renderTheoryTopics()` is triggered for the `theory` tab)
- Modify: `index.html` (add `<div id="theory-saylor-series-mount"></div>` inside `tab-theory`, after `theory-quantum-mount`)
- Test: `tests/unit/test_saylor_series_section.py` (extend)

- [ ] **Step 1: Add the mount div in index.html**

In `index.html`, find:
```html
    <div id="theory-quantum-mount"></div>
```
Replace with:
```html
    <div id="theory-quantum-mount"></div>
    <div id="theory-saylor-series-mount"></div>
```

- [ ] **Step 2: Write the failing test for the render function**

Append to `tests/unit/test_saylor_series_section.py`:

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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_saylor_series_section.py -v`
Expected: FAIL — `renderSaylorSeriesSection is not defined`

- [ ] **Step 4: Implement `renderSaylorSeriesSection()`**

In `js/app-main.js`, add this function directly after `renderTheoryTopics()`:

```js
// ── SAYLOR SERIES — мини-раздел внутри ТЕОРИИ ───────────────────────────
// Эпизоды — топики THEORY_TOPICS.json с target_group: 'saylor-series',
// пропущенные generic-сканером renderTheoryTopics() (см. правку там же).
// Индекс-карточки + полные панели эпизодов рендерятся сюда, в единственную
// статичную точку монтирования theory-saylor-series-mount — без раздувания
// theory-toc на 17 строк. Панель эпизода — тот же renderTheoryTopic(), что
// у theory-dice-seed/theory-quantum, без дублирования кода.
function renderSaylorSeriesSection() {
  const el = document.getElementById('theory-saylor-series-mount');
  if (!el) return;
  const episodes = THEORY_TOPICS.filter(function(t) { return t.target_group === 'saylor-series'; });
  if (!episodes.length) return;

  let html = '<div class="panel" style="margin-top:12px">';
  html += '<div class="panel-head"><span class="panel-title">Saylor Series</span>'
    + '<span class="panel-tag">BREEDLOVE × SAYLOR</span></div>';
  html += '<div style="padding:12px 14px;border-bottom:1px solid var(--line)">'
    + '<div style="font-family:var(--sans);font-size:12px;color:var(--dim);line-height:1.6">'
    + 'Роберт Бридлав и Майкл Сэйлор — 17 эпизодов о деньгах, энергии и цивилизации. Разбор по одному эпизоду за раз.'
    + '</div></div>';

  html += episodes.map(function(ep) {
    const num = String(ep.episode_number || '').padStart(2, '0');
    return '<div onclick="document.getElementById(\'' + sanitize(ep.id) + '\').scrollIntoView({behavior:\'smooth\'})" '
      + 'style="display:flex;align-items:center;gap:12px;padding:12px 14px;border-bottom:1px solid var(--line);cursor:pointer" '
      + 'onmouseover="this.style.background=\'var(--bg3)\'" onmouseout="this.style.background=\'\'">'
      + '<span style="font-family:var(--mono);font-size:10px;color:var(--btc);min-width:20px">' + num + '</span>'
      + '<div style="flex:1"><div style="font-family:var(--serif);font-style:italic;font-weight:500;font-size:14px;color:var(--ivory)">'
      + sanitize(ep.panel_title) + '</div></div>'
      + '<span style="color:var(--dim);font-size:14px">›</span>'
      + '</div>';
  }).join('');

  html += '</div>';
  html += episodes.map(renderTheoryTopic).join('');

  el.innerHTML = html;
}
```

- [ ] **Step 5: Call it where `theory` tab data is triggered**

In `js/app-main.js`, find `if (id === 'theory')` inside `triggerTabData()`. It currently calls `renderTheoryTopics()` then `renderTheoryEssays()`. Add the new call **after** `renderTheoryTopics()` and **before** `renderTheoryEssays()` (so `-essays` mounts inside episode panels exist before essays try to attach — same ordering rule as `test_trigger_tab_data_calls_topics_before_essays_for_theory` in `tests/unit/test_theory_topic_essay_mount.py`):

```js
renderTheoryTopics();
renderSaylorSeriesSection();
renderTheoryEssays();
```

- [ ] **Step 6: Run test to verify it passes**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_saylor_series_section.py -v`
Expected: PASS

- [ ] **Step 7: Run full suite**

Run: `PYTHONHASHSEED=0 python -m pytest -q`
Expected: all passing

> **Found during execution:** `tests/unit/test_site_map_sync.py` requires every literal `panel-title` in `js/app-main.js`/`index.html` to have a matching entry in `data/site_map.json` (per `docs/SITE_MAP.md`). The hardcoded `<span class="panel-title">Saylor Series</span>` in `renderSaylorSeriesSection()` needed a new manifest entry (`e111`, cluster `macro`/tab `theory`, grouped contiguously right after `e108` theory-quantum). Individual episode panel titles (`topic.panel_title`, data-driven, rendered through `sanitize(...)`) don't need their own entries — same pattern as `theory-dice-seed`/`theory-quantum`, which also only have one manifest entry each despite multi-item panels.

- [ ] **Step 8: Commit**

```bash
git add js/app-main.js index.html data/site_map.json tests/unit/test_saylor_series_section.py
git commit -m "feat: рендер индекса и панелей Saylor Series (renderSaylorSeriesSection)"
```

---

## Task 4: Add TOC row

**Files:**
- Modify: `js/app-main.js` (`renderTOC('theory-toc', [...])`)
- Modify: `tests/unit/test_theory_toc_completeness.py`

- [ ] **Step 1: Add the row**

In `js/app-main.js`, find the `renderTOC('theory-toc', [...])` array (ends with `theory-quantum` row added in the previous session). Add as the last element:

```js
  { target: 'theory-saylor-series-mount', title: 'Saylor Series', subtitle: 'Роберт Бридлав и Майкл Сэйлор — 17 эпизодов о деньгах и цивилизации' }
```

- [ ] **Step 2: Run the existing TOC completeness tests**

Run: `PYTHONHASHSEED=0 python -m pytest tests/unit/test_theory_toc_completeness.py -v`
Expected: PASS — `test_theory_toc_has_no_dangling_targets` confirms `theory-saylor-series-mount` resolves (added in Task 3 Step 1); `test_every_theory_tab_mounted_topic_is_in_theory_toc` is unaffected (it only checks `THEORY_TOPICS`-driven ids with a `{id}-mount` div — `saylor-series-01` has no such div, it's mounted by the dedicated function, so it's correctly outside that check's scope)

- [ ] **Step 3: Update `scripts/update_js_cache_bust.py`**

Run: `python scripts/update_js_cache_bust.py`
Expected: `OK: index.html обновлён`

- [ ] **Step 4: Run full suite**

Run: `PYTHONHASHSEED=0 python -m pytest -q`
Expected: all passing

- [ ] **Step 5: Commit**

```bash
git add js/app-main.js index.html
git commit -m "feat: добавить Saylor Series в оглавление вкладки ТЕОРИЯ"
```

---

## Task 5: Remove the superseded THEORY_ESSAYS.json entry

**Files:**
- Modify: `THEORY_ESSAYS.json`

- [ ] **Step 1: Remove the `breedlove-saylor-2020-rise-of-man` item**

Delete the entire object with `"id": "breedlove-saylor-2020-rise-of-man"` from `THEORY_ESSAYS.json.items[]` (added in the previous session, superseded by `saylor-series-01` in `THEORY_TOPICS.json` from Task 1). Keep `breedlove-2020-masters-slaves` and `21ideas-2026-dice-seed` untouched. Fix trailing comma if the removed item wasn't last.

- [ ] **Step 2: Update `meta.last_updated`**

Set `"last_updated": "2026-08-16"` in `THEORY_ESSAYS.json.meta`.

- [ ] **Step 3: Validate JSON**

Run: `python -c "import json; json.load(open('THEORY_ESSAYS.json', encoding='utf-8'))" && echo OK`
Expected: `OK`

- [ ] **Step 4: Run full suite**

Run: `PYTHONHASHSEED=0 python -m pytest -q`
Expected: all passing (no test should reference the removed essay id — if one does, it was added by mistake in a prior session and should be checked before deleting)

- [ ] **Step 5: Commit**

```bash
git add THEORY_ESSAYS.json
git commit -m "signal: убрать эссе про эпизод 1 Saylor Series — заменено полным разбором в THEORY_TOPICS.json"
```

---

## Task 6: Manual verification on the live-equivalent local build

**Files:** none (verification only)

- [ ] **Step 1: Serve the site locally and open it in the browser**

Use whatever local static server is already established for this repo (check `docs/spec-pilot.md` if unsure), navigate to the ТЕОРИЯ tab.

- [ ] **Step 2: Confirm the new TOC row**

Screenshot or visually confirm "Saylor Series" appears as the last row in «📑 СОДЕРЖАНИЕ» on the ТЕОРИЯ tab, with the count badge incremented by 1 from its previous value.

- [ ] **Step 3: Confirm the index card and episode panel**

Click the "Saylor Series" TOC row → confirm it scrolls to a panel with an index card "Огонь, праща и Рим: чему Майкл Сэйлор учит нас об энергии и цивилизации". Click the card → confirm it scrolls to the full episode panel with all 8 accordion items, and that item 05 ("Рим: система важнее героя") expands to show the crosslink to `theory-network`.

- [ ] **Step 4: Confirm the old essay is gone**

Confirm the "Что такое деньги" panel's accordion no longer has item 07 "Энергия, Рим и порча денег" (removed in Task 5) — panel should end at item 06 "Хозяева и рабы денег" plus its essay mount.

If any of these checks fail, stop and diagnose before proceeding — do not push to `main`.

---

## Task 7: Push and open PR

**Files:** none (git/gh operations only)

- [ ] **Step 1: Confirm all commits are in place**

Run: `git log --oneline main..HEAD`
Expected: 6 commits — Task 1 has two (renderAccItem list support, then episode data), Tasks 2, 3, 4, 5 have one each (Task 6 has no commit — verification only)

- [ ] **Step 2: Push the branch**

Run: `git push -u origin <branch-name>` (branch created before Task 1 — if not yet created, create it first: `git checkout -b feat/saylor-series-theory-section` before starting Task 1's commit)

- [ ] **Step 3: Open the PR**

```bash
gh pr create --title "feat: раздел Saylor Series внутри вкладки ТЕОРИЯ" --body "$(cat <<'EOF'
## Summary
- Эпизоды Saylor Series (Breedlove/Saylor) — топики THEORY_TOPICS.json с target_group: "saylor-series", вне generic-сканера renderTheoryTopics()
- Новая renderSaylorSeriesSection() — индекс-карточки + полные панели эпизодов через существующий renderTheoryTopic(), один mount theory-saylor-series-mount, одна строка в theory-toc
- Эпизод 1 записан полностью (8 пунктов), эссе-версия из THEORY_ESSAYS.json удалена (заменена)
- Design doc: docs/superpowers/specs/2026-08-16-saylor-series-theory-section-design.md

## Test plan
- [x] PYTHONHASHSEED=0 python -m pytest -q — все тесты зелёные
- [x] Ручная проверка в браузере (Task 6 плана реализации)
EOF
)"
```

- [ ] **Step 4: Report the PR URL to the user and wait for merge instruction**

Do not merge without explicit user confirmation (established pattern this session: user says "смержи, дождись CI").
