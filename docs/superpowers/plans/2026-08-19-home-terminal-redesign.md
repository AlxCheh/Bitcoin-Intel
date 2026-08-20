# Редизайн ОБЗОРА под терминал (Bloomberg/Arkham) — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Превратить вкладку ОБЗОР (`#tab-home`) в терминальный дашборд — плотная карточка нарратива с полями/связями/сущностями анкорного сигнала, единая лента до 8 кластеров, 2-колоночная раскладка на широком экране (лента + watchlist всех кластеров с реальным pos/neg/neu), нейтральная (не продуктовая) шапка.

**Architecture:** Правки только в `index.html` (разметка/CSS `#tab-home`) и `js/app-main.js` (рендер нарративов). Новые функции — чистые, без DOM API (`renderAnchorFieldsHtml`, `renderAnchorLinksHtml`, `renderAnchorEntitiesHtml`, `renderWatchlistRow`), тестируемые через существующий Node-харнесс (`tests/conftest.py::extract_js_function/run_node_js`). DOM-сборка (`renderNarrativeItem`, `renderWatchlist`) остаётся браузерно-верифицируемой — как и сейчас, у неё нет и не будет Node-теста (использует `document.createElement`, недоступный в чистом Node).

**Tech Stack:** Ванильный JS (без сборки), статический HTML/CSS, GitHub Pages. Тесты — `pytest` + `node` (уже установлены и используются в `tests/unit/*.py`). Визуальная проверка — локальный `python -m http.server` + `mcp__claude-in-chrome`.

**Спека:** `docs/superpowers/specs/2026-08-19-homepage-terminal-redesign-design.md`

---

## Важная находка при подготовке плана

В `tests/unit/test_home_page_reorg.py` уже есть автотесты, завязанные на код, который этот план меняет/удаляет:
- `test_home_has_definition_banner` — проверяет, что `#dash-definition` содержит `"Bitcoin Intel"` и `"нарративного анализа"` — сломается Задачей 1 (текст меняется).
- `test_mini_list_container_exists_in_home`, `test_render_narrative_mini_row_returns_html_string`, `test_render_narrative_mini_row_shows_tension_snippet_as_card` — завязаны на `dash-narratives-mini-list` и функцию `renderNarrativeMiniRow`, которые Задача 3 удаляет.

Каждая задача, где это применимо, обновляет соответствующие тесты в том же коммите — иначе `pytest` красный после мержа.

---

## Задача 1: Нейтральная шапка ОБЗОРА (`#dash-definition`)

**Files:**
- Modify: `index.html` (блок `#dash-definition`, сейчас строки ~2237–2239)
- Modify: `tests/unit/test_home_page_reorg.py` (`test_home_has_definition_banner`)

- [ ] **Шаг 1: Заменить текст `#dash-definition` на нейтральную техническую строку**

В `index.html` найти:

```html
    <!-- ══ ОПРЕДЕЛЕНИЕ САЙТА (2026-08-16) ══ -->
    <div id="dash-definition" style="margin:12px 0;border:1px solid var(--btc);background:var(--bg2);padding:10px 12px;font-family:var(--sans);font-size:11px;line-height:1.5;color:var(--dim)">
      <b style="color:var(--txt)">Bitcoin Intel</b> — платформа нарративного анализа Bitcoin: сталкивает противоречивые сигналы рынка и институтов, показывает где правда ещё не решена.
    </div>
```

Заменить на:

```html
    <!-- ══ ТЕХНИЧЕСКИЙ СКОУП ДАННЫХ (2026-08-19, ранее — питч "ОПРЕДЕЛЕНИЕ САЙТА") ══ -->
    <div id="dash-definition" style="margin:12px 0;border:1px solid var(--btc);background:var(--bg2);padding:10px 12px;font-family:var(--sans);font-size:11px;line-height:1.5;color:var(--dim)">
      Сигналы Bitcoin — on-chain, рыночные, институциональные, макро; у каждого источник и связи confirms/contradicts/context_chain.
    </div>
```

Причина (для коммита и истории): продуктовая формулировка конфликтовала по тону с блоком «Философия проекта» ниже на той же странице — см. `docs/superpowers/specs/2026-08-19-homepage-terminal-redesign-design.md`, §1. Число сигналов сюда намеренно не вписывается статикой (было бы моментально устаревающей цифрой) — оно уже показано динамически ниже, в статус-баре и «Общем фоне».

- [ ] **Шаг 2: Обновить тест, который проверял старый текст**

В `tests/unit/test_home_page_reorg.py` найти:

```python
def test_home_has_definition_banner():
    html = INDEX_HTML.read_text(encoding="utf-8")
    home_start, home_end = _section_range(html, "tab-home")
    home_html = html[home_start:home_end]
    assert 'id="dash-definition"' in home_html
    assert "Bitcoin Intel" in home_html
    assert "нарративного анализа" in home_html
```

Заменить на:

```python
def test_home_has_definition_banner():
    """
    2026-08-19: текст сменён с продуктового питча на нейтральную
    техническую строку (редизайн под терминал, см.
    docs/superpowers/specs/2026-08-19-homepage-terminal-redesign-design.md
    §1) — «Философия проекта» внизу той же страницы теперь единственное
    место, где сайт формулирует свой смысл.
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    home_start, home_end = _section_range(html, "tab-home")
    home_html = html[home_start:home_end]
    assert 'id="dash-definition"' in home_html
    assert "confirms/contradicts/context_chain" in home_html
    assert "платформа" not in home_html.lower(), (
        "dash-definition обязан оставаться нейтральной технической строкой, "
        "не продуктовым питчем — эту роль теперь несёт только блок "
        "«Философия проекта»"
    )
```

- [ ] **Шаг 3: Прогнать тест**

Run: `python -m pytest tests/unit/test_home_page_reorg.py::test_home_has_definition_banner -v`
Expected: PASS

- [ ] **Шаг 4: Коммит**

```bash
git add index.html tests/unit/test_home_page_reorg.py
git commit -m "$(cat <<'EOF'
fix: заменить продуктовый питч dash-definition на нейтральную строку

Формулировка "платформа нарративного анализа... показывает где правда
ещё не решена" конфликтовала по тону с блоком "Философия проекта" —
теперь единственное место, где сайт формулирует свой смысл. Первый шаг
редизайна ОБЗОРА под терминал, см. docs/superpowers/specs/2026-08-19-
homepage-terminal-redesign-design.md §1.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Задача 2: 2-колоночная сетка + контейнер Watchlist

**Files:**
- Modify: `index.html` (CSS-блок ОБЗОРА ~строки 2034–2194; разметка `#tab-home` ~строки 2255–2308)

- [ ] **Шаг 1: Добавить CSS сетки и контейнера watchlist**

