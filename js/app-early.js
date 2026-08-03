

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

// ── Instrument sticky headers: handled via CSS ──

// 2026-08-03: три JS-реактивных попытки синхронизировать .clusterbar с
// показом/скрытием панели мобильного браузера через window.visualViewport
// (GPU-слой + bottom-офсет, затем top-офсет без window.innerHeight) не
// дали полного результата - JS в принципе не успевает за покадровой
// нативной анимацией панели браузера (resize-событие приходит уже
// post-factum). Заменено структурным решением - .clusterbar теперь
// обычный flex-потомок .app-shell (min-height:100dvh), не
// position:fixed/sticky, синхронизация полностью на стороне браузера,
// без JS. См. CSS .app-shell/.app-scroll/.clusterbar в index.html.

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
