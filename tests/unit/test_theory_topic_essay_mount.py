"""
tests/unit/test_theory_topic_essay_mount.py
Bitcoin Intel — регрессионный тест: renderTheoryTopic() обязана генерировать
точку монтирования для THEORY_ESSAYS.json (2026-08-01).

КОНТЕКСТ: найдено пользователем на реальном скриншоте — новый элемент
THEORY_ESSAYS.json с target_panel: "theory-passphrase" (21ideas-2026-dice-seed,
тизер на полную панель "Сид на костях") не появился в панели вообще, без
единой ошибки в консоли. Причина: theory-passphrase — ДАТА-DRIVEN топик
из THEORY_TOPICS.json (рендерится renderTheoryTopic()), не статичная
панель, написанная руками в index.html. У статичных панелей (theory-money)
точка монтирования <div id="{panel}-essays"></div> расставлена вручную;
renderTheoryTopic() для дата-driven топиков такой div никогда не
генерировала. renderTheoryEssays() ищет getElementById(target_panel +
'-essays') и молча делает `if (!el) return` — эссе технически не могло
никуда смонтироваться, и это не проявлялось ничем, кроме отсутствия
контента.

Фикс — renderTheoryTopic() теперь ВСЕГДА эмитит эту точку монтирования,
для любого топика, не только для того, где сегодня нашли пропуск.
"""
import re
import shutil
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
    assert brace_open != -1
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
def render_topic_source() -> str:
    src = APP_MAIN_JS.read_text(encoding="utf-8")
    funcs = [
        _extract_function(src, "sanitize"),
        _extract_function(src, "sanitizeStrong"),
        _extract_function(src, "sourceFooterHtml"),
        _extract_function(src, "renderAccItem"),
        _extract_function(src, "renderTheoryTopic"),
    ]
    return "\n\n".join(funcs)


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestTheoryTopicEssayMount:

    def test_render_theory_topic_emits_essays_mount_div(self, render_topic_source):
        """Минимальный топик (без items/source_footer) всё равно получает свою -essays точку."""
        js = render_topic_source + """
const topic = { id: 'theory-example', panel_title: 'Пример', panel_tag: 'X' };
console.log(JSON.stringify({ html: renderTheoryTopic(topic) }));
"""
        import subprocess, json
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert 'id="theory-example-essays"' in html

    def test_mount_div_positioned_after_items_before_source_footer(self, render_topic_source):
        """Порядок важен — та же позиция, что у ручных статичных панелей (theory-money)."""
        js = render_topic_source + """
const topic = {
  id: 'theory-example',
  panel_title: 'Пример', panel_tag: 'X',
  items: [{ icon: '01', label: 'Пункт', paragraphs: ['текст'] }],
  source_footer: 'ИСТОЧНИК: тест'
};
console.log(JSON.stringify({ html: renderTheoryTopic(topic) }));
"""
        import subprocess, json
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]

        mount_pos = html.find('id="theory-example-essays"')
        items_pos = html.find('Пункт')
        footer_pos = html.find('ИСТОЧНИК: тест')

        assert mount_pos != -1
        assert items_pos != -1 and footer_pos != -1
        assert items_pos < mount_pos < footer_pos, (
            "Точка монтирования должна идти ПОСЛЕ пунктов аккордеона и ДО "
            "source_footer — тот же порядок, что у theory-money-essays в "
            "статичных панелях index.html"
        )

    def test_every_real_theory_topics_json_topic_gets_a_mount(self, render_topic_source):
        """
        Регрессия на реальные данные — не только на синтетике. Прогоняет
        ВСЕ топики из текущего THEORY_TOPICS.json, включая theory-passphrase
        (реальный кейс находки) и theory-dice-seed.
        """
        import subprocess, json
        topics_data = json.loads((REPO_ROOT / "THEORY_TOPICS.json").read_text(encoding="utf-8"))["topics"]

        js = render_topic_source + f"""
const topics = {json.dumps(topics_data)};
const results = {{}};
for (const t of topics) {{
  const html = renderTheoryTopic(t);
  results[t.id] = html.includes('id="' + t.id + '-essays"');
}}
console.log(JSON.stringify(results));
"""
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        results = json.loads(result.stdout)

        missing = [tid for tid, has_mount in results.items() if not has_mount]
        assert not missing, f"Топики без -essays точки монтирования: {missing}"
        assert "theory-passphrase" in results, "theory-passphrase должен существовать в THEORY_TOPICS.json"
