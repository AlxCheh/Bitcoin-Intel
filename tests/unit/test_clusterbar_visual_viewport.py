"""
tests/unit/test_clusterbar_visual_viewport.py
Bitcoin Intel — регрессия на updateClusterbarBottomOffset() (2026-08-03).

КОНТЕКСТ: три предыдущих фикса (transform:translateZ(0) - GPU-слой,
body{min-height:100dvh}, requestAnimationFrame-троттлинг scroll-обработчика)
не решили основную жалобу пользователя - .clusterbar (position:fixed;
bottom:0) визуально "уезжает под панель мобильного браузера" при скролле
вниз. Реальная причина: position:fixed позиционируется относительно
viewport'а (initial containing block), не относительно body - правка
body{min-height:100dvh} из предыдущего PR физически не могла повлиять на
позицию .clusterbar вообще.

Настоящая проблема - разница между LAYOUT viewport (window.innerHeight,
как будто панели браузера всегда убраны) и VISUAL viewport
(visualViewport.height + offsetTop, реально видимая область в моменте) -
эта разница и есть полоса, занятая собственным UI браузера, под которую
"уезжает" bottom:0 элемент на части мобильных браузеров.

window.visualViewport - API специально для этого класса проблем. Тест
проверяет саму логику расчёта отступа, не реальное поведение браузера
(для которого нужен headless-браузер, которого в проекте намеренно нет).
"""
import re
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

    def _run(self, update_fn_source: str, setup_js: str) -> str:
        js = f"""
{setup_js}
{update_fn_source}
updateClusterbarBottomOffset();
console.log(JSON.stringify({{ bottom: clusterbarEl.style.bottom }}));
"""
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        import json
        return json.loads(result.stdout)["bottom"]

    def test_no_browser_toolbar_gives_zero_offset(self, update_fn_source):
        """Когда панель браузера не занимает пространство - отступ 0."""
        setup = """
const clusterbarEl = { style: { bottom: '' } };
const document = { querySelector: (sel) => sel === '.clusterbar' ? clusterbarEl : null };
window = { innerHeight: 800, visualViewport: { height: 800, offsetTop: 0 } };
"""
        bottom = self._run(update_fn_source, setup)
        assert bottom == "0px"

    def test_browser_toolbar_visible_gives_matching_offset(self, update_fn_source):
        """
        Панель браузера занимает 56px внизу (типичная высота нижнего тулбара
        Chrome Android) - visualViewport.height меньше innerHeight на эту величину.
        """
        setup = """
const clusterbarEl = { style: { bottom: '' } };
const document = { querySelector: (sel) => sel === '.clusterbar' ? clusterbarEl : null };
window = { innerHeight: 800, visualViewport: { height: 744, offsetTop: 0 } };
"""
        bottom = self._run(update_fn_source, setup)
        assert bottom == "56px"

    def test_missing_visual_viewport_does_not_throw(self, update_fn_source):
        """Старые браузеры без window.visualViewport - не должно падать."""
        setup = """
const clusterbarEl = { style: { bottom: '' } };
const document = { querySelector: (sel) => sel === '.clusterbar' ? clusterbarEl : null };
window = { innerHeight: 800 };
"""
        bottom = self._run(update_fn_source, setup)
        assert bottom == "", "Без visualViewport функция не должна ничего менять"

    def test_missing_clusterbar_does_not_throw(self, update_fn_source):
        """Если .clusterbar не найден в DOM - не должно падать."""
        setup = """
const document = { querySelector: () => null };
window = { innerHeight: 800, visualViewport: { height: 744, offsetTop: 0 } };
const clusterbarEl = { style: { bottom: 'unchanged' } };
"""
        bottom = self._run(update_fn_source, setup)
        assert bottom == "unchanged"
