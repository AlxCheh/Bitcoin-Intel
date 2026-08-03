"""
tests/unit/test_clusterbar_visual_viewport.py
Bitcoin Intel — updateClusterbarBottomOffset() (2026-08-03, второй заход).

ИСТОРИЯ: первая попытка (PR #714) исправила основной симптом ("уезжает
под панель мобильного браузера") - пользователь подтвердил "теперь
остаётся на месте". Но следующий PR (#715, transition:bottom для
сглаживания) не убрал остаточное дёрганье, и по ошибке весь подход был
полностью откачен (PR #716) вместо точечного устранения именно
transition. Откат воспроизвёл ИСХОДНУЮ проблему заново - подтверждает,
что сама идея (JS через visualViewport) была верна с самого начала.

Второй заход - та же логика расчёта офсета, но без конкурирующего CSS
transition и без лишнего 'scroll'-слушателя на visualViewport (только
'resize' - семантически верное событие для изменения размера видимой
области при показе/скрытии панели браузера).
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
        setup = """
const clusterbarEl = { style: { bottom: '' } };
const document = { querySelector: (sel) => sel === '.clusterbar' ? clusterbarEl : null };
window = { innerHeight: 800, visualViewport: { height: 800, offsetTop: 0 } };
"""
        bottom = self._run(update_fn_source, setup)
        assert bottom == "0px"

    def test_browser_toolbar_visible_gives_matching_offset(self, update_fn_source):
        setup = """
const clusterbarEl = { style: { bottom: '' } };
const document = { querySelector: (sel) => sel === '.clusterbar' ? clusterbarEl : null };
window = { innerHeight: 800, visualViewport: { height: 744, offsetTop: 0 } };
"""
        bottom = self._run(update_fn_source, setup)
        assert bottom == "56px"

    def test_missing_visual_viewport_does_not_throw(self, update_fn_source):
        setup = """
const clusterbarEl = { style: { bottom: '' } };
const document = { querySelector: (sel) => sel === '.clusterbar' ? clusterbarEl : null };
window = { innerHeight: 800 };
"""
        bottom = self._run(update_fn_source, setup)
        assert bottom == ""

    def test_missing_clusterbar_does_not_throw(self, update_fn_source):
        setup = """
const document = { querySelector: () => null };
window = { innerHeight: 800, visualViewport: { height: 744, offsetTop: 0 } };
const clusterbarEl = { style: { bottom: 'unchanged' } };
"""
        bottom = self._run(update_fn_source, setup)
        assert bottom == "unchanged"


def test_only_resize_listener_not_scroll():
    """
    Уточнение второго захода - слушаем только 'resize' на visualViewport,
    не 'scroll' (семантически 'scroll' не про изменение размера видимой
    области, а про панорамирование - не относится к показу/скрытию
    панели браузера, лишний слушатель без пользы для этого симптома).
    """
    src = APP_EARLY_JS.read_text(encoding="utf-8")
    assert "visualViewport.addEventListener('resize'" in src
    assert "visualViewport.addEventListener('scroll'" not in src, (
        "Слушатель 'scroll' на visualViewport не нужен для этого фикса - "
        "убран во втором заходе как вероятный источник лишних, избыточных "
        "срабатываний рядом с 'resize'"
    )


def test_no_competing_css_transition():
    """
    Уточнение второго захода - CSS transition на bottom НЕ должен
    возвращаться без явного, осознанного решения - гипотеза, что он
    конфликтовал с частыми JS-обновлениями во время анимации панели
    браузера, создавая эффект "погони за целью".
    """
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    m = re.search(r"\.clusterbar\s*\{([^}]*)\}", html)
    assert m, ".clusterbar CSS-правило не найдено"
    normalized = re.sub(r"\s+", "", m.group(1))
    assert "transition:bottom" not in normalized, (
        "transition:bottom вернулся в .clusterbar - если это осознанное "
        "решение попробовать снова, обнови этот тест явно вместе с изменением"
    )
