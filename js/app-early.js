

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

// 2026-08-03: полный откат (PR #716) подтвердил - "уезжает под панель
// браузера + серая полоска" воспроизводится и на чистом CSS без каких-либо
// надстроек. Значит JS-оверрайд через visualViewport (первая попытка,
// PR #714) был ПРАВИЛЬНЫМ направлением - пользователь прямо подтверждал
// "теперь остаётся на месте" именно после него. Ошибка была в
// преждевременном полном откате из-за оставшегося дёрганья, а не в самой
// идее использовать visualViewport.
//
// Возвращаем ту же логику расчёта офсета (проверена - решает "уезжание
// под панель"), но с двумя уточнениями по сравнению с первой попыткой:
// 1. Убран конкурирующий CSS transition (был добавлен отдельным PR #715) -
//    гипотеза: transition боролся с частыми повторными JS-обновлениями
//    во время САМОЙ анимации показа/скрытия панели браузера (каждое новое
//    resize-событие перезапускало transition от уже промежуточной,
//    недоехавшей позиции) - это могло создавать эффект "погони за целью"
//    вместо точного, синхронного попадания в реальную позицию панели.
// 2. Слушаем только 'resize' на visualViewport, не 'scroll' - resize
//    семантически корректное событие именно для изменения РАЗМЕРА
//    видимой области (что и происходит при показе/скрытии панели
//    браузера); 'scroll' на visualViewport означает панорамирование
//    видимой области относительно layout viewport (напр. при pinch-zoom),
//    не связано напрямую с этим конкретным симптомом - лишний слушатель
//    добавлял лишние, близко расположенные по времени срабатывания без
//    дополнительной пользы для этой конкретной задачи.
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
  updateClusterbarBottomOffset();
}

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
