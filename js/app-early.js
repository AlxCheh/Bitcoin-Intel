

// ── Instrument sticky top: динамически под последним видимым fixed/sticky элементом ──
function updateInstStickyTop() {
  var header = document.querySelector('header');
  var crumb  = document.querySelector('.nav-crumb');
  var subnav = document.querySelector('.subnav');
  var top = 0;
  // header всегда sticky
  if (header) top = header.getBoundingClientRect().bottom;
  // crumb и subnav скроллятся — учитываем только если ещё видны
  if (crumb) {
    var r = crumb.getBoundingClientRect();
    if (r.bottom > top) top = r.bottom;
  }
  if (subnav) {
    var r2 = subnav.getBoundingClientRect();
    if (r2.bottom > top) top = r2.bottom;
  }
  document.documentElement.style.setProperty('--inst-sticky-top', Math.round(top) + 'px');
}
// 2026-08-03: найдено пользователем - нижняя панель (.clusterbar,
// position:fixed) визуально мелькала/дёргалась во время активного
// скролла. Два CSS-фикса (GPU-слой, dvh) не помогли - пользователь
// проверил на других сайтах в том же браузере, там нормально, значит
// причина не в браузере, а в JS конкретно этого сайта.
// updateInstStickyTop() висела на 'scroll' БЕЗ троттлинга - три вызова
// getBoundingClientRect() (каждый форсирует синхронный layout) плюс
// запись CSS-переменной на <html>, используемой для position:sticky
// таблицы - и всё это на КАЖДОЕ сырое событие scroll, которых при
// быстрой прокрутке может быть кратно больше, чем кадров экрана.
// Классический паттерн scroll-jank. Оборачиваем в requestAnimationFrame -
// стандартный приём, схлопывающий любое число событий между кадрами
// в один вызов работы за кадр, не за событие.
var instStickyTopScheduled = false;
function scheduleInstStickyTopUpdate() {
  if (instStickyTopScheduled) return;
  instStickyTopScheduled = true;
  requestAnimationFrame(function() {
    instStickyTopScheduled = false;
    updateInstStickyTop();
  });
}
// 2026-08-03: структурный фикс .clusterbar (вынос в .app-shell/.app-scroll,
// см. index.html) сделал СКРОЛЛЯЩИМСЯ элементом .app-scroll, не window/body
// как раньше - слушатель на window больше не отражает реальный скролл
// пользователя (или отражает лишь частично, в зависимости от браузера).
// Вешаем тот же обработчик на .app-scroll явно, а не на window.
var appScrollEl = document.querySelector('.app-scroll');
if (appScrollEl) {
  appScrollEl.addEventListener('scroll', scheduleInstStickyTopUpdate, { passive: true });
} else {
  window.addEventListener('scroll', scheduleInstStickyTopUpdate, { passive: true });
}
updateInstStickyTop();

// ── Плавающая кнопка «↑ К содержанию» (2026-08-16) ──────────────────────
// Показывается только на вкладках с оглавлением (theory/macrocontext/
// lightning — те же три, что renderTOC() в app-main.js) после скролла
// ниже порога. currentTabId — глобал, объявленный в app-main.js
// (загружается ПОСЛЕ этого файла); на момент реального вызова этой
// функции (пользователь уже скроллит/переключает вкладки) app-main.js
// уже успел выполниться.
var TOC_FAB_TABS = ['theory', 'macrocontext', 'lightning'];
var TOC_FAB_SCROLL_THRESHOLD = 400;

function updateTocFabVisibility() {
  var fab = document.getElementById('toc-fab');
  var scrollEl = document.querySelector('.app-scroll');
  if (!fab || !scrollEl) return;
  var shouldShow = TOC_FAB_TABS.indexOf(currentTabId) !== -1 && scrollEl.scrollTop > TOC_FAB_SCROLL_THRESHOLD;
  fab.style.display = shouldShow ? 'flex' : 'none';
}