В `index.html`, сразу после блока стилей `.dash-philosophy-footer { ... }` (последний в CSS-блоке ОБЗОРА, прямо перед `</style>`), добавить:

```css

/* ══════════════════════════════════
   ОБЗОР — 2-колоночная сетка (терминал)
══════════════════════════════════ */
.dash-grid { display: block; }
.dash-side { display: block; }

.dash-watchlist { margin: 0 0 16px; background: var(--bg2); border: 1px solid var(--btc); overflow: hidden; }
.dash-watch-row { display: flex; align-items: center; gap: 8px; padding: 6px 14px; font-family: var(--mono); font-size: 10px; cursor: pointer; }
.dash-watch-row:hover { background: var(--bg3); }
.dash-watch-row + .dash-watch-row { border-top: 1px solid var(--line); }
.dash-watch-label { flex: 1; min-width: 0; color: var(--txt); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dash-watch-bar { display: flex; height: 5px; width: 52px; overflow: hidden; gap: 1px; flex-shrink: 0; }
.dash-watch-count { color: var(--dim); width: 22px; text-align: right; flex-shrink: 0; }

@media (min-width: 960px) {
  #tab-home .page { max-width: 1180px; }
  .dash-grid { display: grid; grid-template-columns: 2.1fr 1fr; gap: 16px; align-items: start; }
}
```

- [ ] **Шаг 2: Обернуть разметку ОБЗОРА в сетку и добавить контейнер watchlist**

В `index.html` найти блок от `<!-- ══ ГЛАВНАЯ ИСТОРИЯ ... -->` до закрывающего `</div>` перед `</section>` (сейчас строки ~2255–2308):

```html
    <!-- ══ ГЛАВНАЯ ИСТОРИЯ (2026-08-16, ранее БЛОК 3: ГЛАВНЫЕ НАРРАТИВЫ) ══ -->
    <div class="dash-narratives" id="dash-narratives-wrap">
      <div class="panel-head" style="margin:0">
        <span class="panel-title">Главная история</span>
        <span id="dash-narratives-total" class="chart-meta"></span>
      </div>
      <div id="dash-narratives-list"><!-- PRERENDER:HOME:START --><div class="dash-narrative-item">...</div><!-- PRERENDER:HOME:END --></div>
    </div>

    <!-- ══ ЕЩЁ НАРРАТИВЫ (2026-08-16) ══ -->
    <div id="dash-narratives-mini-wrap" style="margin-top:12px">
      <div id="dash-narratives-mini-label" style="font-family:var(--mono);font-size:9px;color:var(--dim2);letter-spacing:0.1em;margin-bottom:6px"></div>
      <div id="dash-narratives-mini-list"></div>
    </div>

    <!-- ══ ИССЛЕДОВАТЬ ГЛУБЖЕ (2026-08-16) ══ -->
    <div style="margin:16px 0">
      <div style="font-family:var(--mono);font-size:9px;color:var(--dim2);letter-spacing:0.1em;margin-bottom:6px">ИССЛЕДОВАТЬ ГЛУБЖЕ</div>
      <div id="dash-explore-tiles"></div>
    </div>

    <!-- ══ БЛОК 4: СВОДКА СИГНАЛОВ ══ -->
    <div class="dash-summary">
      <div class="panel-head" style="margin:-16px -14px 12px">
        <span class="panel-title">Общий фон</span>
        <span class="chart-meta" id="dash-sum-label">СИГНАЛЫ</span>
      </div>
      <div class="dash-summary-body">
        <div class="dash-sum-bar" id="dash-sum-bar"></div>
        <div class="dash-sum-counts" id="dash-sum-counts"></div>
        <div class="dash-sum-link" onclick="showTab('market', null)">
          ВСЕ СИГНАЛЫ → ДАЙДЖЕСТ <span>→</span>
        </div>
      </div>
    </div>

    <!-- ══ ФИЛОСОФИЯ ПРОЕКТА (2026-08-18) ══ -->
    <div class="dash-philosophy">
      <div class="panel-head">
        <span class="panel-title">Философия проекта</span>
      </div>
      <div class="dash-philosophy-body">
        ...
      </div>
    </div>

  </div>
</section>
```

Заменить на (сохраняя содержимое `dash-narratives-list` PRERENDER-комментария и `dash-philosophy-body` без изменений — переносится только структура-обёртка):

```html
    <!-- ══ СЕТКА ОБЗОРА (2026-08-19) — лента слева, watchlist/сводки справа;
         на экране < 960px .dash-grid схлопывается в блок, оба .dash-feed/
         .dash-side стекают друг под другом в порядке DOM (лента → сайдбар) ══ -->
    <div class="dash-grid">
      <div class="dash-feed">
        <!-- ══ ГЛАВНАЯ ИСТОРИЯ ══ -->
        <div class="dash-narratives" id="dash-narratives-wrap">
          <div class="panel-head" style="margin:0">
            <span class="panel-title">Главная история</span>
            <span id="dash-narratives-total" class="chart-meta"></span>
          </div>
          <div id="dash-narratives-list"><!-- PRERENDER:HOME:START --><div class="dash-narrative-item">...</div><!-- PRERENDER:HOME:END --></div>
        </div>

        <!-- ══ ЕЩЁ НАРРАТИВЫ — упраздняется Задачей 3, контейнер временно остаётся ══ -->
        <div id="dash-narratives-mini-wrap" style="margin-top:12px">
          <div id="dash-narratives-mini-label" style="font-family:var(--mono);font-size:9px;color:var(--dim2);letter-spacing:0.1em;margin-bottom:6px"></div>
          <div id="dash-narratives-mini-list"></div>
        </div>
      </div>

      <div class="dash-side">
        <!-- ══ БЛОК 4: СВОДКА СИГНАЛОВ ══ -->
        <div class="dash-summary">
          <div class="panel-head" style="margin:-16px -14px 12px">
            <span class="panel-title">Общий фон</span>
            <span class="chart-meta" id="dash-sum-label">СИГНАЛЫ</span>
          </div>
          <div class="dash-summary-body">
            <div class="dash-sum-bar" id="dash-sum-bar"></div>
            <div class="dash-sum-counts" id="dash-sum-counts"></div>
            <div class="dash-sum-link" onclick="showTab('market', null)">
              ВСЕ СИГНАЛЫ → ДАЙДЖЕСТ <span>→</span>
            </div>
          </div>
        </div>

        <!-- ══ WATCHLIST — все кластеры (2026-08-19) ══ -->
        <div class="dash-watchlist">
          <div class="panel-head">
            <span class="panel-title">Watchlist</span>
            <span class="chart-meta" id="dash-watchlist-total"></span>
          </div>
          <div id="dash-watchlist-list"></div>
        </div>

        <!-- ══ ИССЛЕДОВАТЬ ГЛУБЖЕ ══ -->
        <div style="margin:16px 0">
          <div style="font-family:var(--mono);font-size:9px;color:var(--dim2);letter-spacing:0.1em;margin-bottom:6px">ИССЛЕДОВАТЬ ГЛУБЖЕ</div>
          <div id="dash-explore-tiles"></div>
        </div>

        <!-- ══ ФИЛОСОФИЯ ПРОЕКТА ══ -->
        <div class="dash-philosophy">
          <div class="panel-head">
            <span class="panel-title">Философия проекта</span>
          </div>
          <div class="dash-philosophy-body">
            ...
          </div>
        </div>
      </div>
    </div>

  </div>
</section>
```

