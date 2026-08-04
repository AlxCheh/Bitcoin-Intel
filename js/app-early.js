

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

// 2026-08-03 (продолжение): пользователь сообщил о новом, более точно
// описанном симптоме - меню "полускрыто" именно на СВЕЖЕЙ загрузке
// страницы, ДО первого реального скролл-взаимодействия; стоит доскроллить
// .app-scroll до конца один раз - меню "вытягивается" в полный размер и
// дальше уже стабильно, вплоть до следующей перезагрузки страницы. Это
// НЕ про постоянное отставание JS от покадровой анимации (та проблема
// уже решена структурно) - это про то, что сам браузер, судя по всему,
// не сразу "фиксирует" точное значение svh при первом рендере, только
// после первого реального скролл-жеста. svh как единица - статична раз
// вычислена, но, видимо, требует явного триггера для самого первого
// вычисления на этом браузере.
//
// Решение - ОДНОРАЗОВАЯ (не покадровая, не непрерывная - именно
// поэтому не повторяет ошибку прошлых четырёх попыток) JS-коррекция:
// на первое реальное scroll-событие внутри .app-scroll явно
// перечитываем и проставляем актуальную высоту .app-shell через
// getBoundingClientRect() документа, затем СРАЗУ снимаем сам
// слушатель - не пытаемся отслеживать дальнейшие изменения, только
// один раз "подталкиваем" браузер зафиксировать корректное значение,
// то же самое, что пользователь уже делает вручную скроллом.
function correctInitialAppShellHeight() {
  var appShell = document.querySelector('.app-shell');
  if (appShell) {
    appShell.style.height = window.innerHeight + 'px';
  }
}
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
