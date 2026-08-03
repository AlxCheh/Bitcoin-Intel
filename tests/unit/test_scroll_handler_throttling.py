"""
tests/unit/test_scroll_handler_throttling.py
Bitcoin Intel — регрессия на троттлинг обработчика 'scroll' через
requestAnimationFrame (2026-08-03).

КОНТЕКСТ: пользователь сообщил про мелькание нижней панели (.clusterbar)
при активном скролле. Два CSS-фикса (GPU-слой, dvh) не помогли -
пользователь проверил на других сайтах в том же браузере, там нормально,
значит причина не в браузере, а в JS этого сайта. updateInstStickyTop()
висела на 'scroll' БЕЗ троттлинга - три getBoundingClientRect() (каждый
форсирует синхронный layout) + запись CSS-переменной на <html> на КАЖДОЕ
сырое событие scroll. Классический scroll-jank паттерн.

Фикс - requestAnimationFrame-троттлинг: любое число scroll-событий между
кадрами схлопывается в один вызов работы за кадр.
"""
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
APP_EARLY_JS = REPO_ROOT / "js" / "app-early.js"


def test_scroll_listener_is_not_the_raw_heavy_function():
    """
    Регрессия на конкретную находку - addEventListener('scroll', ...)
    не должен напрямую указывать на updateInstStickyTop (тяжёлую функцию
    с 3x getBoundingClientRect + style write), а на throttling-обёртку.
    """
    src = APP_EARLY_JS.read_text(encoding="utf-8")
    assert "addEventListener('scroll', updateInstStickyTop" not in src, (
        "updateInstStickyTop() снова напрямую подписана на 'scroll' без "
        "троттлинга через requestAnimationFrame - вернулся scroll-jank "
        "паттерн, из-за которого мелькала .clusterbar (см. находку 2026-08-03)"
    )
    assert "addEventListener('scroll', scheduleInstStickyTopUpdate" in src


def test_throttle_wrapper_uses_request_animation_frame():
    src = APP_EARLY_JS.read_text(encoding="utf-8")
    assert "requestAnimationFrame" in src, (
        "requestAnimationFrame отсутствует - обработчик scroll не троттлится"
    )


def test_many_scroll_events_between_frames_trigger_only_one_heavy_call():
    """
    Поведенческий тест - не только текст исходника, но и реальный эффект:
    множество вызовов scroll-обработчика между кадрами должны схлопнуться
    в ОДИН вызов тяжёлой функции, не в N вызовов.
    """
    src = APP_EARLY_JS.read_text(encoding="utf-8")

    js = """
let callCount = 0;
let rafCallback = null;
global.requestAnimationFrame = function(cb) { rafCallback = cb; };
global.document = {
  querySelector: function() { return null; },
  documentElement: { style: { setProperty: function() {} } }
};
let scrollHandler = null;
global.window = {
  addEventListener: function(event, handler) {
    if (event === 'scroll') scrollHandler = handler;
  }
};
""" + src.replace("function updateInstStickyTop() {", "function updateInstStickyTop() { callCount++;") + """

// Симулируем 10 сырых scroll-событий подряд между кадрами (типично при
// быстрой прокрутке - событий может быть кратно больше, чем кадров экрана)
callCount = 0;
for (let i = 0; i < 10; i++) { scrollHandler(); }
console.log(JSON.stringify({ callsBeforeFrame: callCount, rafScheduled: rafCallback !== null }));

// Один кадр анимации проходит - вызов должен произойти РОВНО один раз
rafCallback();
console.log(JSON.stringify({ callsAfterOneFrame: callCount }));
"""
    result = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"

    import json
    lines = result.stdout.strip().split("\n")
    before = json.loads(lines[0])
    after = json.loads(lines[1])

    assert before["rafScheduled"] is True
    assert before["callsBeforeFrame"] == 0, (
        "Тяжёлая функция не должна вызываться синхронно из scroll-события - "
        "только через requestAnimationFrame"
    )
    assert after["callsAfterOneFrame"] == 1, (
        f"10 scroll-событий между кадрами должны схлопнуться в 1 вызов "
        f"тяжёлой функции, получено {after['callsAfterOneFrame']}"
    )
