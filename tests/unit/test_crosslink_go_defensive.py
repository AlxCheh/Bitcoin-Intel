"""
tests/unit/test_crosslink_go_defensive.py
Bitcoin Intel — тест на crosslinkGo()/uncollapseAndScrollTo() (2026-08-01).

КОНТЕКСТ: пользователь сообщил, что клик по crosslink-блоку ('Полный
пошаговый разбор...') не делает вообще ничего — ни ошибки, ни перехода.
Раньше onclick напрямую вызывал document.getElementById(id).scrollIntoView(...)
инлайн — если элемент не найден в момент клика (по любой причине), вызов
.scrollIntoView() на null бросает необработанное исключение, которое
ничем не проявляется внешне (инлайн onclick не оборачивается в try/catch
браузером) — ровно поведение "нажал, ничего не произошло", без единой
строки в консоли для диагностики.

Эти тесты не доказывают, что ИМЕННО это было причиной у пользователя
(код был синтаксически корректен при статической проверке) — но
гарантируют, что теперь при аналогичном сбое НЕ будет полной тишины:
хотя бы понятное сообщение в консоли вместо необработанного исключения.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
APP_MAIN_JS = REPO_ROOT / "js" / "app-main.js"
NODE_AVAILABLE = shutil.which("node") is not None


def _extract_function(src: str, signature: str) -> str:
    start_marker = f"function {signature}"
    start = src.find(start_marker)
    assert start != -1, f"Function '{signature}' not found in app-main.js"
    brace_open = src.find("{", start)
    depth = 0
    i = brace_open
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1] + "\n"
        i += 1
    raise AssertionError(f"Unbalanced braces extracting '{signature}'")


@pytest.fixture(scope="module")
def helpers_source() -> str:
    src = APP_MAIN_JS.read_text(encoding="utf-8")
    return "\n\n".join([
        _extract_function(src, "crosslinkGo"),
        _extract_function(src, "uncollapseAndScrollTo"),
    ])


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestCrosslinkGoDefensive:

    def test_crosslink_go_missing_element_warns_does_not_throw(self, helpers_source):
        js = helpers_source + """
global.alert = function() {};
const document = { getElementById: function() { return null; } };
let warned = null;
console.warn = function(msg) { warned = msg; };
let threw = false;
try { crosslinkGo('does-not-exist'); } catch (e) { threw = true; }
console.log(JSON.stringify({ threw: threw, warned: warned !== null }));
"""
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        import json
        out = json.loads(result.stdout)
        assert out["threw"] is False
        assert out["warned"] is True

    def test_crosslink_go_found_element_scrolls(self, helpers_source):
        js = helpers_source + """
global.alert = function() {};
let scrolled = false;
const document = { getElementById: function() {
  return { scrollIntoView: function() { scrolled = true; } };
} };
crosslinkGo('exists');
console.log(JSON.stringify({ scrolled: scrolled }));
"""
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        import json
        assert json.loads(result.stdout)["scrolled"] is True

    def test_uncollapse_and_scroll_missing_element_warns_does_not_throw(self, helpers_source):
        js = helpers_source + """
const document = { getElementById: function() { return null; } };
let warned = null;
console.warn = function(msg) { warned = msg; };
let threw = false;
try { uncollapseAndScrollTo('does-not-exist'); } catch (e) { threw = true; }
console.log(JSON.stringify({ threw: threw, warned: warned !== null }));
"""
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        import json
        out = json.loads(result.stdout)
        assert out["threw"] is False
        assert out["warned"] is True

    def test_uncollapse_and_scroll_found_element_uncollapses_and_scrolls(self, helpers_source):
        js = helpers_source + """
let removedClass = null, scrolled = false;
const document = { getElementById: function() {
  return {
    classList: { remove: function(c) { removedClass = c; } },
    scrollIntoView: function() { scrolled = true; }
  };
} };
uncollapseAndScrollTo('exists');
console.log(JSON.stringify({ removedClass: removedClass, scrolled: scrolled }));
"""
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        import json
        out = json.loads(result.stdout)
        assert out["removedClass"] == "collapsed"
        assert out["scrolled"] is True

    def test_all_scroll_targets_use_defensive_helpers_not_raw_inline(self):
        """
        Регрессия на реальную находку: ни один onclick в app-main.js не
        должен напрямую вызывать document.getElementById(...).scrollIntoView(...)
        без null-проверки — кроме мест, где проверка уже встроена инлайн
        (if(el)el.scrollIntoView...).
        """
        src = APP_MAIN_JS.read_text(encoding="utf-8")
        # Убираем JS-комментарии перед проверкой — свои же пояснительные
        # комментарии упоминают старый паттерн по имени (см. ту же ошибку
        # в test_crosslink_target_length.py про CSS-комментарий).
        src_no_line_comments = re.sub(r"//[^\n]*", "", src)
        src_no_comments = re.sub(r"/\*.*?\*/", "", src_no_line_comments, flags=re.DOTALL)
        raw_pattern = re.compile(r"document\.getElementById\([^)]*\)\.scrollIntoView")
        matches = raw_pattern.findall(src_no_comments)
        assert not matches, (
            f"Найдены незащищённые document.getElementById(...).scrollIntoView(...) "
            f"без null-проверки: {matches} — используй crosslinkGo()/uncollapseAndScrollTo() "
            f"или инлайн if(el) перед вызовом"
        )
