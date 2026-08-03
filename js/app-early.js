

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
window.addEventListener('scroll', scheduleInstStickyTopUpdate, { passive: true });
updateInstStickyTop();

// ── Instrument sticky headers: handled via CSS ──

// 2026-08-03: два предыдущих фикса (GPU-слой translateZ(0), затем
// scroll-throttling updateInstStickyTop()) не решили основную жалобу -
// .clusterbar (position:fixed;bottom:0) визуально "уезжает под панель
// мобильного браузера" при скролле вниз. Причина, которую я упустил
// раньше: position:fixed позиционируется относительно viewport'а
// (точнее, initial containing block), НЕ относительно body - поэтому
// правка body{min-height:100dvh} из предыдущего PR физически не могла
// повлиять на реальную позицию .clusterbar вообще, независимо от того,
// правильна ли была сама идея про dvh.
//
// Настоящая проблема глубже: на части мобильных браузеров с динамически
// скрывающейся/появляющейся собственной панелью (адресная строка,
// системная навигация) position:fixed вычисляется относительно LAYOUT
// viewport (как будто панели браузера всегда убраны), а не VISUAL
// viewport (то, что реально видно в моменте) - разница между ними и есть
// та полоса, под которую "уезжает" нижнее меню сайта, когда панель
// браузера показана.
//
// window.visualViewport - API, специально созданный именно для этого
// класса проблем (тот же механизм обычно используют для панели ввода
// поверх появляющейся экранной клавиатуры). Разница между
// window.innerHeight (layout viewport) и visualViewport.height +
// offsetTop (реально видимая область) - это и есть высота полосы,
// занятой собственным UI браузера в данный момент. Явно выставляем эту
// разницу как bottom-отступ .clusterbar, вместо того чтобы полагаться на
// то, как конкретный браузер сам трактует "bottom:0" для fixed-элементов.
var clusterbarVVScheduled = false;
function updateClusterbarBottomOffset() {
  if (!window.visualViewport) return;
  var clusterbar = document.querySelector('.clusterbar');
  if (!clusterbar) return;
  var offsetBottom = window.innerHeight - (window.visualViewport.height + window.visualViewport.offsetTop);
  clusterbar.style.bottom = Math.max(0, Math.round(offsetBottom)) + 'px';
}
function scheduleClusterbarUpdate() {
  if (clusterbarVVScheduled) return;
  clusterbarVVScheduled = true;
  requestAnimationFrame(function() {
    clusterbarVVScheduled = false;
    updateClusterbarBottomOffset();
  });
}
if (window.visualViewport) {
  window.visualViewport.addEventListener('resize', scheduleClusterbarUpdate, { passive: true });
  window.visualViewport.addEventListener('scroll', scheduleClusterbarUpdate, { passive: true });
  updateClusterbarBottomOffset();
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
