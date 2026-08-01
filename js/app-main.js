


// ── DASH STATUS + TOP3 ────────────────────────────────────────────────
function renderDashStatus() {
  // Фаза цикла — из переменных (данные уже загружены)
  const statusPhase = document.getElementById('dash-status-phase');
  const statusRatio = document.getElementById('dash-status-ratio');
  if (statusPhase) {
    if (typeof dashBtcPrice !== 'undefined' && typeof dashProdCost !== 'undefined' && dashBtcPrice && dashProdCost) {
      const { phase } = calcCyclePhase(dashBtcPrice, dashProdCost);
      const ratio = (dashBtcPrice / dashProdCost).toFixed(2);
      statusPhase.textContent = phase;
      if (statusRatio) statusRatio.textContent = '×' + ratio;
    } else {
      const phaseEl = document.getElementById('dash-phase');
      const ratioEl = document.getElementById('dash-ratio');
      if (phaseEl && phaseEl.textContent && phaseEl.textContent !== 'НАКОПЛЕНИЕ') statusPhase.textContent = phaseEl.textContent;
      if (ratioEl && ratioEl.textContent) statusRatio && (statusRatio.textContent = ratioEl.textContent);
    }
  }

  // Фон сигналов
  if (!SIGNALS || !SIGNALS.length) return;
  const pos = SIGNALS.filter(s => s.dir === 'pos').length;
  const neg = SIGNALS.filter(s => s.dir === 'neg').length;
  const neu = SIGNALS.filter(s => s.dir === 'neu').length;
  const total = SIGNALS.length;

  const elPos = document.getElementById('dash-status-pos');
  const elNeg = document.getElementById('dash-status-neg');
  const elNeu = document.getElementById('dash-status-neu');
  const elTotal = document.getElementById('dash-status-total');
  if (elPos) elPos.textContent = pos + '↑';
  if (elNeg) elNeg.textContent = neg + '↓';
  if (elNeu) elNeu.textContent = neu + '→';
  // total не отображаем

  // ТОП-3 последних сигнала
  renderDashTop3();
}

function renderDashTop3() {
  const el = document.getElementById('dash-top3-list');
  if (!el || !SIGNALS || !SIGNALS.length) return;

  const dirArrow = { pos: '↑', neg: '↓', neu: '→' };
  const top3 = [...SIGNALS].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 3);

  el.innerHTML = '';
  top3.forEach(function(s) {
    const dir = s.dir || 'neu';
    const arrow = dirArrow[dir] || '→';
    const date = s.date ? s.date.slice(5).replace('-', '.') : '';
    const div = document.createElement('div');
    div.className = 'dash-top3-item';
    div.setAttribute('data-goto', 'market');
    const sp1 = document.createElement('span');
    sp1.className = 'dash-top3-dir ' + dir;
    sp1.textContent = arrow;
    const sp2 = document.createElement('span');
    sp2.className = 'dash-top3-signal';
    sp2.innerHTML = highlightEntities(s.signal);
    const sp3 = document.createElement('span');
    sp3.className = 'dash-top3-meta';
    sp3.textContent = date;
    div.appendChild(sp1);
    div.appendChild(sp2);
    div.appendChild(sp3);
    el.appendChild(div);
  });
}



// ── ADVANCED NARRATIVE SYNTHESIS (детерминированный) ────────────────

function synthesizeNarrativeAdvanced(key, cl) {
  const sigs = cl.signals;
  const today = new Date();

  const WEIGHT_RANK = { onchain: 4, primary: 3, market: 2, media: 1 };
  const ROLE_RANK   = { trigger: 4, complication: 3, resolution: 2, background: 1 };

  // ── Сортировки ───────────────────────────────────────────────────
  const byDate    = [...sigs].sort((a,b) => new Date(b.date) - new Date(a.date));
  const byWeight  = [...sigs].sort((a,b) => (WEIGHT_RANK[b.weight]||0) - (WEIGHT_RANK[a.weight]||0));
  const byRole    = [...sigs].sort((a,b) => (ROLE_RANK[b.narrative_role]||0) - (ROLE_RANK[a.narrative_role]||0));
  const byContra  = [...sigs].sort((a,b) =>
    ((b.links&&b.links.contradicts&&b.links.contradicts.length)||0) -
    ((a.links&&a.links.contradicts&&a.links.contradicts.length)||0)
  );
  // byTensionPriority: тай-брейк идентичен Python _select_tension_source()
  // (MAX contradicts → MAX weight → MAX date). До фикса (C1 ARR v3) JS
  // использовал byContra напрямую как третий fallback для tensionSig — при
  // равном числе contradicts (типичный случай, т.к. contradicts заполняется
  // редко) порядок схлопывался к порядку массива сигналов, игнорируя weight.
  const byTensionPriority = [...sigs].sort((a,b) => {
    const ca = (a.links&&a.links.contradicts&&a.links.contradicts.length)||0;
    const cb = (b.links&&b.links.contradicts&&b.links.contradicts.length)||0;
    if (cb !== ca) return cb - ca;
    const wa = WEIGHT_RANK[a.weight]||0, wb = WEIGHT_RANK[b.weight]||0;
    if (wb !== wa) return wb - wa;
    return new Date(b.date) - new Date(a.date);
  });

  // ── Этап 1: Определяем главный процесс ──────────────────────────
  // ВАЖНО (C1 ARR v3): формула должна быть идентична Python
  // scripts/synthesizer.py::_detect_phase() — это единственный путь, где
  // пользователь может увидеть расхождение между кэшем и live-фоллбэком,
  // если synthesis_cache.json временно недоступен. До фикса JS объявлял
  // 'active' при наличии ОДНОГО trigger, а Python требует trigger И
  // complication одновременно — расхождение покрыто
  // tests/unit/test_phase_equivalence.py.
  const roleCounts = { trigger:0, complication:0, resolution:0, background:0 };
  sigs.forEach(s => { if (s.narrative_role) roleCounts[s.narrative_role] = (roleCounts[s.narrative_role]||0)+1; });

  const phase = roleCounts.resolution > 0 ? 'resolution'
    : (roleCounts.trigger > 0 && roleCounts.complication > 0) ? 'active'
    : roleCounts.complication > roleCounts.trigger ? 'tension'
    : 'structural';

  // ── Этап 2: Фильтруем сигналы по роли ───────────────────────────
  const triggers      = sigs.filter(s => s.narrative_role === 'trigger');
  const complications = sigs.filter(s => s.narrative_role === 'complication');
  const resolutions   = sigs.filter(s => s.narrative_role === 'resolution');

  // Самый свежий + весомый в каждой группе (копируем массив чтобы не мутировать)
  const pick = (arr) => arr.length ? [...arr].sort((a,b) =>
    (WEIGHT_RANK[b.weight]||0) - (WEIGHT_RANK[a.weight]||0) ||
    new Date(b.date) - new Date(a.date)
  )[0] : null;

  const anchorTrigger     = pick(triggers) || byRole[0];
  const anchorComplication = pick(complications) || byContra[0];
  const anchorResolution  = pick(resolutions);

  // ── Этап 3: core_tension — из противоречия ───────────────────────
  // ВАЖНО (C1 ARR v3): приоритет идентичен Python _select_tension_source():
  // resolution (самый свежий ПО ДАТЕ, без учёта weight) побеждает всегда →
  // иначе MAX(contradicts) → MAX(weight) → MAX(date). До фикса JS не давал
  // resolution приоритет вообще — кластер в фазе resolution мог показать
  // tension от старого complication, если synthesis_cache.json был
  // недоступен.
  const resolutionsByDate = [...resolutions].sort((a, b) => new Date(b.date) - new Date(a.date));
  const newestResolutionWithTension = resolutionsByDate.find(s => s.tension);
  const tensionSig = newestResolutionWithTension
    || byTensionPriority.find(s => s.tension);

  let coreTension = tensionSig ? tensionSig.tension : '';

  // Если tension пустой — строим из двух противоречащих macro_implication
  if (!coreTension && byContra[0] && byContra[0].macro_implication) {
    const sA = byContra[0];
    // Ищем сигнал которому он противоречит
    const contraId = sA.links && sA.links.contradicts && sA.links.contradicts[0];
    const sB = contraId ? sigs.find(s => s.id === contraId) : byContra[1];
    if (sB && sB.macro_implication && sB.macro_implication !== sA.macro_implication) {
      const sAtext = sA.macro_implication.split(/\.\s/)[0];
      coreTension = sAtext.charAt(0).toUpperCase() + sAtext.slice(1) + ' — vs — ' + sB.macro_implication.split(/\.\s/)[0];
    }
  }

  // ── Этап 4: causal_chain — причинно-следственная цепочка ─────────
  const chain = [];
  if (anchorTrigger && anchorTrigger.macro_implication)
    chain.push(anchorTrigger.macro_implication);
  if (anchorComplication && anchorComplication !== anchorTrigger && anchorComplication.macro_implication)
    chain.push(anchorComplication.macro_implication);
  if (anchorResolution && anchorResolution.macro_implication)
    chain.push(anchorResolution.macro_implication);

  // ── Этап 5: market_structure — структурный вывод ─────────────────
  // Приоритет: resolution → trigger → топ по weight
  let marketStructure = '';
  if (anchorResolution && anchorResolution.macro_implication) {
    marketStructure = anchorResolution.macro_implication;
  } else if (anchorTrigger && anchorTrigger.macro_implication) {
    marketStructure = anchorTrigger.macro_implication;
  } else {
    marketStructure = byWeight.map(s => s.macro_implication).find(Boolean) || '';
  }

  // ── Этап 6: btc_implication — из самого весомого свежего ─────────
  const btcImpl = byWeight
    .filter(s => {
      const days = s.date ? Math.floor((today - new Date(s.date)) / 86400000) : 999;
      return days <= 30 && s.macro_implication;
    })
    .map(s => s.macro_implication)[0] || marketStructure;

  // ── Этап 7: key_takeaway — одна мысль ────────────────────────────
  let keyTakeaway = '';
  if (anchorResolution && anchorResolution.macro_implication)
    keyTakeaway = anchorResolution.macro_implication;
  else if (anchorTrigger && anchorTrigger.macro_implication)
    keyTakeaway = anchorTrigger.macro_implication;
  else
    keyTakeaway = byWeight.map(s => s.macro_implication).find(Boolean) || '';

  // ── Дедупликация ────────────────────────────────────────────────
  const dedupe = (a, b) => {
    if (!a || !b) return false;
    const wordsA = a.split(' ').filter(w => w.length > 5);
    return wordsA.filter(w => b.includes(w)).length > 4;
  };

  // ── Связки для синтеза ───────────────────────────────────────────
  const BRIDGES = {
    'active-complication': [
      'при этом', 'однако', 'но одновременно', 'в то время как', 'тогда как'
    ],
    'active-background': [
      'на фоне', 'в условиях', 'несмотря на', 'вопреки'
    ],
    'tension-complication': [
      'что усиливается', 'это усугубляется тем что', 'параллельно'
    ],
    'structural-background': [
      'структурно', 'в долгосрочной перспективе', 'фундаментально'
    ]
  };

  function getBridge(phaseKey, roleKey) {
    const key = phaseKey + '-' + roleKey;
    const arr = BRIDGES[key] || BRIDGES['active-complication'];
    return arr[Math.floor(Math.abs(Math.sin(sigs.length * 7)) * arr.length)];
  }

  // ── Синтез narrative из двух частей ─────────────────────────────
  // Часть A: trigger или топ по weight
  const partA = (anchorTrigger && anchorTrigger.macro_implication)
    ? anchorTrigger.macro_implication.split(/\.\s|[!?]/)[0].trim()
    : byWeight.map(s => s.macro_implication).find(Boolean) || '';

  // Часть B: complication или complication с contradicts
  const compWithContra = [...complications].sort((a,b) => {
    const ca = (a.links&&a.links.contradicts&&a.links.contradicts.length)||0;
    const cb = (b.links&&b.links.contradicts&&b.links.contradicts.length)||0;
    if (cb !== ca) return cb - ca;
    const wa = WEIGHT_RANK[a.weight]||0;
    const wb = WEIGHT_RANK[b.weight]||0;
    if (wb !== wa) return wb - wa;
    return new Date(b.date) - new Date(a.date);
  }).find(s => s.macro_implication) || anchorComplication;

  const partB = (compWithContra && compWithContra.macro_implication
      && !dedupe(compWithContra.macro_implication, partA))
    ? compWithContra.macro_implication.split(/\.\s|[!?]/)[0].trim()
    : '';

  // Склеиваем: A + связка + B
  let narrative = '';
  if (partA && partB) {
    const bridge = getBridge(phase, 'complication');
    narrative = partA + ' — ' + bridge + ' ' + partB.charAt(0).toLowerCase() + partB.slice(1);
  } else {
    narrative = partA || marketStructure;
  }

  // ── Takeaway: complication → trigger → btcImpl (не дублируем narrative) ──
  const takeawayCandidates = [anchorComplication, anchorTrigger, anchorResolution, byWeight[0]].filter(Boolean);
  let takeawaySource = '';
  for (const cand of takeawayCandidates) {
    const mac = cand.macro_implication || '';
    if (mac && !dedupe(mac, narrative) && !dedupe(mac, coreTension)) {
      takeawaySource = mac; break;
    }
  }
  if (!takeawaySource) takeawaySource = btcImpl || marketStructure;
  keyTakeaway = takeawaySource.split(/\.\s|[!?]/)[0].trim();

  // ── signal_strength ──────────────────────────────────────────────
  const totalScore = sigs.reduce((acc, s) => {
    const days = s.date ? Math.floor((today - new Date(s.date)) / 86400000) : 999;
    const fresh = days <= FRESHNESS_FRESH_DAYS ? 3 : days <= FRESHNESS_RECENT_DAYS ? 1 : 0;
    const w = WEIGHT_RANK[s.weight] || 1;
    const t = ((s.links&&s.links.contradicts&&s.links.contradicts.length) ? 5 : 0) + (s.tension ? 2 : 0);
    const r = ROLE_RANK[s.narrative_role] || 0;
    return acc + fresh + w + t + r;
  }, 0);

  const strength = totalScore >= 35 ? 'structural'
    : totalScore >= 20 ? 'strong'
    : totalScore >= 10 ? 'moderate'
    : 'weak';

  // anchor_signal_id — тот же концепт, что Python SynthesisResult.anchor_signal_id:
  // источник tension, либо anchor trigger если tension нигде не задан (C1 ARR v3).
  const anchorSignalId = (tensionSig || anchorTrigger || {}).id || '?';

  // N02 ARR v3: rationale раньше существовал только в Python-кеше — в JS
  // live-фоллбэке anchor-сигнал не объяснялся пользователю вообще. Формат
  // НЕ идентичен Python rationale (там есть confidence/ignored_duplicates,
  // которых JS не считает, см. ADR-010) — честно помечено как live-фоллбэк,
  // а не выдаётся за то же самое вычисление.
  const anchorObj = tensionSig || anchorTrigger || {};
  const rationale = anchorObj.id
    ? 'Tension from ' + anchorObj.id
      + ' (contradicts: ' + ((anchorObj.links && anchorObj.links.contradicts && anchorObj.links.contradicts.length) || 0)
      + ', weight: ' + (anchorObj.weight || '?') + '); phase: ' + phase
      + '; source: live-фоллбэк (synthesis_cache.json недоступен)'
    : '';

  return {
    narrative,
    tension:    coreTension,
    macro:      marketStructure,
    takeaway:   keyTakeaway,
    anchor_signal_id: anchorSignalId,
    rationale,
    strength,
    causal:     chain,
    phase,
    source:     'advanced'
  };
}


// ── ECOSYSTEM RENDER ──────────────────────────────────────────────────
// Редизайн 2026-07-23 (обсуждение в чате: блок "стал неприлично большим
// и неинформативным"). Решение в два уровня:
//   1. Полная карточка — только l2/protocol/infrastructure/exchange.
//      Это единственно растущий, но физически ограниченный пласт
//      объектов (в отличие от компаний, реальных Bitcoin L2 и протоколов
//      не бывает бесконечно много) — и группируется по типу (A).
//   2. Компактная строка-ссылка — corporate/fund/government. У companies
//      уже есть детальная "Топ-100 держателей" (BTC/%supply/mNAV) —
//      полная карточка с одной строкой summary дублирует её беднее.
//      У fund/government своего отдельного дома на сайте нет, но полная
//      карточка для них избыточна не менее.
// Плюс общий механизм "показать ещё N" (B) — применяется к любой секции
// независимо от группировки, снимает проблему роста базы без решения
// вопроса отбора (который остался открытым).
const ECO_TYPES = [
  { key: 'all',            label: 'ВСЕ' },
  { key: 'l2',             label: 'L2' },
  { key: 'protocol',       label: 'ПРОТОКОЛЫ' },
  { key: 'infrastructure', label: 'ИНФРА' },
  { key: 'exchange',       label: 'БИРЖИ' },
];

// Типы, уходящие в компактную секцию вместо полной карточки.
const ECO_COMPACT_TYPES = new Set(['corporate', 'fund', 'government']);

const ECO_TYPE_LABEL = {
  l2: 'L2', protocol: 'PROTOCOL', infrastructure: 'INFRA', exchange: 'EXCHANGE',
  corporate: 'CORP', fund: 'FUND', government: 'GOV',
};
const ECO_STATUS_LABEL = { active: 'ACTIVE', closed: 'CLOSED', pending: 'PENDING' };

// Куда ведёт "→" в компактной строке. corporate → Топ-100 держателей
// (детальные BTC/%supply/mNAV уже там). government → Структура владения
// (там есть категория 'governments' в разбивке по типам держателей —
// более релевантная цель, чем Топ-100, который строго про компании).
// fund — целевой панели пока нет, ссылки нет (не придумываем несуществующее).
const ECO_COMPACT_LINK = {
  corporate:  { tab: 'holders', title: 'Топ-100 держателей BTC',         label: '→ Топ-100' },
  government: { tab: 'holders', title: 'Структура владения · 2009–2026', label: '→ Структура владения' },
};

const ECO_GROUP_SHOW_MORE_STEP   = 6; // карточек на группу до кнопки "показать ещё"
const ECO_COMPACT_SHOW_MORE_STEP = 8; // строк в компактной секции до кнопки

let ecoFilter = 'all';
let ecoSearch = '';
// Какие секции сейчас полностью развёрнуты (ключ группы -> true). Сбрасывается
// при смене таба, чтобы новый таб не наследовал случайно чужой expanded-стейт.
let ecoExpandedGroups = new Set();

function ecoCardHtml(e) {
  const metrics = (e.profile?.metrics || []).slice(0, 2);
  const statusLabel = ECO_STATUS_LABEL[e.status] || sanitize(e.status);
  const typeLabel = ECO_TYPE_LABEL[e.type] || sanitize(e.type).toUpperCase();
  return '<div class="eco-card" data-entity-id="' + sanitize(e.id) + '">'
    + '<div class="eco-card-head">'
    +   '<span class="eco-card-name">' + sanitize(e.name) + '</span>'
    +   '<div class="eco-card-badges">'
    +     '<span class="eco-badge">' + typeLabel + '</span>'
    +     '<span class="eco-badge ' + sanitize(e.status) + '">' + statusLabel + '</span>'
    +   '</div>'
    + '</div>'
    + '<div class="eco-card-summary">' + sanitize(e.summary) + '</div>'
    + (metrics.length ? '<div class="eco-card-metrics">' + metrics.map(m => '<span class="eco-metric-chip">' + sanitize(m) + '</span>').join('') + '</div>' : '')
    + '</div>';
}

