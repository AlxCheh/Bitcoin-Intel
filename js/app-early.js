

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

// 2026-08-03 (третий заход): второй заход (top - bottom-офсет через
// window.innerHeight - visualViewport.height) исправил "уезжание под
// панель", но пользователь сообщил о НОВОМ симптоме - просвет с
// содержимым страницы МЕЖДУ меню и панелью браузера, то есть офсет
// временами ПЕРЕОЦЕНИВАЛСЯ (толкал панель выше, чем нужно), а не
// только недооценивался. Вероятная причина: window.innerHeight ведёт
// себя непоследовательно между мобильными браузерами/версиями - на
// части из них обновляется синхронно с visualViewport при показе/
// скрытии панели браузера, на части - остаётся статичным (значение
// "большого" viewport всегда) - в зависимости от того, КАКОЙ из двух
// случаев на конкретном устройстве, разница (innerHeight -
// visualViewport.height) может быть то верной, то нет, отсюда дёрганье
// в обе стороны скролла и то заниженный, то завышенный офсет.
//
// Убираем window.innerHeight из формулы полностью - вместо офсета
// "снизу", посчитанного как разница двух потенциально рассинхронизированных
// величин, позиционируем панель через top, вычисленный НАПРЯМУЮ из
// собственных свойств visualViewport (height, offsetTop) и реальной
// высоты самой панели - ни одна из этих величин не зависит от того, как
// конкретный браузер трактует innerHeight.
var clusterbarVVScheduled = false;
function updateClusterbarBottomOffset() {
  if (!window.visualViewport) return;
  var clusterbar = document.querySelector('.clusterbar');
  if (!clusterbar) return;
  var vv = window.visualViewport;
  var barHeight = clusterbar.offsetHeight;
  var top = vv.height + vv.offsetTop - barHeight;
  clusterbar.style.top = Math.round(top) + 'px';
  clusterbar.style.bottom = 'auto';
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