(`...` в обоих блоках выше — плейсхолдер только в этом плане, означающий «содержимое не меняется»; при реальном редактировании файла это уже существующий текст, который просто перемещается вместе с окружающей обёрткой — Edit-инструмент должен захватить его целиком, не вписывать буквальные точки.)

- [ ] **Шаг 2: Проверить в браузере на широком и узком экране**

```bash
cd "D:\Claude\Bitcoin-Intel" && (python -m http.server 8731 > /tmp/http_server.log 2>&1 &) ; sleep 1 ; curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8731/index.html
```

Открыть `http://localhost:8731/index.html` через `mcp__claude-in-chrome`:
- Сделать скриншот при ширине окна ≥1000px — ожидается 2 колонки: лента слева (шире), справа сверху вниз «Общий фон» → (пустой Watchlist — заполнится Задачей 5) → «Исследовать глубже» → «Философия проекта».
- Сделать скриншот при ширине окна ≤700px — ожидается одна колонка, тот же порядок блоков друг под другом.

Expected: раскладка меняется по ширине, содержимое (карточка нарратива, Общий фон, плитки, философия) визуально не потеряно и не задвоено.

Остановить сервер: `powershell -NoProfile -Command 'Get-NetTCPConnection -LocalPort 8731 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }; "done"'`

- [ ] **Шаг 3: Коммит**

```bash
git add index.html
git commit -m "$(cat <<'EOF'
feat: 2-колоночная сетка ОБЗОРА + контейнер watchlist

Лента нарративов слева, сводки (Общий фон/Watchlist/Исследовать
глубже/Философия) справа на экранах ≥960px; на узких схлопывается в
одну колонку в том же порядке DOM. Watchlist пока пуст — заполняется
Задачей 5. См. docs/superpowers/specs/2026-08-19-homepage-terminal-
redesign-design.md §4.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Задача 3: Единая лента до 8 карточек (упразднить «ещё нарративы»)

**Files:**
- Modify: `js/app-main.js` (константа `MAX_SHOWN`, блок рендера ~строки 2864–2894, удалить функцию `renderNarrativeMiniRow` ~строки 2843–2862)
- Modify: `index.html` (удалить контейнер `#dash-narratives-mini-wrap`, удалить CSS-правило `.dash-narrative-mini:hover`)
- Modify: `tests/unit/test_home_page_reorg.py` (удалить 3 теста про мини-формат, добавить 2 регрессионных)

- [ ] **Шаг 1: Поднять порог показа с 4 до 8**

В `js/app-main.js` найти:

```js
  const MAX_SHOWN   = 4;
```

Заменить на:

```js
  const MAX_SHOWN   = 8;
```

- [ ] **Шаг 2: Объединить рендер в один цикл по `renderNarrativeItem`**

В `js/app-main.js` найти блок (текущие строки ~2864–2894):

```js
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
      miniHtml += renderNarrativeMiniRow(key, cl, score, synthesis);
    }
  });
  if (miniListEl) {
    miniListEl.innerHTML = miniHtml;
    if (miniHtml) {
      if (miniLabelEl) miniLabelEl.textContent = 'ЕЩЁ НАРРАТИВЫ';
      // 2026-08-18: goToNarrative(), не goToDigest() — клик обязан вести к уже
      // готовому синтезированному нарративу этого кластера (ВСЕ НАРРАТИВЫ),
      // не к сырому списку сигналов (ДАЙДЖЕСТ), см. goToNarrative() выше.
      miniListEl.querySelectorAll('[data-cl]').forEach(function(el) {
        el.addEventListener('click', function() { goToNarrative(this.dataset.cl); });
      });
    } else if (miniLabelEl) {
      miniLabelEl.textContent = '';
    }
  }
```

Заменить на:

```js
  // 2026-08-19: редизайн терминала — единая лента, все `shown` (до
  // MAX_SHOWN=8) рендерятся полной карточкой renderNarrativeItem(),
  // деления на "главная" (idx 0) + компактные "ещё нарративы" (idx>0)
  // больше нет. См. docs/superpowers/specs/2026-08-19-homepage-
  // terminal-redesign-design.md §3.
  shown.forEach(({ key, cl, score, weak }, idx) => {
    const cached = SYNTHESIS_CACHE[key];
    const synthesis = (cached && cached.tension)
      ? cached
      : synthesizeNarrativeAdvanced(key, cl);
    const item = renderNarrativeItem(key, cl, score, weak, idx, synthesis);
    listEl.appendChild(item);
  });

  // Watchlist — все кластеры (не только shown), реальный pos/neg/neu.
  // Реализация — Задача 5 этого плана.
  renderWatchlist(scored);
```

(Строка `renderWatchlist(scored);` временно вызовет `ReferenceError`, если открыть страницу прямо сейчас — функция появится в Задаче 5. Это ожидаемо: Задача 3 фокусируется на объединении ленты; полная работоспособность страницы восстанавливается по завершении Задачи 5. Чтобы Задача 3 была самостоятельно проверяемой, временно закомментировать эту строку — раскомментировать в Задаче 5.)

Уточнение шага 2 — временно закомментировать вызов:

```js
  // Watchlist — все кластеры (не только shown), реальный pos/neg/neu.
  // Реализация — Задача 5 этого плана.
  // renderWatchlist(scored); // TODO(Задача 5): раскомментировать
```

- [ ] **Шаг 3: Удалить функцию `renderNarrativeMiniRow`**

В `js/app-main.js` найти и удалить целиком блок (текущие строки ~2830–2862, от комментария до конца функции):

