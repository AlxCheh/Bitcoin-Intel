"""
tests/unit/test_clusterbar_visual_viewport.py
Bitcoin Intel — updateClusterbarBottomOffset() (2026-08-03, третий заход).

ИСТОРИЯ: второй заход (офсет через window.innerHeight - visualViewport.height)
исправил "уезжание под панель", но пользователь сообщил о НОВОМ симптоме -
просвет с содержимым страницы МЕЖДУ меню и панелью браузера (офсет
временами переоценивался). Вероятная причина: window.innerHeight ведёт
себя непоследовательно между мобильными браузерами/версиями - на части
обновляется синхронно с visualViewport, на части остаётся статичным.

Третий заход убирает window.innerHeight из формулы полностью -
позиционирует панель через `top`, вычисленный НАПРЯМУЮ из собственных
свойств visualViewport (height, offsetTop) и реальной высоты самой
панели (offsetHeight) - ни одна из этих величин не зависит от того, как
конкретный браузер трактует innerHeight.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
APP_EARLY_JS = REPO_ROOT / "js" / "app-early.js"
NODE_AVAILABLE = shutil.which("node") is not None


def _extract_function(src: str, signature: str) -> str:
    start_marker = f"function {signature}"
    start = src.find(start_marker)
    assert start != -1, f"Function '{signature}' not found in app-early.js"
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
def update_fn_source() -> str:
    src = APP_EARLY_JS.read_text(encoding="utf-8")
    return _extract_function(src, "updateClusterbarBottomOffset")


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestClusterbarVisualViewport:

    def _run(self, update_fn_source: str, setup_js: str) -> dict:
        js = f"""
{setup_js}
{update_fn_source}
updateClusterbarBottomOffset();
console.log(JSON.stringify({{ top: clusterbarEl.style.top, bottom: clusterbarEl.style.bottom }}));
"""
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        import json
        return json.loads(result.stdout)

    def test_no_browser_toolbar_bar_sits_at_visible_bottom(self, update_fn_source):
        """Панель высотой 56px, видимая область 800px без панели браузера -> top:744px."""
        setup = """
const clusterbarEl = { style: { top: '', bottom: '' }, offsetHeight: 56 };
const document = { querySelector: (sel) => sel === '.clusterbar' ? clusterbarEl : null };
window = { visualViewport: { height: 800, offsetTop: 0 } };
"""
        result = self._run(update_fn_source, setup)
        assert result["top"] == "744px"
        assert result["bottom"] == "auto"

    def test_browser_toolbar_visible_bar_sits_above_it(self, update_fn_source):
        """Панель браузера съедает 56px снизу -> видимая область 744px -> top:688px."""
        setup = """
const clusterbarEl = { style: { top: '', bottom: '' }, offsetHeight: 56 };
const document = { querySelector: (sel) => sel === '.clusterbar' ? clusterbarEl : null };
window = { visualViewport: { height: 744, offsetTop: 0 } };
"""
        result = self._run(update_fn_source, setup)
        assert result["top"] == "688px"

    def test_calculation_does_not_reference_window_inner_height(self, update_fn_source):
        """
        Регрессия на находку третьего захода - формула не должна снова
        зависеть от window.innerHeight (непоследовательное поведение на
        разных мобильных браузерах было вероятной причиной то занижения,
        то завышения офсета).
        """
        assert "innerHeight" not in update_fn_source, (
            "window.innerHeight вернулся в расчёт - см. находку 2026-08-03 "
            "(третий заход): непоследовательное поведение этого свойства "
            "между браузерами было вероятной причиной просвета с контентом "
            "страницы под панелью"
        )

    def test_missing_visual_viewport_does_not_throw(self, update_fn_source):
        setup = """
const clusterbarEl = { style: { top: '', bottom: '' }, offsetHeight: 56 };
const document = { querySelector: (sel) => sel === '.clusterbar' ? clusterbarEl : null };
window = {};
"""
        result = self._run(update_fn_source, setup)
        assert result["top"] == "" and result["bottom"] == ""

    def test_missing_clusterbar_does_not_throw(self, update_fn_source):
        setup = """
const document = { querySelector: () => null };
window = { visualViewport: { height: 744, offsetTop: 0 } };
const clusterbarEl = { style: { top: 'unchanged', bottom: 'unchanged' }, offsetHeight: 56 };
"""
        result = self._run(update_fn_source, setup)
        assert result["top"] == "unchanged"


def test_only_resize_listener_not_scroll():
    src = APP_EARLY_JS.read_text(encoding="utf-8")
    assert "visualViewport.addEventListener('resize'" in src
    assert "visualViewport.addEventListener('scroll'" not in src


def test_no_stale_contradictory_comments():
    """
    Регрессия на находку третьего захода - предыдущий коммит оставил
    мёртвый комментарий, утверждающий "убран полностью" рядом с реально
    существующей функцией (пережиток отменённого отката). Явно проверяем,
    что такого противоречия нет.
    """
    src = APP_EARLY_JS.read_text(encoding="utf-8")
    assert "убран полностью" not in src, (
        "Найден потенциально устаревший комментарий про полное удаление "
        "рядом с активным кодом - проверь, не пережиток ли это отменённого "
        "отката (см. находку 2026-08-03, третий заход)"
    )