// Компактная строка: имя + тип-бейдж + BTC-холдинги (если факт отслеживается
// — через универсальный data-fact-key механизм, applyFactsToDOM() заполнит
// сам, если факта нет — остаётся пустым, это не ошибка) + ссылка на детальную
// панель, если применимо для этого типа.
function ecoCompactRowHtml(e) {
  const typeLabel = ECO_TYPE_LABEL[e.type] || sanitize(e.type).toUpperCase();
  const link = ECO_COMPACT_LINK[e.type];
  const linkTitleEscaped = link ? link.title.replace(/'/g, "\\'") : '';
  return '<div class="eco-compact-row" data-entity-id="' + sanitize(e.id) + '">'
    + '<span class="eco-badge">' + typeLabel + '</span>'
    + '<span class="eco-compact-name">' + sanitize(e.name) + '</span>'
    + '<span class="eco-compact-fact" data-fact-key="' + sanitize(e.id) + '.btc_holdings" data-fact-format="k"></span>'
    + (e.status !== 'active' ? '<span class="eco-badge ' + sanitize(e.status) + '">' + (ECO_STATUS_LABEL[e.status] || sanitize(e.status)) + '</span>' : '')
    + (link ? '<button class="eco-compact-link" onclick="siteMapGoTo(\'' + link.tab + '\',\'' + linkTitleEscaped + '\')">' + link.label + '</button>' : '')
    + '</div>';
}

function ecoMatchesSearch(e, q) {
  if (!q) return true;
  return e.name.toLowerCase().includes(q) || (e.summary || '').toLowerCase().includes(q);
}

// Общий рендер секции (группа полных карточек ИЛИ компактный список) с
// порогом "показать ещё". Поиск полностью отключает порог — не хотим,
// чтобы явный поиск объекта упирался в лимит показа.
function renderEcoSection(items, htmlFn, step, groupKey, hasSearch) {
  const expanded = hasSearch || ecoExpandedGroups.has(groupKey);
  const shown = expanded ? items : items.slice(0, step);
  let html = shown.map(htmlFn).join('');
  if (!expanded && items.length > step) {
    html += '<button class="eco-show-more" data-eco-expand="' + groupKey + '">Показать ещё ' + (items.length - step) + '</button>';
  }
  return html;
}

function renderEcosystem() {
  const tabsEl        = document.getElementById('eco-tabs');
  const listEl        = document.getElementById('eco-list');
  const compactWrap   = document.getElementById('eco-compact-section');
  const countEl       = document.getElementById('eco-count');
  const archiveEl     = document.getElementById('eco-archive');
  const archiveList   = document.getElementById('eco-archive-list');
  const archiveCount  = document.getElementById('eco-archive-count');
  if (!tabsEl || !listEl || !ENTITIES.length) return;

  const q = ecoSearch.trim().toLowerCase();
  const hasSearch = !!q;
  const active = ENTITIES.filter(e => e.status !== 'closed');
  const closed = ENTITIES.filter(e => e.status === 'closed');

  // Табы — только для полнокарточных типов; corporate/fund/government
  // всегда в компактной секции, вне зависимости от выбранного таба.
  const fullActive = active.filter(e => !ECO_COMPACT_TYPES.has(e.type));
  const presentTypes = new Set(fullActive.map(e => e.type));
  const tabs = ECO_TYPES.filter(t => t.key === 'all' || presentTypes.has(t.key));
  tabsEl.innerHTML = tabs.map(t =>
    '<button class="eco-tab' + (ecoFilter === t.key ? ' active' : '') + '" data-eco-filter="' + t.key + '">' + t.label + '</button>'
  ).join('');

  const filteredFull = fullActive
    .filter(e => ecoFilter === 'all' || e.type === ecoFilter)
    .filter(e => ecoMatchesSearch(e, q))
    .sort((a, b) => a.name.localeCompare(b.name, 'ru'));

  // Компактная секция показывается только во вкладке "ВСЕ" — при выборе
  // конкретного полнокарточного типа (L2/ПРОТОКОЛЫ/...) она не относится
  // к делу и не показывается.
  const filteredCompact = ecoFilter === 'all'
    ? active.filter(e => ECO_COMPACT_TYPES.has(e.type)).filter(e => ecoMatchesSearch(e, q)).sort((a, b) => a.name.localeCompare(b.name, 'ru'))
    : [];

  const totalShown = filteredFull.length + filteredCompact.length;
  countEl.textContent = totalShown + ' ' + ruPlural(totalShown, 'ОБЪЕКТ', 'ОБЪЕКТА', 'ОБЪЕКТОВ');

  // Группировка по типу (A) — только при "ВСЕ", где типы смешаны; для
  // одного выбранного таба группировка избыточна (и так один тип).
  let listHtml = '';
  if (!filteredFull.length) {
    listHtml = ecoFilter === 'all' && filteredCompact.length ? '' : '<div class="eco-empty">НЕТ ОБЪЕКТОВ</div>';
  } else if (ecoFilter === 'all') {
    ECO_TYPES.forEach(t => {
      if (t.key === 'all') return;
      const groupItems = filteredFull.filter(e => e.type === t.key);
      if (!groupItems.length) return;
      listHtml += '<div class="eco-group-head"><span>' + sanitize(t.label) + '</span><span class="eco-group-slash">/</span><span class="eco-group-count">' + groupItems.length + '</span></div>';
      listHtml += renderEcoSection(groupItems, ecoCardHtml, ECO_GROUP_SHOW_MORE_STEP, 'full-' + t.key, hasSearch);
    });
  } else {
    listHtml = renderEcoSection(filteredFull, ecoCardHtml, ECO_GROUP_SHOW_MORE_STEP, 'full-' + ecoFilter, hasSearch);
  }
  listEl.innerHTML = listHtml;

  if (compactWrap) {
    if (filteredCompact.length) {
      compactWrap.innerHTML =
        '<div class="eco-group-head"><span>КОМПАНИИ / ФОНДЫ / ПРАВИТЕЛЬСТВА</span><span class="eco-group-slash">/</span><span class="eco-group-count">' + filteredCompact.length + '</span></div>'
        + renderEcoSection(filteredCompact, ecoCompactRowHtml, ECO_COMPACT_SHOW_MORE_STEP, 'compact', hasSearch);
      compactWrap.style.display = '';
    } else {
      compactWrap.innerHTML = '';
      compactWrap.style.display = 'none';
    }
  }

  // Спаны eco-compact-fact уже в DOM — заполняем сразу, если facts.json
  // уже подъехал (idempotent, дёшево; не полагаемся на порядок вызова
  // относительно fetchFacts() из loadSignals()).
  applyFactsToDOM();

  // Архив — без изменений в логике: закрытые объекты редки (сейчас 2),
  // полная карточка независимо от типа, порог "показать ещё" не нужен.
  const filteredClosed = closed
    .filter(e => ecoMatchesSearch(e, q))
    .sort((a, b) => a.name.localeCompare(b.name, 'ru'));

  if (archiveEl && archiveList && archiveCount) {
    archiveCount.textContent = '(' + filteredClosed.length + ')';
    archiveList.innerHTML = filteredClosed.length
      ? filteredClosed.map(ecoCardHtml).join('')
      : '<div class="eco-empty">НЕТ ОБЪЕКТОВ</div>';
    archiveEl.style.display = closed.length ? '' : 'none';
    // При поиске, который что-то находит в архиве — разворачиваем автоматически
    if (q && filteredClosed.length) archiveEl.open = true;
  }
}

function setEcoFilter(key) {
  ecoFilter = key;
  ecoExpandedGroups.clear(); // новый таб не наследует чужой "показать ещё"
  renderEcosystem();
}

function setEcoSearch(value) {
  ecoSearch = value;
  renderEcosystem();
}

// Делегирование для eco-tabs и "показать ещё"
document.addEventListener('click', function(ev) {
  const tab = ev.target.closest('[data-eco-filter]');
  if (tab) { setEcoFilter(tab.getAttribute('data-eco-filter')); return; }
  const expandBtn = ev.target.closest('[data-eco-expand]');
  if (expandBtn) {
    ecoExpandedGroups.add(expandBtn.getAttribute('data-eco-expand'));
    renderEcosystem();
  }
});

// Живой поиск по экосистеме
document.addEventListener('input', function(ev) {
  if (ev.target && ev.target.id === 'eco-search') setEcoSearch(ev.target.value);
});

// ── REVENUE ENGINES ─────────────────────────────────────────────────────
let REVENUE_ENGINES = [];

const RE_TREND_LABEL = { growing: 'GROWING', declining: 'DECLINING', stable: 'STABLE', stressed: 'STRESSED' };

function renderRevenueEngines() {
  const listEl  = document.getElementById('re-list');
  const countEl = document.getElementById('re-count');
  if (!listEl || !countEl) return;

  if (!REVENUE_ENGINES.length) {
    countEl.textContent = '—';
    listEl.innerHTML = '<div class="eco-empty">НЕТ ДАННЫХ</div>';
    return;
  }

  const sorted = [...REVENUE_ENGINES].sort((a, b) => a.entity_name.localeCompare(b.entity_name, 'ru'));
  countEl.textContent = sorted.length + ' ' + ruPlural(sorted.length, 'МЕХАНИЗМ', 'МЕХАНИЗМА', 'МЕХАНИЗМОВ');

  // Нумерованные аккордеоны (01, 02, 03...) — тот же паттерн, что у mNAV
  // и Семи сетевых эффектов, вместо плоских некликабельных карточек.
  listEl.innerHTML = sorted.map((r, i) => {
    const num = String(i + 1).padStart(2, '0');
    const metrics = (r.metrics || []).slice(0, 2);
    const trendLabel = RE_TREND_LABEL[r.trend] || sanitize(r.trend || '').toUpperCase();
    return '<div class="acc-item">'
      + '<div class="acc-head" onclick="toggleAcc(this)">'
      +   '<span class="acc-icon">' + num + '</span>'
      +   '<span class="acc-label">' + sanitize(r.entity_name) + '</span>'
      +   '<span class="re-trend-badge ' + sanitize(r.trend || '') + '" style="margin-left:auto">' + trendLabel + '</span>'
      +   '<span class="acc-arrow">▼</span>'
      + '</div>'
      + '<div class="acc-body">'
      +   '<span class="re-engine-link" onclick="event.stopPropagation(); openEngineDetail(\'' + sanitize(r.id) + '\')">' + sanitize(r.name) + '</span>'
      +   '<p class="re-card-summary">' + sanitize(r.summary) + '</p>'
      +   (metrics.length ? '<div class="re-card-metrics">' + metrics.map(m => '<span class="re-metric-chip">' + sanitize(m) + '</span>').join('') + '</div>' : '')
      + '</div>'
      + '</div>';
  }).join('');
}

// Оверлей деталей доходного движка — полная информация (не обрезанная до
// 2 метрик) + таймлайн history, который растёт с каждым новым сигналом
// по этой сущности (см. REVENUE_ENGINES.json, поле history).
function openEngineDetail(engineId) {
  const engine = REVENUE_ENGINES.find(r => r.id === engineId);
  if (!engine) return;
  const overlay = document.getElementById('re-detail-overlay');
  const title   = document.getElementById('re-detail-title');
  const body    = document.getElementById('re-detail-body');

  title.textContent = engine.entity_name;

  let html = '';
  html += '<div class="re-detail-section"><div class="re-detail-label">Механизм</div>'
        + '<div class="re-detail-text" style="color:var(--btc);font-weight:700;margin-bottom:8px">' + sanitize(engine.name) + '</div>'
        + '<div class="re-detail-text">' + sanitize(engine.how_it_works || engine.summary) + '</div></div>';

  if ((engine.metrics || []).length) {
    html += '<div class="re-detail-section"><div class="re-detail-label">Метрики</div>'
          + '<div class="re-card-metrics">' + engine.metrics.map(m => '<span class="re-metric-chip">' + sanitize(m) + '</span>').join('') + '</div></div>';
  }

  const trendLabel = RE_TREND_LABEL[engine.trend] || sanitize(engine.trend || '').toUpperCase();
  html += '<div class="re-detail-section"><div class="re-detail-label">Тренд</div>'
        + '<span class="re-trend-badge ' + sanitize(engine.trend || '') + '">' + trendLabel + '</span>'
        + (engine.trend_evidence ? '<div class="re-detail-text" style="margin-top:8px">' + sanitize(engine.trend_evidence) + '</div>' : '')
        + '</div>';

  if ((engine.risk_factors || []).length) {
    html += '<div class="re-detail-section"><div class="re-detail-label">Риски</div>'
          + engine.risk_factors.map(r => '<div class="re-detail-risk-item">' + sanitize(r) + '</div>').join('')
          + '</div>';
  }

  if ((engine.history || []).length) {
    html += '<div class="re-detail-section"><div class="re-detail-label">История (' + engine.history.length + ')</div>'
          + [...engine.history].reverse().map(h =>
              '<div class="re-history-item">'
              + '<span class="re-history-date">' + sanitize(h.date) + '</span>'
              + '<span class="re-history-event">' + sanitize(h.event) + '</span>'
              + '<span class="re-history-signal">' + sanitize(h.signal_id) + '</span>'
              + '</div>'
            ).join('')
          + '</div>';
  }

  body.innerHTML = html;
  overlay.classList.add('open');
}

function closeEngineDetail() {
  document.getElementById('re-detail-overlay').classList.remove('open');
}

// ── ДОПОЛНИТЕЛЬНЫЕ ПАНЕЛИ ТЕОРИИ (data-driven, SBBA-IRP Wave 2) ─────────
// Контент уточняется правкой THEORY_TOPICS.json — не index.html — по мере
// появления новых сигналов темы macro/narrative (см. docs/SBBA_IRP_v1.md,
// REM-OG2). Переиспользует acc-item/panel разметку остальных панелей theory,
// но собирается из JSON, а не пишется вручную HTML-ом на каждую тему.
let THEORY_TOPICS = [];
let THEORY_ESSAYS = [];

// Общая плашка «ИСТОЧНИК: …» (низ панели или пункта аккордеона) — до
// аудита 2.2 этот inline-блок дублировался в renderEssayItem и
// renderTheoryTopic и уже успел бы разойтись при первой правке стиля.
// content — готовый HTML (вызывающий сам решает, что sanitize'ить:
// у THEORY_ESSAYS источник структурированный и экранируется по полям,
// у THEORY_TOPICS source_footer — сырой авторский HTML со ссылкой).
function sourceFooterHtml(content) {
  return '<div style="padding:10px 14px;border-top:1px solid var(--line);background:var(--bg3)">'
    + '<div style="font-family:var(--mono);font-size:9px;color:var(--dim);letter-spacing:0.08em">'
    + content
    + '</div></div>';
}

// Единый рендер пункта аккордеона для THEORY_TOPICS и THEORY_ESSAYS —
// слит из renderTheoryItem + renderEssayItem (аудит 2.1): функции были
// построчными дубликатами, эволюционировавшими врозь (item.open появлялся
// только в одной, crosslink/source — только в другой; отсутствие
// crosslink в THEORY_TOPICS остановило миграцию «Семи сетевых эффектов»).
// Схема-надмножество: open, paragraphs (через sanitizeStrong — узкий
// allowlist <strong>, для текста без <strong> вывод идентичен sanitize),
// highlight, crosslink, source.
function renderAccItem(item) {
  let html = '<div class="acc-item">';
  html += '<div class="acc-head" onclick="toggleAcc(this)">';
  html += '<span class="acc-icon">' + sanitize(item.icon) + '</span>';
  html += '<span class="acc-label">' + sanitize(item.label) + '</span>';
  html += '<span class="acc-arrow">▼</span>';
  html += '</div>';
  html += '<div class="acc-body' + (item.open ? ' open' : '') + '">';
  if (item.paragraphs && item.paragraphs.length) {
    html += item.paragraphs.map(function(p){ return '<p>' + sanitizeStrong(p) + '</p>'; }).join('');
  }
  if (item.highlight) {
    html += '<div class="callout-mono">'
      + sanitize(item.highlight) + '</div>';
  }
  if (item.crosslink) {
    const cl = item.crosslink;
    // target_tab — опционально (добавлено 2026-07-20): межвкладочная
    // ссылка через уже существующий siteMapGoTo(tab, title) вместо
    // getElementById+scrollIntoView, который не переключает вкладки.
    // target_panel в этом случае — точный текст .panel-title цели (как
    // ищет siteMapGoTo), не id. Без target_tab — прежнее поведение
    // (та же вкладка), не тронуто — обратная совместимость сохранена.
    const onclickAttr = cl.target_tab
      ? 'siteMapGoTo(\'' + sanitize(cl.target_tab) + '\',\'' + sanitize(cl.target_panel) + '\')'
      : 'document.getElementById(\'' + sanitize(cl.target_panel) + '\').scrollIntoView({behavior:\'smooth\'})';
    html += '<div class="crosslink" onclick="' + onclickAttr + '">'
      + '<span class="crosslink-arrow">↳</span>'
      + '<span class="crosslink-text">' + sanitize(cl.text) + '</span>'
      + '<span class="crosslink-target">' + sanitize(cl.target_label) + '</span>'
      + '</div>';
  }
  html += '</div></div>';
  if (item.source) {
    const s = item.source;
    html += sourceFooterHtml(
      'ИСТОЧНИК (' + sanitize(item.icon) + '): ' + sanitize(s.author) + ' · «' + sanitize(s.title) + '» · ' + sanitize(s.date)
      + (s.url ? ' · <a href="' + sanitize(s.url) + '" target="_blank" style="color:var(--btc);text-decoration:underline;text-decoration-style:dotted;text-underline-offset:2px">' + sanitize(s.url.replace(/^https?:\/\//, '').slice(0, 40)) + '</a>' : '')
    );
  }
  return html;
}

function renderTheoryTopic(topic) {
  let html = '<div class="panel" id="' + sanitize(topic.id) + '" style="scroll-margin-top:64px;margin-top:12px">';
  html += '<div class="panel-head">';
  html += '<span class="panel-title">' + sanitize(topic.panel_title) + '</span>';
  html += '<span class="panel-tag">' + sanitize(topic.panel_tag) + '</span>';
  html += '</div>';
  if (topic.intro) {
    const intros = Array.isArray(topic.intro) ? topic.intro : [topic.intro];
    html += intros.map(function(txt) {
      return '<div style="padding:12px 14px;border-bottom:1px solid var(--line)">'
        + '<div style="font-family:var(--sans);font-size:12px;color:var(--dim);line-height:1.6">' + sanitize(txt) + '</div>'
        + '</div>';
    }).join('');
  }
  if (topic.items && topic.items.length) {
    html += topic.items.map(renderAccItem).join('');
  }
  if (topic.conclusion) {
    html += '<div style="padding:12px 14px;background:var(--bg3);border-top:1px solid var(--line)">'
      + '<p style="margin:0;font-size:12px;color:var(--txt);line-height:1.6">' + sanitize(topic.conclusion) + '</p>'
      + '</div>';
  }
  // 2026-08-01: точка монтирования для THEORY_ESSAYS.json — найдено
  // пользователем на реальном скриншоте ("блок такой же скупой, как
  // раньше"): renderTheoryEssays() ищет document.getElementById(target_panel
  // + '-essays'), но ЭТА функция (для ЛЮБОГО дата-driven топика из
  // THEORY_TOPICS.json) никогда такой div не генерировала — только
  // статичные, написанные вручную панели в index.html (theory-money) имели
  // его расставленным руками. Эссе с target_panel на дата-driven топик
  // (theory-passphrase, мой же 21ideas-2026-dice-seed) технически не могло
  // никуда смонтироваться — renderTheoryEssays() тихо делает if (!el) return,
  // без единой ошибки в консоли, поэтому баг не проявлялся ничем кроме
  // "эссе просто не появилось". Добавлено здесь, а не точечно в JSON
  // конкретной панели — теперь работает для ЛЮБОГО топика из
  // THEORY_TOPICS.json, не только для того, где сегодня нашли пропуск.
  html += '<div id="' + sanitize(topic.id) + '-essays"></div>';
  if (topic.source_footer) {
    html += sourceFooterHtml(topic.source_footer);
  }
  html += '</div>';
  return html;
}

function renderTheoryTopics() {
  const rest = [];
  THEORY_TOPICS.forEach(function(topic) {
    // Идемпотентность: тема может рендериться с любой из двух вкладок
    // (theory — из-за точечных якорей ниже, macrocontext — из-за общего
    // контейнера), triggerTabData() может вызвать эту функцию дважды за
    // сессию. Если панель с этим id уже в DOM — пропускаем полностью.
    if (document.getElementById(topic.id)) return;
    // Точечный якорь: если в разметке уже стоит элемент с id="{id}-mount"
    // на конкретном месте (нужен позиционный контроль внутри своей
    // вкладки — например, среди других статичных панелей ТЕОРИИ), тема
    // рендерится ИМЕННО туда через outerHTML, а не в общий контейнер
    // theory-topics-container (который физически лежит в tab-macrocontext
    // и всегда добавляет темы в конец). Тема без такого mount-якоря
    // ведёт себя как раньше — уходит в общий контейнер.
    const mount = document.getElementById(topic.id + '-mount');
    if (mount) {
      mount.outerHTML = renderTheoryTopic(topic);
    } else {
      rest.push(topic);
    }
  });
  const el = document.getElementById('theory-topics-container');
  // rest.length === 0 на повторном вызове — не трогаем innerHTML вовсе,
  // иначе затрём уже отрисованный контейнер пустой строкой.
  if (el && rest.length) el.innerHTML = rest.map(renderTheoryTopic).join('');
}

// ── СТОРОННИЕ ЭССЕ/МАТЕРИАЛЫ — доп. пункты аккордеона в уже существующих
// панелях (не создают новых панелей). Реестр в THEORY_ESSAYS.json, не в
// index.html — добавление нового материала = запись в файл, без правки HTML.
function renderTheoryEssays() {
  if (!THEORY_ESSAYS.length) return;
  const byPanel = {};
  THEORY_ESSAYS.forEach(function(item) {
    (byPanel[item.target_panel] = byPanel[item.target_panel] || []).push(item);
  });
  Object.keys(byPanel).forEach(function(panelId) {
    const el = document.getElementById(panelId + '-essays');
    if (!el) return;
    el.innerHTML = byPanel[panelId].map(renderAccItem).join('');
  });
}

// ── ФУНКЦИИ BITCOIN ─────────────────────────────────────────────────────
let BITCOIN_FUNCTIONS = [];

function renderToolBlock(tool) {
  let html = '<div style="margin-top:10px;padding-top:10px;border-top:1px solid var(--line)">';
  html += '<div style="font-family:var(--mono);font-size:11px;font-weight:700;color:var(--txt);letter-spacing:.03em">🛠 ' + sanitize(tool.name) + '</div>';
  if (tool.important_note) {
    html += '<div style="margin-top:6px;padding:8px 10px;background:var(--bg3);border-left:2px solid var(--btc);font-size:11px;color:var(--dim);line-height:1.6">' + sanitize(tool.important_note) + '</div>';
  }
  if (tool.how_it_works) {
    html += '<p style="margin-top:8px;font-size:12px;color:var(--txt);line-height:1.6">' + sanitize(tool.how_it_works) + '</p>';
  }
  if (tool.requirements && tool.requirements.length) {
    html += '<div style="margin-top:8px;font-size:11px;color:var(--dim)">Нужно:</div>';
    html += '<ul style="margin:4px 0 0;padding-left:18px;font-size:12px;color:var(--txt);line-height:1.7">'
      + tool.requirements.map(function(r){ return '<li>' + sanitize(r) + '</li>'; }).join('')
      + '</ul>';
  }
  if (tool.steps && tool.steps.length) {
    html += '<ol style="margin:8px 0 0;padding-left:18px;font-size:12px;color:var(--txt);line-height:1.8">'
      + tool.steps.map(function(s){ return '<li style="margin-bottom:4px">' + sanitize(s) + '</li>'; }).join('')
      + '</ol>';
  }
  if (tool.limitation) {
    html += '<div style="margin-top:8px;font-size:11px;color:var(--dim);font-style:italic">⚠ ' + sanitize(tool.limitation) + '</div>';
  }
  if (tool.description) {
    html += '<p style="margin-top:8px;font-size:12px;color:var(--txt);line-height:1.6">' + sanitize(tool.description) + '</p>';
  }
  html += '</div>';
  return html;
}

function renderFunctionCard(fn) {
  let html = '<div class="acc-item">';
  html += '<div class="acc-head" onclick="toggleAcc(this)">';
  html += '<span class="acc-icon">' + sanitize(fn.icon || '⚙') + '</span>';
  html += '<span class="acc-label">' + sanitize(fn.name) + '</span>';
  html += '<span class="acc-arrow">▼</span>';
  html += '</div>';
  html += '<div class="acc-body">';
  if (fn.hook) {
    html += '<p style="font-style:italic;color:var(--btc);font-size:12px">' + sanitize(fn.hook) + '</p>';
  }
  if (fn.story && fn.story.length) {
    html += fn.story.map(function(p){ return '<p style="margin-top:8px">' + sanitize(p) + '</p>'; }).join('');
  }
  if (fn.explanation) {
    html += '<p style="margin-top:10px;font-weight:600;color:var(--txt)">' + sanitize(fn.explanation) + '</p>';
  }
  if (fn.tools && fn.tools.length) {
    html += '<div style="margin-top:12px;font-family:var(--mono);font-size:10px;color:var(--dim);letter-spacing:.05em">КАК ИСПОЛЬЗОВАТЬ</div>';
    html += fn.tools.map(renderToolBlock).join('');
  }
  html += '</div></div>';
  return html;
}

function renderBitcoinFunctions() {
  const countEl = document.getElementById('bf-count');
  const listEl = document.getElementById('bf-list');
  if (!countEl || !listEl) return;
  if (!BITCOIN_FUNCTIONS.length) {
    countEl.textContent = '—';
    listEl.innerHTML = '';
    return;
  }
  countEl.textContent = BITCOIN_FUNCTIONS.length + ' ' + ruPlural(BITCOIN_FUNCTIONS.length, 'ФУНКЦИЯ', 'ФУНКЦИИ', 'ФУНКЦИЙ');
  listEl.innerHTML = BITCOIN_FUNCTIONS.map(renderFunctionCard).join('');
}


let TREASURY_HOLDERS = [];
let TOP_ADDRESSES = [];
let TOP_ADDRESSES_META = {};
let taExpanded = false; // "показать ещё" — тот же паттерн, что Экосистема Bitcoin
let BIP110_SIGNALING = {};
let TREASURY_META = {};
let thSearch = '';
let thSortKey = 'btc';
let thSortDir = -1; // -1 desc, 1 asc

function thMatchesSearch(h, q) {
  if (!q) return true;
  return h.name.toLowerCase().includes(q) || (h.ticker || '').toLowerCase().includes(q);
}

function renderTreasuryHolders() {
  const countEl = document.getElementById('th-count');
  const metaEl  = document.getElementById('th-meta');
  const tbody   = document.getElementById('th-tbody');
  if (!countEl || !metaEl || !tbody) return;

  if (!TREASURY_HOLDERS.length) {
    countEl.textContent = '—';
    metaEl.textContent = 'Нет данных';
    tbody.innerHTML = '<tr><td colspan="7" class="th-empty">НЕТ ДАННЫХ</td></tr>';
    return;
  }

  const supplyCap = TREASURY_META.supply_cap || 21000000;
  const q = thSearch.trim().toLowerCase();
  const filtered = TREASURY_HOLDERS.filter(h => thMatchesSearch(h, q));

  const sorted = [...filtered].sort((a, b) => {
    let av, bv;
    if (thSortKey === 'pct') { av = a.btc; bv = b.btc; }
    else { av = a[thSortKey]; bv = b[thSortKey]; }
    if (typeof av === 'string') return thSortDir * av.localeCompare(bv, 'ru');
    av = (av === null || av === undefined) ? -Infinity : av;
    bv = (bv === null || bv === undefined) ? -Infinity : bv;
    return thSortDir * (av - bv);
  });

  countEl.textContent = filtered.length + ' ИЗ ' + TREASURY_HOLDERS.length;

  const snapDate = TREASURY_META.snapshot_date ? sanitize(TREASURY_META.snapshot_date) : '—';
  const totalPct = TREASURY_META.total_top100_btc ? (TREASURY_META.total_top100_btc / supplyCap * 100).toFixed(2) : '—';
  metaEl.innerHTML = 'Снимок: <b>' + snapDate + '</b> · Источник: ' + sanitize(TREASURY_META.source || '—')
    + ' · Топ-100: <b>' + (TREASURY_META.total_top100_btc || 0).toLocaleString('ru-RU') + ' BTC</b> (' + totalPct + '% supply)'
    + (TREASURY_META.total_all_public_btc ? ' · Все публичные держатели (' + (TREASURY_META.public_holders_count || '?') + '): ' + TREASURY_META.total_all_public_btc.toLocaleString('ru-RU') + ' BTC' : '');

  tbody.innerHTML = sorted.length ? sorted.map(h => {
    const pct = (h.btc / supplyCap * 100);
    const pctStr = pct >= 0.01 ? pct.toFixed(3) + '%' : '<0.01%';
    return '<tr>'
      + '<td class="th-rank">' + h.rank + '</td>'
      + '<td class="th-name">' + sanitize(h.name) + '</td>'
      + '<td>' + sanitize(h.country || '—') + '</td>'
      + '<td>' + sanitize(h.ticker || '—') + '</td>'
      + '<td class="th-btc">' + h.btc.toLocaleString('ru-RU') + '</td>'
      + '<td class="th-pct">' + pctStr + '</td>'
      + '<td class="th-mnav">' + (h.mnav != null ? h.mnav.toFixed(2) + 'x' : '—') + '</td>'
      + '</tr>';
  }).join('') : '<tr><td colspan="7" class="th-empty">НИЧЕГО НЕ НАЙДЕНО</td></tr>';

  document.querySelectorAll('.th-table th[data-sort]').forEach(th => {
    th.classList.toggle('sorted', th.getAttribute('data-sort') === thSortKey);
  });
}

function setThSearch(value) {
  thSearch = value;
  renderTreasuryHolders();
}

// ── ТОП-100 БОГАТЕЙШИХ АДРЕСОВ (data/top_addresses.json, Blockchair) ────
// Добавлено 2026-07-25. Компактные строки с цветной полосой категории
// (биржа/потеряно-конфисковано/неизвестно) — тот же язык бейджей, что
// "Экосистема Bitcoin", не отдельная новая иконография. "Показать ещё" —
// тот же порог/паттерн, что renderEcoSection() (см. ту секцию файла).
const TA_SHOW_MORE_STEP = 10;
const TA_CATEGORY_LABEL = { exchange: 'БИРЖА', lost_confiscated: 'ПОТЕРЯНО/КОНФИСКОВАНО', unknown: 'НЕИЗВЕСТНО' };

function taRowHtml(e) {
  const name = e.label ? sanitize(e.label) : sanitize(e.address.slice(0, 10) + '…' + e.address.slice(-6));
  const addrShort = e.label ? sanitize(e.address.slice(0, 14) + '…' + e.address.slice(-6)) : '';
  const catLabel = TA_CATEGORY_LABEL[e.category] || 'НЕИЗВЕСТНО';
  return '<div class="ta-row cat-' + sanitize(e.category) + '">'
    + '<span class="ta-rank">' + e.rank + '</span>'
    + '<div class="ta-body">'
    +   '<div class="ta-name">' + name + '<span class="eco-badge" style="margin-left:6px">' + catLabel + '</span></div>'
    +   (addrShort ? '<div class="ta-addr">' + addrShort + '</div>' : '')
    + '</div>'
    + '<div class="ta-bal">'
    +   '<div class="ta-btc">' + e.balance_btc.toLocaleString('ru-RU', {maximumFractionDigits: 0}) + ' BTC</div>'
    +   '<div class="ta-pct">' + e.pct_of_supply.toFixed(3) + '%</div>'
    + '</div>'
    + '</div>';
}

function renderTopAddresses() {
  const countEl = document.getElementById('ta-count');
  const metaEl  = document.getElementById('ta-meta');
  const listEl  = document.getElementById('ta-list');
  if (!countEl || !metaEl || !listEl) return;

  if (!TOP_ADDRESSES.length) {
    countEl.textContent = '—';
    metaEl.textContent = 'Нет данных';
    listEl.innerHTML = '<div class="eco-empty">НЕТ ДАННЫХ</div>';
    return;
  }

  countEl.textContent = TOP_ADDRESSES.length + ' АДРЕСОВ';
  const updated = TOP_ADDRESSES_META.updated_at ? new Date(TOP_ADDRESSES_META.updated_at).toLocaleDateString('ru-RU') : '—';
  metaEl.innerHTML = 'Обновлено: <b>' + sanitize(updated) + '</b> · Источник: ' + sanitize(TOP_ADDRESSES_META.source || '—')
    + (TOP_ADDRESSES_META.caveat ? '<br>⚠ ' + sanitize(TOP_ADDRESSES_META.caveat) : '');

  const shown = taExpanded ? TOP_ADDRESSES : TOP_ADDRESSES.slice(0, TA_SHOW_MORE_STEP);
  let html = shown.map(taRowHtml).join('');
  if (!taExpanded && TOP_ADDRESSES.length > TA_SHOW_MORE_STEP) {
    html += '<button class="eco-show-more" id="ta-show-more">Показать ещё ' + (TOP_ADDRESSES.length - TA_SHOW_MORE_STEP) + '</button>';
  }
  listEl.innerHTML = html;
}

document.addEventListener('click', function(ev) {
  if (ev.target && ev.target.id === 'ta-show-more') {
    taExpanded = true;
    renderTopAddresses();
  }
});

function setThSort(key) {
  if (thSortKey === key) {
    thSortDir *= -1;
  } else {
    thSortKey = key;
    thSortDir = (key === 'name' || key === 'country' || key === 'ticker') ? 1 : -1;
  }
  renderTreasuryHolders();
}

document.addEventListener('input', function(ev) {
  if (ev.target && ev.target.id === 'th-search') setThSearch(ev.target.value);
});
document.addEventListener('click', function(ev) {
  const th = ev.target.closest('.th-table th[data-sort]');
  if (th) setThSort(th.getAttribute('data-sort'));
});

// ── СВОРАЧИВАЕМЫЕ ПАНЕЛИ ────────────────────────────────────────────────
document.addEventListener('click', function(ev) {
  const head = ev.target.closest('.panel-head.collapsible');
  if (!head) return;
  const targetId = head.getAttribute('data-collapse-target');
  const panel = targetId ? document.getElementById(targetId) : head.closest('.panel');
  if (panel) panel.classList.toggle('collapsed');
});

// ── ENTITIES BASE ──────────────────────────────────────────────────────
let ENTITIES = [];

async function loadEntities() {
  try {
    const resp = await fetch('ENTITIES.json?v=' + Date.now());
    const data = await resp.json();
    ENTITIES = data.entities || [];
    // Перерендериваем сигналы если они уже загружены
    if (SIGNALS && SIGNALS.length) {
      const marketTab = document.getElementById('tab-market');
      if (marketTab && marketTab.classList.contains('active')) renderSignals();
    }
  } catch(e) {
    console.error('ENTITIES.json load error:', e);
  }
}

const TYPE_META = {
  l2:            'L2',
  protocol:      'PROTOCOL',
  corporate:     'CORP',
  fund:          'FUND',
  infrastructure:'INFRA',
  exchange:      'EXCHANGE',
};

// ── XSS-защита (B2 ARR v3, SECURITY.md T1) ─────────────────────────────────
// Все поля сигналов (signals.json) и артефактов (ENTITIES.json) — свободный
// текст, заполняемый аналитиком вручную. Перед вставкой через innerHTML их
// необходимо экранировать — без этого произвольный <img onerror=...> в любом
// текстовом поле сигнала выполнился бы в браузере читателя сайта.
//
// Единая функция применяется централизованно (без дублирования логики) во
// всех местах, где данные сигнала/сущности попадают в innerHTML. Санитизация
// выполняется ДО highlightEntities() — порядок важен, иначе экранируются и
// собственные <span> теги, которые highlightEntities добавляет для подсветки
// упомянутых сущностей.
function sanitize(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}

// Узкий allowlist поверх sanitize() — только <strong>/</strong>, для
// параграфов THEORY_TOPICS.json с инлайн-выделением слов в оригинальном
// авторском тексте. Экранирует ВСЁ как sanitize(), затем точечно
// возвращает буквально только эти два тега — никакой другой HTML или
// атрибут через это пройти не может.
function sanitizeStrong(str) {
  return sanitize(str)
    .replace(/&lt;strong&gt;/g, '<strong>')
    .replace(/&lt;\/strong&gt;/g, '</strong>');
}

function highlightEntities(text) {
  if (!ENTITIES || !ENTITIES.length) return sanitize(text);
  let result = sanitize(text);
  const sorted = [...ENTITIES].sort((a, b) => b.name.length - a.name.length);
  sorted.forEach(e => {
    const safeName = sanitize(e.name);
    const escaped = safeName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp('(' + escaped + ')', 'g');
    result = result.replace(re, '<span class="entity-link" data-entity-id="' + sanitize(e.id) + '">$1</span>');
  });
  return result;
}

// 2026-07-28 (по запросу пользователя, утверждено превью 5 вариантов) —
// выделение "vs" в тензии бейджем-капсулой. Применяется ПОСЛЕ
// highlightEntities() (которая сама делает sanitize() входного текста) —
// не до, иначе injected-теги бейджа сами были бы заэкранированы
// повторным sanitize() внутри highlightEntities(). Проверено — ни одна
// сущность не содержит "vs" как отдельное слово в id/name (иначе
// регулярка задела бы её случайно).
function highlightVs(html) {
  return html.replace(/\bvs\b/g, '<span class="tension-vs-badge">VS</span>');
}

// 2026-07-28 (по запросу пользователя): tension/macro_implication/summary/
// metrics в исходных данных (signals.json/ENTITIES.json) в основном без
// точки в конце — проверено: 223/231 полей ENTITIES.json, 170/200 полей
// signals.json. Редактировать сами данные ретроактивно нельзя для
// tension/macro_implication (Immutability Policy, NIES AD-7 — уже учтены
// в синтезе), да и в ENTITIES.json это отдельная миграция на 200+ правок.
// Решение — нормализация ТОЛЬКО на уровне отображения: добавляем точку в
// конце каждой непустой строки многострочного текста, если там уже нет
// финальной пунктуации (. ! ? …). Применяется к СЫРОМУ тексту, до
// sanitize()/highlightEntities()/highlightVs() — просто вставляет литерал
// ".", дальше текст проходит все обычные преобразования как есть.
function ensureSentencePunctuation(text) {
  if (!text) return text;
  return text.split('\n').map(line => {
    const trimmed = line.replace(/\s+$/, '');
    if (!trimmed) return line;
    if (/[.!?…]$/.test(trimmed)) return trimmed;
    return trimmed + '.';
  }).join('\n');
}

// Делегирование — один обработчик на весь документ
document.addEventListener('click', function(ev) {
  const el = ev.target.closest('[data-entity-id]');
  if (el) {
    ev.stopPropagation();
    showEntityPopup(el.getAttribute('data-entity-id'));
    return;
  }
  const goto = ev.target.closest('[data-goto]');
  if (goto) showTab(goto.getAttribute('data-goto'), null);
});

function showEntityPopup(id) {
  const e = ENTITIES.find(x => x.id === id);
  if (!e) return;

  document.getElementById('ep-name').textContent = e.name;
  const typeEl = document.getElementById('ep-type');
  typeEl.textContent = TYPE_META[e.type] || e.type.toUpperCase();
  if (e.status === 'closed') typeEl.classList.add('ep-status-closed');
  else typeEl.classList.remove('ep-status-closed');

  document.getElementById('ep-summary').textContent = e.summary;

  const metrics = e.profile?.metrics || [];
  const metricsEl = document.getElementById('ep-metrics');
  metricsEl.innerHTML = metrics.length
    ? metrics.map(m => '<div class="ep-metric">· ' + sanitize(m) + '</div>').join('')
    : '';

  const notableEl = document.getElementById('ep-notable');
  notableEl.innerHTML = e.profile?.notable
    ? '<div class="ep-notable">' + sanitize(e.profile.notable) + '</div>'
    : '';

  const refs = e.signal_refs || [];
  document.getElementById('ep-refs').innerHTML = refs.length
    ? refs.map(r => '<span class="ep-ref">' + sanitize(r) + '</span>').join('')
    : '';

  document.getElementById('entity-popup').classList.add('visible');
  document.getElementById('ep-overlay').classList.add('visible');
}

function closeEntityPopup() {
  document.getElementById('entity-popup').classList.remove('visible');
  document.getElementById('ep-overlay').classList.remove('visible');
}

// ── SIGNALS BASE (загружается из signals.json) ──
// Схема записи: { date, cat, catLabel, dir (neg|pos|neu), signal, data:[], context, caveat, source }
let SIGNALS = [];
// КРИТИЧНО: объявлена здесь (не рядом с initCharts() ниже по файлу),
// потому что restoreLastActiveTab() (см. ниже) может СИНХРОННО вызвать
// showTab('analytics') -> triggerTabData() -> initCharts() ещё во время
// разбора этого же script-блока, до того как исполнение дойдёт до более
// поздней строки с "let chartsInited". Обнаружено 2026-07-25: если
// bi_active_tab в localStorage равен 'analytics', necaught ReferenceError
// (temporal dead zone) в этой точке обрывал ВЕСЬ оставшийся синхронный
// код скрипта, включая последующий вызов loadSignals() — сайт переставал
// загружать вообще что-либо, не только вкладку МЕТРИКИ.
let chartsInited = false;
let SYNTHESIS_CACHE = {}; // Путь 3: кеш Python-синтеза

// 2026-07-28: полная аналитика по кластерам (ВСЕ НАРРАТИВЫ, все N кластеров,
// ступенчато — топ-3 полной карточкой + остальные компактно). Объявлены
// рано по той же причине, что chartsInited/PRESET_SIGNALS_LIST выше —
// triggerTabData('base') может быть вызван СИНХРОННО при восстановлении
// вкладки (bi_active_tab='base' в localStorage), до того как обычное
// линейное исполнение дошло бы до этой точки ниже по файлу.
const CLUSTER_WEIGHT_RANK = { onchain: 4, primary: 3, market: 2, media: 1 };
const CLUSTER_ROLE_RANK   = { trigger: 4, complication: 3, resolution: 2, background: 0 };

// 2026-07-28 (по запросу пользователя): готовые сигналы для кластеров
// раньше строились как сырые обрывки тензии (первые 70 симв. до " vs ") —
// на скриншоте пользователь показал, что это выглядит криво (перенос на
// 2 строки в таблеточной кнопке, обрезание посреди числа "$2...", смесь
// стилей с короткими вопросами про сущности). Курируемый список коротких
// вопросов — не эвристика из подписи кластера (подпись часто не
// пересекается словами с реальной тензией, см. коммит про сущности
// раньше в этой же сессии). Каждый вопрос ПРОВЕРЕН вручную —
// действительно ведёт в СВОЙ кластер через localAnalyzeSignal(), не в
// чужой (учтена русская морфология — падежные формы должны буквально
// совпадать со словами в реальном тексте тензии, не парафраз).
// 2026-07-28 (по запросу пользователя, Вариант 4 из
// docs/ANALYSIS-preset-question-grammar.md): раньше вопрос для каждого
// кластера генерировался НА ЛЕТУ — случайное окно 4-6 слов из реального
// текста тензии. Пользователь показал реальные примеры несклада ("Что с
// баланса до 7700 BTC?", "Что с на каждые...", "Что с млн BTC...") —
// причина не в списке стоп-слов (JUNK_WORD_START), а в согласовании
// падежей: слово в источнике стоит в падеже своей роли в ИСХОДНОМ
// предложении, не в том, что требуется после "Что с" (творительный).
// Списком стоп-слов эту задачу не решить — падеж свойство КАЖДОГО
// слова окна, не только крайних. Полный разбор — см. документ выше.
//
// Решение — по 4 ВРУЧНУЮ написанных, грамматически цельных вопроса на
// кластер (не вырезанных из текста, а составленных заново из его
// словаря), каждый ПРОВЕРЕН через localAnalyzeSignal() перед принятием
// (скрипт-проверка, не на глаз) — 44 вопроса, 0 провалов при финальной
// проверке. generatePresetSignals() выбирает случайный вопрос из пула
// каждого кластера при каждом рендере — рандомность сохраняется, но из
// заведомо корректного множества, не из непроверяемого пространства
// произвольных окон слов.
const CLUSTER_PRESET_QUESTIONS = {
  strategy_model_stress:       ['Что с резервом и дилюцией акций?', 'Что с дивидендной машиной STRC?', 'Что с падением STRC ниже номинала?', 'Испытывает ли давление дивидендная машина?'],
  etf_institutional_flow:      ['Что банки получили право хранить?', 'Что с капитуляцией розницы?', 'Что требует Базель III от банков?', 'Что с конфигурацией декабря 2022?'],
  btc_treasury_competition:    ['Что с трекером баланса BTC?', 'Как эволюционирует казначейство?', 'Что заявляет представитель МВФ?', 'Эволюционирует ли BTC-казначейство?'],
  supply_scarcity:             ['Что с LTH и держателями BTC?', 'Ликвидное предложение BTC — что происходит?', 'Убеждённые держатели поглощают давление?', 'Что с режимом медвежьего дна?'],
  leverage_deleveraging_cycle: ['Что с отклонением от тренда?', 'Что могут макро-катализаторы?', 'Насколько хрупок рынок BTC сейчас?', 'Способны ли макро-катализаторы развернуть рынок?'],
  bitcoin_governance_debate:   ['Что с консенсусом по BIP-110?', 'Что формализует институциональный лагерь?', 'Что с голосованием клиентов по BIP-110?', 'Что означает снижение порога консенсусной активации?'],
  wallet_security_incidents:   ['Что случилось с безопасностью Coldcard?', 'Насколько защищена генерация ключей в аппаратных кошельках?', 'Что произошло с self-custody инфраструктурой?', 'Какие уязвимости нашли в аппаратных кошельках?'],
  quantum_security:            ['Что с квантовой угрозой?', 'Что с институциональной подготовкой к quantum-risk?', 'Опережает ли практика протокольный стандарт?', 'Что с BIP-360 и BIP-361 для кошельков?'],
  mining_operations:           ['Что с децентрализацией майнинга?', 'Что с переходом от теории к практике?', 'Кто контролирует состав блоков?', 'Что с колебаниями мощности сети?'],
  layer2_programmability:      ['Что со стеком инфраструктуры?', 'Что с utility за пределами золота?', 'Что с расчётным слоем стейблкоинов?', 'Гарантирует ли Bitcoin смену платформы?'],
  mining_ai_diversification:   ['Майнеры диверсифицируются в AI?', 'Что вознаграждает рынок у майнеров?', 'Продолжают ли майнеры продавать BTC?', 'Как рынок оценивает энергетику AI?'],
  lightning_payments:          ['Что с видимостью мемпула?', 'Что с funding-рельсами платформ?', 'Что с funding-рельсами финансовых платформ?', 'Требует ли сервис честности федерации?']
};

// 2026-07-28: вынесено на уровень модуля из renderSignals() (была
// локальная const, недоступная извне) — по запросу пользователя короткий
// бейдж "Найдено: X" в результате анализатора (localAnalyzeSignal(),
// отдельная top-level функция) должен использовать эти же короткие
// подписи, не длинные CLUSTER_LABELS_AI. Та же TDZ-дисциплина, что и для
// остальных ранних объявлений — localAnalyzeSignal() может быть вызвана
// раньше, чем renderSignals() успела бы объявить локальную версию.
const DIGEST_CLUSTER_LABELS = {
  strategy_model_stress:    '🏦 STRATEGY',
  etf_institutional_flow:   '📊 ETF',
  btc_treasury_competition: '💰 КАЗНАЧЕЙСТВА',
  supply_scarcity:          '⬛ ПРЕДЛОЖЕНИЕ',
  leverage_deleveraging_cycle: '💥 ДЕЛЕВЕРИДЖ',
  bitcoin_governance_debate: '⚖️ УПРАВЛЕНИЕ',
  wallet_security_incidents: '🔓 БЕЗОПАСНОСТЬ КОШЕЛЬКОВ',
  quantum_security:         '🔐 Q-DAY',
  mining_operations:        '⛏️ МАЙНИНГ',
  layer2_programmability:   '🔗 L2',
  mining_ai_diversification: '🤖 МАЙНИНГ И AI',
  lightning_payments:       '⚡ LIGHTNING',
};

// 2026-07-26: перенесено сюда с исходного места (рядом с analyzeSignal()),
// той же причине, что chartsInited выше — bi_active_tab='signals' в
// localStorage синхронно вызывал triggerTabData → renderPresetSignals(),
// который обращался к PRESET_SIGNALS_LIST ДО того, как исполнение доходило
// до её исходного (более позднего) объявления — необработанный
// ReferenceError (TDZ) обрывал весь оставшийся синхронный код скрипта,
// включая loadSignals(). Заодно перенесены соседние объявления того же
// функционального блока (ANALYSIS_STEPS/analysisResult/currentStepIdx/
// AI_STOP_WORDS/CLUSTER_LABELS_AI) — по той же логике профилактически,
// не только упавшая переменная.
const PRESET_SIGNALS_LIST = [
  'Крупное государство продаёт BTC',
  'ETFs поглощают продажи без падения цены',
  'Халвинг приближается',
  'Компании начинают покупать BTC',
  'Цена не реагирует на негативные новости',
  'Новый исторический максимум добытых BTC'
];

let analysisResult = null;

const AI_STOP_WORDS = new Set([
  'и','в','во','не','что','он','на','я','с','со','как','а','то','все','она',
  'так','его','но','да','ты','к','у','же','вы','за','бы','по','только','её',
  'мне','было','вот','от','меня','ещё','нет','о','из','ему','когда','даже',
  'ну','если','уже','или','быть','был','до','вас','для','мы','их','чем',
  'была','без','раз','себе','под','будет','этот','того','этого','какой',
  'этом','это','также','через','есть','можно','при','об','этой','этих',
  'какие','какая','какое','сколько','кто','где','почему','зачем',
  // 2026-07-26: найдено на реальном примере — "Сколько BTC у Stratagy?"
  // ложно совпало с кластером про Сальвадор ЕДИНСТВЕННО по слову "btc"
  // (встречается в тексте почти любого кластера — центральное слово всего
  // сайта, ноль различающей способности для этой конкретной задачи).
  'btc','bitcoin','биткоин','биткойн','биткоина','биткойна','биткоину','биткойну'
]);

const CLUSTER_LABELS_AI = {
  strategy_model_stress:       '🏦 Strategy: модель под давлением',
  etf_institutional_flow:      '📊 ETF: институциональный поток',
  btc_treasury_competition:    '💰 Казначейства: конкуренция',
  supply_scarcity:             '⬛ Предложение',
  leverage_deleveraging_cycle: '💥 Левередж: циклы на плече',
  bitcoin_governance_debate:   '⚖️ Управление: спор о консенсусе',
  wallet_security_incidents:   '🔓 Безопасность self-custody кошельков',
  quantum_security:            '🔐 Q-Day: квантовая угроза',
  mining_operations:           '⛏️ Майнинг: операции и безопасность',
  layer2_programmability:      '🔗 L2: программируемость Bitcoin',
  mining_ai_diversification:   '🤖 Майнинг и AI: гибридная модель',
  lightning_payments:          '⚡ Lightning: платежи и расчёты'
};

// M3 ARR v3: единый источник истины для порогов freshness-скоринга —
// ontology.json (та же логика, что Python config/settings.py STALE_THRESHOLD,
// см. tests/unit/test_ontology_settings_consistency.py). Дефолты ниже —
// fallback на случай недоступности ontology.json (DEGRADE GRACEFULLY,
// см. ERROR_PHILOSOPHY в config/settings.py) и совпадают с текущими
// значениями ontology.json на момент этого коммита.
let FRESHNESS_FRESH_DAYS  = 7;
let FRESHNESS_RECENT_DAYS = 30;

let priceChartInited = false;
function initPriceChart() {
  if (priceChartInited) return;
  priceChartInited = true;

  // ── TERMINAL PRICE CHART ─────────────────────────────────────────────────
  (function renderTerminalChart() {
    const wrap = document.getElementById('terminal-price-chart');
    if (!wrap) { console.error('PRICE CHART: wrap not found'); return; }
    const wrapOuter = document.getElementById('price-chart-wrap');
    if (wrapOuter) wrapOuter.style.display = '';
    wrap.innerHTML = '<div style="padding:8px 14px;font-family:monospace;font-size:10px;color:#F7931A">INIT OK — загрузка данных...</div>';
    console.log('PRICE CHART: wrap found, starting init');

    // CSS variables from project palette (resolved once)
    const CS = getComputedStyle(document.documentElement);
    const C = {
      bg:    CS.getPropertyValue('--bg').trim()    || '#0C0F14',
      bg2:   CS.getPropertyValue('--bg2').trim()   || '#111520',
      bg3:   CS.getPropertyValue('--bg3').trim()   || '#171D2B',
      line:  CS.getPropertyValue('--line').trim()  || '#242A38',
      line2: CS.getPropertyValue('--line2').trim() || '#2E3648',
      txt:   CS.getPropertyValue('--txt').trim()   || '#E8EDF5',
      dim:   CS.getPropertyValue('--dim').trim()   || '#7A8BA0',
      dim2:  CS.getPropertyValue('--dim2').trim()  || '#2D3748',
      btc:   CS.getPropertyValue('--btc').trim()   || '#F7931A',
      grn:   CS.getPropertyValue('--grn').trim()   || '#5A9E72',
      red:   CS.getPropertyValue('--red').trim()   || '#C26060',
      mono:  CS.getPropertyValue('--mono').trim()  || "'IBM Plex Mono', monospace",
    };

    const DAY = 86400000;
    const now  = Date.now();
    const PERIODS = [
      { label: '7D',  days: 7   },
      { label: '30D', days: 30  },
      { label: '90D', days: 90  },
      { label: '1Y',  days: 365 },
    ];
    let activePeriod = 2; // default 90D

    // ── localStorage + incremental fetch ────────────────────────────────────
    // Strategy:
    //   1. Load cached data from localStorage (instant, no network)
    //   2. Find the last cached date
    //   3. Fetch only missing days from mempool.space (timestamp by timestamp)
    //      — if cache is empty: fetch full history once
    //      — if cache has today: no fetch at all
    //   4. Merge, dedupe, trim to 365 days, save back to localStorage
    //   5. render()

    const LS_KEY = 'btc_price_history_v1';
    let allData = [];
    let dataLoaded = false;

    // Expose update hook so fetchProdCost() can sync the live price
    window.terminalChartUpdate = function(realPrice) {
      if (!dataLoaded || !realPrice || realPrice <= 0 || !allData.length) return;
      allData[allData.length - 1].price = Math.round(realPrice);
      render();
    };

    // Show skeleton immediately
    wrap.innerHTML =
      '<div style="padding:10px 14px 6px;border-bottom:1px solid ' + C.line + ';display:flex;justify-content:space-between;align-items:center">' +
        '<div style="width:90px;height:10px;background:' + C.line2 + ';border-radius:2px;animation:skPulse 1.2s ease-in-out infinite"></div>' +
        '<div style="width:60px;height:10px;background:' + C.line2 + ';border-radius:2px;animation:skPulse 1.2s ease-in-out infinite"></div>' +
      '</div>' +
      '<div style="padding:12px 14px 14px">' +
        '<svg width="100%" height="80" style="display:block;opacity:.2">' +
          '<polyline points="0,60 40,50 80,55 120,35 160,40 200,25 240,30 280,20 320,28 360,15 400,22 440,18 480,10" fill="none" stroke="' + C.btc + '" stroke-width="1.5"/>' +
        '</svg>' +
      '</div>';
    if (!document.getElementById('skPulseKF')) {
      const st = document.createElement('style');
      st.id = 'skPulseKF';
      st.textContent = '@keyframes skPulse{0%,100%{opacity:.3}50%{opacity:.7}}';
      document.head.appendChild(st);
    }

    // ── Helpers ──────────────────────────────────────────────────────────────
    // Normalise raw mempool price array → {ts, price} deduplicated by day
    function normalisePrices(rawArr) {
      const byDay = {};
      rawArr.forEach(p => {
        if (!p.time || !p.USD || p.USD <= 0) return;
        const day = new Date(p.time * 1000).toISOString().slice(0, 10);
        // keep the last entry per day
        if (!byDay[day] || p.time > byDay[day].time) byDay[day] = p;
      });
      return Object.keys(byDay).sort().map(d => ({
        ts:    byDay[d].time * 1000,
        price: Math.round(byDay[d].USD),
        day:   d,
      }));
    }

    // Today's date string (UTC)
    function todayStr() {
      return new Date().toISOString().slice(0, 10);
    }

    // Save to localStorage (trim to last 365 days before saving)
    function saveCache(data) {
      const cutoff = Date.now() - 366 * 86400000;
      const trimmed = data.filter(d => d.ts >= cutoff);
      try {
        localStorage.setItem(LS_KEY, JSON.stringify(trimmed));
      } catch(e) {} // ignore quota errors
    }

    // Load from localStorage
    function loadCache() {
      try {
        const raw = localStorage.getItem(LS_KEY);
        if (!raw) return [];
        return JSON.parse(raw);
      } catch(e) { return []; }
    }

    // Merge two arrays by day, keep newest price per day, sort ascending
    function mergeData(existing, incoming) {
      const byDay = {};
      [...existing, ...incoming].forEach(p => {
        const day = p.day || new Date(p.ts).toISOString().slice(0, 10);
        if (!byDay[day] || p.ts > byDay[day].ts) byDay[day] = { ...p, day };
      });
      return Object.keys(byDay).sort().map(d => byDay[d]);
    }

    // ── Main load function ────────────────────────────────────────────────────
    async function loadPriceData() {
      const cached = loadCache();
      const today  = todayStr();
      const cutoffTs = Date.now() - 366 * 86400000;

      // ── Шаг 1: мгновенно рендерим кеш если он есть ──
      if (cached.length) {
        allData = cached.filter(d => d.ts >= cutoffTs);
        if (typeof dashBtcPrice === 'number' && dashBtcPrice > 0 && allData.length)
          allData[allData.length - 1].price = Math.round(dashBtcPrice);
        dataLoaded = true;
        render(); // моментальный рендер из кеша
      }

      // ── Шаг 2: определяем нужен ли сетевой запрос ──
      const lastCachedDay = cached.length
        ? (cached[cached.length - 1].day || new Date(cached[cached.length - 1].ts).toISOString().slice(0, 10))
        : null;

      if (lastCachedDay === today) return; // кеш свежий — ничего не делаем

      // ── Шаг 3: один запрос — всегда полная история, фильтруем нужное ──
      const fromTs = lastCachedDay
        ? Math.floor(new Date(lastCachedDay).getTime() / 1000)
        : Math.floor(Date.now() / 1000) - 365 * 86400;

      const res  = await fetch('https://mempool.space/api/v1/historical-price?currency=USD');
      const json = await res.json();
      const raw  = (json.prices || []).filter(p => p.time > fromTs);
      const fetched = normalisePrices(raw);

      // ── Шаг 4: merge + save + re-render ──
      const merged = mergeData(cached, fetched);
      saveCache(merged);
      allData = merged.filter(d => d.ts >= cutoffTs);
      if (typeof dashBtcPrice === 'number' && dashBtcPrice > 0 && allData.length)
        allData[allData.length - 1].price = Math.round(dashBtcPrice);
      dataLoaded = true;
      render(); // обновляем с актуальными данными
    }

    // Formatters
    const fmtP = v => '$' + Math.round(v).toLocaleString('en-US');
    const fmtD = (ts, compact) => {
      const d = new Date(ts);
      return compact
        ? d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
        : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    };

    // SVG namespace helper
    const svgEl = (tag, attrs = {}) => {
      const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
      Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
      return el;
    };
    const div = (attrs = {}, styles = {}) => {
      const el = document.createElement('div');
      Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
      Object.assign(el.style, styles);
      return el;
    };

    // State
    let hoverIdx = null;

    function render() {
      if (!allData.length) return; // wait for API data
      wrap.innerHTML = '';
      const data = allData.slice(-PERIODS[activePeriod].days);
      const prices = data.map(d => d.price);
      const minP = Math.min(...prices), maxP = Math.max(...prices);
      const last = data[data.length - 1].price, first = data[0].price;
      const chg = (last - first) / first * 100;
      const up = chg >= 0;
      const accent = up ? C.grn : C.red;
      const W = 700, PH = 220;
      const PAD = { t: 20, b: 0 };
      const range = maxP - minP || 1;

      // Map to SVG coords
      const pts = data.map((d, i) => ({
        ...d,
        x: (i / (data.length - 1)) * W,
        y: PAD.t + (1 - (d.price - minP) / range) * (PH - PAD.t - 10),
      }));

      // ── TOP BAR — вариант D: BTC/USD · цена ▲% в одну строку ──
      const topBar = div({}, {
        background: C.bg2, borderBottom: '1px solid ' + C.line,
        padding: '11px 14px',
        display: 'flex', alignItems: 'center', gap: '0',
      });

      // Тикер
      const ticker = document.createElement('span');
      ticker.textContent = 'BTC/USD';
      Object.assign(ticker.style, {
        fontFamily: C.mono, color: C.btc, fontSize: '11px', fontWeight: 'bold',
        letterSpacing: '0.12em', whiteSpace: 'nowrap',
      });

      // Разделитель
      const sep = document.createElement('span');
      sep.textContent = ' · ';
      Object.assign(sep.style, { color: C.dim, fontSize: '14px', margin: '0 6px' });

      // Цена
      const priceEl = document.createElement('span');
      priceEl.id = 'tc-price';
      priceEl.textContent = fmtP(last);
      Object.assign(priceEl.style, {
        color: C.txt, fontSize: '20px', fontWeight: 'bold', letterSpacing: '-0.02em',
      });

      // Разделитель 2
      const sep2 = document.createElement('span');
      sep2.textContent = ' · ';
      Object.assign(sep2.style, { color: C.dim, fontSize: '14px', margin: '0 4px' });

      // Изменение %
      const chgEl = document.createElement('span');
      chgEl.textContent = (up ? '▲ ' : '▼ ') + Math.abs(chg).toFixed(2) + '%';
      Object.assign(chgEl.style, {
        fontFamily: C.mono, color: accent, fontSize: '10px',
        background: up ? 'rgba(90,158,114,0.1)' : 'rgba(194,96,96,0.1)',
        padding: '2px 7px', borderRadius: '2px',
      });

      const dateEl = document.createElement('span');
      dateEl.id = 'tc-date';
      Object.assign(dateEl.style, { color: C.dim, fontSize: '9px', fontFamily: C.mono, marginLeft: '8px' });

      topBar.appendChild(ticker);
      topBar.appendChild(sep);
      topBar.appendChild(priceEl);
      topBar.appendChild(sep2);
      topBar.appendChild(chgEl);
      topBar.appendChild(dateEl);
      wrap.appendChild(topBar);

      // ── STATS ROW ──
      const statsRow = div({}, {
        background: C.bg, borderBottom: '1px solid ' + C.line,
        padding: '7px 16px', display: 'flex', gap: '24px', flexWrap: 'wrap',
      });
      [['HIGH', fmtP(maxP)], ['LOW', fmtP(minP)], ['RANGE', fmtP(maxP - minP)], ['OPEN', fmtP(first)]].forEach(([l, v]) => {
        const cell = div({}, {});
        const lbl = document.createElement('div');
        lbl.textContent = l;
        Object.assign(lbl.style, { color: C.dim, fontSize: '10px', letterSpacing: '0.12em', fontFamily: C.mono });
        const val = document.createElement('div');
        val.textContent = v;
        Object.assign(val.style, { color: C.txt, fontSize: '13px', marginTop: '2px', fontFamily: C.mono });
        cell.appendChild(lbl); cell.appendChild(val); statsRow.appendChild(cell);
      });

      // Периоды — справа в statsRow
      const periodsWrap = div({}, { display: 'flex', gap: '3px', marginLeft: 'auto', alignItems: 'center' });
      PERIODS.forEach((per, i) => {
        const btn = document.createElement('button');
        btn.textContent = per.label;
        Object.assign(btn.style, {
          background: activePeriod === i ? accent : 'transparent',
          color: activePeriod === i ? C.bg : C.dim,
          border: '1px solid ' + (activePeriod === i ? accent : C.line2),
          borderRadius: '2px', padding: '3px 9px', fontSize: '9px',
          fontFamily: C.mono, fontWeight: 'bold',
          letterSpacing: '0.06em', cursor: 'pointer',
        });
        btn.addEventListener('click', () => { activePeriod = i; hoverIdx = null; render(); });
        periodsWrap.appendChild(btn);
      });
      statsRow.appendChild(periodsWrap);
      wrap.appendChild(statsRow);

      // ── PRICE SVG ──
      const chartWrap = div({}, { position: 'relative' });
      const svg = svgEl('svg', { width: '100%', viewBox: `0 0 ${W} ${PH}`, preserveAspectRatio: 'none', style: 'display:block;cursor:crosshair' });

      // ── Mean price for zone coloring ──
      const meanPrice = Math.round(data.reduce((s, d) => s + d.price, 0) / data.length);
      const meanY = PAD.t + (1 - (meanPrice - minP) / (maxP - minP || 1)) * (PH - PAD.t - 10);

      // Defs — two gradients: green (above mean) and red (below mean)
      const defs = svgEl('defs');
      const gradG = svgEl('linearGradient', { id: 'tc-grn', x1: '0', y1: '0', x2: '0', y2: '1' });
      gradG.appendChild(svgEl('stop', { offset: '0%', 'stop-color': C.grn, 'stop-opacity': '0.45' }));
      gradG.appendChild(svgEl('stop', { offset: '100%', 'stop-color': C.grn, 'stop-opacity': '0.10' }));
      const gradR = svgEl('linearGradient', { id: 'tc-red', x1: '0', y1: '0', x2: '0', y2: '1' });
      gradR.appendChild(svgEl('stop', { offset: '0%', 'stop-color': C.red, 'stop-opacity': '0.10' }));
      gradR.appendChild(svgEl('stop', { offset: '100%', 'stop-color': C.red, 'stop-opacity': '0.45' }));
      defs.appendChild(gradG); defs.appendChild(gradR); svg.appendChild(defs);

      // Grid lines + Y labels
      [0.15, 0.38, 0.62, 0.85].forEach(t => {
        const gy = PAD.t + t * (PH - PAD.t - 10);
        svg.appendChild(svgEl('line', { x1: 0, y1: gy, x2: W, y2: gy, stroke: C.line, 'stroke-width': '1' }));
        const txt = svgEl('text', { x: W - 6, y: gy - 4, fill: C.dim, 'font-size': '10', 'text-anchor': 'end', 'font-family': C.mono });
        txt.textContent = fmtP(Math.round(maxP - t * (maxP - minP)));
        svg.appendChild(txt);
      });

      // Build zone-split area paths (clipped at mean line)
      function buildZoneArea(aboveFlag) {
        let d = ''; let open = false;
        const n = pts.length;
        for (let i = 0; i < n; i++) {
          const x = pts[i].x.toFixed(1), y = pts[i].y.toFixed(1);
          const isAbove = pts[i].y <= meanY;
          const match = aboveFlag ? isAbove : !isAbove;
          if (i === 0) {
            if (match) { d += `M${x},${meanY.toFixed(1)} L${x},${y}`; open = true; }
            continue;
          }
          const px = pts[i-1].x, py = pts[i-1].y;
          const wasAbove = py <= meanY;
          const wasMatch = aboveFlag ? wasAbove : !wasAbove;
          if (!wasMatch && match) {
            const t = (meanY - py) / (pts[i].y - py);
            const cx = (px + t * (pts[i].x - px)).toFixed(1);
            d += ` M${cx},${meanY.toFixed(1)} L${x},${y}`; open = true;
          } else if (wasMatch && !match) {
            const t = (meanY - py) / (pts[i].y - py);
            const cx = (px + t * (pts[i].x - px)).toFixed(1);
            d += ` L${cx},${meanY.toFixed(1)} Z`; open = false;
          } else if (match) {
            d += ` L${x},${y}`;
          }
        }
        if (open) d += ` L${pts[n-1].x.toFixed(1)},${meanY.toFixed(1)} Z`;
        return d;
      }

      const aboveArea = buildZoneArea(true);
      const belowArea = buildZoneArea(false);
      svg.appendChild(svgEl('path', { d: aboveArea, fill: 'url(#tc-grn)' }));
      svg.appendChild(svgEl('path', { d: belowArea, fill: 'url(#tc-red)' }));

      // Mean line + label
      svg.appendChild(svgEl('line', { x1: 0, y1: meanY, x2: W, y2: meanY, stroke: C.dim, 'stroke-width': '1', 'stroke-dasharray': '5,4', opacity: '0.6' }));
      const meanLbl = svgEl('text', { x: 6, y: meanY - 4, fill: C.dim, 'font-size': '8', 'font-family': C.mono, opacity: '0.8' });
      meanLbl.textContent = 'AVG ' + fmtP(meanPrice);
      svg.appendChild(meanLbl);

      // Price line — coloured by zone (green above mean, red below)
      (function drawColoredLine() {
        const n = pts.length;
        let seg = '', lastColor = null;
        for (let i = 0; i < n; i++) {
          const x = pts[i].x.toFixed(1), y = pts[i].y.toFixed(1);
          const col = pts[i].y <= meanY ? C.grn : C.red;
          if (i === 0) { seg = `M${x},${y}`; lastColor = col; continue; }
          const py = pts[i-1].y, px2 = pts[i-1].x;
          const crossedMean = (py <= meanY) !== (pts[i].y <= meanY);
          if (crossedMean) {
            // interpolate crossing
            const t = (meanY - py) / (pts[i].y - py);
            const cx = (px2 + t * (pts[i].x - px2)).toFixed(1);
            seg += ` L${cx},${meanY.toFixed(1)}`;
            svg.appendChild(svgEl('path', { d: seg, fill: 'none', stroke: lastColor, 'stroke-width': '1.8', 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
            seg = `M${cx},${meanY.toFixed(1)} L${x},${y}`;
            lastColor = col;
          } else {
            seg += ` L${x},${y}`;
          }
        }
        if (seg) svg.appendChild(svgEl('path', { d: seg, fill: 'none', stroke: lastColor, 'stroke-width': '1.8', 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
      })();

      // Crosshair & end dot (will update on hover)
      const crossV   = svgEl('line', { x1: 0, y1: 0, x2: 0, y2: PH, stroke: C.line2, 'stroke-width': '1', 'stroke-dasharray': '3,4', opacity: '0' });
      const crossH   = svgEl('line', { x1: 0, y1: 0, x2: W, y2: 0, stroke: C.line2, 'stroke-width': '1', 'stroke-dasharray': '3,4', opacity: '0' });
      const crossLblBg = svgEl('rect', { x: W-80, y: 0, width: 80, height: 18, fill: C.bg3, opacity: '0' });
      const crossLbl  = svgEl('text', { x: W-6, y: 0, fill: accent, 'font-size': '9', 'text-anchor': 'end', 'font-family': "'IBM Plex Mono', monospace", 'font-weight': 'bold', opacity: '0' });
      const zoneAccent = last > meanPrice ? C.grn : C.red;
      const dotMain   = svgEl('circle', { cx: pts[pts.length-1].x, cy: pts[pts.length-1].y, r: '3.5', fill: zoneAccent });
      const dotRing   = svgEl('circle', { cx: pts[pts.length-1].x, cy: pts[pts.length-1].y, r: '7', fill: 'none', stroke: zoneAccent, 'stroke-width': '1', opacity: '0.35' });
      const lastDash  = svgEl('line', { x1: 0, y1: pts[pts.length-1].y, x2: W, y2: pts[pts.length-1].y, stroke: zoneAccent, 'stroke-width': '0.6', 'stroke-dasharray': '4,5', opacity: '0.4' });
      svg.appendChild(lastDash); svg.appendChild(crossV); svg.appendChild(crossH); svg.appendChild(crossLblBg); svg.appendChild(crossLbl); svg.appendChild(dotMain); svg.appendChild(dotRing);

      // Tooltip div
      const tooltip = div({}, {
        position: 'absolute', background: C.bg2, border: '1px solid ' + C.line,
        borderLeft: `2px solid ${accent}`, borderRadius: '2px', padding: '7px 11px',
        pointerEvents: 'none', zIndex: '10', minWidth: '138px', display: 'none',
        fontFamily: "'IBM Plex Mono', monospace",
      });
      chartWrap.appendChild(svg); chartWrap.appendChild(tooltip); wrap.appendChild(chartWrap);

      // Mouse events
      svg.addEventListener('mousemove', e => {
        const rect = svg.getBoundingClientRect();
        const mx = (e.clientX - rect.left) / rect.width * W;
        let closest = 0, minDist = Infinity;
        pts.forEach((pt, i) => { const d = Math.abs(pt.x - mx); if (d < minDist) { minDist = d; closest = i; } });
        hoverIdx = closest;
        const hp = pts[closest], hd = data[closest];

        // Update crosshair
        crossV.setAttribute('x1', hp.x); crossV.setAttribute('x2', hp.x); crossV.setAttribute('opacity', '1');
        crossH.setAttribute('y1', hp.y); crossH.setAttribute('y2', hp.y); crossH.setAttribute('opacity', '1');
        crossLblBg.setAttribute('y', hp.y - 10); crossLblBg.setAttribute('opacity', '1');
        crossLbl.setAttribute('y', hp.y + 4); crossLbl.textContent = fmtP(hd.price); crossLbl.setAttribute('opacity', '1');
        dotMain.setAttribute('cx', hp.x); dotMain.setAttribute('cy', hp.y); dotMain.setAttribute('r', '4');
        dotRing.setAttribute('cx', hp.x); dotRing.setAttribute('cy', hp.y); dotRing.setAttribute('opacity', '0.4');
        lastDash.setAttribute('opacity', '0');

        // Update header price + date
        document.getElementById('tc-price').textContent = fmtP(hd.price);
        document.getElementById('tc-date').textContent = fmtD(hd.ts);

        // Tooltip
        const hChg = ((hd.price - first) / first * 100);
        tooltip.innerHTML = `
          <div style="color:" + C.dim + ";font-size:9px;letter-spacing:.1em;margin-bottom:5px">${fmtD(hd.ts).toUpperCase()}</div>
          <div style="color:" + C.txt + ";font-size:16px;font-weight:bold">${fmtP(hd.price)}</div>
          <div style="margin-top:6px;border-top:1px solid " + C.line + ";padding-top:6px">

            <div style="display:flex;justify-content:space-between;gap:14px;margin-top:3px">
              <span style="color:" + C.dim2 + ";font-size:9px;letter-spacing:.1em">CHG</span>
              <span style="color:${hChg>=0?'#00e676':'#ff4444'};font-size:10px">${(hChg>=0?'+':'') + hChg.toFixed(2)}%</span>
            </div>
          </div>`;
        const pct = hp.x / W * 100;
        tooltip.style.display = 'block';
        tooltip.style.left  = (pct > 70 ? (pct - 22) : pct + 2) + '%';
        tooltip.style.top   = Math.max(2, hp.y / PH * 100 - 16) + '%';
      });

      svg.addEventListener('mouseleave', () => {
        crossV.setAttribute('opacity','0'); crossH.setAttribute('opacity','0');
        crossLblBg.setAttribute('opacity','0'); crossLbl.setAttribute('opacity','0');
        lastDash.setAttribute('opacity','0.4');
        dotMain.setAttribute('cx', pts[pts.length-1].x); dotMain.setAttribute('cy', pts[pts.length-1].y); dotMain.setAttribute('r','3.5');
        dotRing.setAttribute('cx', pts[pts.length-1].x); dotRing.setAttribute('cy', pts[pts.length-1].y); dotRing.setAttribute('opacity','0.35');
        document.getElementById('tc-price').textContent = fmtP(last);
        document.getElementById('tc-date').textContent = '';
        tooltip.style.display = 'none';
        hoverIdx = null;
      });



      // ── X-AXIS ──
      const xAxis = div({}, { background: C.bg, borderTop: '1px solid ' + C.line, padding: '5px 0 8px', position: 'relative', height: '18px' });
      const xCount = data.length <= 7 ? data.length : 5;
      Array.from({ length: xCount }, (_, i) => {
        const idx = Math.round((i / (xCount - 1)) * (data.length - 1));
        const sp = document.createElement('span');
        sp.textContent = fmtD(data[idx].ts, true).toUpperCase();
        Object.assign(sp.style, { position: 'absolute', left: (pts[idx].x / W * 100) + '%', transform: 'translateX(-50%)', color: C.dim, fontSize: '10px', letterSpacing: '0.06em', whiteSpace: 'nowrap', fontFamily: C.mono });
        xAxis.appendChild(sp);
      });
      wrap.appendChild(xAxis);

      // ── STATUS BAR ──
      const statusBar = div({}, {
        background: C.bg2, borderTop: '1px solid ' + C.line,
        padding: '5px 16px', display: 'flex', justifyContent: 'space-between',
        color: C.dim, fontSize: '10px', letterSpacing: '0.1em',
      });
      const sl = document.createElement('span'); sl.textContent = 'BTC · BITCOIN NETWORK ANALYTICS';
      const sr = document.createElement('span'); sr.textContent = '● LIVE';
      Object.assign(sr.style, { color: accent, opacity: '0.55' });
      statusBar.appendChild(sl); statusBar.appendChild(sr);
      wrap.appendChild(statusBar);
    }

    loadPriceData().catch(() => {
      const cached = loadCache();
      if (cached.length) {
        allData = cached.filter(d => d.ts >= Date.now() - 366 * 86400000);
        dataLoaded = true;
        render();
      } else {
        wrap.innerHTML = '<div style="padding:20px 16px;color:' + C.red + ';font-family:' + C.mono + ';font-size:10px">⚠ Нет данных. Нет соединения с mempool.space</div>';
      }
    });
  })();
} // end initPriceChart

async function loadSignals() {
  try {
    const [sigResp, entResp, cacheResp, ontResp, reResp, thResp, bfResp, ttResp, teResp, taResp, bipResp] = await Promise.all([
      fetch('signals.json?v=' + Date.now()),
      fetch('ENTITIES.json?v=' + Date.now()),
      fetch('data/synthesis_cache.json?v=' + Date.now()),
      fetch('ontology.json?v=' + Date.now()),
      fetch('REVENUE_ENGINES.json?v=' + Date.now()),
      fetch('TREASURY_HOLDERS.json?v=' + Date.now()),
      fetch('BITCOIN_FUNCTIONS.json?v=' + Date.now()),
      fetch('THEORY_TOPICS.json?v=' + Date.now()),
      fetch('THEORY_ESSAYS.json?v=' + Date.now()),
      fetch('data/top_addresses.json?v=' + Date.now()),
      fetch('data/bip110_signaling.json?v=' + Date.now())
    ]);
    const data = await sigResp.json();
    const entData = await entResp.json();
    // Путь 3: загружаем Python-синтез, DEGRADE GRACEFULLY если недоступен
    try { SYNTHESIS_CACHE = await cacheResp.json(); } catch(e) { SYNTHESIS_CACHE = {}; }
    // M3 ARR v3: единый источник freshness-порогов. Если ontology.json
    // недоступен или повреждён — остаются дефолты, заданные при объявлении
    // FRESHNESS_FRESH_DAYS/FRESHNESS_RECENT_DAYS выше (graceful degradation,
    // не падаем и не блокируем рендер дашборда).
    try {
      const ont = await ontResp.json();
      const fw = ont && ont.freshness_windows;
      if (fw && Number.isFinite(fw.fresh_days)) FRESHNESS_FRESH_DAYS = fw.fresh_days;
      if (fw && Number.isFinite(fw.recent_days)) FRESHNESS_RECENT_DAYS = fw.recent_days;
    } catch(e) {
      console.warn('ontology.json load error, using default freshness thresholds:', e);
    }
    ENTITIES = entData.entities || [];
    try {
      const reData = await reResp.json();
      REVENUE_ENGINES = reData.engines || [];
    } catch(e) {
      console.warn('REVENUE_ENGINES.json load error, panel stays empty:', e);
      REVENUE_ENGINES = [];
    }
    try {
      const thData = await thResp.json();
      TREASURY_HOLDERS = thData.holders || [];
      TREASURY_META = thData.meta || {};
    } catch(e) {
      console.warn('TREASURY_HOLDERS.json load error, panel stays empty:', e);
      TREASURY_HOLDERS = [];
      TREASURY_META = {};
    }
    try {
      const bfData = await bfResp.json();
      BITCOIN_FUNCTIONS = bfData.functions || [];
    } catch(e) {
      console.warn('BITCOIN_FUNCTIONS.json load error, panel stays empty:', e);
      BITCOIN_FUNCTIONS = [];
    }
    try {
      const ttData = await ttResp.json();
      THEORY_TOPICS = ttData.topics || [];
    } catch(e) {
      console.warn('THEORY_TOPICS.json load error, panels stay empty:', e);
      THEORY_TOPICS = [];
    }
    try {
      const teData = await teResp.json();
      THEORY_ESSAYS = teData.items || [];
    } catch(e) {
      console.warn('THEORY_ESSAYS.json load error, panels stay empty:', e);
      THEORY_ESSAYS = [];
    }
    try {
      const taData = await taResp.json();
      TOP_ADDRESSES = taData.entries || [];
      TOP_ADDRESSES_META = { updated_at: taData.updated_at, source: taData.source, caveat: taData.caveat };
    } catch(e) {
      console.warn('data/top_addresses.json load error, panel stays empty:', e);
      TOP_ADDRESSES = [];
      TOP_ADDRESSES_META = {};
    }
    try {
      const bipData = await bipResp.json();
      BIP110_SIGNALING = bipData.current || {};
    } catch(e) {
      console.warn('data/bip110_signaling.json load error, panel stays empty:', e);
      BIP110_SIGNALING = {};
    }
    // Поддержка нового формата {meta, signals} и старого массива
    if (Array.isArray(data)) {
      SIGNALS = data;
    } else {
      SIGNALS = data.signals || [];
      if (data.meta) {
        window.SIGNALS_META = data.meta;
        // Обновить константу резерва если fetchMstrData уже запущен
        if (typeof fetchMstrData === 'function') fetchMstrData();
      }
    }
    fetchFacts(); // машиночитаемые факты из сигналов — независимо от meta
    fetchSiteMap(); // прогрев карты сайта — не ждём первого открытия оверлея
    renderDashboard();
    renderDifficultySignalBridge(); // мост к последнему mining-сигналу в панели "Сложность сети"
    setTimeout(renderDashStatus, 600);
    // Перерисовать данные ТЕКУЩЕЙ вкладки после завершения загрузки —
    // не только 'market' (была точечная заплатка только для него), а
    // любую. Раньше это было условие 'if marketTab.active', которое не
    // спасало другие вкладки от той же гонки: restoreLastActiveTab()
    // вызывает showTab() СИНХРОННО при загрузке страницы, до того как
    // loadSignals() успевает завершиться — если сохранённая вкладка
    // (например ХОЛДЕРЫ) зависит от SIGNALS/TREASURY_HOLDERS/
    // REVENUE_ENGINES, её панели рендерились с пустыми массивами и
    // никогда не перерисовывались повторно. currentTabId отслеживает
    // реально активную вкладку на момент завершения загрузки.
    if (currentTabId) triggerTabData(currentTabId);
  } catch(e) {
    console.error('signals.json load error:', e);
  }
}


const DIR_META = {
  neg: { icon: '🔴', label: 'НЕГАТИВ' },
  pos: { icon: '🟢', label: 'ПОЗИТИВ' },
  neu: { icon: '<span style="color:var(--slate)">◉</span>', label: 'НЕЙТРАЛЬНО' }
};

let sigFilter = 'all';
let pendingScrollSignal = null;
let sigActorFilter = 'all';
let sigMode = 'date'; // 'date' | 'theme'

const THEME_META = {
  supply:              { label: '⬛ ПРЕДЛОЖЕНИЕ',       order: 0 },
  institutionalization:{ label: '🏦 ИНСТИТУЦИОНАЛЫ',   order: 1 },
  ownership:           { label: '🏦 ИНСТИТУЦИОНАЛЫ',   order: 1 },
  infrastructure:      { label: '🔗 ИНФРАСТРУКТУРА',   order: 2 },
  layer2:              { label: '🔗 LAYER 2',           order: 3 },
  onchain:             { label: '📊 ON-CHAIN',          order: 4 },
  macro:               { label: '📉 МАКРО',             order: 5 },
  narrative:           { label: '📰 НАРРАТИВ',          order: 6 },
};

const ACTOR_META = {
  etf:       { label: '🏦 ETF' },
  corporate: { label: '🏢 КОРПОРАЦИИ' },
  government:{ label: '🏛️ ПРАВИТЕЛЬСТВА' },
  defi:      { label: '🔗 DEFI' },
  retail:    { label: '👤 РОЗНИЦА' },
  miner:     { label: '⛏️ МАЙНЕРЫ' }
};

const FLOW_META = {
  inflow:  { icon: '📥', label: 'ПРИТОК' },
  outflow: { icon: '📤', label: 'ОТТОК' },
  neutral: { icon: '➖', label: '' }
};

function renderSignals() {
  const sumWrap = document.getElementById('sig-summary');
  const filWrap = document.getElementById('sig-filters');
  const feed = document.getElementById('sig-feed');
  if (!feed) return;

  // сводка по направлению
  const counts = { neg: 0, pos: 0, neu: 0 };
  SIGNALS.forEach(s => counts[s.dir]++);
  const activeSum = ['pos','neg','neu'].includes(sigFilter) ? sigFilter : '';
  sumWrap.innerHTML =
    '<div class="sig-summary">'
    + '<div class="sig-sum-cell neg' + (activeSum==='neg'?' active':'') + '" onclick="setSigFilter(\'neg\')""><div class="sig-sum-n">' + counts.neg + '</div><div class="sig-sum-l">🔴 НЕГАТИВ</div></div>'
    + '<div class="sig-sum-cell pos' + (activeSum==='pos'?' active':'') + '" onclick="setSigFilter(\'pos\')""><div class="sig-sum-n">' + counts.pos + '</div><div class="sig-sum-l">🟢 ПОЗИТИВ</div></div>'
    + '<div class="sig-sum-cell neu' + (activeSum==='neu'?' active':'') + '" onclick="setSigFilter(\'neu\')""><div class="sig-sum-n">' + counts.neu + '</div><div class="sig-sum-l">⚪ НЕЙТРАЛ</div></div>'
    + '</div>';

  // переключатель режима
  let fhtml =
    '<div style="display:flex;gap:8px;margin-bottom:10px">'
    + '<button class="sig-fbtn' + (sigMode==='date'?' active':'') + '" onclick="setSigMode(\'date\')">📅 ПО ДАТЕ</button>'
    + '<button class="sig-fbtn' + (sigMode==='theme'?' active':'') + '" onclick="setSigMode(\'theme\')">🗂 ПО ТЕМЕ</button>'
    + '</div>';

  // фильтры по кластеру (DIGEST_CLUSTER_LABELS теперь на уровне модуля —
  // см. рядом с CLUSTER_LABELS_AI выше по файлу; вынесено 2026-07-28,
  // понадобилось из localAnalyzeSignal() для короткого бейджа "Найдено")
  const cats = {};
  const catCounts = {};
  const catDir = {};
  SIGNALS.forEach(s => {
    const cl = s.cluster || s.theme || s.cat;
    cats[cl] = DIGEST_CLUSTER_LABELS[cl] || sanitize(cl).toUpperCase();
    catCounts[cl] = (catCounts[cl] || 0) + 1;
    if (!catDir[cl]) catDir[cl] = { pos: 0, neg: 0, neu: 0 };
    catDir[cl][s.dir] = (catDir[cl][s.dir] || 0) + 1;
  });

  function makeBar(dir, total) {
    if (!dir || !total) return '';
    return '<span class="sig-fbtn-bar">'
      + '<span class="sig-fbtn-bar-pos" style="flex:' + (dir.pos||0) + '"></span>'
      + '<span class="sig-fbtn-bar-neg" style="flex:' + (dir.neg||0) + '"></span>'
      + '<span class="sig-fbtn-bar-neu" style="flex:' + (dir.neu||0.1) + '"></span>'
      + '</span>';
  }

  const allDir = { pos: 0, neg: 0, neu: 0 };
  SIGNALS.forEach(s => { allDir[s.dir] = (allDir[s.dir]||0) + 1; });

  fhtml += '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px">'
    + '<button class="sig-fbtn' + (sigFilter==='all'?' active':'') + '" onclick="setSigFilter(\'all\')">ВСЕ'
    + '<span class="sig-fbtn-count">' + SIGNALS.length + '</span>'
    + '</button>';

  Object.keys(cats).forEach(c => {
    const n = catCounts[c] || 0;
    fhtml += '<button class="sig-fbtn' + (sigFilter===c?' active':'') + '" onclick="setSigFilter(\'' + c + '\')">'
      + cats[c]
      + '<span class="sig-fbtn-count">' + n + '</span>'
      + '</button>';
  });
  fhtml += '</div>';

  // фильтры по actor — только те акторы что есть в данных
  const actors = {};
  SIGNALS.forEach(s => { if (s.actor) actors[s.actor] = true; });
  fhtml += '<div style="display:flex;flex-wrap:wrap;gap:8px;padding-top:8px;border-top:1px solid #1A1F2A">'
    + '<button class="sig-fbtn' + (sigActorFilter==='all'?' active':'') + '" onclick="setSigActorFilter(\'all\')" style="font-size:10px">ВСЕ АКТОРЫ</button>';
  Object.keys(actors).forEach(a => {
    const meta = ACTOR_META[a] || { label: sanitize(a).toUpperCase() };
    fhtml += '<button class="sig-fbtn' + (sigActorFilter===a?' active':'') + '" onclick="setSigActorFilter(\'' + sanitize(a) + '\')" style="font-size:10px">' + meta.label + '</button>';
  });
  fhtml += '</div>';

  filWrap.innerHTML = fhtml;

  // фильтрация — категория/dir + actor
  const dirKeys = ['pos', 'neg', 'neu'];
  const items = SIGNALS
    .filter(s => sigFilter === 'all' || (dirKeys.includes(sigFilter) ? s.dir === sigFilter : (s.cluster || s.theme || s.cat) === sigFilter))
    .filter(s => sigActorFilter === 'all' || s.actor === sigActorFilter)
    .slice().sort((a, b) => b.date.localeCompare(a.date));

  function cardHTML(s) {
    const d = DIR_META[s.dir];
    const chips = s.data.map(x => '<span class="sig-chip">' + sanitize(x) + '</span>').join('');
    const horizonLabel = { short: 'SHORT', mid: 'MID', long: 'LONG' }[s.horizon] || '';
    const flowMeta = s.flow && s.flow !== 'neutral' ? FLOW_META[s.flow] : null;
    const actorMeta = s.actor ? ACTOR_META[s.actor] : null;
    const roleColor = {trigger:'var(--btc)', complication:'var(--amber)', resolution:'var(--grn)', background:'var(--slate)'}[s.narrative_role] || 'var(--dim)';
    const roleDot = s.narrative_role ? '<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:' + roleColor + ';margin-right:2px;vertical-align:middle"></span>' : '';
    const safeTheoryRef = sanitize(s.theory_ref || '');
    return '<div class="sig-card ' + s.dir + '" id="sig-' + sanitize(s.id) + '">'
      + '<div class="sig-top"><span class="sig-cat">' + (DIGEST_CLUSTER_LABELS[s.cluster || s.theme] || sanitize(s.catLabel)) + '</span>' + roleDot + '<span>' + sanitize(s.date) + '</span><span class="sig-dir">' + d.icon + ' ' + d.label + '</span></div>'
      + '<div class="sig-signal">' + highlightEntities(s.signal) + '</div>'
      + '<div class="sig-data">' + chips
      + (horizonLabel ? '<span class="sig-chip" style="'
        + (s.horizon === 'short' ? 'color:var(--red);border-color:rgba(194,96,96,0.3)' :
           s.horizon === 'mid'   ? 'color:var(--amber);border-color:rgba(212,160,23,0.35)' :
           s.horizon === 'long'  ? 'color:var(--slate);border-color:rgba(74,93,117,0.4)' : 'opacity:.5')
        + '">⏱ ' + horizonLabel + '</span>' : '')
      + (actorMeta ? '<span class="sig-chip" style="opacity:.5">' + actorMeta.label + '</span>' : '')
      + (flowMeta ? '<span class="sig-chip" style="opacity:.5">' + flowMeta.icon + ' ' + flowMeta.label + '</span>' : '')
      + '</div>'
      + '<div class="sig-body">'
      + '<p><span class="lbl">КОНТЕКСТ.</span> ' + highlightEntities(s.context) + '</p>'
      + '<p><span class="lbl">ОГОВОРКИ.</span> ' + highlightEntities(s.caveat) + '</p>'
      + '</div>'
      + '<div class="sig-src">ИСТОЧНИК: ' + sanitize(s.source) + '</div>'
      + (s.theory_ref ? '<div style="padding:6px 14px 10px;border-top:1px solid var(--line)"><button onclick="showTab(\'theory\',null);setTimeout(()=>{const el=document.getElementById(\'' + safeTheoryRef + '\');if(el)el.scrollIntoView({behavior:\'smooth\'})},120)" style="background:transparent;border:1px solid rgba(247,147,26,0.3);border-radius:3px;color:var(--btc);padding:4px 10px;font-size:10px;cursor:pointer;font-family:var(--mono);letter-spacing:0.08em">↗ ТЕОРИЯ · ' + (s.theory_ref === 'theory-network' ? 'СЕМЬ СЕТЕВЫХ ЭФФЕКТОВ' : safeTheoryRef.replace('theory-','').toUpperCase()) + '</button></div>' : '')
      + '</div>';
  }

  if (sigMode === 'date') {
    feed.innerHTML = items.length
      ? items.map(cardHTML).join('')
      : '<div style="padding:24px;text-align:center;color:#4A5568;font-family:\'IBM Plex Mono\',monospace;font-size:12px">НЕТ СИГНАЛОВ ПО ВЫБРАННЫМ ФИЛЬТРАМ</div>';
  } else {
    const groups = {};
    items.forEach(s => {
      const t = s.theme || 'narrative';
      if (!groups[t]) groups[t] = [];
      groups[t].push(s);
    });
    const sortedThemes = Object.keys(groups).sort((a,b) =>
      (THEME_META[a]?.order ?? 99) - (THEME_META[b]?.order ?? 99)
    );
    feed.innerHTML = sortedThemes.length
      ? sortedThemes.map(t => {
          const meta = THEME_META[t] || { label: t.toUpperCase() };
          return '<div style="margin-bottom:8px;padding:6px 0;border-bottom:1px solid #1A1F2A">'
            + '<span style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:#F7931A;letter-spacing:.08em">'
            + meta.label + ' · ' + groups[t].length + ' сигн.</span></div>'
            + groups[t].map(cardHTML).join('');
        }).join('')
      : '<div style="padding:24px;text-align:center;color:#4A5568;font-family:\'IBM Plex Mono\',monospace;font-size:12px">НЕТ СИГНАЛОВ ПО ВЫБРАННЫМ ФИЛЬТРАМ</div>';
  }

  if (pendingScrollSignal) {
    const _target = pendingScrollSignal;
    pendingScrollSignal = null;
    requestAnimationFrame(() => {
      const el = document.getElementById('sig-' + _target);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }
}

function setSigMode(mode) {
  sigMode = mode;
  renderSignals();
}

function setSigActorFilter(actor) {
  sigActorFilter = actor;
  renderSignals();
}

// ── PRODUCTION COST & DASHBOARD ──
// Параметры флота (Cambridge 2026)
const FLEET_EFF   = 22;      // J/TH — средняя эффективность флота
const ELEC_PRICE  = 0.065;   // $/kWh
const OVERHEAD    = 0.15;    // 15% накладных расходов
const BLOCK_REW   = 3.125;   // BTC/блок после халвинга 2024
const BLOCKS_DAY  = 144;     // блоков в сутки

let dashBtcPrice = null;
let dashProdCost = null;

async function fetchProdCost() {
  try {
    // 1. Хешрейт и цена BTC из mempool.space
    const [statsRes, priceRes] = await Promise.all([
      fetch('https://mempool.space/api/v1/mining/hashrate/3d'),
      fetch('https://mempool.space/api/v1/prices')
    ]);
    const stats = await statsRes.json();
    const prices = await priceRes.json();

    // Текущий хешрейт в H/s (последнее значение)
    const hrEntry = stats.hashrates[stats.hashrates.length - 1];
    const hashrateHS = hrEntry ? hrEntry.avgHashrate : null;

    // Цена BTC в USD
    dashBtcPrice = prices.USD || null;

    if (hashrateHS && dashBtcPrice) {
      // Формула Production Cost:
      // Cost = (HR [H/s] * Eff [J/TH] * 1e-12 * ElecPrice [$/Wh / 1000] * 3600 * 24 * (1+OH))
      //        / (144 blocks/day * 3.125 BTC/block)
      const wattsTotal   = hashrateHS * FLEET_EFF * 1e-12 * 1e12; // Watts = HR[EH/s]*1e18 * Eff[J/TH]*1e-12 → упрощаем
      // HR в TH/s = hashrateHS / 1e12
      const hrTHs        = hashrateHS / 1e12;
      const powerWatts   = hrTHs * FLEET_EFF;              // Total Watts = TH/s * J/TH = W
      const powerKWh_day = powerWatts * 24 / 1000;         // kWh/day
      const elecCost_day = powerKWh_day * ELEC_PRICE;       // $/day
      const totalCost    = elecCost_day * (1 + OVERHEAD);   // с накладными
      const btcPerDay    = BLOCKS_DAY * BLOCK_REW;          // BTC/day
      dashProdCost       = totalCost / btcPerDay;            // $/BTC
    }
  } catch(e) {
    console.warn('ProdCost fetch error:', e);
  }
  renderDashboard();
  // Обновить RP-соотношение при новой BTC-цене
  if (typeof window._lastRP === 'number') updateRealizedPriceUI(window._lastRP);
}

function calcCyclePhase(price, prodCost) {
  if (!price || !prodCost) return { phase: 'ЗАГРУЗКА...', sub: 'Получаем данные...', cls: '', seg: 0 };
  const ratio = price / prodCost;
  if (ratio < 1.0)  return { phase: 'ДНО',        sub: 'Цена ниже себестоимости. Экстремальная зона — исторически редкий момент.', cls: 'danger', seg: 0 };
  if (ratio < 1.15) return { phase: 'НАКОПЛЕНИЕ', sub: 'Цена у себестоимости добычи. Исторически — зона долгосрочных покупок.', cls: '',       seg: 1 };
  if (ratio < 2.0)  return { phase: 'РОСТ',        sub: 'Цена уверенно выше себестоимости. Майнеры в плюсе, сеть расширяется.', cls: 'warn',   seg: 2 };
  return               { phase: 'ЭЙФОРИЯ',     sub: 'Цена более чем вдвое выше себестоимости. Исторически — зона осторожности.', cls: 'danger', seg: 3 };
}

function renderDashboard() {
  // ── Блок 1: цикловой индикатор ──
  const cycleBlock = document.querySelector('.dash-cycle');
  const phaseEl    = document.getElementById('dash-phase');
  const subEl      = document.getElementById('dash-phase-sub');
  const trackSegs  = document.querySelectorAll('.dct-seg');
  const labelsEl   = document.querySelectorAll('.dash-cycle-labels span');

  if (phaseEl) {
    const { phase, sub, cls, seg } = calcCyclePhase(dashBtcPrice, dashProdCost);
    phaseEl.textContent = phase;
    const ratioEl = document.getElementById('dash-ratio');
    if (ratioEl && dashBtcPrice && dashProdCost) {
      const ratio = (dashBtcPrice / dashProdCost).toFixed(2);
      ratioEl.textContent = '×' + ratio;
      const noteEl = document.getElementById('dash-ratio-note');
      if (noteEl) noteEl.textContent = '×' + ratio;
    }
    if (subEl) subEl.textContent = sub;
    if (cycleBlock) {
      cycleBlock.classList.remove('warn', 'danger');
      if (cls) cycleBlock.classList.add(cls);
    }
    // Трек прогресса
    trackSegs.forEach((s, i) => {
      s.classList.remove('done', 'current');
      if (i < seg) s.classList.add('done');
      if (i === seg) s.classList.add('current');
    });
    // Метки фаз
    const phaseNames = ['ДНО', 'НАКОПЛЕНИЕ', 'РОСТ', 'ЭЙФОРИЯ'];
    labelsEl.forEach((el, i) => {
      el.classList.remove('dct-active');
      el.textContent = (i === seg ? '▲ ' : '') + phaseNames[i];
      if (i === seg) el.classList.add('dct-active');
    });
  }

  // ── Блок 2: метрики ──
  const priceEl = document.getElementById('dash-price');
  const costEl  = document.getElementById('dash-cost');
  const gapEl   = document.getElementById('dash-gap');
  const gapAux  = document.getElementById('dash-gap-aux');
  const priceInline = document.getElementById('dash-price-inline');
  const costInline  = document.getElementById('dash-cost-inline');

  const fmtK = v => '$' + (v >= 1000 ? (v/1000).toFixed(1)+'K' : v.toFixed(0));

  if (priceEl && dashBtcPrice) priceEl.textContent = fmtK(dashBtcPrice);
  if (costEl  && dashProdCost) costEl.textContent  = fmtK(dashProdCost);
  if (priceInline && dashBtcPrice) priceInline.textContent = fmtK(dashBtcPrice);
  if (costInline  && dashProdCost) costInline.textContent  = fmtK(dashProdCost);

  if (dashBtcPrice && dashProdCost) {
    const gap = ((dashBtcPrice - dashProdCost) / dashProdCost * 100);
    const gapStr = (gap >= 0 ? '+' : '') + gap.toFixed(1) + '%';
    const gapCls = gap < 0 ? 'dash-m-neg' : gap < 15 ? 'dash-m-warn' : 'dash-m-up';
    if (gapEl) {
      gapEl.textContent = gapStr;
      gapEl.style.color = gap < 0 ? 'var(--red)' : gap < 15 ? 'var(--amber)' : 'var(--grn)';
    }
    if (gapAux) {
      gapAux.textContent = gapStr;
      gapAux.className = 'dash-m-val ' + gapCls;
    }
  }

  // Обновляем Terminal price chart реальной ценой
  if (dashBtcPrice && typeof window.terminalChartUpdate === 'function') {
    window.terminalChartUpdate(dashBtcPrice);
  }

  if (!SIGNALS || !SIGNALS.length) return;

  // ── Блок 3: главные нарративы — scoring algorithm v2 ──
  if (SIGNALS && SIGNALS.length) {

  const WEIGHT_RANK = { onchain: 4, primary: 3, market: 2, media: 1 };
  const ROLE_RANK   = { trigger: 4, complication: 3, resolution: 2, background: 0 };
  const SCORE_MIN   = 10;
  const SCORE_HOT   = 20;
  const MAX_SHOWN   = 4;

  const CLUSTER_LABELS = {
    strategy_model_stress:    '🏦 STRATEGY: МОДЕЛЬ ПОД ДАВЛЕНИЕМ',
    etf_institutional_flow:   '📊 ETF: ИНСТИТУЦИОНАЛЬНЫЙ ПОТОК',
    btc_treasury_competition: '💰 КАЗНАЧЕЙСТВА: КОНКУРЕНЦИЯ',
    supply_scarcity:          '⬛ ПРЕДЛОЖЕНИЕ',
    leverage_deleveraging_cycle: '💥 ДЕЛЕВЕРИДЖ: ЦИКЛЫ НА ПЛЕЧЕ',
    bitcoin_governance_debate: '⚖️ УПРАВЛЕНИЕ: СПОР О КОНСЕНСУСЕ',
    wallet_security_incidents: '🔓 БЕЗОПАСНОСТЬ SELF-CUSTODY КОШЕЛЬКОВ',
    quantum_security:         '🔐 КВАНТОВАЯ УГРОЗА',
    mining_operations:        '⛏️ МАЙНИНГ: ОПЕРАЦИИ И БЕЗОПАСНОСТЬ',
    layer2_programmability:   '🔗 L2: ПРОГРАММИРУЕМОСТЬ BITCOIN',
    mining_ai_diversification: '🤖 МАЙНИНГ И AI: ГИБРИДНАЯ МОДЕЛЬ',
    lightning_payments:       '⚡ LIGHTNING: ПЛАТЕЖИ И РАСЧЁТЫ',
  };

  // Собираем кластеры
  const clusters = {};
  const today = new Date();
  SIGNALS.forEach(s => {
    const cl = s.cluster || s.theme || 'narrative';
    if (!clusters[cl]) clusters[cl] = { signals: [], pos: 0, neg: 0, neu: 0 };
    clusters[cl].signals.push(s);
    clusters[cl][s.dir] = (clusters[cl][s.dir] || 0) + 1;
  });

  // Скоринг каждого кластера
  function scoreCluster(signals) {
    let freshness = 0, weight = 0, tension = 0, roles = 0;
    signals.forEach(s => {
      // Freshness
      const days = s.date ? Math.floor((today - new Date(s.date)) / 86400000) : 999;
      freshness += days <= FRESHNESS_FRESH_DAYS ? 3 : days <= FRESHNESS_RECENT_DAYS ? 1 : 0;
      // Weight
      weight += WEIGHT_RANK[s.weight] || 1;
      // Tension
      if (s.links && s.links.contradicts && s.links.contradicts.length) tension += 5;
      if (s.tension) tension += 2;
      // Role
      roles += ROLE_RANK[s.narrative_role] || 0;
    });
    return { total: freshness + weight + tension + roles, freshness, weight, tension, roles };
  }

  // Отбор и сортировка
  const scored = Object.keys(clusters).map(key => ({
    key,
    cl: clusters[key],
    score: scoreCluster(clusters[key].signals)
  })).sort((a, b) => b.score.total - a.score.total);

  const active = scored.filter(x => x.score.total >= SCORE_MIN).slice(0, MAX_SHOWN);
  const shown  = active.length > 0 ? active : [{ ...scored[0], weak: true }];

  // Счётчик в шапке
  const totalEl = document.getElementById('dash-narratives-total');
  if (totalEl) totalEl.textContent = shown.length + ' НАРРАТИВ' + (shown.length === 1 ? '' : shown.length < 5 ? 'А' : 'ОВ');

  // Рендер
  const listEl = document.getElementById('dash-narratives-list');
  if (!listEl) return;
  listEl.innerHTML = '';

  // ── Алгоритмический синтез нарратива ───────────────────────────────────
  // Рендер одного нарратива
  // M4 ARR v3: synthesis_cache.json содержит generated_at для каждого
  // кластера (пишется scripts/synthesizer.py), но раньше нигде не читалось
  // на UI — пользователь не мог узнать, что видит устаревший кеш. Эта
  // функция превращает generated_at в человекочитаемую метку; если синтез
  // пришёл не из кеша, а из JS live-фоллбэка (synthesizeNarrativeAdvanced,
  // см. ADR-010) — generated_at отсутствует, и метка явно говорит "live",
  // а не молчит об источнике.
  function formatSynthesisFreshness(synthesis) {
    if (!synthesis || !synthesis.generated_at) {
      return { label: 'live-расчёт', stale: false, title: 'Кеш недоступен — посчитано прямо в браузере' };
    }
    const generated = new Date(synthesis.generated_at);
    if (isNaN(generated.getTime())) {
      return { label: 'live-расчёт', stale: false, title: 'Некорректная дата в кеше' };
    }
    const ageMs = Date.now() - generated.getTime();
    const ageMin = Math.floor(ageMs / 60000);
    const ageHr  = Math.floor(ageMin / 60);
    const ageDay = Math.floor(ageHr / 24);

    let label;
    if (ageMin < 1)        label = 'обновлено только что';
    else if (ageMin < 60)  label = 'обновлено ' + ageMin + ' мин назад';
    else if (ageHr < 24)   label = 'обновлено ' + ageHr + ' ч назад';
    else                   label = 'обновлено ' + ageDay + ' дн назад';

    // STALE_THRESHOLD (config/settings.py) = 30 дней — тот же порог, что и
    // freshness-скоринг сигналов (M3 ARR v3), переиспользован для
    // согласованности понятия "устарело" по всему дашборду.
    const stale = ageDay > FRESHNESS_RECENT_DAYS;
    return { label, stale, title: synthesis.generated_at };
  }

  // N06 ARR v3: phase раньше существовала только в данных (synthesis.phase),
  // визуально никак не отличалась на UI — пользователь не мог отличить
  // "разрешённое противоречие" от "активного конфликта" с первого взгляда.
  function formatPhaseLabel(phase) {
    switch (phase) {
      case 'resolution': return { label: '✓ РАЗРЕШЕНО',      color: 'var(--grn)', border: 'rgba(90,158,114,.4)' };
      case 'active':     return { label: 'АКТИВНЫЙ КОНФЛИКТ', color: 'var(--btc)', border: 'rgba(247,147,26,.4)' };
      case 'tension':    return { label: 'ПРОТИВОРЕЧИЕ',      color: 'var(--amber)', border: 'rgba(200,168,75,.4)' };
      case 'structural': return { label: 'СТРУКТУРНЫЙ ФОН',   color: 'var(--dim)', border: 'rgba(122,139,160,.35)' };
      default:           return { label: '',                  color: 'var(--dim)', border: 'rgba(122,139,160,.35)' };
    }
  }

  // N04 ARR v3: handle_uncertainty() (scripts/synthesizer.py) уже считает
  // contested-состояние и stale-tension, но раньше эти данные нигде не
  // отображались — confidence просто тихо занижался без объяснения
  // причины. Вынесено в чистую функцию для тестируемости (см.
  // tests/unit/test_uncertainty_indicator.py).
  function buildUncertaintyWarnings(uncertainty) {
    const u = uncertainty || {};
    const warnings = [];
    if (u.direction === 'contested') {
      warnings.push('⚠ ПРОТИВОРЕЧИВЫЕ СИГНАЛЫ — почти поровну pos/neg, оценка занижена');
    }
    if (u.tension_stale) {
      warnings.push(u.tension_stale_label || '⚠ Нарратив устарел');
    }
    return warnings;
  }

  // N07 ARR v3: is_minority_anchor / entity_count / anchor_entity_share
  // (Фаза B, scripts/synthesizer.py, 2026-07) считаются с момента слияния
  // PR #399, но нигде не отображались на UI — читатель не мог отличить
  // tension, за которым стоит большинство сущностей кластера, от tension,
  // где победивший сигнал представляет лишь периферийную долю (напр.
  // 2 сигнала из 21). Диагностика — не отбор: не меняет что показано как
  // tension, только помечает его репрезентативность. Присутствует только
  // когда синтез пришёл из Python-кеша (JS live-фоллбэк не считает
  // entity-diversity, тот же паттерн что uncertainty выше) — поэтому ?.
  // везде ниже, отсутствие поля не ошибка.
  function buildMinorityAnchorWarning(synthesis) {
    const s = synthesis || {};
    if (!s.is_minority_anchor) return null;
    const pct = Math.round((s.anchor_entity_share || 0) * 100);
    return '⚠ Якорь — периферийная сущность: ' + pct + '% сигналов кластера'
      + (s.entity_count ? ' (' + s.entity_count + ' сущностей всего)' : '');
  }

  // Разворот карточки нарратива: список сигналов signals_used/signals_ignored,
  // каждый id кликабелен — переход во вкладку Дайджест + скролл к карточке
  // сигнала (переиспользует существующий pendingScrollSignal-паттерн, см.
  // cardHTML() и блок экосистемы). Резолвит id → короткий текст signal из
  // глобального SIGNALS для читаемости (голый id бесполезен для читателя).
  function renderSignalRefList(ids, title) {
    if (!ids || !ids.length) return '';
    const rows = ids.map(function(id) {
      const sig = SIGNALS.find(function(s) { return s.id === id; });
      const label = sig ? sanitize(sig.signal).slice(0, 50) + (sig.signal.length > 50 ? '…' : '') : '(сигнал не найден)';
      return '<div onclick="pendingScrollSignal=\'' + id + '\';showTab(\'market\',null)" '
        + 'style="cursor:pointer;padding:3px 0;color:var(--dim);font-size:9px;line-height:1.4" '
        + 'onmouseover="this.style.color=\'var(--btc)\'" onmouseout="this.style.color=\'var(--dim)\'">'
        + '↗ <span style="font-family:var(--mono)">' + sanitize(id) + '</span> — ' + label
        + '</div>';
    }).join('');
    return '<div class="dash-breakdown-row" style="display:block;margin-top:6px;padding-top:6px;border-top:1px solid var(--line)">'
      + '<div style="color:var(--dim);font-size:9px;font-weight:600;letter-spacing:.05em;margin-bottom:3px">' + title + ' (' + ids.length + ')</div>'
      + rows
      + '</div>';
  }

  function renderNarrativeItem(key, cl, score, weak, idx, synthesis) {
    const n      = cl.signals.length;
    const dirCls = cl.neg > cl.pos ? 'neg' : cl.pos > cl.neg ? 'pos' : 'neu';
    const isHot  = score.total >= SCORE_HOT;
    const bdId   = 'nbd-' + idx;
    const label  = CLUSTER_LABELS[key] || sanitize(key).toUpperCase();
    const macroText = ensureSentencePunctuation(synthesis.narrative) || '—';
    const tension   = synthesis.tension ? ensureSentencePunctuation(synthesis.tension.charAt(0).toUpperCase() + synthesis.tension.slice(1)) : '';
    // synthesis доступен для takeaway и strength
    const freshness = formatSynthesisFreshness(synthesis);
    const phaseInfo = formatPhaseLabel(synthesis.phase);

    // N04 ARR v3: handle_uncertainty() (scripts/synthesizer.py) уже считает
    // contested-состояние и stale-tension, но раньше эти данные нигде не
    // отображались — confidence просто тихо занижался без объяснения
    // причины. uncertainty присутствует только когда синтез пришёл из
    // Python-кеша (JS live-фоллбэк не повторяет handle_uncertainty(), см.
    // ADR-010 "Дальнейшая работа") — поэтому ?. везде ниже, не считаем
    // отсутствие uncertainty ошибкой.
    const uncertainty = synthesis.uncertainty || {};
    const warnings = buildUncertaintyWarnings(uncertainty).map(sanitize);
    const minorityWarning = buildMinorityAnchorWarning(synthesis);
    const minorityWarningHtml = minorityWarning
      ? '<div class="dash-narrative-minority-anchor" title="Победивший tension определяется по числу contradicts-связей одного сигнала, не по доле сущностей в кластере — см. CLAUDE.md, раздел Нарративный синтез">'
        + sanitize(minorityWarning) + '</div>'
      : '';

    const item = document.createElement('div');
    item.className = 'dash-narrative-item ' + dirCls;
    item.dataset.clusterKey = key;
    if (idx > 0) item.style.borderTop = '1px solid var(--line)';

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
      + '<div class="dash-sum-counts" style="margin:5px 0">'
      +   '<span class="dsc-pos">🟢 ' + (cl.pos||0) + '</span>'
      +   '<span class="dsc-neg">🔴 ' + (cl.neg||0) + '</span>'
      +   '<span class="dsc-neu">⚪ ' + (cl.neu||0) + '</span>'
      + '</div>'
      + '<div style="display:flex;align-items:center;justify-content:space-between;margin-top:6px;padding-top:6px;border-top:1px solid var(--line)">'
      +   '<div class="dash-narrative-link" style="margin:0;padding:0;border:none" data-cl="' + key + '">СМОТРЕТЬ В ДАЙДЖЕСТЕ <span>→</span></div>'
      +   '<div class="dash-narrative-score' + (isHot ? ' hot' : '') + '" data-bd="' + bdId + '">'
      +     '<span class="dash-narrative-strength strength-' + sanitize(synthesis.strength||'moderate') + '">' + sanitize((synthesis.strength||'').toUpperCase()) + '</span>'
      +     (isHot ? '🔥 ' : '') + 'score: ' + score.total + ' ▾'
      +   '</div>'
      + '</div>'
      + '<div class="dash-breakdown" id="' + bdId + '">'
      +   '<div class="dash-breakdown-row"><span>freshness</span><span>+' + score.freshness + '</span></div>'
      +   '<div class="dash-breakdown-row"><span>weight</span><span>+' + score.weight + '</span></div>'
      +   '<div class="dash-breakdown-row"><span>tension</span><span>+' + score.tension + '</span></div>'
      +   '<div class="dash-breakdown-row"><span>roles</span><span>+' + score.roles + '</span></div>'
      +   '<div class="dash-breakdown-row dash-breakdown-total"><span>total</span><span>' + score.total + '</span></div>'
      +   (synthesis.rationale ? '<div class="dash-breakdown-row" style="display:block;margin-top:4px;padding-top:4px;border-top:1px solid var(--line);color:var(--dim);font-size:9px;line-height:1.5">' + sanitize(synthesis.rationale) + '</div>' : '')
      +   renderSignalRefList(synthesis.signals_used, 'ИСПОЛЬЗОВАНО')
      +   renderSignalRefList(synthesis.signals_ignored, 'НЕ УЧТЕНО')
      + '</div>';

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

  } // end if SIGNALS

    // ── Блок 4: сводка ──
  const counts = { pos: 0, neg: 0, neu: 0 };
  SIGNALS.forEach(s => counts[s.dir]++);
  const total = SIGNALS.length;
  document.getElementById('dash-sum-label').textContent = 'ОБЩИЙ ФОН · ' + total + ' СИГНАЛ' + (total === 1 ? '' : total < 5 ? 'А' : 'ОВ');
  document.getElementById('dash-sum-bar').innerHTML =
    '<div class="dsb-pos" style="flex:' + counts.pos + '"></div>' +
    '<div class="dsb-neg" style="flex:' + counts.neg + '"></div>' +
    '<div class="dsb-neu" style="flex:' + (counts.neu||0.1) + '"></div>';
  document.getElementById('dash-sum-counts').innerHTML =
    '<span class="dsc-pos">🟢 ' + counts.pos + ' позитив</span>' +
    '<span class="dsc-neg">🔴 ' + counts.neg + ' негатив</span>' +
    '<span class="dsc-neu">⚪ ' + counts.neu + ' нейтрал</span>';
  renderDashStatus();
}

function setSigFilter(c) {
  sigFilter = c;
  renderSignals();
}

function goToDigest(clusterKey) {
  sigFilter = clusterKey || 'all';
  showTab('market', null);
  window.scrollTo(0, 0);
}

// 2026-07-28 (по запросу пользователя): «Главные нарративы» на ОБЗОРЕ
// показывают только топ-4 кластера по score — при 11 реальных кластерах
// это осмысленное усечение для дайджеста, но не даёт увидеть остальные.
// Полная аналитика — отдельная секция в ANALYSIS → ВСЕ НАРРАТИВЫ (вкладка была
// пустой заглушкой, естественное место). Решения пользователя: (1)
// ступенчато — топ-N полной карточкой + остальные компактным списком,
// не всё в одном формате; (2) score — только порядок показа, не фильтр
// включения (в отличие от renderDashboard(), здесь нет ни SCORE_MIN,
// ни жёсткого MAX_SHOWN — показываются ВСЕ кластеры, что есть в SIGNALS,
// значит масштабируется автоматически при появлении новых кластеров).
//
// scoreClusterSignals()/computeAllClusterScores() — та же формула, что
// renderDashboard() использует внутри себя (freshness+weight+tension+
// roles) — сознательно НЕ рефакторили renderDashboard() под общий код:
// этот файл уже дважды ловил TDZ-баги от переупорядочивания существующей
// логики в этой сессии, риск регресса в уже отлаженной "Главных
// нарративах" не оправдан ради устранения дублирования формулы в ~15
// строк. Если формула скоринга когда-нибудь изменится — обновить оба
// места (здесь и внутри renderDashboard()).
function scoreClusterSignals(signals) {
  let freshness = 0, weight = 0, tension = 0, roles = 0;
  const today = new Date();
  signals.forEach(s => {
    const days = s.date ? Math.floor((today - new Date(s.date)) / 86400000) : 999;
    freshness += days <= FRESHNESS_FRESH_DAYS ? 3 : days <= FRESHNESS_RECENT_DAYS ? 1 : 0;
    weight += CLUSTER_WEIGHT_RANK[s.weight] || 1;
    if (s.links && s.links.contradicts && s.links.contradicts.length) tension += 5;
    if (s.tension) tension += 2;
    roles += CLUSTER_ROLE_RANK[s.narrative_role] || 0;
  });
  return { total: freshness + weight + tension + roles, freshness, weight, tension, roles };
}

function computeAllClusterScores() {
  const clusters = {};
  (SIGNALS || []).forEach(s => {
    const cl = s.cluster || s.theme || 'narrative';
    if (!clusters[cl]) clusters[cl] = { signals: [], pos: 0, neg: 0, neu: 0 };
    clusters[cl].signals.push(s);
    clusters[cl][s.dir] = (clusters[cl][s.dir] || 0) + 1;
  });
  return Object.keys(clusters)
    .map(key => ({ key, cl: clusters[key], score: scoreClusterSignals(clusters[key].signals) }))
    .sort((a, b) => b.score.total - a.score.total);
}

// 2026-07-28 (по запросу пользователя, Вариант 4 из
// docs/ANALYSIS-preset-question-grammar.md): попытка генерировать вопрос
// НА ЛЕТУ (случайное окно слов из реального текста тензии, см. историю
// в git — pickRandomWordWindow/JUNK_WORD_START) была отклонена и убрана
// целиком, не патчилась дальше. Причина — согласование падежей: слово в
// источнике стоит в падеже своей роли в ИСХОДНОМ предложении, не в том,
// что требуется после "Что с" (творительный) — список стоп-слов может
// убрать плохие КРАЯ окна, но не может проверить падеж КАЖДОГО слова
// внутри, а падеж — не только у первого/последнего слова. Пользователь
// показал реальные примеры несклада ("Что с баланса до 7700 BTC?"),
// подтвердившие, что это не редкий край, а системное ограничение
// подхода. Полный разбор — см. документ выше.
//
// Решение — простой случайный выбор из CLUSTER_PRESET_QUESTIONS (44
// вручную написанных и проверенных вопроса, 4 на кластер) — рандомность
// сохраняется на уровне ВЫБОРА, не на уровне ГЕНЕРАЦИИ текста.
function generateClusterPresetQuestion(key) {
  const pool = CLUSTER_PRESET_QUESTIONS[key];
  if (!pool || !pool.length) return null;
  return pool[Math.floor(Math.random() * pool.length)];
}

function renderClusterFullAnalytics() {
  const listEl = document.getElementById('archive-cluster-list');

  if (!listEl) return;
  if (!SIGNALS || !SIGNALS.length) {
    listEl.innerHTML = '<div style="padding:24px 14px;text-align:center;color:var(--dim);font-size:12px;font-family:var(--mono)">Сигналы ещё загружаются…</div>';
    return;
  }

  const scored = computeAllClusterScores();
  const FEATURED_COUNT = 3;
  const featured = scored.slice(0, FEATURED_COUNT);
  const rest = scored.slice(FEATURED_COUNT);

  const totalEl = document.getElementById('archive-cluster-total');
  if (totalEl) {
    const n = scored.length;
    totalEl.textContent = n + ' КЛАСТЕР' + (n === 1 ? '' : (n >= 2 && n <= 4) ? 'А' : 'ОВ');
  }

  listEl.innerHTML = '';

  featured.forEach(({ key, cl, score }) => {
    const cached = SYNTHESIS_CACHE[key];
    const synthesis = (cached && cached.tension) ? cached : synthesizeNarrativeAdvanced(key, cl);
    const label = CLUSTER_LABELS_AI[key] || sanitize(key).toUpperCase();
    const tension = synthesis.tension ? ensureSentencePunctuation(synthesis.tension.charAt(0).toUpperCase() + synthesis.tension.slice(1)) : '—';
    const macro = ensureSentencePunctuation(synthesis.narrative) || '—';

    const div = document.createElement('div');
    div.className = 'panel';
    div.style.marginBottom = '10px';
    div.innerHTML =
        '<div class="panel-head"><span class="panel-title">' + sanitize(label) + '</span>'
      +   '<span class="panel-tag">' + cl.signals.length + ' СИГН. · score ' + score.total + '</span></div>'
      + '<div style="padding:12px 14px">'
      +   '<p style="font-size:13px;color:var(--txt);line-height:1.6;margin-bottom:8px">' + highlightVs(highlightEntities(tension)) + '</p>'
      +   '<p style="font-size:12px;color:var(--dim);line-height:1.6">' + highlightEntities(macro) + '</p>'
      +   '<div style="margin-top:8px"><span class="dash-narrative-link" data-cl="' + key + '" style="cursor:pointer;color:var(--btc);font-size:11px;font-family:var(--mono)">СМОТРЕТЬ В ДАЙДЖЕСТЕ →</span></div>'
      + '</div>';
    div.querySelector('[data-cl]').addEventListener('click', function () { goToDigest(this.dataset.cl); });
    listEl.appendChild(div);
  });

  if (rest.length) {
    const wrap = document.createElement('div');
    wrap.className = 'panel';
    wrap.innerHTML = '<div class="panel-head"><span class="panel-title">Остальные кластеры</span><span class="panel-tag">' + rest.length + '</span></div>';
    const body = document.createElement('div');
    rest.forEach(({ key, cl }) => {
      const cached = SYNTHESIS_CACHE[key];
      const synthesis = (cached && cached.tension) ? cached : synthesizeNarrativeAdvanced(key, cl);
      const label = CLUSTER_LABELS_AI[key] || sanitize(key).toUpperCase();
      const tension = ensureSentencePunctuation(synthesis.tension) || '—';

      const row = document.createElement('div');
      row.style.cssText = 'padding:10px 14px;border-top:1px solid var(--line);cursor:pointer';
      row.innerHTML =
          '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">'
        +   '<span style="font-size:12px;color:var(--txt);font-weight:600">' + sanitize(label) + '</span>'
        +   '<span style="font-size:10px;color:var(--dim);font-family:var(--mono)">' + cl.signals.length + '</span>'
        + '</div>'
        + '<div style="font-size:11px;color:var(--dim);line-height:1.5;overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical">'
        +   highlightVs(sanitize(tension))
        + '</div>';
      row.addEventListener('click', function () { goToDigest(key); });
      body.appendChild(row);
    });
    wrap.appendChild(body);
    listEl.appendChild(wrap);
  }
}

// ── TABS ──

// ── Инициализация крошки ──
function updateCrumb(id) {
  const clusterKey = TAB_TO_CLUSTER[id];
  if (!clusterKey) return;
  const clusterEl = document.getElementById('crumb-cluster');
  const tabEl     = document.getElementById('crumb-tab');
  if (clusterEl) {
    clusterEl.textContent = CLUSTERS[clusterKey].label.toLowerCase();
    clusterEl.dataset.cluster = clusterKey;
  }
  if (tabEl) tabEl.textContent = id;
}


const CLUSTERS = {
  live:      { label: 'LIVE',     tabs: [['home','ОБЗОР'],['market','ДАЙДЖЕСТ'],['analytics','МЕТРИКИ'],['pools','ПУЛЫ']] },
  knowledge: { label: 'ECOSYSTEM', tabs: [['tech','ТЕХНОЛОГИИ'],['instruments','ИНСТРУМЕНТЫ'],['lightning','LIGHTNING']] },
  macro:     { label: 'FUNDAMENTAL', tabs: [['theory','ТЕОРИЯ'],['macrocontext','МАКРОКОНТЕКСТ'],['history','ЭМИССИЯ']] },
  analysis:  { label: 'ANALYSIS', tabs: [['signals','АНАЛИЗАТОР'],['holders','ХОЛДЕРЫ'],['base','ВСЕ НАРРАТИВЫ']] }
};
const TAB_TO_CLUSTER = {
  home:'live', analytics:'live', pools:'live', market:'live',
  tech:'knowledge', lightning:'knowledge', instruments:'knowledge',
  theory:'macro', history:'macro', macrocontext:'macro',
  signals:'analysis', holders:'analysis', base:'analysis'
};

let activeCluster = 'live';

// Крошка при загрузке — скрипт в конце body, DOM уже готов
updateCrumb('home');

// выбор кластера снизу: рендерит подвкладки и открывает первую вкладку
function selectCluster(key) {
  activeCluster = key;
  document.querySelectorAll('.cbar-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('cbar-' + key).classList.add('active');
  renderSubnav(key);
  renderCrumbDots(key);
  // открыть первую вкладку кластера
  showTab(CLUSTERS[key].tabs[0][0], null, true);
}

// точки-индикаторы кластера в хлебной крошке
function renderCrumbDots(activeKey) {
  const el = document.getElementById('crumb-dots');
  if (!el) return;
  el.innerHTML = Object.keys(CLUSTERS).map(k =>
    '<span class="crumb-dot' + (k === activeKey ? ' on' : '') + '"></span>'
  ).join('');
}
renderCrumbDots('live');

// ── Свайп по хлебной крошке — переключение между кластерами ──
(function() {
  const crumb = document.querySelector('.nav-crumb');
  if (!crumb) return;
  const SWIPE_THRESHOLD = 50;
  let startX = null, startY = null, swiped = false;

  crumb.addEventListener('pointerdown', function(e) {
    startX = e.clientX; startY = e.clientY; swiped = false;
  });
  crumb.addEventListener('pointermove', function(e) {
    if (startX === null || swiped) return;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    if (Math.abs(dx) > SWIPE_THRESHOLD && Math.abs(dx) > Math.abs(dy) * 1.5) {
      swiped = true;
      const keys = Object.keys(CLUSTERS);
      const idx = keys.indexOf(activeCluster);
      const nextIdx = dx < 0
        ? (idx + 1) % keys.length
        : (idx - 1 + keys.length) % keys.length;
      selectCluster(keys[nextIdx]);
    }
  });
  crumb.addEventListener('pointerup', function() { startX = null; startY = null; });
  crumb.addEventListener('pointercancel', function() { startX = null; startY = null; });
})();

// отрисовать подвкладки активного кластера, подсветить activeId
function renderSubnav(key, activeId) {
  const sub = document.getElementById('subnav');
  sub.innerHTML = CLUSTERS[key].tabs.map(([id, label]) =>
    '<button class="nav-btn' + (id === activeId ? ' active' : '') + '" onclick="showTab(\'' + id + '\', this)">' + label + '</button>'
  ).join('');
}

let currentTabId = null;

// Массив последних блоков (mempool.space) — питает «Последние блоки» на
// ОБЗОРЕ и getCurrentBlockHeight(). ОБЯЗАН быть объявлен ЗДЕСЬ, выше
// triggerTabData(): она читает LATEST_BLOCKS, а restoreLastActiveTab()
// вызывает её СИНХРОННО при загрузке страницы (через showTab), когда в
// localStorage сохранена вкладка 'home'/'pools'. При объявлении ниже по
// файлу это давало TDZ ReferenceError («Cannot access before
// initialization»), убивавший ВЕСЬ script-блок — сайт открывался без
// единого работающего скрипта («везде прочерки») у любого
// возвращающегося посетителя. Обнаружено 2026-07-18 через диагностическую
// плашку window.onerror; латентная гонка коммитов f07b9db (чтение в
// triggerTabData) и #290 (синхронный restoreLastActiveTab).
let LATEST_BLOCKS = [];

// Триггеры загрузки/рендера данных для конкретной вкладки — вынесено из
// showTab() в отдельную функцию, чтобы её можно было вызвать ПОВТОРНО
// после завершения loadSignals() (см. ниже, почему это нужно).
function triggerTabData(id) {
  if (id === 'home')      { fetchProdCost(); if (!LATEST_BLOCKS.length) fetchBlocks(); initPriceChart(); }
  if (id === 'analytics') { initCharts(); renderBip110Signaling(); }
  if (id === 'market')    renderSignals();
  if (id === 'pools') {
    const detail = document.getElementById('pool-detail');
    if (!detail || !detail.innerHTML.trim()) {
      renderPoolSummary();
      if (!LATEST_BLOCKS.length) fetchBlocks();
    }
  }
  if (id === 'holders')   { renderHolders(); renderTreasuryHolders(); renderTopAddresses(); }
  if (id === 'lightning') renderTheoryTopics();
  if (id === 'theory') { renderTheoryTopics(); renderTheoryEssays(); }
  if (id === 'macrocontext') { renderTheoryTopics(); renderRevenueEngines(); }
  if (id === 'tech') { renderEcosystem(); renderBitcoinFunctions(); }
  if (id === 'history')   { renderEmission(); fetchRemainingSupply(); renderHalvingBlock(); }
  if (id === 'signals')   renderPresetSignals();
  if (id === 'base')      renderClusterFullAnalytics();
}

function showTab(id, btn, keepCluster) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  currentTabId = id;

  // синхронизировать кластер, если перешли на вкладку другого кластера (напр. клик по пулу)
  const cluster = TAB_TO_CLUSTER[id];
  if (cluster && cluster !== activeCluster) {
    activeCluster = cluster;
    document.querySelectorAll('.cbar-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('cbar-' + cluster).classList.add('active');
  }
  // перерисовать подвкладки с подсветкой текущей
  renderSubnav(activeCluster, id);

  // крошки
  if (TAB_TO_CLUSTER[id]) {
    updateCrumb(id);
  }

  // 2026-08-01: try/catch — до этой правки исключение внутри triggerTabData()
  // (например, гонка restoreLastActiveTab() vs ещё не пришедшие async-данные,
  // см. комментарий там же) оставляло DOM и currentTabId РАССИНХРОНИЗИРОВАННЫМИ:
  // .active класс и currentTabId выше УЖЕ обновлены на id, но если catch в
  // restoreLastActiveTab() ловил исключение снаружи и откатывал currentTabId
  // на 'home' БЕЗ отката видимого DOM (чтобы не задвоить init Chart.js) —
  // вкладка оставалась визуально активной и пустой НАВСЕГДА: последующий
  // triggerTabData(currentTabId) целился в 'home', не в реально показанную
  // сломанную вкладку. Теперь currentTabId/DOM выше в этой функции остаются
  // консистентны с id независимо от того, упал ли рендер данных — именно
  // поэтому более поздний triggerTabData(currentTabId) (после loadSignals())
  // корректно доперерисует ИМЕННО эту вкладку. Общая защита для ЛЮБОГО
  // вызова showTab(), не только restoreLastActiveTab().
  try {
    triggerTabData(id);
  } catch (e) {
    console.warn('showTab(' + id + '): triggerTabData упал, вкладка переключена, но контент может быть неполным до повторной перерисовки:', e);
  }

  // Запоминаем активную вкладку — при перезагрузке страницы восстановится
  // именно она, а не дефолтный ОБЗОР (localStorage, не sessionStorage —
  // сохраняется и между полным закрытием вкладки браузера).
  try { localStorage.setItem('bi_active_tab', id); } catch (e) {}
}

// Восстановление последней активной вкладки при загрузке страницы.
// Если сохранённой вкладки нет (первый визит) или соответствующего
// tab-<id> уже не существует (переименовали/удалили) — падаем на
// обычный дефолт (ОБЗОР), не ломаемся молча.
(function restoreLastActiveTab() {
  let saved = null;
  try { saved = localStorage.getItem('bi_active_tab'); } catch (e) {}
  if (saved && document.getElementById('tab-' + saved)) {
    // 2026-07-26: try/catch — второй раз подряд находим let/const,
    // объявленную НИЖЕ по файлу, но синхронно затронутую именно этим
    // ранним восстановлением вкладки (temporal dead zone): сначала
    // 'analytics'→chartsInited, теперь 'signals'→PRESET_SIGNALS_LIST
    // (renderPresetSignals() внутри triggerTabData). Без этой защиты
    // необработанное исключение здесь обрывает ВЕСЬ оставшийся синхронный
    // код скрипта, включая loadSignals() чуть ниже — сайт не грузит вообще
    // ничего, не только восстанавливаемую вкладку. Обе конкретные причины
    // исправлены точечно (перенос объявлений раньше), но независимо от
    // того, найдём ли мы когда-нибудь ТРЕТЬЮ такую переменную — этот catch
    // не даст ей повторить тот же катастрофический масштаб поломки.
    try {
      showTab(saved, null);
    } catch (e) {
      // 2026-08-01: раньше здесь откатывался только currentTabId, не видимый
      // DOM — если showTab() успела навесить .active на сохранённую вкладку
      // до броска исключения (шаги ДО triggerTabData, который теперь сам
      // защищён try/catch внутри showTab() — см. комментарий там), вкладка
      // оставалась визуально активной и пустой навсегда, а currentTabId
      // указывал на 'home' — рассинхрон, из-за которого более поздний
      // triggerTabData(currentTabId) чинил не ту вкладку. Явный сброс
      // .active классов здесь (не полный showTab('home') — не задвоить
      // init Chart.js) гарантирует, что видимый DOM и currentTabId снова
      // согласованы, каким бы шагом внутри showTab() ни бросило исключение.
      console.warn('restoreLastActiveTab: showTab(' + saved + ') упал, откатываюсь на ОБЗОР:', e);
      document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
      const homeSection = document.getElementById('tab-home');
      if (homeSection) homeSection.classList.add('active');
      document.querySelectorAll('.cbar-btn').forEach(b => b.classList.remove('active'));
      const homeCbar = document.getElementById('cbar-live');
      if (homeCbar) homeCbar.classList.add('active');
      activeCluster = 'live';
      renderSubnav('live', 'home');
      currentTabId = 'home';
    }
  } else {
    // Не showTab('home') — home и так инициализируется отдельно ниже
    // (fetchProdCost/initPriceChart/fetchBlocks на верхнем уровне);
    // повторный вызов через showTab() задвоил бы инициализацию Chart.js
    // на тот же canvas. currentTabId ставим явно, чтобы loadSignals()
    // всё равно знал какую вкладку перерисовать при необходимости.
    renderSubnav('live', 'home');
    currentTabId = 'home';
  }
})();

// загрузка сигналов из signals.json
// ── ШАБЛОН ОГЛАВЛЕНИЯ ВКЛАДКИ («СОДЕРЖАНИЕ») ────────────────────────────
// Общий рендер для любой вкладки: рамка var(--btc), шапка СОДЕРЖАНИЕ +
// счётчик, пронумерованные строки (заголовок+подзаголовок+стрелка),
// клик — scrollIntoView, снимает .collapsed если панель была свёрнута.
// Единственное место, где эта разметка теперь пишется — не копировать
// inline-стилями в новые вкладки, добавлять сюда данные и вызывать renderTOC().
function ruPlural(n, one, few, many) {
  const mod10 = n % 10, mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

function renderTOC(containerId, items) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const n = items.length;

  let html = '<div style="margin-top:12px;border:1px solid var(--btc);background:var(--bg2)">';
  html += '<div style="display:flex;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid var(--btc);background:var(--bg3)">'
    + '<span>📑</span>'
    + '<span style="font-family:var(--mono);font-size:11px;font-weight:700;color:var(--btc);letter-spacing:0.08em">СОДЕРЖАНИЕ</span>'
    + '<span style="margin-left:auto;font-family:var(--mono);font-size:9px;color:var(--btc);border:1px solid rgba(247,147,26,0.4);padding:2px 7px;border-radius:2px">' + n + '</span>'
    + '</div>';

  html += items.map(function(item, i) {
    const num = String(i + 1).padStart(2, '0');
    const isLast = i === items.length - 1;
    const borderStyle = isLast ? '' : 'border-bottom:1px solid var(--line);';
    return '<div onclick="document.getElementById(\'' + item.target + '\').classList.remove(\'collapsed\');'
      + 'document.getElementById(\'' + item.target + '\').scrollIntoView({behavior:\'smooth\'})" '
      + 'style="display:flex;align-items:center;gap:12px;padding:12px 14px;' + borderStyle + 'cursor:pointer;transition:background 0.12s" '
      + 'onmouseover="this.style.background=\'var(--bg3)\'" onmouseout="this.style.background=\'\'">'
      + '<span style="font-family:var(--mono);font-size:10px;color:var(--btc);min-width:20px">' + num + '</span>'
      + '<div style="flex:1">'
      + '<div style="font-family:var(--serif);font-style:italic;font-weight:500;font-size:15px;color:var(--ivory);margin-bottom:3px">' + sanitize(item.title) + '</div>'
      + '<div style="font-size:10px;color:var(--dim)">' + sanitize(item.subtitle) + '</div>'
      + '</div>'
      + '<span style="color:var(--dim);font-size:14px">›</span>'
      + '</div>';
  }).join('');

  html += '</div>';
  el.innerHTML = html;
}

renderTOC('theory-toc', [
  { target: 'theory-money', title: 'Что такое деньги', subtitle: 'Функции, свойства, история от бартера до Bitcoin' },
  { target: 'theory-network', title: 'Семь сетевых эффектов', subtitle: 'Почему Bitcoin побеждает структурно' },
  { target: 'theory-governance', title: 'Bitcoin Governance', subtitle: 'Как принимаются решения без центральной власти' },
  { target: 'theory-dca', title: 'Стратегия DCA', subtitle: 'Как накапливать без эмоций и таймирования' },
  { target: 'theory-passphrase', title: 'Насколько надёжна ваша парольная фраза?', subtitle: 'Diceware, математика взлома, Trezor Trusted Display' },
  { target: 'theory-hashrate-units', title: 'Хешрейт и сложность: единицы измерения', subtitle: 'TH/s vs T — почему их путают' }
]);

renderTOC('macrocontext-toc', [
  { target: 'theory-mnav', title: 'mNAV — механика BTC-казначейств', subtitle: 'Премия, дисконт, аккреция, BTC Yield' },
  { target: 'revenue-engines-panel', title: 'Доходные движки', subtitle: 'Как компании зарабатывают на BTC-резервах' },
  { target: 'theory-macro', title: 'Макроэкономика и Bitcoin', subtitle: 'Канал воздействия: ставки → ликвидность → BTC' },
  { target: 'theory-regulation', title: 'Регуляторная среда', subtitle: 'Юрисдикции, асимметрия реакции, роли государства' }
]);

renderTOC('lightning-toc', [
  { target: 'lightning-what', title: 'Что такое Lightning Network', subtitle: 'Layer 2, платёжные каналы, зачем нужен второй уровень' },
  { target: 'lightning-routing', title: 'Как работает маршрутизация', subtitle: 'Каналы, HTLC, ликвидность' },
  { target: 'lightning-connect', title: 'Как подключиться к Lightning', subtitle: 'Кастодиан, non-custodial, своя нода — 3 пути' },
  { target: 'lightning-comparison', title: 'Сравнение подходов', subtitle: 'Плюсы и минусы каждого варианта подключения' },
  { target: 'lightning-risks', title: 'Ограничения и риски', subtitle: 'Что важно знать перед использованием' }
]);

renderTOC('tech-toc', [
  { target: 'eco-panel', title: 'Экосистема Bitcoin', subtitle: 'L2, протоколы, компании, фонды' },
  { target: 'protocols-panel', title: 'Протоколы', subtitle: 'Proof-of-Work, Lightning Network' },
  { target: 'bitcoin-functions-panel', title: 'Функции Bitcoin', subtitle: 'Практические возможности протокола' },
  { target: 'architecture-panel', title: 'Архитектура', subtitle: 'Блокчейн, ключи и адреса, модель UTXO' }
]);

renderTOC('holders-toc', [
  { target: 'holders-structure', title: 'Структура владения · 2009–2026', subtitle: 'On-chain распределение по категориям держателей' },
  { target: 'holders-trends-panel', title: 'Ключевые тренды', subtitle: 'Динамика перераспределения владения' },
  { target: 'holders-waves-panel', title: 'Три волны институционализации', subtitle: 'Корпорации, ETF, государства' },
  { target: 'treasury-panel', title: 'Топ-100 держателей BTC', subtitle: 'Рейтинг публичных компаний по резервам BTC' }
]);

loadSignals();

// ── ACCORDION ──
function toggleAcc(head) {
  const body = head.nextElementSibling;
  const arrow = head.querySelector('.acc-arrow');
  const isOpen = body.classList.contains('open');
  document.querySelectorAll('.acc-body').forEach(b => b.classList.remove('open'));
  document.querySelectorAll('.acc-arrow').forEach(a => a.style.transform = '');
  if (!isOpen) {
    body.classList.add('open');
    arrow.style.transform = 'rotate(180deg)';
  }
}

// ══════════════════════════════════════════════════════
// SITEMAP — интерактивная карта сайта
// data/site_map.json — единственный источник истины по структуре сайта
// (аналог FACTS, но для структуры, не данных). Сверяется тестом
// tests/unit/test_site_map_sync.py в обе стороны при каждом CI-прогоне.
// ══════════════════════════════════════════════════════
let SITE_MAP = null;

async function fetchSiteMap() {
  try {
    const res = await fetch('data/site_map.json', { cache: 'no-store' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    SITE_MAP = await res.json();
  } catch (e) {
    console.warn('fetchSiteMap:', e);
  }
}

function openSiteMap() {
  const overlay = document.getElementById('sitemap-overlay');
  overlay.classList.add('open');
  const search = document.getElementById('sitemap-search');
  search.value = '';
  search.focus();
  if (SITE_MAP) {
    renderSiteMap(SITE_MAP.entries);
    renderSiteMapTabs('live');
  } else {
    document.getElementById('sitemap-body').innerHTML = '<div class="sm-empty">Загрузка карты сайта…</div>';
    fetchSiteMap().then(() => { if (SITE_MAP) { renderSiteMap(SITE_MAP.entries); renderSiteMapTabs('live'); } });
  }
}

function closeSiteMap() {
  document.getElementById('sitemap-overlay').classList.remove('open');
}

// Быстрый переход к заголовку кластера внутри оверлея (кнопки LIVE/
// ECOSYSTEM/FUNDAMENTAL/ANALYSIS вверху) — сбрасывает поиск, чтобы
// заголовок гарантированно был в DOM (при активном фильтре кластер
// без совпадений может быть скрыт целиком).
function jumpToSiteMapCluster(clusterKey) {
  const search = document.getElementById('sitemap-search');
  if (search.value) { search.value = ''; renderSiteMap(SITE_MAP.entries); }
  renderSiteMapTabs(clusterKey);
  const head = document.querySelector('.sm-cluster-head[data-cluster="' + clusterKey + '"]');
  if (head) head.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Постоянная строка вкладок сразу под кнопками кластеров (не повторяется
// внутри дерева на каждый кластер отдельно) — обновляется при переключении
// кластера, по умолчанию показывает вкладки первого кластера (LIVE).
// Заодно подсвечивает активную кнопку кластера — вызывается и при
// открытии оверлея, и по клику, так что подсветка не дублируется отдельно.
function renderSiteMapTabs(clusterKey) {
  const wrap = document.getElementById('sitemap-tabs');
  if (!SITE_MAP || !wrap) return;
  document.querySelectorAll('.sm-cluster-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.cluster === clusterKey)
  );
  const seen = [];
  const labels = {};
  SITE_MAP.entries.forEach(e => {
    if (e.cluster !== clusterKey) return;
    if (!(e.tab in labels)) { labels[e.tab] = e.tab_label; seen.push(e.tab); }
  });
  wrap.innerHTML = seen.map(tabKey =>
    '<button class="sm-tab-btn" onclick="jumpToSiteMapTab(\'' + tabKey + '\')">' + labels[tabKey] + '</button>'
  ).join('');
}

// Переход к заголовку конкретной вкладки внутри дерева (строка кнопок
// под названием кластера) — id вкладок уникальны сайт-целиком, доп.
// скоуп по кластеру не нужен.
function jumpToSiteMapTab(tabKey) {
  const search = document.getElementById('sitemap-search');
  if (search.value) { search.value = ''; renderSiteMap(SITE_MAP.entries); }
  const head = document.querySelector('.sm-tab-head[data-tab="' + tabKey + '"]');
  if (head) head.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function filterSiteMap(query) {
  if (!SITE_MAP) return;
  const q = query.trim().toLowerCase();
  if (!q) { renderSiteMap(SITE_MAP.entries); return; }
  const filtered = SITE_MAP.entries.filter(e =>
    e.title.toLowerCase().includes(q) ||
    (e.keywords || []).some(k => k.toLowerCase().includes(q)) ||
    e.tab_label.toLowerCase().includes(q) ||
    e.cluster_label.toLowerCase().includes(q)
  );
  renderSiteMap(filtered);
}

function renderSiteMap(entries) {
  const body = document.getElementById('sitemap-body');
  if (!entries.length) {
    body.innerHTML = '<div class="sm-empty">Ничего не найдено</div>';
    return;
  }
  // группировка кластер → вкладка, с сохранением исходного порядка появления
  const clusterOrder = [];
  const clusters = {};
  entries.forEach(e => {
    if (!clusters[e.cluster]) { clusters[e.cluster] = { label: e.cluster_label, tabOrder: [], tabs: {} }; clusterOrder.push(e.cluster); }
    const c = clusters[e.cluster];
    if (!c.tabs[e.tab]) { c.tabs[e.tab] = { label: e.tab_label, items: [] }; c.tabOrder.push(e.tab); }
    c.tabs[e.tab].items.push(e);
  });

  let html = '';
  clusterOrder.forEach(clusterKey => {
    const cluster = clusters[clusterKey];
    html += '<div class="sm-cluster-head" data-cluster="' + clusterKey + '">' + cluster.label + '</div>';
    cluster.tabOrder.forEach(tabKey => {
      const tab = cluster.tabs[tabKey];
      html += '<div class="sm-tab-head" data-tab="' + tabKey + '">' + tab.label + '</div>';
      tab.items.forEach(item => {
        const titleAttr = item.title.replace(/'/g, "\\'");
        html += '<div class="sm-entry" onclick="siteMapGoTo(\'' + tabKey + '\', \'' + titleAttr + '\')">'
          + '<span class="sm-dot ' + item.source + '"></span>'
          + '<span class="sm-entry-title">' + item.title + '</span>'
          + '</div>';
      });
    });
  });
  body.innerHTML = html;
}

// Переход из карты сайта к конкретной панели: переключает вкладку и находит
// панель по точному тексту заголовка (не по id — большинство панелей их не
// имеют, а искать по совпадению текста надёжнее, чем расставлять id на
// полсотни мест только ради этой функции). Раскрывает аккордеон, если он
// был свёрнут.
function siteMapGoTo(tabId, title) {
  closeSiteMap();
  showTab(tabId, null);

  // Находит span по точному тексту заголовка и скроллит к нему + раскрывает
  // аккордеон, если был свёрнут. Вынесено в отдельную функцию — вызывается
  // дважды (см. ниже, почему).
  function scrollToTitle() {
    const activeSection = document.querySelector('.section.active');
    if (!activeSection) return;
    const spans = activeSection.querySelectorAll('.panel-title, .acc-label, .instrument-ticker');
    for (const span of spans) {
      if (span.textContent.trim() === title) {
        span.scrollIntoView({ behavior: 'smooth', block: 'start' });
        const head = span.closest('.acc-head');
        if (head) {
          const accBody = head.nextElementSibling;
          if (accBody && !accBody.classList.contains('open')) toggleAcc(head);
        }
        return;
      }
    }
  }

  // Двойной вызов: сразу после переключения вкладки (80мс) асинхронный
  // контент (графики Chart.js, живые виджеты типа 'Сложность сети',
  // JS-таблицы) ещё не дорисовался — страница физически короче, чем
  // станет через долю секунды, поэтому scrollIntoView упирается в
  // ТОГДАШНИЙ предел скролла раньше времени, оставляя панель в середине
  // экрана вместо самого верха. Повторный вызов через 500мс — когда
  // страница уже выросла до финальной высоты — исправляет позицию.
  setTimeout(scrollToTitle, 80);
  setTimeout(scrollToTitle, 500);
}

// ── POOLS DATABASE ──
const POOLS = {
  'foundryusa': {
    name: 'Foundry USA', country: '🇺🇸 США', founded: '2019',
    share: '~30–34%', fee: 'FPPS, по объёму', site: 'foundrydigital.com',
    owner: 'Digital Currency Group (DCG)',
    history: 'Запущен в 2019 как майнинговое подразделение DCG. Быстро стал крупнейшим пулом сети за счёт работы с публичными майнинговыми компаниями Северной Америки и хостинг-провайдерами.',
    notes: 'Институциональный фокус, compliance-first. Обслуживает в первую очередь крупные публичные майнинговые фирмы, а не розничных майнеров. Тесная интеграция с энергорынками США (demand-response, ERCOT).'
  },
  'antpool': {
    name: 'AntPool', country: '🇨🇳 Китай', founded: '2014',
    share: '~14–19%', fee: '0% PPLNS / до 4% FPPS', site: 'antpool.com',
    owner: 'Bitmain',
    history: 'Создан Bitmain в 2014 году. Долгое время был крупнейшим пулом мира до возвышения Foundry.',
    notes: 'Дефолтный пул для оборудования Antminer. Выигрывает от прямой связи с крупнейшим производителем ASIC. Широкая география серверов: Северная Америка, Европа, Азия.'
  },
  'viabtc': {
    name: 'ViaBTC', country: '🇨🇳 Китай', founded: '2016',
    share: '~10–11%', fee: '2% PPLNS / до 4% FPPS', site: 'viabtc.com',
    owner: 'Независимый (изначально при поддержке Bitmain)',
    history: 'Запущен в 2016, изначально поддерживался Bitmain, затем стал независимым оператором.',
    notes: 'Особо силён в России и соседних регионах. Дружелюбный интерфейс для розничных майнеров, низкие пороги вывода. Поддерживает множество PoW-монет помимо BTC.'
  },
  'f2pool': {
    name: 'F2Pool', country: '🇨🇳 Китай', founded: '2013',
    share: '~10–11%', fee: 'FPPS / PPS+', site: 'f2pool.com',
    owner: 'Независимый (Discus Fish)',
    history: 'Один из старейших пулов, работает непрерывно с 2013 года. Известен также как «Discus Fish».',
    notes: 'Ранний пионер merged-mining. Поддерживает широкий спектр PoW-сетей. Развитые инструменты мониторинга для индивидуальных и крупных майнеров.'
  },
  'spiderpool': {
    name: 'SpiderPool', country: '🌏 Азия', founded: '2022',
    share: '~10%', fee: 'PPLNS / FPPS', site: 'spiderpool.io',
    owner: 'Независимый',
    history: 'Относительно молодой пул, быстро вырос до топ-5 по хешрейту к 2026 году.',
    notes: 'Привлекает майнеров низкими комиссиями. Один из подписантов перехода на Stratum V2.'
  },
  'marapool': {
    name: 'MARA Pool', country: '🇺🇸 США', founded: '2021',
    share: '~4–5%', fee: 'Собственный', site: 'mara.com',
    owner: 'Marathon Digital Holdings',
    history: 'Собственный пул публичной майнинговой компании Marathon (MARA), запущен в 2021.',
    notes: 'Корпоративный пул — обслуживает в основном собственные мощности Marathon. Публичная компания на NASDAQ.'
  },
  'binancepool': {
    name: 'Binance Pool', country: '🌍 Глобально', founded: '2020',
    share: '~5%', fee: 'FPPS', site: 'binance.com',
    owner: 'Binance',
    history: 'Запущен биржей Binance в 2020 году как часть экосистемы.',
    notes: 'Интегрирован с биржей Binance — удобно для вывода и торговли. Поддержка нескольких алгоритмов.'
  },
  'ocean': {
    name: 'Ocean', country: '🌍 Глобально', founded: '2023',
    share: '~1–2%', fee: 'TIDES', site: 'ocean.xyz',
    owner: 'Независимый (при участии Jack Dorsey)',
    history: 'Запущен в 2023, при поддержке Джека Дорси. Фокус на децентрализации.',
    notes: 'Некастодиальные выплаты напрямую на адреса майнеров (модель TIDES). Идеологически ориентирован на децентрализацию выбора транзакций.'
  },
  'braiinspool': {
    name: 'Braiins Pool', country: '🇨🇿 Чехия', founded: '2010',
    share: '~1–2%', fee: 'FPPS', site: 'braiins.com',
    owner: 'Braiins (ex-Slush Pool)',
    history: 'Старейший майнинговый пул в мире — основан в 2010 как Slush Pool, переименован в Braiins.',
    notes: 'Первопроходец пулового майнинга. Разработчик протокола Stratum V2, активно продвигает децентрализацию.'
  }
};

function normPool(name) {
  return name.toLowerCase().replace(/[^a-z0-9]/g, '');
}

function openPool(key) {
  const p = POOLS[key];
  const wrap = document.getElementById('pool-detail');
  const summary = document.getElementById('pool-summary');
  if (!p || !wrap) return;
  if (summary) summary.style.display = 'none';
  wrap.innerHTML =
    '<div class="pool-back" onclick="closePool()">← К ПУЛАМ</div>'
    + '<div class="panel" style="margin-top:8px">'
    + '<div class="panel-head"><span class="panel-title">' + p.name + '</span><span class="panel-tag">⛏️ ПУЛ · ' + p.country + '</span></div>'
    + '<div class="pool-stats">'
    + statCell('ДОЛЯ ХЕШРЕЙТА', p.share)
    + statCell('ОСНОВАН', p.founded)
    + statCell('КОМИССИЯ', p.fee)
    + statCell('САЙТ', p.site)
    + '</div>'
    + '<div class="panel-body"><p><strong>Владелец:</strong> ' + p.owner + '</p>'
    + '<p style="margin-top:10px"><strong>История.</strong> ' + p.history + '</p>'
    + '<p style="margin-top:10px"><strong>Особенности.</strong> ' + p.notes + '</p></div>'
    + '</div>';
  showTab('pools', null);
  window.scrollTo(0, 0);
}

function closePool() {
  const wrap = document.getElementById('pool-detail');
  const summary = document.getElementById('pool-summary');
  if (wrap) wrap.innerHTML = '';
  if (summary) summary.style.display = '';
  renderPoolSummary();
  window.scrollTo(0, 0);
}

function statCell(label, val) {
  return '<div class="pool-stat"><div class="pool-stat-label">' + label
    + '</div><div class="pool-stat-val">' + val + '</div></div>';
}

// ── LATEST BLOCKS ──
function timeAgo(ts) {
  const s = Math.floor(Date.now()/1000 - ts);
  if (s < 60) return s + 's';
  if (s < 3600) return Math.floor(s/60) + 'm';
  return Math.floor(s/3600) + 'h ' + Math.floor((s%3600)/60) + 'm';
}

// let LATEST_BLOCKS — объявление перенесено выше triggerTabData(),
// см. комментарий у объявления (фикс TDZ-краша при восстановлении вкладки).
function renderBlocks(blocks) {
  LATEST_BLOCKS = blocks;
  const list = document.getElementById('blocks-list');
  const title = document.getElementById('block-title');
  if (title && blocks[0]) {
    title.textContent = 'LATEST_BLOCKS — TIP #' + blocks[0].height.toLocaleString('ru-RU');
  }
  if (list) {
    list.innerHTML = blocks.slice(0, 10).map(b => {
      const pool = (b.extras && b.extras.pool && b.extras.pool.name) ? b.extras.pool.name : 'Unknown';
      const tx = b.tx_count != null ? b.tx_count.toLocaleString('ru-RU') : '—';
      const known = POOLS[normPool(pool)];
      const poolCell = known
        ? '<span class="blk-pool">' + pool + '<span class="pool-badge" onclick="openPool(\'' + normPool(pool) + '\')">INFO</span></span>'
        : '<span class="blk-pool">' + pool + '</span>';
      return '<div class="blk-row">'
        + '<span class="blk-h">#' + b.height.toLocaleString('ru-RU') + '</span>'
        + poolCell
        + '<span class="blk-tx">' + tx + '</span>'
        + '<span class="blk-age">' + timeAgo(b.timestamp) + '</span>'
        + '</div>';
    }).join('');
  }
  // обновить сводку пулов, если вкладка ПУЛЫ открыта без выбранного пула
  const detail = document.getElementById('pool-detail');
  if (detail && !detail.innerHTML.trim()) renderPoolSummary();
}

function renderPoolSummary() {
  const wrap = document.getElementById('pool-summary');
  if (!wrap) return;
  if (!LATEST_BLOCKS.length) {
    wrap.innerHTML = '<div class="pool-empty">Загрузка данных о блоках...</div>';
    return;
  }
  const last10 = LATEST_BLOCKS.slice(0, 10);
  const counts = {};
  last10.forEach(b => {
    const name = (b.extras && b.extras.pool && b.extras.pool.name) ? b.extras.pool.name : 'Unknown';
    if (!counts[name]) counts[name] = { name: name, n: 0 };
    counts[name].n++;
  });
  const rows = Object.values(counts).sort((a, b) => b.n - a.n);
  const heights = last10.map(b => b.height);
  const range = '#' + Math.min(...heights).toLocaleString('ru-RU') + ' – #' + Math.max(...heights).toLocaleString('ru-RU');

  wrap.innerHTML =
    '<div class="panel">'
    + '<div class="panel-head"><span class="panel-title">Пулы последних 10 блоков</span><span class="panel-tag">⛏️ LIVE · ' + range + '</span></div>'
    + '<div class="psum-head"><span>ПУЛ</span><span>БЛОКОВ</span><span>ДОЛЯ</span></div>'
    + rows.map(r => {
        const key = normPool(r.name);
        const known = POOLS[key];
        const pct = (r.n * 10) + '%';
        const nameCell = known
          ? '<span class="psum-name">' + r.name + '<span class="pool-badge" onclick="openPool(\'' + key + '\')">INFO</span></span>'
          : '<span class="psum-name">' + r.name + '</span>';
        return '<div class="psum-row">'
          + nameCell
          + '<span class="psum-n">' + r.n + '</span>'
          + '<span class="psum-bar-wrap"><span class="psum-bar" style="width:' + pct + '"></span><span class="psum-pct">' + pct + '</span></span>'
          + '</div>';
      }).join('')
    + '<div class="psum-note">«Доля» — срез по последним 10 блокам (краткосрочно, колеблется), не общая доля хешрейта сети. Долгосрочную долю смотри в карточке пула по кнопке INFO.</div>'
    + '</div>';
}

function fetchBlocks() {
  fetch('https://mempool.space/api/v1/blocks')
    .then(r => r.json())
    .then(renderBlocks)
    .catch(() => {
      const list = document.getElementById('blocks-list');
      const title = document.getElementById('block-title');
      if (title) title.textContent = 'LATEST_BLOCKS — offline';
      if (list) list.innerHTML = '<div class="blk-row blk-loading">данные недоступны</div>';
    });
}
fetchBlocks();
setInterval(fetchBlocks, 60000);
fetchProdCost();
setInterval(fetchProdCost, 300000);


// ── REALIZED PRICE (Glassnode via CoinMetrics public) ──────────────────────
async function fetchRealizedPrice() {
  try {
    // CoinMetrics public API — realized price (CapMrktCurUSD / SplyCur)
    const res = await fetch(
      'https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=CapRealUSD,SplyCur&frequency=1d&page_size=1&api_key=',
      { cache: 'no-store' }
    );
    const json = await res.json();
    const row  = json?.data?.[0];
    if (!row) return;

    const realizedCap = parseFloat(row.CapRealUSD);
    const supply      = parseFloat(row.SplyCur);
    if (!realizedCap || !supply) return;

    const rp = realizedCap / supply;
    updateRealizedPriceUI(rp);
  } catch(e) {
    // Тихо — блок остаётся со статичным значением
  }
}

function updateRealizedPriceUI(rp) {
  window._lastRP = rp;
  const rpEl     = document.getElementById('rp-value');
  const ratioEl  = document.getElementById('rp-ratio');
  const vsEl     = document.getElementById('rp-vs-market');
  const statusEl = document.getElementById('rp-status-text');

  if (rpEl) rpEl.textContent = '$' + Math.round(rp).toLocaleString('ru-RU');

  if (typeof dashBtcPrice === 'number' && dashBtcPrice > 0) {
    const ratio  = dashBtcPrice / rp;
    const pct    = ((dashBtcPrice - rp) / rp * 100).toFixed(1);
    const above  = dashBtcPrice >= rp;

    if (ratioEl) {
      ratioEl.textContent = ratio.toFixed(2) + '×';
      ratioEl.style.color = above ? 'var(--grn)' : 'var(--red)';
      ratioEl.style.borderColor = above ? 'rgba(90,158,114,0.3)' : 'rgba(194,96,96,0.3)';
    }

    if (vsEl) {
      vsEl.textContent = (above ? '+' : '') + pct + '% от RP';
      vsEl.style.color = above ? 'var(--grn)' : 'var(--red)';
    }

    if (statusEl) {
      if (above) {
        statusEl.innerHTML = 'Цена <span style="color:var(--grn)">выше</span> Realized Price — большинство держателей в прибыли. До RP: <span style="color:var(--txt)">−$' + Math.round(dashBtcPrice - rp).toLocaleString('ru-RU') + '</span>';
      } else {
        statusEl.innerHTML = 'Цена <span style="color:var(--red)">ниже</span> Realized Price — большинство держателей в убытке. <span style="color:var(--red)">Зона капитуляции</span>';
      }
    }
  }
}

setTimeout(fetchRealizedPrice, 500);
// Realized Price обновляется раз в сутки — достаточно при загрузке

// ── FACTS — машиночитаемые факты из сигналов (CLAUDE.md v8.2) ──────────────
// data/facts.json регенерируется scripts/build_facts.py из signals.json —
// НЕ редактируется руками. Приоритет разрешения значения (высший → низший):
// facts.json (свежайшее по as_of среди сигналов) → signals.json.meta
// (устаревающий вручную обновляемый снэпшот) → захардкоженная константа.
window.FACTS = window.FACTS || {};
async function fetchFacts() {
  try {
    const res = await fetch('data/facts.json', { cache: 'no-store' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    window.FACTS = data.facts || {};
    renderFactsAggregate();
    applyFactsToDOM();
  } catch (e) {
    console.warn('fetchFacts:', e);
  }
}

// Универсальный механизм: любой элемент с data-fact-key="entity_id.metric"
// автоматически подхватывает актуальное значение из window.FACTS при
// каждом fetchFacts(). Формат вывода — data-fact-format:
//   full (по умолчанию) — "843 375" (toLocaleString ru-RU)
//   k                    — "844K" (округление до тысяч)
// Оборачивать только САМО число в разметке, не весь текст/предложение —
// так фраза вокруг числа не теряется при миграции старого статичного текста.
function fmtFactValue(value, format) {
  if (format === 'k') return Math.round(value / 1000) + 'K';
  if (format === 'usd_b') return '$' + (value / 1e9).toFixed(1).replace('.', ',') + ' млрд';
  return value.toLocaleString('ru-RU');
}
function applyFactsToDOM() {
  document.querySelectorAll('[data-fact-key]').forEach(el => {
    const fact = window.FACTS[el.dataset.factKey];
    if (!fact) return; // факт ещё не подъехал/ключ не найден — оставляем плейсхолдер как есть
    el.textContent = fmtFactValue(fact.value, el.dataset.factFormat);
    el.title = 'Источник: ' + fact.signal_id + ' · на ' + fact.as_of;
  });
}

function renderFactsAggregate() {
  const el = document.getElementById('th-facts-aggregate');
  if (!el) return;
  const top100 = window.FACTS['top100_public_companies.btc_holdings'];
  const etfEx   = window.FACTS['etf_exchanges.btc_holdings'];
  if (!top100 && !etfEx) return;
  const fmt = v => (v / 1e6).toFixed(2) + 'M BTC';
  const parts = [];
  if (top100) parts.push('Топ-100: ' + fmt(top100.value) + ' (на ' + top100.as_of + ')');
  if (etfEx)  parts.push('ETF+биржи: ' + fmt(etfEx.value) + ' (на ' + etfEx.as_of + ')');
  el.textContent = parts.join(' · ');
}

// ── MSTR live data ──────────────────────────────────────────────────────────
const MSTR_BTC_RESERVE = 847363;
const MSTR_SHARES      = 242000000;  // акций в обращении
const MSTR_DEBT        = 8200000000; // долг ~$8.2B
const MSTR_PREF        = 4100000000; // привилегированные обязательства ~$4.1B

async function fetchMstrData() {
  try {
    // Гарантируем, что facts.json загружен (idempotent — fetch дешёвый,
    // не полагаемся на порядок вызовов из внешних мест инициализации)
    if (!Object.keys(window.FACTS).length) await fetchFacts();

    // Приоритет источника резерва BTC: facts.json (из сигналов) → meta
    // signals.json (устаревающий вручную) → захардкоженная константа
    const sm          = window.SIGNALS_META || {};
    const factReserve = window.FACTS['strategy.btc_holdings'];
    const btcReserve  = (factReserve && factReserve.value) || sm.strategy_btc_reserve || MSTR_BTC_RESERVE;
    const shares      = sm.strategy_shares_outstanding   || MSTR_SHARES;
    const debt        = sm.strategy_debt_usd             || MSTR_DEBT;
    const pref        = sm.strategy_pref_obligations_usd || MSTR_PREF;

    // Обновить отображение резерва в шапке
    const btcEl = document.getElementById('mstr-live-btc');
    if (btcEl) btcEl.textContent = btcReserve.toLocaleString('ru-RU');

    // Цена MSTR через Yahoo Finance
    const res = await fetch(
      'https://query1.finance.yahoo.com/v8/finance/chart/MSTR?interval=1d&range=1d',
      { cache: 'no-store' }
    );
    const data = await res.json();
    const meta = data?.chart?.result?.[0]?.meta;
    const mstrPrice = meta?.regularMarketPrice || meta?.previousClose;

    if (!mstrPrice) return;

    // Цена в шапке
    const priceEl = document.getElementById('mstr-live-price');
    if (priceEl) {
      priceEl.textContent = '$' + mstrPrice.toFixed(2);
      priceEl.style.color = mstrPrice < 100 ? 'var(--red)' : 'var(--grn)';
    }

    // NAV-мультипликатор
    if (typeof dashBtcPrice === 'number' && dashBtcPrice > 0) {
      const btcNav   = btcReserve * dashBtcPrice;
      const netNav   = btcNav - debt - pref;
      const navPerSh = netNav / shares;
      const mult     = mstrPrice / navPerSh;
      const navEl    = document.getElementById('mstr-nav-val');
      if (navEl && navPerSh > 0) {
        const label = mult >= 1
          ? 'Премия ' + mult.toFixed(2) + '×'
          : 'Дисконт ' + mult.toFixed(2) + '×';
        navEl.textContent = label;
        navEl.style.color = mult >= 1 ? 'var(--grn)' : 'var(--red)';
      }
    }
  } catch(e) {
    // тихо — не ломаем страницу
  }
}

// Запускаем после того как BTC-цена уже загружена (300ms delay)
setTimeout(fetchMstrData, 300);
setInterval(fetchMstrData, 300000); // обновляем каждые 5 мин вместе с BTC

initPriceChart();

// ── DIFFICULTY — Вариант 2: Контекст ────────────────────────────────────────
async function fetchDifficulty() {
  try {
    const [adjRes, hrRes] = await Promise.all([
      fetch('https://mempool.space/api/v1/difficulty-adjustment'),
      fetch('https://mempool.space/api/v1/mining/hashrate/1y'),
    ]);
    const adj = await adjRes.json();
    const hr  = await hrRes.json();

    const diffs     = hr.difficulty  || [];
    const hashrates = hr.hashrates   || [];
    // curDiff — из готового поля API (currentDifficulty), не из
    // последнего элемента массива diffs: массив может иметь другую
    // резолюцию/полноту, готовое поле надёжнее.
    const lastDiff  = diffs.length   ? diffs[diffs.length - 1]     : null;
    const curDiff   = hr.currentDifficulty || (lastDiff ? lastDiff.difficulty : null);
    // firstDiff — не diffs[0] "как есть" (был баг: если массив с сервера
    // приходит не ровно за 365 дней или другой плотности, diffs[0] может
    // оказаться намного ближе к текущей дате, чем "год назад" — отсюда
    // наблюдавшийся ×1.00 роста при почти неизменном значении). Ищем
    // запись, чей timestamp реально ближе всего к (сейчас − 365 дней).
    let firstDiff = null;
    if (diffs.length) {
      const oneYearAgoSec = Date.now() / 1000 - 365 * 86400;
      let closest = diffs[0];
      let closestDelta = Math.abs(closest.timestamp - oneYearAgoSec);
      for (const d of diffs) {
        const delta = Math.abs(d.timestamp - oneYearAgoSec);
        if (delta < closestDelta) { closest = d; closestDelta = delta; }
      }
      firstDiff = closest.difficulty;
    }

    // ATH difficulty (max in history array)
    const athDiff = diffs.length ? Math.max(...diffs.map(d => d.difficulty)) : null;
    const athPct  = (curDiff && athDiff) ? (curDiff / athDiff * 100) : null;

    // Ранг текущего значения среди значений ЭТОГО ЖЕ массива за год —
    // честно вычисляемый (не хардкод), в отличие от прежнего статичного
    // "3-е по низости значение года", которое было бы неверным уже на
    // следующей корректировке. rank=1 — минимум года.
    let rankText = null;
    if (curDiff && diffs.length > 1) {
      const sorted = [...new Set(diffs.map(d => d.difficulty))].sort((a, b) => a - b);
      const rank = sorted.indexOf(curDiff) + 1;
      if (rank > 0) rankText = rank + '-е по низости значение за год (из ' + sorted.length + ')';
    }

    // Year-over-year multiplier
    const yoyDiff = firstDiff && curDiff ? (curDiff / firstDiff) : null;

    // Current hashrate (last entry, H/s → EH/s)
    const lastHR    = hashrates.length ? hashrates[hashrates.length - 1] : null;
    const hrEH      = lastHR ? (lastHR.avgHashrate / 1e18) : null;

    // Derived: avg block time = difficulty * 2^32 / hashrate / 60
    const blockTimeMins = (curDiff && lastHR)
      ? (curDiff * Math.pow(2, 32) / lastHR.avgHashrate / 60)
      : null;

    // ASIC equivalent (Antminer S19 = 110 TH/s)
    const asicM = hrEH ? (hrEH * 1e18 / 110e12 / 1e6) : null;

    // ── Update DOM ────────────────────────────────────────────────────────────
    const $ = id => document.getElementById(id);

    // Header: только дата ретаргета (было + % изменения — перенесено
    // в hero как заметный бейдж, не дублируется здесь)
    if (adj.estimatedRetargetDate) {
      const eta = new Date(adj.estimatedRetargetDate * 1000);
      const el = $('diff-next-label');
      if (el) el.textContent = 'РЕТАРГЕТ ' + eta.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }).toUpperCase();
    }

    // Hero value
    if (curDiff) {
      const tVal = curDiff / 1e12;
      const el = $('diff-value');
      if (el) el.textContent = tVal >= 100 ? Math.round(tVal) : tVal.toFixed(2);
    }

    // Hero delta badge (перенесено из header — было diff-change там)
    if (adj.difficultyChange !== undefined) {
      const chg = adj.difficultyChange;
      const el = $('diff-change');
      if (el) {
        el.textContent = (chg >= 0 ? '▲ +' : '▼ ') + chg.toFixed(2) + '%';
        el.classList.toggle('pos', chg >= 0);
      }
    }

    // ATH% + честный ранг за год (вместо прежнего выдуманного "3-е место")
    if (athPct) {
      const el = $('diff-ath-pct');
      if (el) {
        el.innerHTML = '<b style="color:var(--txt);font-weight:400">' + athPct.toFixed(1) + '%</b> от годового максимума'
          + (rankText ? ' · ' + rankText : '');
      }
    }

    // Свёрнутые вторичные метрики
    if (blockTimeMins) {
      const el = $('diff-blocktime');
      if (el) el.textContent = blockTimeMins.toFixed(1) + ' мин/блок';
    }
    if (asicM) {
      const el = $('diff-asic');
      if (el) el.textContent = asicM.toFixed(1) + 'M машин';
    }
    if (yoyDiff) {
      const el    = $('diff-yoy');
      const desc  = $('diff-yoy-desc');
      const label = $('diff-yoy-label');
      if (el) el.textContent = '×' + yoyDiff.toFixed(2) + ' за год';
      const growing = yoyDiff > 1.03;
      const declining = yoyDiff < 0.97;
      if (label) label.textContent = growing ? 'РОСТ ЗА ГОД' : declining ? 'СНИЖЕНИЕ ЗА ГОД' : 'ГОД К ГОДУ';
      if (desc && firstDiff) {
        const changeText = growing
          ? 'Хешрейт сети вырос за этот период.'
          : declining
          ? 'Хешрейт сети снизился за этот период — давление на маржу майнеров.'
          : 'Хешрейт сети почти не изменился за этот период.';
        desc.textContent = 'Год назад: ' + (firstDiff / 1e12).toFixed(1) + 'T. ' + changeText;
      }
    }

    // Epoch progress bar + remaining blocks
    if (adj.progressPercent !== undefined) {
      const pct = Math.min(100, Math.max(0, adj.progressPercent));
      const elPct = $('diff-progress-pct');
      const elBar = $('diffBar');
      const elBlk = $('diff-blocks');
      if (elPct) elPct.textContent = pct.toFixed(1) + '%';
      if (elBlk && adj.remainingBlocks !== undefined) elBlk.textContent = adj.remainingBlocks.toLocaleString('ru-RU');
      setTimeout(() => { if (elBar) elBar.style.width = pct.toFixed(1) + '%'; }, 500);
    }

    // ── SVG history chart — СТУПЕНЧАТЫЙ (вариант B): сложность физически
    // меняется скачком раз в ~2 недели на ретаргете, не непрерывно —
    // прежняя сглаженная линия технически приукрашивала природу данных.
    const svg      = $('diff-chart');
    const labelsEl = $('diff-chart-labels');
    if (svg && diffs.length > 1) {
      const W = 600, H = 72, Pt = 6, Pb = 4;
      const vals = diffs.map(d => d.difficulty);
      const minD = Math.min(...vals), maxD = Math.max(...vals);
      const range = maxD - minD || 1;
      const n = diffs.length;
      const pts = diffs.map((d, i) => ({
        x: (i / (n - 1)) * W,
        y: Pt + (1 - (d.difficulty - minD) / range) * (H - Pt - Pb),
        ts: d.time * 1000,
      }));
      // Ступенчатая интерполяция step-after: горизонталь на уровне текущей
      // точки до x следующей, затем вертикальный скачок — так и ведёт себя
      // сложность между ретаргетами на самом деле.
      let stepD = `M${pts[0].x.toFixed(1)},${pts[0].y.toFixed(1)}`;
      for (let i = 1; i < n; i++) {
        stepD += ` L${pts[i].x.toFixed(1)},${pts[i-1].y.toFixed(1)} L${pts[i].x.toFixed(1)},${pts[i].y.toFixed(1)}`;
      }
      const areaD = stepD + ` L${W},${H} L0,${H} Z`;
      svg.innerHTML = `
        <defs>
          <linearGradient id="dg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="var(--btc)" stop-opacity=".2"/>
            <stop offset="100%" stop-color="var(--btc)" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <path d="${areaD}" fill="url(#dg)"/>
        <path d="${stepD}" fill="none" stroke="var(--btc)" stroke-width="1.5" stroke-linejoin="round"/>
        <circle cx="${pts[n-1].x.toFixed(1)}" cy="${pts[n-1].y.toFixed(1)}" r="3" fill="var(--btc)"/>
      `;
      if (labelsEl) {
        const picks = [pts[0], pts[Math.floor(n / 2)], pts[n - 1]];
        labelsEl.innerHTML = picks.map(p =>
          `<span style="font-size:10px;color:#7A8BA0">${new Date(p.ts).toLocaleDateString('ru-RU', { month: 'short', year: '2-digit' })}</span>`
        ).join('');
      }
    }

  } catch(e) {
    console.warn('Difficulty fetch error:', e);
  }
}

// Мост к сигналам — последний сигнал категории mining вместо прежнего
// мёртвого статичного блока "Июнь 2026". Вызывается из loadSignals()
// после того как SIGNALS точно загружен (не из fetchDifficulty() —
// разные источники данных, разное время готовности).
function renderDifficultySignalBridge() {
  const bridge = document.getElementById('diff-signal-bridge');
  if (!bridge) return;
  const mining = SIGNALS.filter(s => s.cat === 'mining').sort((a, b) => b.date.localeCompare(a.date));
  if (!mining.length) return; // нет ни одного mining-сигнала — блок остаётся скрытым
  const s = mining[0];
  const titleEl = document.getElementById('diff-signal-title');
  if (titleEl) { titleEl.textContent = sanitize(s.signal); titleEl.dataset.sigid = s.id; }
  const dateEl = document.getElementById('diff-signal-date');
  if (dateEl) dateEl.textContent = new Date(s.date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });
  const tensionEl = document.getElementById('diff-signal-tension');
  if (tensionEl) tensionEl.textContent = s.tension;
  const clusterEl = document.getElementById('diff-signal-cluster');
  if (clusterEl) {
    const count = SIGNALS.filter(x => x.cluster === s.cluster).length;
    clusterEl.textContent = sanitize(s.cluster) + ' · ' + count + ' сигнал' + ruPlural(count, '', 'а', 'ов');
  }
  bridge.style.display = 'block';
}

// ── CHARTS ──
function initCharts() {
  if (chartsInited) return;
  chartsInited = true;
  fetchDifficulty();  // live difficulty data + chart
  setInterval(fetchDifficulty, 300000); // refresh every 5 min
  fetchVolumeData();  // объём торгов — статичный data/volume.json, обновляется раз в сутки GitHub Action'ом
  fetchHashrateHistory();  // живой график вместо статичного массива 2016–2025 (см. функцию ниже)
}

// BIP-110 сигналинг — читает статичный data/bip110_signaling.json (обновляется
// раз в 3 часа GitHub Action'ом scripts/fetch_bip110_signaling.py). Не live-fetch
// в браузере — см. подробный комментарий у панели в HTML про то, почему.
function renderBip110Signaling() {
  const periodEl   = document.getElementById('bip110-period-label');
  const pctEl      = document.getElementById('bip110-pct');
  const blocksEl   = document.getElementById('bip110-blocks');
  const barEl      = document.getElementById('bip110-bar');
  if (!periodEl || !pctEl || !blocksEl || !barEl) return;

  const c = BIP110_SIGNALING;
  if (!c || c.signal_pct == null) {
    periodEl.textContent = 'ПЕРИОД —';
    pctEl.textContent = '—';
    blocksEl.textContent = 'Нет данных';
    return;
  }

  periodEl.textContent = 'ПЕРИОД ' + c.period;
  pctEl.textContent = c.signal_pct.toFixed(2);
  blocksEl.textContent = c.signaling_blocks + ' из ' + c.blocks_counted + ' блоков сигналят (высота ' + c.tip_height + ')';
  const barPct = Math.min(100, (c.signal_pct / (c.threshold_pct || 55)) * 100);
  barEl.style.width = barPct.toFixed(1) + '%';
}

// Объём торгов BTC/USD — читает статичный data/volume.json (обновляется раз в
// сутки GitHub Action'ом scripts/fetch_volume.py, к CoinGecko при загрузке
// страницы напрямую не обращаемся — см. CLAUDE.md / spec-pilot.md)
function fmtVolumeUsd(n) {
  if (n >= 1e9) return '$' + (n / 1e9).toFixed(2) + 'B';
  if (n >= 1e6) return '$' + (n / 1e6).toFixed(1) + 'M';
  return '$' + n.toLocaleString('en-US');
}

// Осталось добыть BTC — детерминированный расчёт по текущей высоте блока
// (протокольная константа, не аналитический факт — не через FACTS/сигналы,
// см. CLAUDE.md 'FACTS' § Что НЕ проходит через этот механизм).
// Раньше это был статичный текст с данными Oct 2024 (2,086,170 BTC) —
// молча разошёлся с реальностью (в июле 2026 фактически ~947K).
function calcTotalMined(height) {
  let mined = 0, reward = 50, blocksLeft = height;
  while (blocksLeft > 0 && reward > 1e-8) {
    const blocksInEra = Math.min(blocksLeft, 210000);
    mined += blocksInEra * reward;
    blocksLeft -= blocksInEra;
    reward /= 2;
  }
  return mined;
}

// Единый источник текущей высоты блока для всех виджетов сайта —
// переиспользует LATEST_BLOCKS (тот же массив, что питает "Последние
// блоки" на ОБЗОРЕ), не дёргает отдельный эндпоинт с риском получить
// другое число из-за задержки/рассинхронизации между двумя live-фетчами.
async function getCurrentBlockHeight() {
  if (LATEST_BLOCKS.length) return LATEST_BLOCKS[0].height;
  try {
    const res = await fetch('https://mempool.space/api/v1/blocks');
    const blocks = await res.json();
    renderBlocks(blocks);
    return blocks[0].height;
  } catch (e) {
    const res2 = await fetch('https://mempool.space/api/blocks/tip/height');
    return parseInt(await res2.text(), 10);
  }
}

// Переход к "Последние блоки" на ОБЗОРЕ — клик по номеру блока в halving-block
function goToLatestBlocks() {
  showTab('home', null);
  function scroll() {
    const el = document.getElementById('latest-blocks-panel');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  // Двойной вызов — та же причина, что в siteMapGoTo(): ОБЗОР тоже грузит
  // асинхронный контент (Фаза цикла, график цены), страница физически
  // короче в момент первого вызова.
  setTimeout(scroll, 50);
  setTimeout(scroll, 500);
}

// Halving-block: прогресс текущей эпохи + живая высота блока (общий
// источник с "Последние блоки" — см. getCurrentBlockHeight() выше)
const HALVING_EPOCH_START = 840000; // блок 4-го халвинга (апрель 2024)
const HALVING_EPOCH_LEN   = 210000;
async function renderHalvingBlock() {
  const fillEl  = document.getElementById('halving-progress-fill');
  const blockEl = document.getElementById('halving-block-link');
  const daysEl  = document.getElementById('halving-days-left');
  if (!fillEl) return;
  try {
    const height = await getCurrentBlockHeight();
    const blocksIn = height - HALVING_EPOCH_START;
    const progress = Math.min(100, Math.max(0, blocksIn / HALVING_EPOCH_LEN * 100));
    const blocksLeft = Math.max(0, HALVING_EPOCH_LEN - blocksIn);
    const daysLeft = Math.round(blocksLeft / 144);

    fillEl.style.width = progress.toFixed(1) + '%';
    if (blockEl) blockEl.textContent = 'Блок ' + height.toLocaleString('ru-RU');
    if (daysEl) daysEl.textContent = '~' + daysLeft.toLocaleString('ru-RU') + ' дней · апрель 2028';
  } catch (e) {
    console.warn('renderHalvingBlock:', e);
  }
}

async function fetchRemainingSupply() {
  const el = document.getElementById('emission-remaining-foot');
  if (!el) return;
  try {
    const height = await getCurrentBlockHeight();
    const totalMined = calcTotalMined(height);
    const remaining = 21000000 - totalMined;
    const remainingPct = (remaining / 21000000 * 100).toFixed(2);
    el.textContent = 'Осталось добыть: ~' + (remaining / 1e6).toFixed(2) + 'M BTC (' +
      remainingPct + '%). Последний BTC — ~2140 год. Текущая эмиссия: 3.125 BTC/блок. ' +
      '(блок ' + height.toLocaleString('ru-RU') + ')';
  } catch (e) {
    console.warn('fetchRemainingSupply:', e);
  }
}

// Хешрейт сети — живой график вместо статичного массива 2016–2025.
// mempool.space отдаёт максимум 3 года истории через этот эндпоинт
// (документированные периоды: 1m,3m,6m,1y,2y,3y) — полную историю с 2016
// как раньше показать нельзя без отдельного датасета, зато данные живые,
// не протухнут молча как было раньше (см. CLAUDE.md 'FACTS', этот график
// не входит в сам механизм, но той же природы баг — статичный массив,
// который никто не обновлял).
async function fetchHashrateHistory() {
  const svg    = document.getElementById('hashrateChart');
  const meta   = document.getElementById('hashrate-chart-meta');
  const capEl  = document.getElementById('hashrate-chart-caption');
  const labelsEl = document.getElementById('hashrate-chart-labels');
  if (!svg) return;
  try {
    const res = await fetch('https://mempool.space/api/v1/mining/hashrate/3y');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    const points = data.hashrates || [];
    if (!points.length) throw new Error('empty hashrates');

    // Сырые данные — примерно ежедневные за 3 года; агрегируем по месяцам,
    // иначе на графике не поместится и не читается.
    const monthly = {};
    points.forEach(p => {
      const d = new Date(p.timestamp * 1000);
      const key = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
      if (!monthly[key]) monthly[key] = { sum: 0, n: 0, ts: p.timestamp * 1000 };
      monthly[key].sum += p.avgHashrate;
      monthly[key].n += 1;
    });
    const labels = Object.keys(monthly).sort();
    const values = labels.map(k => (monthly[k].sum / monthly[k].n) / 1e18); // H/s → EH/s
    const n = values.length;

    if (meta) meta.textContent = 'EH/s · ' + labels[0].slice(2).replace('-', '/') +
      ' – ' + labels[labels.length - 1].slice(2).replace('-', '/');
    if (capEl) capEl.textContent = 'ИСТОРИЯ · ' + n + ' МЕСЯЦ' + ruPlural(n, '', 'А', 'ЕВ');

    // ── SVG-график того же оформления, что diff-chart (Сложность сети):
    // градиентная заливка + линия var(--btc) + точка на последнем значении,
    // без осей/сетки/тултипов Chart.js. Линия плавная (не ступенчатая) —
    // помесячное среднее непрерывно по природе, в отличие от сложности,
    // которая меняется скачком на ретаргете.
    const W = 600, H = 100, Pt = 6, Pb = 4;
    const minV = Math.min(...values), maxV = Math.max(...values);
    const range = maxV - minV || 1;
    const pts = values.map((v, i) => ({
      x: n > 1 ? (i / (n - 1)) * W : W / 2,
      y: Pt + (1 - (v - minV) / range) * (H - Pt - Pb),
    }));
    const lineD = pts.map((p, i) => (i === 0 ? 'M' : 'L') + p.x.toFixed(1) + ',' + p.y.toFixed(1)).join(' ');
    const areaD = lineD + ` L${W},${H} L0,${H} Z`;
    svg.innerHTML = `
      <defs>
        <linearGradient id="hg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--btc)" stop-opacity=".2"/>
          <stop offset="100%" stop-color="var(--btc)" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <path d="${areaD}" fill="url(#hg)"/>
      <path d="${lineD}" fill="none" stroke="var(--btc)" stroke-width="1.5" stroke-linejoin="round"/>
      <circle cx="${pts[n-1].x.toFixed(1)}" cy="${pts[n-1].y.toFixed(1)}" r="3" fill="var(--btc)"/>
    `;
    if (labelsEl) {
      const pickIdx = [0, Math.floor((n - 1) / 2), n - 1];
      labelsEl.innerHTML = pickIdx.map(i =>
        `<span style="font-size:10px;color:#7A8BA0">${labels[i].slice(2).replace('-', '/')}</span>`
      ).join('');
    }
  } catch (e) {
    if (meta) meta.textContent = 'ДАННЫЕ НЕДОСТУПНЫ';
    console.warn('fetchHashrateHistory:', e);
  }
}

async function fetchVolumeData() {
  const elCurrent  = document.getElementById('volume-current');
  const elChange   = document.getElementById('volume-change');
  const elMeta     = document.getElementById('volume-chart-meta');
  const elCaption  = document.getElementById('volume-chart-caption');
  const elLabels   = document.getElementById('volume-chart-labels');
  const elStats    = document.getElementById('volume-stats-row');
  const elTop3Body = document.getElementById('volume-top3-body');
  const svg        = document.getElementById('volumeChart');
  if (!svg) return;

  try {
    const res = await fetch('data/volume.json', { cache: 'no-store' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    const history = data.history || [];
    if (!history.length) throw new Error('empty history');

    if (elCurrent) elCurrent.textContent = fmtVolumeUsd(data.current.volume_usd);
    if (elChange && typeof data.current.change_24h_pct === 'number') {
      const pct = data.current.change_24h_pct;
      elChange.textContent = (pct >= 0 ? '▲ +' : '▼ ') + pct.toFixed(2) + '%';
      elChange.style.color = pct >= 0 ? 'var(--grn)' : 'var(--red)';
    }
    if (elMeta) elMeta.textContent = 'ОБНОВЛЕНО ' + data.updated_at.slice(0, 10);

    const vals  = history.map(h => h.volume_usd);
    const minV  = Math.min(...vals);
    const maxV  = Math.max(...vals);
    const avgV  = vals.reduce((a, b) => a + b, 0) / vals.length;
    const sorted = [...vals].sort((a, b) => a - b);
    const medV  = sorted.length % 2
      ? sorted[(sorted.length - 1) / 2]
      : (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2;

    // ── Строка статистики ──
    if (elStats) {
      const cell = (label, val) =>
        '<div><div style="font-size:9px;color:var(--dim);font-family:var(--mono)">' + label + '</div>' +
        '<div style="font-size:12px;font-family:var(--mono);color:var(--txt)">' + val + '</div></div>';
      elStats.innerHTML = cell('HIGH', fmtVolumeUsd(maxV)) + cell('LOW', fmtVolumeUsd(minV)) +
                           cell('MEDIAN', fmtVolumeUsd(medV)) + cell('AVG', fmtVolumeUsd(avgV));
    }

    // ── SVG-график того же оформления, что diff-chart (Сложность сети):
    // градиентная заливка + линия var(--btc) + точка на последнем значении,
    // без баров/дашед-линии среднего/тултипов. Линия плавная (не ступенчатая)
    // — дневной объём торгов непрерывен по природе, тот же принцип, что
    // уже применён к hashrateChart.
    const n = history.length;
    if (elCaption) elCaption.textContent = 'ИСТОРИЯ · ' + n + ' ' + ruPlural(n, 'ДЕНЬ', 'ДНЯ', 'ДНЕЙ');

    const W = 600, H = 100, Pt = 6, Pb = 4;
    const range = maxV - minV || 1;
    const pts = history.map((h, i) => ({
      x: n > 1 ? (i / (n - 1)) * W : W / 2,
      y: Pt + (1 - (h.volume_usd - minV) / range) * (H - Pt - Pb),
    }));
    const lineD = pts.map((p, i) => (i === 0 ? 'M' : 'L') + p.x.toFixed(1) + ',' + p.y.toFixed(1)).join(' ');
    const areaD = lineD + ` L${W},${H} L0,${H} Z`;
    svg.innerHTML = `
      <defs>
        <linearGradient id="vg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--btc)" stop-opacity=".2"/>
          <stop offset="100%" stop-color="var(--btc)" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <path d="${areaD}" fill="url(#vg)"/>
      <path d="${lineD}" fill="none" stroke="var(--btc)" stroke-width="1.5" stroke-linejoin="round"/>
      <circle cx="${pts[n-1].x.toFixed(1)}" cy="${pts[n-1].y.toFixed(1)}" r="3" fill="var(--btc)"/>
    `;
    if (elLabels) {
      const pickIdx = [0, Math.floor((n - 1) / 2), n - 1];
      elLabels.innerHTML = pickIdx.map(i =>
        `<span>${sanitize(history[i].date.slice(5))}</span>`
      ).join('');
    }

    // ── Топ-3 дня по объёму ──
    if (elTop3Body) {
      const top3 = [...history].sort((a, b) => b.volume_usd - a.volume_usd).slice(0, 3);
      elTop3Body.innerHTML = top3.map((h, i) =>
        '<tr><td>' + (i + 1) + '</td><td>' + h.date + '</td><td class="td-btc">' +
        fmtVolumeUsd(h.volume_usd) + '</td></tr>'
      ).join('');
    }
  } catch (err) {
    if (elMeta) elMeta.textContent = 'ДАННЫЕ НЕДОСТУПНЫ';
    console.warn('fetchVolumeData:', err);
  }
}

// ══════════════════════════════════════════════════════
// MACRO — рендер вкладок из HOLDERS_DATA
// ══════════════════════════════════════════════════════

function renderHolders() {
  const cats = [
    { key: 'individuals',  label: 'Individuals' },
    { key: 'lost_satoshi', label: 'Lost & Satoshi' },
    { key: 'governments',  label: 'Governments' },
    { key: 'companies',    label: 'Companies' },
    { key: 'etfs',         label: 'ETFs & Funds' },
    { key: 'not_mined',    label: 'Not Yet Mined' }
  ];

  // Таблица снэпшотов — транспонирована: бывшие названия столбцов теперь строки,
  // бывшие строки (даты) теперь столбцы, от 2024 года на уменьшение
  const snapsDesc = [...HOLDERS_DATA.snapshots].reverse();

  let tbl = '<div style="overflow-x:auto"><table class="htable"><thead><tr><th></th>';
  snapsDesc.forEach(s => tbl += '<th>' + s.date + '</th>');
  tbl += '</tr></thead><tbody>';

  tbl += '<tr><td class="htable-dim">Событие</td>';
  snapsDesc.forEach(s => tbl += '<td class="htable-dim htable-event" title="' + sanitize(s.event) + '">' + sanitize(s.event) + '</td>');
  tbl += '</tr>';

  cats.forEach(c => {
    const isCompanies = c.key === 'companies';
    const labelCell = isCompanies
      ? '<td style="cursor:pointer;color:var(--btc);text-decoration:underline;text-decoration-style:dotted;text-underline-offset:2px" onclick="document.getElementById(\'treasury-panel\').scrollIntoView({behavior:\'smooth\',block:\'start\'})" title="Смотреть детализацию по компаниям">' + c.label + '</td>'
      : '<td>' + c.label + '</td>';
    tbl += '<tr>' + labelCell;
    snapsDesc.forEach(s => {
      const v = s.categories[c.key];
      tbl += v
        ? '<td><div class="htable-pct-row"><span>' + v.btc.toLocaleString('ru-RU') + '</span><span class="htable-pct">' + v.pct + '%</span></div></td>'
        : '<td class="htable-dim">—</td>';
    });
    tbl += '</tr>';
  });

  tbl += '<tr><td class="htable-btc">Total Mined</td>';
  snapsDesc.forEach(s => tbl += '<td class="htable-btc">' + s.total_mined.toLocaleString('ru-RU') + '</td>');
  tbl += '</tr>';

  tbl += '</tbody></table></div>';
  document.getElementById('holders-table-wrap').innerHTML = tbl;

  // Тренды — вычисляются из HOLDERS_DATA.snapshots, не захардкожены.
  // Раньше это был статичный массив текста, ссылавшийся на Oct 2024 —
  // молча разошёлся с реальностью, когда снэпшот обновили до Jul 2026.
  // Теперь автоматически актуализируется при любом обновлении снэпшота
  // (см. CLAUDE.md, 'HOLDERS_DATA — правило верификации': при поступлении
  // сигнала со свежей цифрой по категории снэпшот обновляется — эта
  // таблица подхватывает изменение без отдельной правки).
  function computeHolderTrend(key, label, extraNote) {
    const points = HOLDERS_DATA.snapshots
      .map(s => ({ date: s.date, cat: s.categories[key] }))
      .filter(p => p.cat);
    if (!points.length) return null;
    const first = points[0];
    const last = points[points.length - 1];
    const peak = points.reduce((m, p) => p.cat.pct > m.cat.pct ? p : m, points[0]);
    let note;
    if (points.length === 1) {
      note = 'Впервые зафиксированы в ' + first.date + ': ' + first.cat.pct + '% · ' + first.cat.btc.toLocaleString('ru-RU') + ' BTC';
    } else if (peak.date === last.date) {
      note = 'Выросли с ' + first.cat.pct + '% (' + first.date + ') до ' + last.cat.pct + '% (' + last.date + ', ' + last.cat.btc.toLocaleString('ru-RU') + ' BTC)';
    } else {
      note = 'Росли с ' + first.cat.pct + '% (' + first.date + ') до пика ' + peak.cat.pct + '% (' + peak.date + '), затем снизились до ' + last.cat.pct + '% (' + last.date + ', ' + last.cat.btc.toLocaleString('ru-RU') + ' BTC)';
    }
    if (extraNote) note += ' ' + extraNote;
    return { label: label, note: note };
  }

  const trendDefs = [
    ['individuals', 'Individuals', null],
    ['companies', 'Companies', null],
    ['etfs', 'ETFs & Funds', null],
    ['governments', 'Governments', '— последняя точка является минимальной (floor) оценкой, не полной суммой всех государств.'],
    ['lost_satoshi', 'Lost & Satoshi', '— оценочная категория, точное значение неизвестно.']
  ];
  const trends = trendDefs.map(([key, label, note]) => computeHolderTrend(key, label, note)).filter(Boolean);

  let tr = '';
  trends.forEach(t => {
    tr += '<div style="padding:10px 14px;border-bottom:1px solid var(--line)">'
        + '<span style="font-family:var(--mono);font-size:11px;color:var(--btc)">' + t.label + '</span>'
        + '<p style="font-size:12px;color:var(--dim);margin-top:4px;line-height:1.5">' + t.note + '</p>'
        + '</div>';
  });
  document.getElementById('holders-trends').innerHTML = tr;

  // Три волны
  let wv = '';
  HOLDERS_DATA.institutional_waves.forEach(w => {
    wv += '<div style="padding:12px 14px;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:flex-start">'
        + '<div style="background:var(--btc);color:#000;font-family:var(--mono);font-weight:700;font-size:11px;'
        + 'padding:2px 8px;border-radius:2px;white-space:nowrap;margin-top:2px">ВОЛНА ' + w.wave + '</div>'
        + '<div><div style="font-size:13px;color:var(--txt)">' + w.label + ' · ' + w.year + '</div>'
        + '<div style="font-size:11px;color:var(--dim);margin-top:3px">' + w.event + '</div>'
        + '<div style="font-size:11px;color:var(--dim);margin-top:2px;font-style:italic">' + w.note + '</div></div>'
        + '</div>';
  });
  document.getElementById('holders-waves').innerHTML = wv;
}

function renderEmission() {
  // Таблица Not Yet Mined
  let tbl = '<div style="overflow-x:auto"><table class="dtable zebra"><thead><tr>'
          + '<th>Дата</th><th>Not Yet Mined %</th><th>Not Yet Mined BTC</th><th>Total Mined</th><th>Событие</th>'
          + '</tr></thead><tbody>';
  HOLDERS_DATA.snapshots.forEach((s, i) => {
    const nm = s.categories.not_mined;
    const isLast = i === HOLDERS_DATA.snapshots.length - 1;
    tbl += '<tr' + (isLast ? ' class="current"' : '') + '>'
         + '<td>' + s.date + '</td>'
         + '<td>' + (nm ? nm.pct + '%' : '—') + '</td>'
         + '<td>' + (nm ? nm.btc.toLocaleString('ru-RU') : '—') + '</td>'
         + '<td>' + s.total_mined.toLocaleString('ru-RU') + '</td>'
         + '<td>' + sanitize(s.event) + '</td>'
         + '</tr>';
  });
  tbl += '</tbody></table></div>';
  document.getElementById('emission-table-wrap').innerHTML = tbl;
}

// ══════════════════════════════════════════════════════
// ANALYSIS / SIGNALS — AI-анализатор
// ══════════════════════════════════════════════════════
// PRESET_SIGNALS_LIST/ANALYSIS_STEPS/analysisResult/currentStepIdx/
// AI_STOP_WORDS/CLUSTER_LABELS_AI — перенесены выше (см. рядом с
// chartsInited) после того, как найден и исправлен TDZ-краш: 2026-07-26,
// bi_active_tab='signals' → triggerTabData → renderPresetSignals() →
// PRESET_SIGNALS_LIST (была объявлена здесь, ПОСЛЕ этой точки исполнения) —
// та же причина, что раньше ловили на chartsInited (bi_active_tab='analytics').

// 2026-07-26 (по запросу пользователя): готовые сигналы теперь строятся из
// РЕАЛЬНЫХ данных, а не фиксированного списка примеров — используют оба
// слоя, что мы построили для самого анализатора (сущности + тензии
// кластеров), поэтому клик по любой кнопке гарантированно ведёт к
// содержательному результату через тот же findMatchingEntity()/keyword-overlap.
//
// ВАЖНО про порядок вызова: renderPresetSignals() вызывается ПЕРВЫЙ раз
// синхронно при restoreLastActiveTab() (см. комментарий там) — то есть ДО
// того, как loadSignals() успевает заполнить ENTITIES/SYNTHESIS_CACHE/SIGNALS
// реальными данными. generatePresetSignals() поэтому явно проверяет пустоту
// и отдаёт PRESET_SIGNALS_LIST (статичный, старый список) как временную
// заглушку на этот первый рендер — triggerTabData(currentTabId) после
// loadSignals() (см. там же) вызовет renderPresetSignals() второй раз, уже
// с настоящими данными.
//
// Подобрано намеренно, не произвольно:
// - Сущности — топ-3 по числу signal_refs (гарантия, что у них реально
//   есть чем ответить через findMatchingEntity(), не пустой список related_signals)
// - Кластеры — короткий вопрос из CLUSTER_PRESET_QUESTIONS (курируемый
//   список, не сырой обрывок тензии — см. комментарий у самого словаря
//   выше по файлу, найдено пользователем на скриншоте 2026-07-28: обрывки
//   тензии переносились на 2 строки в таблеточной кнопке и обрезались
//   посреди слова/числа)
function generatePresetSignals() {
  const hasEntities = Array.isArray(ENTITIES) && ENTITIES.length > 0;
  const hasClusters = SYNTHESIS_CACHE && Object.keys(SYNTHESIS_CACHE).some(k => !k.startsWith('_') && k !== 'meta');
  if (!hasEntities || !hasClusters) return PRESET_SIGNALS_LIST;

  // 2026-07-28 (по запросу пользователя): раньше слоты были жёстко
  // поделены "3 сущности + 3 кластера/сигнала" — состав всегда был
  // одинаковой формы, менялось только содержание внутри неё. Теперь все
  // ~6 слотов тянутся из ОДНОГО перемешанного пула (сущности + кластеры
  // + сигнальные preset_question вместе) — состав тоже случаен: иногда
  // больше сущностей, иногда больше кластерных вопросов, без фиксированной
  // структуры. Каждый кандидат по-прежнему проверяется через
  // localAnalyzeSignal() (или уже предпроверенный курируемый пул кластеров)
  // непосредственно перед принятием — рандомность состава не жертвует
  // надёжностью, тот же принцип, что уже применялся трижды в сессии.
  const entityPool = [...ENTITIES]
    .filter(e => (e.signal_refs || []).length > 0)
    .sort((a, b) => (b.signal_refs || []).length - (a.signal_refs || []).length)
    .slice(0, 8)
    .map(e => ({ type: 'entity', e }));

  const clusterEntries = Object.entries(SYNTHESIS_CACHE).filter(([k]) => !k.startsWith('_') && k !== 'meta');
  const clusterSignalCounts = {};
  (SIGNALS || []).forEach(s => { if (s.cluster) clusterSignalCounts[s.cluster] = (clusterSignalCounts[s.cluster] || 0) + 1; });
  const clusterPool = clusterEntries
    .filter(([k]) => (clusterSignalCounts[k] || 0) >= 2)
    .sort((a, b) => (clusterSignalCounts[b[0]] || 0) - (clusterSignalCounts[a[0]] || 0))
    .slice(0, 6)
    .map(([key]) => ({ type: 'cluster', key }));

  // preset_question — опциональное поле сигнала (CLAUDE.md схема, НЕ
  // покрывается Immutability Policy), ОБЯЗАН быть проверен через
  // localAnalyzeSignal() перед записью (Шаг 7) — здесь перепроверяем ещё
  // раз на лету (defense in depth) на случай изменения кластера/тензии
  // со временем после записи сигнала.
  const signalQuestionPool = (SIGNALS || [])
    .filter(s => s.preset_question)
    .map(s => ({ type: 'signal', s }));

  const combined = [...entityPool, ...clusterPool, ...signalQuestionPool];
  const shuffled = [...combined].sort(() => Math.random() - 0.5);

  const presets = [];
  const TOTAL_SLOTS = 6;
  for (const candidate of shuffled) {
    if (presets.length >= TOTAL_SLOTS) break;
    let q = null;
    if (candidate.type === 'entity') {
      // Многословные имена ("El Salvador", "Bitcoin Standard Treasury
      // Company") не находятся через findMatchingEntity() — посимвольное
      // сравнение с многословным кандидатом не проходит порог
      // Левенштейна — отсюда проверка перед принятием, не только для
      // кластеров.
      const cleanName = (candidate.e.name || candidate.e.id).replace(/\s*\(.*?\)\s*/g, '');
      const attempt = 'Сколько BTC у ' + cleanName + '?';
      if (localAnalyzeSignal(attempt).matched) q = attempt;
    } else if (candidate.type === 'cluster') {
      q = generateClusterPresetQuestion(candidate.key);
    } else {
      const attempt = candidate.s.preset_question;
      if (attempt && localAnalyzeSignal(attempt).matched) q = attempt;
    }
    if (q) presets.push(q);
  }

  return presets.length ? presets : PRESET_SIGNALS_LIST;
}

function renderPresetSignals() {
  const wrap = document.getElementById('preset-signals');
  if (!wrap) return;
  const list = generatePresetSignals();
  wrap.innerHTML = list.map(s => {
    const safe = sanitize(s);
    return '<button onclick="selectPreset(this)" data-signal="' + safe + '" '
      + 'style="background:transparent;border:1px solid var(--line2);border-radius:20px;'
      + 'color:var(--dim);padding:6px 14px;font-size:11px;cursor:pointer;'
      + 'font-family:var(--mono);letter-spacing:0.03em">' + safe + '</button>';
  }).join('');
}

function selectPreset(btn) {
  document.getElementById('sig-input').value = btn.dataset.signal;
  updateClearBtn();
  analyzeSignal();
}

// 2026-07-25 (обсуждение в чате, "Вариант C"): раньше analyzeSignal() делал
// живой fetch к api.anthropic.com БЕЗ API-ключа — гарантированно падал на
// любом вопросе (401 authentication_error, ключ отсутствовал в заголовках;
// зашить реальный ключ владельца в публичный клиентский JS нельзя — его
// увидит любой посетитель через просмотр кода страницы). Три варианта
// обсуждались: (A) ключ в коде — риск утечки, отклонено; (B) BYOK — каждый
// посетитель вводит свой ключ; (C) вообще без LLM-вызова — локальный анализ
// прямо по уже связанным и проанализированным данным сайта (тензии
// нарративных кластеров, data/synthesis_cache.json, + реальные сигналы того
// кластера как подтверждение) — выбран пользователем.
//
// Метод сопоставления — простое пересечение ключевых слов (без стоп-слов),
// не эмбеддинги/TF-IDF — по объёму данных (7 кластеров) этого достаточно,
// тот же принцип "сначала простой шаг", что уже применялся к ADR-018 Фазе 1.

function aiTokenize(text) {
  return (text || '')
    .toLowerCase()
    .match(/[а-яёa-z0-9]+/g) || [];
}

function aiSignificantTokens(text) {
  return aiTokenize(text).filter(w => w.length > 2 && !AI_STOP_WORDS.has(w));
}

// 2026-07-26: найдено на реальном примере ("Сколько BTC у Stratagy?" —
// опечатка в "Strategy") — простое пересечение слов с текстом тензии
// кластера не может ответить на вопрос про КОНКРЕТНУЮ компанию: тензия
// кластера btc_treasury_competition — это общий нарратив (напр. про
// Сальвадор), не про Strategy отдельно, а опечатка "Stratagy" не совпадает
// с "Strategy" как строка вообще. Реальная точность здесь выше, если
// сначала попробовать узнать КОНКРЕТНУЮ сущность (ENTITIES.json — уже
// готовый список компаний/протоколов) через нечёткое сравнение (терпимое
// к опечаткам), и ответить её собственными данными (profile.summary,
// signal_refs) — гораздо точнее общей тензии кластера.
function levenshtein(a, b) {
  if (a === b) return 0;
  const m = a.length, n = b.length;
  if (m === 0) return n;
  if (n === 0) return m;
  let prev = Array.from({ length: n + 1 }, (_, i) => i);
  for (let i = 1; i <= m; i++) {
    const cur = [i];
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      cur[j] = Math.min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost);
    }
    prev = cur;
  }
  return prev[n];
}

function findMatchingEntity(inputTokens) {
  let best = null, bestDist = Infinity;
  for (const e of (ENTITIES || [])) {
    const candidates = [
      (e.id || '').toLowerCase(),
      (e.name || '').replace(/\s*\(.*?\)\s*/g, '').toLowerCase()
    ].filter(Boolean);
    for (const token of inputTokens) {
      for (const cand of candidates) {
        if (Math.abs(token.length - cand.length) > 3) continue; // дёшево отсекаем заведомо далёкие пары
        const dist = levenshtein(token, cand);
        const threshold = Math.max(1, Math.floor(cand.length * 0.25)); // терпимость ~25% длины слова
        if (dist <= threshold && dist < bestDist) {
          bestDist = dist;
          best = e;
        }
      }
    }
  }
  return best;
}

// Экспортирована на window для теста (tests/unit/test_ai_local_analyzer_equivalence.py,
// тот же паттерн JS↔Python эквивалентности, что уже используется для других
// чистых функций — см. ADR-010).
function localAnalyzeSignal(input) {
  const inputTokensArr = aiSignificantTokens(input);
  const inputTokens = new Set(inputTokensArr);

  // ПРИОРИТЕТ 1 — узнанная сущность (нечёткое сравнение, терпимое к
  // опечаткам). Отвечает её собственными данными — точнее, чем тензия
  // всего кластера, если вопрос про конкретную компанию/протокол.
  const matchedEntity = findMatchingEntity(inputTokensArr);
  if (matchedEntity) {
    const relatedSignals = (SIGNALS || [])
      .filter(s => (matchedEntity.signal_refs || []).includes(s.id))
      .sort((a, b) => (b.date || '').localeCompare(a.date || ''))
      .slice(0, 3)
      .map(s => ({ id: s.id, date: s.date, title: s.signal, caveat: s.caveat }));
    const metricsText = ensureSentencePunctuation((matchedEntity.profile && matchedEntity.profile.metrics || []).join('\n'));
    const caveatsText = ensureSentencePunctuation(relatedSignals
      .filter(s => s.caveat)
      .slice(0, 2)
      .map(s => s.id + ': ' + s.caveat)
      .join('\n\n')) || 'Оговорок не зафиксировано в сигналах об этой сущности.';

    return {
      signal: input,
      matched: true,
      cluster_label: '🏢 ' + (matchedEntity.name || matchedEntity.id),
      tension: ensureSentencePunctuation(matchedEntity.summary) || '—',
      narrative: metricsText || '—',
      related_signals: relatedSignals,
      caveats: caveatsText
    };
  }

  // ПРИОРИТЕТ 2 (fallback) — конкретная сущность не узнана, ищем по
  // пересечению ключевых слов тензию/вывод самого релевантного кластера.
  const scored = Object.entries(SYNTHESIS_CACHE)
    .filter(([key]) => !key.startsWith('_') && key !== 'meta')
    .map(([key, cl]) => {
      const clusterTokens = aiSignificantTokens((cl && cl.tension || '') + ' ' + (cl && cl.narrative || ''));
      const overlap = clusterTokens.filter(t => inputTokens.has(t)).length;
      return { key, cl: cl || {}, overlap };
    })
    .sort((a, b) => b.overlap - a.overlap);

  const top = scored[0];
  const matched = !!(top && top.overlap > 0);

  if (!matched) {
    return {
      signal: input,
      matched: false,
      tension: 'Прямого совпадения по ключевым словам не найдено — вот все активные кластеры сейчас:',
      narrative: scored.map(s => (CLUSTER_LABELS_AI[s.key] || s.key)).join('\n'),
      related_signals: [],
      caveats: 'Локальный анализ работает через простое пересечение ключевых слов, не через понимание смысла вопроса — попробуй переформулировать ближе к терминам сайта (казначейство, ETF, предложение, майнинг, левередж, консенсус) или назвать конкретную компанию/протокол.'
    };
  }

  // 2026-07-28 (по запросу пользователя): "Подтверждающие сигналы" раньше
  // брали просто 3 САМЫХ СВЕЖИХ сигнала во всём кластере — не обязательно
  // те, что реально относятся к показанной тензии. Реальный пример: вопрос
  // "Как эволюционирует казначейство?" матчился на btc_treasury_competition,
  // показывал тензию именно про Сальвадор (STR-2026-0701-002) — но список
  // "подтверждающих" сигналов состоял из Strive/Satsuma/Canaan (просто
  // более свежие даты в том же широком кластере), ни один не про Сальвадор.
  // Пользователь не мог понять, о какой стране речь, глядя только на текст.
  // Исправлено — сигналы ранжируются по пересечению значимых слов с самой
  // ТЕНЗИЕЙ (тот же aiSignificantTokens, что и основной матчинг), не только
  // по дате; дата — тай-брейк при равной релевантности.
  const tensionTokens = new Set(aiSignificantTokens(top.cl.tension || ''));
  const relatedSignals = (SIGNALS || [])
    .filter(s => s.cluster === top.key)
    .map(s => ({
      s,
      relevance: aiSignificantTokens((s.signal || '') + ' ' + (s.tension || '')).filter(t => tensionTokens.has(t)).length
    }))
    .sort((a, b) => b.relevance - a.relevance || (b.s.date || '').localeCompare(a.s.date || ''))
    .slice(0, 3)
    .map(({ s }) => ({ id: s.id, date: s.date, title: s.signal, caveat: s.caveat }));

  const caveatsText = ensureSentencePunctuation(relatedSignals
    .filter(s => s.caveat)
    .slice(0, 2)
    .map(s => s.id + ': ' + s.caveat)
    .join('\n\n')) || 'Оговорок не зафиксировано в подтверждающих сигналах этого кластера.';

  return {
    signal: input,
    matched: true,
    cluster_label: DIGEST_CLUSTER_LABELS[top.key] || top.key,
    tension: ensureSentencePunctuation(top.cl.tension) || '—',
    narrative: ensureSentencePunctuation(top.cl.narrative) || '—',
    related_signals: relatedSignals,
    caveats: caveatsText
  };
}

function analyzeSignal() {
  // 2026-07-26: раньше здесь не было try/catch вообще — любое исключение
  // (включая случай, если #sig-input вдруг не найден) проваливалось молча —
  // пользователь видит "ничего не происходит", ни я, ни он не может понять
  // причину без доступа к консоли браузера, которой на мобильном обычно нет.
  // Теперь любая ошибка видна прямо на экране — достаточно скриншота, не
  // нужен доступ к devtools.
  try {
    const input = document.getElementById('sig-input').value.trim();
    if (!input) return;
    analysisResult = localAnalyzeSignal(input);
    showAnalysisResult();
  } catch (e) {
    document.getElementById('analysis-loading').style.display = 'none';
    document.getElementById('result-signal-title').textContent = document.getElementById('sig-input') ? document.getElementById('sig-input').value : '—';
    const tagEl = document.querySelector('#analysis-result .panel-tag');
    if (tagEl) tagEl.textContent = 'ОШИБКА';
    document.getElementById('result-steps').innerHTML =
      '<div style="padding:12px 14px;border-bottom:1px solid var(--line)">'
      + '<div style="font-family:var(--mono);font-size:10px;color:var(--red);letter-spacing:0.15em;margin-bottom:6px">ОШИБКА ВЫПОЛНЕНИЯ</div>'
      + '<p style="font-size:12px;color:var(--dim);line-height:1.6;font-family:var(--mono);white-space:pre-wrap">'
      + sanitize(String(e && e.stack || e))
      + '</p></div>';
    document.getElementById('analysis-result').style.display = 'block';
    const presetPanel = document.getElementById('preset-signals-panel');
    if (presetPanel) presetPanel.style.display = 'none';
  }
}

function showAnalysisResult() {
  document.getElementById('analysis-loading').style.display = 'none';
  document.getElementById('result-signal-title').textContent = analysisResult.signal;
  const tagEl = document.querySelector('#analysis-result .panel-tag');
  // 2026-07-28 (по решению пользователя, Вариант 2 из превью): короткий
  // бейдж — только эмодзи + краткая подпись кластера/сущности, без
  // префикса "НАЙДЕНО:" и без принудительного uppercase (ломал вид
  // сущностей типа "🏢 Strategy (MSTR)"). Раньше длинный текст
  // ("НАЙДЕНО: ⚡ LIGHTNING: ПЛАТЕЖИ И РАСЧЁТЫ") сжимал заголовок вопроса
  // в flex-строке, заставляя его переноситься на 2 строки.
  if (tagEl) tagEl.textContent = analysisResult.matched ? (analysisResult.cluster_label || '') : 'НЕ НАЙДЕНО';
  renderFullAnswer();
  document.getElementById('analysis-result').style.display = 'block';
  const presetPanel = document.getElementById('preset-signals-panel');
  if (presetPanel) presetPanel.style.display = 'none';
}

// 2026-07-26 (по запросу пользователя): полноценный связный ответ сразу,
// не разбитый на шаги "01/02/03/04" с кнопкой ДАЛЕЕ — та стеснённая подача
// имитировала внутреннюю схему обработки сигналов (Шаги 3-6 CLAUDE.md),
// что было уместно для ПРОЗРАЧНОСТИ рассуждения при РУЧНОЙ обработке
// сигналов мной, но избыточно и неудобно для читателя, ожидающего просто
// ответ на свой вопрос. Важно: без живого LLM (Вариант C — бессерверно,
// см. обсуждение в чате) это по-прежнему СОБРАННЫЙ из тех же реальных
// данных текст (tension+narrative+related_signals+caveats), не свободная
// генерация — просто показан весь сразу, одним блоком, а не по частям.
function renderFullAnswer() {
  const wrap = document.getElementById('result-steps');
  const r = analysisResult;

  const mainText = [r.tension, r.narrative].filter(Boolean).join('\n\n');

  let signalsHtml = '';
  if (r.related_signals && r.related_signals.length) {
    signalsHtml = '<div style="padding:12px 14px;border-top:1px solid var(--line)">'
      + '<div style="font-family:var(--mono);font-size:9px;color:var(--dim);letter-spacing:0.1em;margin-bottom:8px">ПОДТВЕРЖДАЮЩИЕ СИГНАЛЫ</div>'
      + r.related_signals.map(s =>
          '<div style="margin-bottom:8px">'
          + '<span style="font-family:var(--mono);font-size:10px;color:var(--btc)">' + sanitize(s.id) + ' · ' + sanitize(s.date) + '</span>'
          + '<div style="font-size:12px;color:var(--txt);margin-top:1px">' + sanitize(s.title) + '</div>'
          + '</div>'
        ).join('')
      + '</div>';
  }

  let caveatsHtml = '';
  if (r.caveats) {
    caveatsHtml = '<div style="padding:12px 14px;border-top:1px solid var(--line)">'
      + '<div style="font-family:var(--mono);font-size:9px;color:var(--amber);letter-spacing:0.1em;margin-bottom:6px">⚠ ОГОВОРКИ</div>'
      + '<p style="font-size:12px;color:var(--dim);line-height:1.6;white-space:pre-line">' + sanitize(r.caveats) + '</p>'
      + '</div>';
  }

  wrap.innerHTML =
    '<div style="padding:14px">'
    + '<p style="font-size:14px;color:var(--txt);line-height:1.7;white-space:pre-line">' + highlightVs(sanitize(mainText || '—')) + '</p>'
    + '</div>'
    + signalsHtml
    + caveatsHtml;
}

// Крестик очистки поля ввода — по запросу пользователя (2026-07-26).
function updateClearBtn() {
  const input = document.getElementById('sig-input');
  const btn = document.getElementById('sig-input-clear');
  if (!input || !btn) return;
  btn.style.display = input.value ? 'block' : 'none';
}

function clearSigInput() {
  const input = document.getElementById('sig-input');
  if (!input) return;
  input.value = '';
  input.focus();
  updateClearBtn();
}

function resetAnalysis() {
  document.getElementById('analysis-result').style.display = 'none';
  document.getElementById('sig-input').value = '';
  analysisResult = null;
  const presetPanel = document.getElementById('preset-signals-panel');
  if (presetPanel) presetPanel.style.display = '';
  updateClearBtn();
  // 2026-07-28 (по запросу пользователя): при клике "НОВЫЙ СИГНАЛ" готовые
  // сигналы должны перемешиваться заново, не оставаться теми же, что были
  // до анализа — renderPresetSignals() уже содержит случайный выбор
  // (сущности + курируемый пул вопросов на кластер), просто не вызывалась
  // повторно здесь раньше.
  renderPresetSignals();
}

// ── Инициализация MACRO и ANALYSIS при открытии вкладок ──
// Обработка встроена напрямую в showTab выше