function scrollToActiveToc() {
  var toc = document.getElementById(currentTabId + '-toc');
  if (toc) toc.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Тот же rAF-throttling паттерн, что у scheduleInstStickyTopUpdate выше —
// см. комментарий там же про scroll-jank от необёрнутых 'scroll'-событий.
var tocFabScheduled = false;
function scheduleTocFabUpdate() {
  if (tocFabScheduled) return;
  tocFabScheduled = true;
  requestAnimationFrame(function() {
    tocFabScheduled = false;
    updateTocFabVisibility();
  });
}
if (appScrollEl) {
  appScrollEl.addEventListener('scroll', scheduleTocFabUpdate, { passive: true });
} else {
  window.addEventListener('scroll', scheduleTocFabUpdate, { passive: true });
}

// ── Instrument sticky headers: handled via CSS ──

// 2026-08-03: три JS-реактивных попытки синхронизировать .clusterbar с
// показом/скрытием панели мобильного браузера через window.visualViewport
// не дали полного результата - JS в принципе не успевает за покадровой
// нативной анимацией панели браузера. Заменено структурным решением -
// .clusterbar теперь обычный flex-потомок .app-shell, не position:fixed/
// sticky. .app-shell сначала использовала height:100dvh (не min-height),
// затем height:100svh (dvh не пересчитывался плавно синхронно с
// анимацией на части браузеров, известная, широко задокументированная
// проблема - см. историю коммитов). Текущее состояние CSS - см. .app-shell
// в index.html, эта заметка описывает историю, не текущее значение
// дословно, чтобы не пришлось править эту заметку при каждой смене
// единицы измерения.

// 2026-08-03 (третье продолжение): предыдущая версия корректировала
// высоту ТОЛЬКО по первому scroll-событию - пользователь подтвердил,
// что это действительно снимает застревание (теперь достаточно любого
// свайпа, не обязательно доскролливать до конца), НО не решает саму
// суть жалобы - между загрузкой страницы и первым скролл-взаимодействием
// пользователь всё равно ВИДИТ сломанное, "полузападшее" состояние.
// Ждать любого взаимодействия вообще не годится - нужна коррекция ДО
// первой видимой отрисовки, без участия пользователя.
//
// Тройная защита, от самой ранней попытки к самой поздней:
// 1. Немедленный синхронный вызов - сразу при выполнении этого скрипта
//    (script без defer/async, выполняется в момент парсинга документа,
//    .app-shell к этому моменту уже есть в DOM - тег подключается после
//    неё в разметке).
// 2. Двойной requestAnimationFrame - известный приём "дождаться, пока
//    браузер точно завершит текущий цикл layout/paint" - следующий кадр
//    после текущего почти наверняка успевает после того, как браузер
//    "устаканил" реальные размеры собственного UI, даже без скролла.
// 3. Прежний once-слушатель на первый scroll .app-scroll - оставлен как
//    финальная страховка на случай, если даже двойной RAF всё ещё
//    попадает на неустоявшееся значение на каких-то устройствах.
function correctInitialAppShellHeight() {
  var appShell = document.querySelector('.app-shell');
  if (appShell) {
    appShell.style.height = window.innerHeight + 'px';
  }
}
correctInitialAppShellHeight();
requestAnimationFrame(function() {
  requestAnimationFrame(correctInitialAppShellHeight);
});
var scrollElForInitFix = document.querySelector('.app-scroll');
if (scrollElForInitFix) {
  scrollElForInitFix.addEventListener('scroll', correctInitialAppShellHeight, { passive: true, once: true });
}

function toggleInstrument(id) {
  var body = document.getElementById(id + '-body');
  var arrow = document.getElementById(id + '-arrow');
  if (!body) return;
  var collapsed = body.style.display === 'none';
  body.style.display = collapsed ? '' : 'none';
  arrow.style.transform = collapsed ? '' : 'rotate(-90deg)';
}
function toggleNav(id) {
  var body = document.getElementById(id);
  var arrow = document.getElementById('arr-' + id);
  if (!body) return;
  var collapsed = body.style.display === 'none';
  body.style.display = collapsed ? '' : 'none';
  if (arrow) arrow.style.transform = collapsed ? 'rotate(90deg)' : '';
}