```js
  // 2026-08-16: компактная строка для "ещё нарративы" на ОБЗОРЕ — только
  // топ-1 (idx===0) идёт полной карточкой через renderNarrativeItem(),
  // остальные сюда. Возвращает HTML-строку (не DOM-узел), тот же стиль,
  // что у renderTOC()/renderTheoryTopic() в этом файле — не ради
  // единообразия ради единообразия, а потому что клик вешается ПОСЛЕ
  // вставки в DOM через querySelectorAll (см. вызов ниже), как и для
  // остальных .innerHTML-based рендеров.
  // 2026-08-18: Вариант 2 из 5 предложенных пользователю (карточка с рамкой
  // + двухстрочный тизер tension вместо голой строки-списка) — "по текущим
  // не понятно, что внутри, не хочется переходить". Тот же формат tension
  // (ensureSentencePunctuation + highlightVs + highlightEntities), что уже
  // используют featured-карточки renderClusterFullAnalytics() — единый
  // визуальный язык, не изобретение нового форматирования текста.
  function renderNarrativeMiniRow(key, cl, score, synthesis) {
    const dirCls = cl.neg > cl.pos ? 'neg' : cl.pos > cl.neg ? 'pos' : 'neu';
    const dotColor = dirCls === 'pos' ? 'var(--grn)' : dirCls === 'neg' ? 'var(--red)' : 'var(--dim)';
    const label = CLUSTER_LABELS[key] || sanitize(key).toUpperCase();
    const tension = synthesis && synthesis.tension
      ? ensureSentencePunctuation(synthesis.tension.charAt(0).toUpperCase() + synthesis.tension.slice(1))
      : '';
    return '<div class="dash-narrative-mini" data-cl="' + sanitize(key) + '" '
      + 'style="border:1px solid var(--line);background:var(--bg2);padding:12px 14px;margin-bottom:8px;cursor:pointer">'
      + '<div style="display:flex;align-items:center;gap:8px;margin-bottom:' + (tension ? '6px' : '0') + '">'
      +   '<span style="width:6px;height:6px;border-radius:50%;flex-shrink:0;background:' + dotColor + '"></span>'
      +   '<span style="flex:1;color:var(--txt);font-size:12px;font-weight:600">' + label + '</span>'
      +   '<span style="font-family:var(--mono);font-size:9px;color:var(--dim);flex-shrink:0">' + cl.signals.length + ' · ' + score.total + '</span>'
      + '</div>'
      + (tension
          ? '<div style="font-size:11px;color:var(--dim);line-height:1.55;margin-bottom:8px;overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical">' + highlightVs(highlightEntities(tension)) + '</div>'
          : '')
      + '<div style="font-family:var(--mono);font-size:10px;color:var(--btc);letter-spacing:0.04em">→ НАРРАТИВ</div>'
      + '</div>';
  }

```

- [ ] **Шаг 4: Удалить контейнер `#dash-narratives-mini-wrap` из HTML**

В `index.html` найти и удалить:

```html
        <!-- ══ ЕЩЁ НАРРАТИВЫ — упраздняется Задачей 3, контейнер временно остаётся ══ -->
        <div id="dash-narratives-mini-wrap" style="margin-top:12px">
          <div id="dash-narratives-mini-label" style="font-family:var(--mono);font-size:9px;color:var(--dim2);letter-spacing:0.1em;margin-bottom:6px"></div>
          <div id="dash-narratives-mini-list"></div>
        </div>
```

- [ ] **Шаг 5: Удалить мёртвое CSS-правило `.dash-narrative-mini:hover`**

В `index.html` найти и удалить:

```css
/* 2026-08-18: "ещё нарративы" на ОБЗОРЕ — Вариант 2 из 5 предложенных
   (карточка с рамкой вместо голой строки-списка), пользователь выбрал
   этот вариант. Тот же hover-язык, что .toc-card. */
.dash-narrative-mini:hover {
  border-color: var(--btc);
  background: var(--bg3);
}
```

- [ ] **Шаг 6: Удалить обесценившиеся тесты про мини-формат**

В `tests/unit/test_home_page_reorg.py` удалить целиком три функции: `test_mini_list_container_exists_in_home`, `test_render_narrative_mini_row_returns_html_string`, `test_render_narrative_mini_row_shows_tension_snippet_as_card` (их субъект — `dash-narratives-mini-list` и `renderNarrativeMiniRow` — удалены этой задачей).

- [ ] **Шаг 7: Добавить регрессионные тесты на месте удалённых**

В `tests/unit/test_home_page_reorg.py`, на месте удалённого в Шаге 6 блока, добавить:

```python
def test_mini_narrative_format_removed_from_home():
    """
    2026-08-19: лента ОБЗОРА объединена в одну однородную ленту подробных
    карточек (редизайн терминала) — отдельный компактный список
    "ещё нарративы" упразднён. См. docs/superpowers/specs/2026-08-19-
    homepage-terminal-redesign-design.md §3.
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    home_start, home_end = _section_range(html, "tab-home")
    home_html = html[home_start:home_end]
    assert 'id="dash-narratives-mini-list"' not in home_html
    assert 'id="dash-narratives-mini-wrap"' not in home_html


def test_max_shown_raised_to_eight():
    """Лента ОБЗОРА теперь показывает до 8 кластеров вместо 4 — терминалу
    важнее полнота картины, чем куратор-выборка "главного"."""
    import re
    src = (REPO_ROOT / "js" / "app-main.js").read_text(encoding="utf-8")
    match = re.search(r"const MAX_SHOWN\s*=\s*(\d+);", src)
    assert match, "Константа MAX_SHOWN не найдена в app-main.js"
    assert match.group(1) == "8"
```

- [ ] **Шаг 8: Запустить тесты**

Run: `python -m pytest tests/unit/test_home_page_reorg.py -v`
Expected: все тесты PASS (12 старых минус 3 удалённых плюс 2 новых = 11 тестов, все зелёные)

- [ ] **Шаг 9: Запустить cache-bust и проверить в браузере**

```bash
cd "D:\Claude\Bitcoin-Intel" && python scripts/update_js_cache_bust.py
```

Открыть страницу локальным сервером (как в Задаче 2, Шаг 2), убедиться, что в ленте до 8 полных карточек (сколько именно — зависит от того, сколько кластеров в текущем `signals.json` проходят `SCORE_MIN=10`), у каждой — рамка, счётчик, tension, macro; строки-«тизеры» больше нет.

- [ ] **Шаг 10: Коммит**

