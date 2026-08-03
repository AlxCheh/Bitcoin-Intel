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
        # 2026-08-02: тот же ARG_MAX-риск, что и в TestTheoryRenderCallOrder
        # ниже — файл THEORY_TOPICS.json растёт, полный дамп через node -e
        # рано или поздно упирается в системный лимит длины аргумента.
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
        results = json.loads(result.stdout)

        missing = [tid for tid, has_mount in results.items() if not has_mount]
        assert not missing, f"Топики без -essays точки монтирования: {missing}"
        assert "theory-passphrase" in results, "theory-passphrase должен существовать в THEORY_TOPICS.json"


# ─── Порядок вызова renderTheoryTopics()/renderTheoryEssays() (2026-08-01) ──
# Отдельная, вторая находка на тот же баг: даже с точкой монтирования (фикс
# выше) эссе для дата-driven топика не появляется, если renderTheoryEssays()
# вызывается РАНЬШЕ renderTheoryTopics() — мостик <div id="...-essays">
# создаёт именно renderTheoryTopics(), до её вызова элемента ещё не
# существует, и renderTheoryEssays() тихо делает if (!el) return. Найдено
# пользователем на реальном скриншоте: PR с фиксом точки монтирования
# смержен, панель всё равно 'такая же скупая, как была' — porядок вызова
# в triggerTabData() был именно обратным (renderTheoryEssays() первой).

class TestTheoryRenderCallOrder:

    def test_trigger_tab_data_calls_topics_before_essays_for_theory(self):
        """
        Статическая проверка исходника — то же место, что уже дважды
        подводило (renderTheoryEssays() до renderTheoryTopics() в
        triggerTabData()). Ищет буквальную позицию вызовов в строке
        'if (id === \\'theory\\') { ... }'.
        """
        src = APP_MAIN_JS.read_text(encoding="utf-8")
        marker = "if (id === 'theory')"
        start = src.find(marker)
        assert start != -1, "Ветка theory в triggerTabData() не найдена"
        end = src.find("\n", start)
        line = src[start:end]

        topics_pos = line.find("renderTheoryTopics()")
        essays_pos = line.find("renderTheoryEssays()")
        assert topics_pos != -1 and essays_pos != -1
        assert topics_pos < essays_pos, (
            "renderTheoryTopics() должна вызываться ПЕРВОЙ — она создаёт "
            "точку монтирования <div id='...-essays'>, которую ищет "
            "renderTheoryEssays(). Обратный порядок молча ничего не "
            "рендерит, без единой ошибки (см. коммит 2026-08-01)."
        )

    def test_wrong_order_produces_empty_mount_right_order_does_not(self):
        """
        Не просто порядок в исходнике, а реальное поведение на реальных
        данных: неверный порядок даёт 0 символов в точке монтирования,
        верный — реальный контент. Доказывает, ЧТО именно проверяет
        предыдущий тест, не только форму записи.
        """
        src = APP_MAIN_JS.read_text(encoding="utf-8")
        funcs = "\n\n".join([
            _extract_function(src, "sanitize"),
            _extract_function(src, "sanitizeStrong"),
            _extract_function(src, "sourceFooterHtml"),
            _extract_function(src, "renderAccItem"),
            _extract_function(src, "renderTheoryTopic"),
            _extract_function(src, "renderTheoryTopics"),
            _extract_function(src, "renderTheoryEssays"),
        ])

        import json
        import subprocess
        topics_data = json.loads((REPO_ROOT / "THEORY_TOPICS.json").read_text(encoding="utf-8"))["topics"]
        essays_data = json.loads((REPO_ROOT / "THEORY_ESSAYS.json").read_text(encoding="utf-8"))["items"]

        def _run(order_topics_first: bool) -> int:
            calls = (
                "renderTheoryTopics(); renderTheoryEssays();"
                if order_topics_first else
                "renderTheoryEssays(); renderTheoryTopics();"
            )
            # renderTheoryTopics() создаёт панели через container.innerHTML =
            # ..., а не через отдельные getElementById-вставки — минимальный
            # mock должен сам регистрировать вложенные id после присвоения.
            # Мини-DOM только на то, что здесь реально нужно: container с
            # innerHTML, который при записи регистрирует id вложенных div'ов
            # как отдельные "элементы" — этого достаточно, чтобы честно
            # проверить порядок вызовов, не поднимая jsdom ради одного теста
            # (см. test_show_tab_resilience.py про этот же принцип).
            js = f"""
{funcs}
const THEORY_TOPICS = {json.dumps(topics_data)};
const THEORY_ESSAYS = {json.dumps(essays_data)};

const registry = {{}};
function makeMount(id) {{ return {{ innerHTML: '' }}; }}
const containerEl = {{ set innerHTML(html) {{
  this._html = html;
  const re = /id="([\\w-]+)"/g;
  let m;
  while ((m = re.exec(html))) {{ if (!registry[m[1]]) registry[m[1]] = makeMount(m[1]); }}
}}, get innerHTML() {{ return this._html || ''; }} }};
registry['theory-topics-container'] = containerEl;

const document = {{
  getElementById: function(id) {{ return registry[id] || null; }}
}};
{calls}
const mount = document.getElementById('theory-passphrase-essays');
console.log(JSON.stringify({{ len: mount ? mount.innerHTML.length : -1 }}));
"""
            # 2026-08-02: THEORY_TOPICS.json выросло за сессию (новые
            # crosslinks) - передача всего js одним аргументом command-line
            # (node -e "...") упёрлась в системный лимит ARG_MAX ("Argument
            # list too long"). Пишем во временный файл и запускаем node на
            # нём - устойчиво к дальнейшему росту файла, тот же результат.
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
            return json.loads(result.stdout)["len"]

        wrong_order_len = _run(order_topics_first=False)
        right_order_len = _run(order_topics_first=True)

        assert wrong_order_len == 0, (
            f"Ожидался пустой mount при неверном порядке (эссе раньше топиков), "
            f"получено {wrong_order_len} символов — тест сам мог сломаться"
        )
        assert right_order_len > 0, (
            "При верном порядке (топики раньше эссе) mount обязан заполниться реальным контентом"
        )
