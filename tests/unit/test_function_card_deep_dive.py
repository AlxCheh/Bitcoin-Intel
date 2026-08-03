"""
tests/unit/test_function_card_deep_dive.py
Bitcoin Intel — тест на deep_dive/deep_dive_title/deep_dive_highlight в
renderFunctionCard() (BITCOIN_FUNCTIONS.json), добавлено 2026-08-02.

Прогрессивное раскрытие детализации поверх краткого explanation — для
случаев, когда пользователь присылает более глубокий технический разбор
уже существующей функции (напр. "почему OP_RETURN называется именно так").
Элементы deep_dive — либо строка (абзац), либо {code: [...строки...]} —
блок кода, тот же визуальный класс .code, что уже используется в статичной
разметке сайта.
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
def render_source() -> str:
    src = APP_MAIN_JS.read_text(encoding="utf-8")
    return "\n\n".join([
        _extract_function(src, "sanitize"),
        _extract_function(src, "sanitizeStrong"),
        _extract_function(src, "renderToolBlock"),
        _extract_function(src, "renderFunctionCard"),
    ])


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestFunctionCardDeepDive:

    def test_function_without_deep_dive_still_renders(self, render_source):
        """Обратная совместимость - функция без deep_dive рендерится как раньше."""
        import json
        js = render_source + f"""
const fn = {json.dumps({"id": "x", "icon": "⚙", "name": "Тест", "hook": "H", "story": ["S"], "explanation": "E"})};
console.log(JSON.stringify({{ html: renderFunctionCard(fn) }}));
"""
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert "Тест" in html and "🔬" not in html

    def test_deep_dive_paragraph_and_code_block_render(self, render_source):
        import json
        fn = {
            "id": "x", "icon": "⚙", "name": "Тест",
            "deep_dive_title": "Заголовок разбора",
            "deep_dive": ["Обычный абзац", {"code": ["строка 1", "строка 2"]}],
            "deep_dive_highlight": "Итоговая фраза"
        }
        js = render_source + f"""
const fn = {json.dumps(fn)};
console.log(JSON.stringify({{ html: renderFunctionCard(fn) }}));
"""
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]

        assert "Заголовок разбора" in html
        assert "Обычный абзац" in html
        assert 'class="code"' in html
        assert "строка 1" in html and "строка 2" in html
        assert "callout-mono" in html and "Итоговая фраза" in html

    def test_real_op_return_entry_renders_without_error(self, render_source):
        """Регрессия на реальные данные, не только синтетику."""
        import json
        functions = json.loads((REPO_ROOT / "BITCOIN_FUNCTIONS.json").read_text(encoding="utf-8"))["functions"]
        op_return = next((f for f in functions if f["id"] == "op-return-blockchain-notary"), None)
        assert op_return is not None, "op-return-blockchain-notary не найден в BITCOIN_FUNCTIONS.json"

        # 2026-08-02: renderFunctionCard() теперь читает глобальный SIGNALS
        # для рендера signal_refs как кликабельных .crosslink (найдено
        # пользователем - "не вижу рабочих связей", signal_refs раньше
        # были только данными без реального перехода). Без объявления
        # SIGNALS здесь - ReferenceError, не тихий сбой (SIGNALS - не
        # объявленная переменная, `SIGNALS || []` в этом случае не спасает).
        signals_data = json.loads((REPO_ROOT / "signals.json").read_text(encoding="utf-8"))["signals"]

        js = render_source + f"""
const SIGNALS = {json.dumps(signals_data)};
const fn = {json.dumps(op_return)};
console.log(JSON.stringify({{ html: renderFunctionCard(fn) }}));
"""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as tmp:
            tmp.write(js)
            tmp_path = tmp.name
        try:
            result = subprocess.run(["node", tmp_path], capture_output=True, text=True, timeout=10)
        finally:
            os.unlink(tmp_path)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert 'class="code"' in html
        assert "callout-mono" in html
        assert "Элиз" not in html, "Отсылка на неподтверждённую историю не должна попасть в контент"
        # signal_refs должны рендериться как реально кликабельные .crosslink,
        # не просто упоминание id текстом внутри deep_dive
        assert "pendingScrollSignal='NAR-2026-0711-001'" in html
        assert "pendingScrollSignal='NAR-2026-0717-003'" in html
        assert "showTab('market',null)" in html