```bash
git add index.html js/app-main.js tests/unit/test_home_page_reorg.py
git commit -m "$(cat <<'EOF'
feat: объединить ленту ОБЗОРА в 8 подробных карточек вместо 4+мини

MAX_SHOWN 4 → 8, renderNarrativeMiniRow и связанный компактный формат
"ещё нарративы" удалены — все показанные кластеры рендерятся через
renderNarrativeItem() в одну ленту. Терминалу важна полнота картины
watchlist-стиля, не куратор-выборка "главного". Вызов renderWatchlist()
временно закомментирован — реализация в следующем коммите (Задача 5).
См. docs/superpowers/specs/2026-08-19-homepage-terminal-redesign-
design.md §3.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Задача 4: Поля/связи/сущности анкорного сигнала в карточке

**Files:**
- Modify: `js/app-main.js` (добавить 3 функции перед `renderNarrativeItem`, ~строка 2750; расширить `renderNarrativeItem`)
- Modify: `index.html` (CSS для новых блоков карточки)
- Create: тесты в `tests/unit/test_home_terminal_redesign.py` (новый файл)

- [ ] **Шаг 1: Написать падающие тесты для трёх новых чистых функций**

Создать `tests/unit/test_home_terminal_redesign.py`:

```python
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
```

- [ ] **Шаг 2: Убедиться, что тесты падают (функции ещё не существуют)**

Run: `python -m pytest tests/unit/test_home_terminal_redesign.py -v`
Expected: 3 FAIL с `AssertionError: Function 'renderAnchorFieldsHtml' not found in source` (и аналогично для двух других)

- [ ] **Шаг 3: Реализовать три функции**

В `js/app-main.js` вставить перед `function renderNarrativeItem(key, cl, score, weak, idx, synthesis) {` (текущая строка 2750, сразу после конца `renderSignalRefList`):

```js
  // 2026-08-19: редизайн терминала — плотная строка полей анкорного
  // сигнала кластера (DIR/HORIZON/WEIGHT/ROLE/ACTOR), как security-header
  // в Bloomberg. Чистая функция (без DOM API) — тестируется через Node,
  // см. tests/unit/test_home_terminal_redesign.py. anchor — сигнал из
  // cl.signals с id === synthesis.anchor_signal_id, см. вызов ниже.
  function renderAnchorFieldsHtml(anchor) {
    if (!anchor) return '';
    const dirCls = anchor.dir === 'neg' ? 'neg' : anchor.dir === 'pos' ? 'pos' : 'neu';
    const cells = [
      { label: 'DIR', value: (anchor.dir || '—').toUpperCase(), cls: dirCls },
      { label: 'HORIZON', value: (anchor.horizon || '—').toUpperCase(), cls: '' },
      { label: 'WEIGHT', value: (anchor.weight || '—').toUpperCase(), cls: '' },
      { label: 'ROLE', value: (anchor.narrative_role || '—').toUpperCase(), cls: 'amber' },
      { label: 'ACTOR', value: (anchor.actor || '—').toUpperCase(), cls: '' }
    ];
    return '<div class="dash-anchor-fields">'
      + cells.map(function(c) {
          return '<div class="dash-anchor-field"><div class="dash-anchor-field-label">' + c.label + '</div>'
            + '<div class="dash-anchor-field-value' + (c.cls ? ' ' + c.cls : '') + '">' + sanitize(c.value) + '</div></div>';
        }).join('')
      + '</div>';
  }

  // Чипы связей анкорного сигнала (confirms/contradicts/context_chain) —
  // показываются только непустые типы, счётчик = длина массива.
  function renderAnchorLinksHtml(anchor) {
    if (!anchor || !anchor.links) return '';
    const l = anchor.links;
    const chips = [];
    if (l.confirms && l.confirms.length) chips.push('<span class="dash-anchor-chip confirms">✓ ПОДТВЕРЖДАЕТ · ' + l.confirms.length + '</span>');
    if (l.contradicts && l.contradicts.length) chips.push('<span class="dash-anchor-chip contradicts">✗ ПРОТИВОРЕЧИТ · ' + l.contradicts.length + '</span>');
    if (l.context_chain && l.context_chain.length) chips.push('<span class="dash-anchor-chip context">↳ КОНТЕКСТ · ' + l.context_chain.length + '</span>');
    if (!chips.length) return '';
    return '<div class="dash-anchor-links">' + chips.join('') + '</div>';
  }

  // Теги сущностей ENTITIES.json, чей signal_refs содержит id анкорного
  // сигнала — те же сущности, что уже ведутся Шагом 8 алгоритма обработки
  // сигнала (CLAUDE.md, "База артефактов").
  function renderAnchorEntitiesHtml(anchor) {
    if (!anchor) return '';
    const ents = (ENTITIES || []).filter(function(e) {
      return e.signal_refs && e.signal_refs.indexOf(anchor.id) !== -1;
    });
    if (!ents.length) return '';
    return '<div class="dash-anchor-entities">'
      + ents.map(function(e) { return '<span class="dash-anchor-entity">' + sanitize(e.name) + '</span>'; }).join('')
      + '</div>';
  }

```

- [ ] **Шаг 4: Прогнать тесты — теперь зелёные**

Run: `python -m pytest tests/unit/test_home_terminal_redesign.py -v`
Expected: 3 PASS

- [ ] **Шаг 5: Вписать анкорный сигнал и три новых блока в `renderNarrativeItem`**

В `js/app-main.js`, в `function renderNarrativeItem(key, cl, score, weak, idx, synthesis) {`, найти:

```js
  function renderNarrativeItem(key, cl, score, weak, idx, synthesis) {
    const n      = cl.signals.length;
    const dirCls = cl.neg > cl.pos ? 'neg' : cl.pos > cl.neg ? 'pos' : 'neu';
```

Заменить на:

```js
  function renderNarrativeItem(key, cl, score, weak, idx, synthesis) {
    const n      = cl.signals.length;
    // 2026-08-19: анкорный сигнал — тот, с которого синтез взял tension
    // (synthesis.anchor_signal_id, см. Python SynthesisResult и JS
    // synthesizeNarrativeAdvanced() — оба поля называют одинаково).
    // Ищем в cl.signals (сигналы этого кластера), не во всём SIGNALS —
    // дешевле и всегда содержит нужный id, если синтез вообще валиден.
    const anchor = cl.signals.find(function(s) { return s.id === synthesis.anchor_signal_id; }) || null;
    const dirCls = cl.neg > cl.pos ? 'neg' : cl.pos > cl.neg ? 'pos' : 'neu';
```

Затем в том же файле найти сборку `item.innerHTML` (текущие строки ~2782–2823):

```js
    item.innerHTML =
        '<div class="dash-narrative-cluster">'
      +   '<div class="dash-narrative-cluster-top">'
      +     '<div class="dash-narrative-cluster-name" title="' + sanitize(label) + '">' + label + '</div>'
      +     '<span class="dash-meta-badge" style="color:var(--btc);border-color:rgba(247,147,26,.4)">' + n + '</span>'
      +   '</div>'
      +   '<div class="dash-narrative-meta">'
      +     (weak ? '<span class="dash-meta-badge" style="color:var(--red);border-color:rgba(194,96,96,.4)">СЛАБЫЙ СИГНАЛ</span>' : '')
      +     (phaseInfo.label ? '<span class="dash-meta-badge" style="color:' + phaseInfo.color + ';border-color:' + phaseInfo.border + '">' + phaseInfo.label + '</span>' : '')
      +     '<span class="dash-meta-badge" style="color:' + (freshness.stale ? 'var(--red)' : 'var(--dim)') + ';border-color:' + (freshness.stale ? 'rgba(194,96,96,.4)' : 'rgba(122,139,160,.35)') + '" title="' + sanitize(freshness.title) + '">'
      +       (freshness.stale ? '⚠ ' : '') + sanitize(freshness.label)
      +     '</span>'
      +   '</div>'
      + '</div>'
      + (warnings.length ? '<div style="color:var(--red);font-size:10px;font-weight:600;margin-bottom:6px">' + warnings.join(' · ') + '</div>' : '')
      + (tension ? '<div class="dash-narrative-tension" style="border-left-color:' + phaseInfo.color + '">' + highlightVs(highlightEntities(tension)) + '</div>' : '')
      + minorityWarningHtml
      + '<div class="dash-narrative-macro">' + highlightEntities(macroText) + '</div>'
      + (synthesis.takeaway ? '<div class="dash-narrative-takeaway">→ ' + sanitize(synthesis.takeaway) + '</div>' : '')
      + buildAltScenarioHtml(synthesis)
      + '<div class="dash-sum-counts" style="margin:5px 0">'
```

Заменить на (добавлены `renderAnchorFieldsHtml(anchor)` после блока заголовка и `renderAnchorLinksHtml`/`renderAnchorEntitiesHtml`/строка источника после macro — остальное не меняется):

```js
    item.innerHTML =
        '<div class="dash-narrative-cluster">'
      +   '<div class="dash-narrative-cluster-top">'
      +     '<div class="dash-narrative-cluster-name" title="' + sanitize(label) + '">' + label + '</div>'
      +     '<span class="dash-meta-badge" style="color:var(--btc);border-color:rgba(247,147,26,.4)">' + n + '</span>'
      +   '</div>'
      +   '<div class="dash-narrative-meta">'
      +     (weak ? '<span class="dash-meta-badge" style="color:var(--red);border-color:rgba(194,96,96,.4)">СЛАБЫЙ СИГНАЛ</span>' : '')
      +     (phaseInfo.label ? '<span class="dash-meta-badge" style="color:' + phaseInfo.color + ';border-color:' + phaseInfo.border + '">' + phaseInfo.label + '</span>' : '')
      +     '<span class="dash-meta-badge" style="color:' + (freshness.stale ? 'var(--red)' : 'var(--dim)') + ';border-color:' + (freshness.stale ? 'rgba(194,96,96,.4)' : 'rgba(122,139,160,.35)') + '" title="' + sanitize(freshness.title) + '">'
      +       (freshness.stale ? '⚠ ' : '') + sanitize(freshness.label)
      +     '</span>'
      +   '</div>'
      + '</div>'
      + renderAnchorFieldsHtml(anchor)
      + (warnings.length ? '<div style="color:var(--red);font-size:10px;font-weight:600;margin-bottom:6px">' + warnings.join(' · ') + '</div>' : '')
      + (tension ? '<div class="dash-narrative-tension" style="border-left-color:' + phaseInfo.color + '">' + highlightVs(highlightEntities(tension)) + '</div>' : '')
      + minorityWarningHtml
      + '<div class="dash-narrative-macro">' + highlightEntities(macroText) + '</div>'
      + renderAnchorLinksHtml(anchor)
      + renderAnchorEntitiesHtml(anchor)
      + (anchor && anchor.source ? '<div class="dash-anchor-source">' + sanitize(anchor.source) + '</div>' : '')
      + (synthesis.takeaway ? '<div class="dash-narrative-takeaway">→ ' + sanitize(synthesis.takeaway) + '</div>' : '')
      + buildAltScenarioHtml(synthesis)
      + '<div class="dash-sum-counts" style="margin:5px 0">'
```

- [ ] **Шаг 6: Добавить CSS для новых блоков**

В `index.html`, сразу после правила `.dash-narrative-macro { ... }` (текущие строки ~2101–2107), добавить:

```css
.dash-anchor-fields {
  display: grid; grid-template-columns: repeat(5, 1fr); gap: 1px;
  background: var(--line); border: 1px solid var(--line);
  margin-bottom: 8px;
}
.dash-anchor-field { background: var(--bg3); padding: 4px 6px; }
.dash-anchor-field-label { font-family: var(--mono); font-size: 8px; color: var(--dim); letter-spacing: 0.06em; margin-bottom: 2px; }
.dash-anchor-field-value { font-family: var(--mono); font-size: 9.5px; font-weight: 700; color: var(--txt); }
.dash-anchor-field-value.pos { color: var(--grn); }
.dash-anchor-field-value.neg { color: var(--red); }
.dash-anchor-field-value.neu { color: var(--dim); }
.dash-anchor-field-value.amber { color: var(--btc); }

.dash-anchor-links { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
.dash-anchor-chip { font-family: var(--mono); font-size: 9px; padding: 2px 7px; border: 1px solid; letter-spacing: 0.03em; }
.dash-anchor-chip.confirms { border-color: var(--grn); color: var(--grn); }
.dash-anchor-chip.contradicts { border-color: var(--red); color: var(--red); }
.dash-anchor-chip.context { border-color: var(--line2); color: var(--dim); }

.dash-anchor-entities { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; }
.dash-anchor-entity { font-family: var(--mono); font-size: 9px; padding: 2px 7px; background: var(--bg3); color: var(--txt); border: 1px solid var(--line2); }

.dash-anchor-source { font-family: var(--mono); font-size: 9px; color: var(--dim); margin-bottom: 4px; }
```

- [ ] **Шаг 7: Запустить полный набор JS-тестов + cache-bust + браузерная проверка**

```bash
cd "D:\Claude\Bitcoin-Intel" && python -m pytest tests/unit/ -v -k "home or terminal" && python scripts/update_js_cache_bust.py
```

Expected: все тесты PASS.

Открыть страницу локальным сервером (как в Задаче 2, Шаг 2). На каждой из карточек ленты ожидается строка из 5 полей (DIR/HORIZON/WEIGHT/ROLE/ACTOR) сразу под заголовком, затем tension/macro как раньше, затем (если есть) чипы связей, теги сущностей и строка источника перед остальным (takeaway/score/breakdown не меняются).

- [ ] **Шаг 8: Коммит**

```bash
git add index.html js/app-main.js tests/unit/test_home_terminal_redesign.py
git commit -m "$(cat <<'EOF'
feat: поля/связи/сущности анкорного сигнала в карточке нарратива

Новый блок под заголовком карточки — DIR/HORIZON/WEIGHT/ROLE/ACTOR
анкорного сигнала кластера (security-header в духе Bloomberg), плюс
чипы confirms/contradicts/context_chain, теги сущностей ENTITIES.json
и строка источника — все данные уже есть в signals.json/ENTITIES.json,
новых fetch не потребовалось. Три новые функции — чистые (без DOM API),
покрыты Node-тестами. См. docs/superpowers/specs/2026-08-19-homepage-
terminal-redesign-design.md §2.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Задача 5: Watchlist — реальный pos/neg/neu по всем кластерам

**Files:**
- Modify: `js/app-main.js` (добавить `renderWatchlistRow`/`renderWatchlist`, раскомментировать вызов из Задачи 3)
- Modify: `index.html` (CSS уже добавлен Задачей 2 — здесь не трогается)
- Modify: `tests/unit/test_home_terminal_redesign.py` (добавить тест)

- [ ] **Шаг 1: Написать падающий тест для `renderWatchlistRow`**

В `tests/unit/test_home_terminal_redesign.py` добавить в конец файла:

```python


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
```

- [ ] **Шаг 2: Убедиться, что тест падает**

Run: `python -m pytest tests/unit/test_home_terminal_redesign.py::test_render_watchlist_row_shows_real_pos_neg_neu_ratio -v`
Expected: FAIL с `Function 'renderWatchlistRow' not found in source`

- [ ] **Шаг 3: Реализовать `renderWatchlistRow` и `renderWatchlist`**

В `js/app-main.js` вставить сразу после конца цикла `shown.forEach(...)`, добавленного в Задаче 3 (то есть после закрывающей `});` этого цикла, перед строкой `renderWatchlist(scored);`, которая сейчас закомментирована):

```js
  // 2026-08-19: watchlist — ВСЕ кластеры (не только shown/MAX_SHOWN), с
  // реальным соотношением pos/neg/neu, посчитанным по всем сигналам
  // кластера (cl.pos/neg/neu уже агрегированы выше при сборке `clusters`)
  // — не по dir одного анкорного сигнала. См. спеку §5.
  function renderWatchlistRow(key, cl, score) {
    const total = cl.signals.length;
    const pos = cl.pos || 0, neg = cl.neg || 0, neu = cl.neu || 0;
    const label = DIGEST_CLUSTER_LABELS[key] || sanitize(key).toUpperCase();
    return '<div class="dash-watch-row" data-cl="' + sanitize(key) + '">'
      + '<span class="dash-watch-label" title="' + sanitize(label) + '">' + label + '</span>'
      + '<div class="dash-watch-bar">'
      +   (pos ? '<div style="flex:' + pos + ';background:var(--grn)"></div>' : '')
      +   (neg ? '<div style="flex:' + neg + ';background:var(--red)"></div>' : '')
      +   (neu ? '<div style="flex:' + neu + ';background:var(--dim2)"></div>' : '')
      + '</div>'
      + '<span class="dash-watch-count">' + total + '</span>'
      + '</div>';
  }

  function renderWatchlist(scoredAll) {
    const el = document.getElementById('dash-watchlist-list');
    if (!el) return;
    el.innerHTML = scoredAll.map(function(x) {
      return renderWatchlistRow(x.key, x.cl, x.score);
    }).join('');
    const totalEl = document.getElementById('dash-watchlist-total');
    if (totalEl) totalEl.textContent = scoredAll.length + ' КЛАСТЕРОВ';
    // Клик по строке — к синтезированному нарративу кластера (как в
    // ленте), не к сырому дайджесту — тот же goToNarrative(), что уже
    // используется для карточек ленты.
    el.querySelectorAll('[data-cl]').forEach(function(row) {
      row.addEventListener('click', function() { goToNarrative(this.dataset.cl); });
    });
  }

```

- [ ] **Шаг 4: Раскомментировать вызов `renderWatchlist(scored)` из Задачи 3**

В `js/app-main.js` найти:

```js
  // Watchlist — все кластеры (не только shown), реальный pos/neg/neu.
  // Реализация — Задача 5 этого плана.
  // renderWatchlist(scored); // TODO(Задача 5): раскомментировать
```

Заменить на:

```js
  // Watchlist — все кластеры (не только shown), реальный pos/neg/neu.
  renderWatchlist(scored);
```

- [ ] **Шаг 5: Прогнать тест — теперь зелёный**

Run: `python -m pytest tests/unit/test_home_terminal_redesign.py -v`
Expected: все тесты (включая новый) PASS

- [ ] **Шаг 6: cache-bust + браузерная проверка**

```bash
cd "D:\Claude\Bitcoin-Intel" && python scripts/update_js_cache_bust.py
```

Открыть страницу локальным сервером. Проверить:
- Блок Watchlist справа (на широком экране) больше не пуст — по строке на каждый кластер `signals.json`, у каждой мини-полоса из 3 сегментов и число сигналов.
- Клик по строке watchlist ведёт на вкладку «ВСЕ НАРРАТИВЫ» к карточке этого кластера (та же механика, что клик по карточке в ленте).
- В консоли браузера (`mcp__claude-in-chrome` → `read_console_messages`) нет `ReferenceError: renderWatchlist is not defined`.

- [ ] **Шаг 7: Коммит**

```bash
git add index.html js/app-main.js tests/unit/test_home_terminal_redesign.py
git commit -m "$(cat <<'EOF'
feat: watchlist со всеми кластерами и реальным pos/neg/neu

renderWatchlistRow (чистая, покрыта Node-тестом) + renderWatchlist
(DOM-сборка) — заполняет контейнер из Задачи 2 всеми кластерами
signals.json (не только теми, что попали в ленту), с мини-полосой
pos/neg/neu, посчитанной по реальным сигналам кластера, не по dir
одного анкорного сигнала. См. docs/superpowers/specs/2026-08-19-
homepage-terminal-redesign-design.md §5.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Задача 6: Философия — тизер на десктопе, полный текст на мобильном

**Files:**
- Modify: `index.html` (CSS + одна строка разметки в `.dash-philosophy-body`)
- Modify: `js/app-early.js` (новая функция `togglePhilosophy`)

- [ ] **Шаг 1: Добавить CSS сворачивания (только на ширине ≥960px)**

В `index.html`, внутри существующего блока `@media (min-width: 960px) { ... }` (добавлен Задачей 2), после правила `.dash-grid { display: grid; ... }`, добавить:

```css
  .dash-side .dash-philosophy-body:not(.dpb-expanded) {
    max-height: 70px; overflow: hidden; position: relative;
  }
  .dash-side .dash-philosophy-body:not(.dpb-expanded)::after {
    content: '';
    position: absolute; left: 0; right: 0; bottom: 0; height: 26px;
    background: linear-gradient(to bottom, transparent, var(--bg2));
  }
  .dash-philosophy-toggle { display: block; }
```

Вне `@media`-блока (например, сразу после правила `.dash-philosophy-footer { ... }`), добавить:

```css
.dash-philosophy-toggle {
  display: none;
  margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--line);
  font-family: var(--mono); font-size: 9px; letter-spacing: 0.06em; color: var(--btc);
  cursor: pointer; text-align: center;
}
```

(`display: none` по умолчанию — на мобильном тумблер не нужен, там текст и так всегда полный; `display: block` включается только внутри `@media (min-width: 960px)` выше.)

- [ ] **Шаг 2: Добавить кнопку-тумблер в разметку**

В `index.html`, внутри `.dash-philosophy-body`, сразу после закрывающего `</div>` блока `.dash-philosophy-footer` (последний элемент внутри `.dash-philosophy-body`), добавить:

```html
        <div class="dash-philosophy-toggle" onclick="togglePhilosophy(this)">развернуть ▾</div>
```

- [ ] **Шаг 3: Добавить `togglePhilosophy` в app-early.js**

В `js/app-early.js` добавить в конец файла (после существующей `toggleNav`):

```js

function togglePhilosophy(el) {
  const body = el.closest('.dash-philosophy-body');
  if (!body) return;
  const expanded = body.classList.toggle('dpb-expanded');
  el.textContent = expanded ? 'свернуть ▴' : 'развернуть ▾';
}
```

- [ ] **Шаг 4: cache-bust + браузерная проверка на обеих ширинах**

```bash
cd "D:\Claude\Bitcoin-Intel" && python scripts/update_js_cache_bust.py
```

Открыть страницу локальным сервером:
- На ширине ≥1000px: блок «Философия проекта» в сайдбаре обрезан (~70px высоты) с градиентным затуханием и кнопкой «развернуть ▾» под ним. Клик по кнопке — текст полностью раскрывается, кнопка меняется на «свернуть ▴»; повторный клик сворачивает обратно.
- На ширине ≤700px: блок «Философия проекта» показывает полный текст без обрезки и без видимой кнопки-тумблера.

- [ ] **Шаг 5: Коммит**

```bash
git add index.html js/app-early.js
git commit -m "$(cat <<'EOF'
feat: свернуть «Философию проекта» тизером на десктопе

На экранах ≥960px блок в сайдбаре ОБЗОРА обрезается до ~70px с
тумблером "развернуть/свернуть" — не должен доминировать над лентой
данных в узкой колонке сайдбара. На мобильном (одна колонка) текст
остаётся полным, как раньше — блок и так последний в скролле. См.
docs/superpowers/specs/2026-08-19-homepage-terminal-redesign-design.md
§4.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Задача 7: Финальная сквозная проверка

**Files:** нет изменений — только верификация.

- [ ] **Шаг 1: Полный прогон тестов проекта**

Run: `python -m pytest tests/ -q`
Expected: все тесты PASS (в т.ч. `tests/unit/test_claude_md_schema_sync.py`, `tests/unit/test_signals_md_sync.py` и другие сторожа, которые эта работа не должна была задеть — они проверяют файлы, не тронутые этим планом, но полный прогон подтверждает отсутствие случайных побочных эффектов)

- [ ] **Шаг 2: Полный визуальный проход в браузере**

```bash
cd "D:\Claude\Bitcoin-Intel" && (python -m http.server 8731 > /tmp/http_server.log 2>&1 &) ; sleep 1 ; curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8731/index.html
```

Через `mcp__claude-in-chrome`:
1. Открыть `http://localhost:8731/index.html` на ширине ≥1000px, сделать скриншот — сверить с раскладкой из спеки (2 колонки, лента + сайдбар).
2. Прокрутить ленту до конца — убедиться, что показано ожидаемое число карточек (≤8), у каждой поля/tension/macro/связи (если есть)/сущности (если есть)/источник.
3. Сверить watchlist справа — число строк должно совпадать с числом уникальных `cluster` в `signals.json`.
4. Кликнуть по любой карточке ленты и по любой строке watchlist — оба должны вести на вкладку «ВСЕ НАРРАТИВЫ» к соответствующей карточке кластера.
5. Изменить ширину окна на ≤700px, сделать скриншот — одна колонка, порядок: статус-бар → лента → Общий фон → Watchlist → Исследовать глубже → Философия (полный текст).
6. Открыть `read_console_messages` — не должно быть JS-ошибок.

Остановить сервер: `powershell -NoProfile -Command 'Get-NetTCPConnection -LocalPort 8731 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }; "done"'`

- [ ] **Шаг 3: Ничего не коммитить** (эта задача — только проверка; если что-то не совпало с ожиданиями, вернуться к соответствующей задаче и исправить перед тем, как считать план выполненным)

---

## Self-Review (проведён при написании плана)

**Spec coverage:**
- §1 (нейтральная строка) → Задача 1.
- §2 (карточка: поля/tension/macro/связи/сущности/источник) → Задачи 3 (unified feed, предпосылка) + 4 (сами поля).
- §3 (MAX_SHOWN 4→8, единая лента) → Задача 3.
- §4 (2-колоночная сетка, брейкпоинт 960px, философия-тизер на десктопе) → Задачи 2 + 6.
- §5 (watchlist, реальный pos/neg/neu, сортировка как в ленте) → Задача 5 (сортировка гарантирована использованием того же `scored`, что и лента).
- Вне скоупа (другие вкладки, схема сигналов, алгоритм синтеза) — не затронуты ни одной задачей.

**Placeholder scan:** код во всех задачах — рабочий, не псевдокод; единственное намеренное временное состояние — закомментированный вызов `renderWatchlist(scored)` между Задачами 3 и 5, явно помечен и раскомментируется в Задаче 5 тем же планом (не забытый TODO, а осознанный промежуточный шаг ради проверяемости Задачи 3 по отдельности).

**Type consistency:** `anchor_signal_id` — везде это поле синтеза (и в Python `SynthesisResult`, и в JS `synthesizeNarrativeAdvanced()`), не переименовывается по ходу плана. `renderWatchlistRow(key, cl, score)` — сигнатура одинакова в определении (Задача 5, Шаг 3) и в вызове из `renderWatchlist` (тот же шаг) и в тесте (Задача 5, Шаг 1). `DIGEST_CLUSTER_LABELS` — используется как уже существующая структура (объявлена на верхнем уровне модуля, строка 1504), не переопределяется.

**Scope check:** один связный фиче-план (переплетённые части одной страницы, не независимые подсистемы) — декомпозиция на отдельные спеки не требовалась ещё на этапе брейншторминга, актуально и для плана.
