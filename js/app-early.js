

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

// 2026-08-03: JS-оверрайд через visualViewport (updateClusterbarBottomOffset())
// был добавлен как фикс "меню уезжает под панель браузера", но пользователь
// сообщил, что дёрганье и серая полоска-артефакт ПРОДОЛЖИЛИСЬ после этого
// фикса, и явно указал: "раньше всё было идеально" - то есть простой CSS
// (position:fixed;bottom:0) без какого-либо JS-вмешательства работал
// корректно САМ ПО СЕБЕ. Наиболее вероятное объяснение: современные
// мобильные браузеры уже корректно позиционируют position:fixed
// относительно РЕАЛЬНО видимой области нативно, без необходимости в
// ручном JS-пересчёте - а мой JS-оверрайд (принудительная запись
// style.bottom на каждый resize/scroll visualViewport) активно
// конфликтовал с этим уже правильным нативным поведением браузера,
// создавая рассинхронизацию (два независимых механизма одновременно
// пытаются управлять одним и тем же bottom) - отсюда и "дёрганье", и
// серая полоска. Убран полностью - .clusterbar снова управляется только
// CSS (position:fixed;bottom:0), без активного JS поверх него.

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
