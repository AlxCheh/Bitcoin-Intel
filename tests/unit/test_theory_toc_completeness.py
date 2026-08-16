"""
tests/unit/test_theory_toc_completeness.py
Bitcoin Intel — регрессионный тест: renderTOC('theory-toc', [...]) обязан
перечислять КАЖДЫЙ дата-driven топик THEORY_TOPICS.json, который реально
монтируется внутри вкладки ТЕОРИЯ (id="{topic.id}-mount" в index.html).

КОНТЕКСТ: найдено пользователем на реальном сайте — панели «Сид на костях:
как создать ключ, не доверяя генератору» (theory-dice-seed) и «Квантовая
угроза: подготовка началась» (theory-quantum) не отражались в оглавлении
(«📑 СОДЕРЖАНИЕ») вкладки ТЕОРИЯ. Обе панели реально существуют и рендерятся
(есть точка монтирования theory-{id}-mount в index.html внутри самой вкладки
ТЕОРИЯ, отличие от theory-macro/theory-regulation, которые монтируются в
общий контейнер вкладки MACROCONTEXT и корректно перечислены в отдельном
massиве renderTOC('macrocontext-toc', ...)). Причина — renderTOC('theory-toc',
[...]) в js/app-main.js это ручной захардкоженный список; при добавлении
новой data-driven панели с mount-якорем внутри вкладки ТЕОРИЯ никто не
обязан (и не обязывался тестом) дописать сюда строку — расхождение молчит,
без единой ошибки в консоли, ровно как в test_theory_topic_essay_mount.py.

НЕ баг (сознательно не покрывается этим тестом): пункты THEORY_ESSAYS.json
(напр. эссе Бридлав/Сэйлор, target_panel: theory-money) — по дизайну не
создают отдельных панелей, это доп. пункты аккордеона внутри уже
перечисленной в TOC панели-хозяина (см. renderTheoryEssays()).
"""
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
APP_MAIN_JS = REPO_ROOT / "js" / "app-main.js"
THEORY_TOPICS_JSON = REPO_ROOT / "THEORY_TOPICS.json"


def _theory_toc_targets() -> set:
    src = APP_MAIN_JS.read_text(encoding="utf-8")
    marker = "renderTOC('theory-toc', ["
    start = src.find(marker)
    assert start != -1, "Вызов renderTOC('theory-toc', [...]) не найден в js/app-main.js"
    end = src.find("]);", start)
    assert end != -1, "Не найдено закрытие массива renderTOC('theory-toc', [...])"
    block = src[start:end]
    return set(re.findall(r"target:\s*'([\w-]+)'", block))


def _theory_tab_html() -> str:
    """
    Разметка ТОЛЬКО вкладки ТЕОРИЯ (<section id="tab-theory">...</section>),
    не всего index.html. Важно: THEORY_TOPICS.json — общий реестр на
    НЕСКОЛЬКО вкладок (напр. topic id="lightning-routing" монтируется во
    вкладке LIGHTNING, не ТЕОРИЯ, и у него тоже есть "{id}-mount" — без
    сужения до границ секции такой топик ложно попал бы в требования этого
    теста, хотя он вообще не про renderTOC('theory-toc', ...)).
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    start = html.find('id="tab-theory"')
    assert start != -1, 'Секция <section id="tab-theory"> не найдена в index.html'
    end = html.find('<section class="section" id="tab-', start + 1)
    assert end != -1, "Не найдена следующая секция после tab-theory — граница вкладки не определена"
    return html[start:end]


def _topics_mounted_inside_theory_tab() -> set:
    """
    Топики THEORY_TOPICS.json, у которых есть явный якорь
    id="{topic.id}-mount" внутри секции вкладки ТЕОРИЯ — т.е. они рендерятся
    НЕ в общий контейнер вкладки MACROCONTEXT (theory-topics-container), а в
    конкретную заранее размеченную позицию на вкладке ТЕОРИЯ
    (theory-macro/theory-regulation — топики без явного mount — уходят в
    MACROCONTEXT и здесь не учитываются).
    """
    theory_html = _theory_tab_html()
    topics = json.loads(THEORY_TOPICS_JSON.read_text(encoding="utf-8"))["topics"]
    return {t["id"] for t in topics if f'id="{t["id"]}-mount"' in theory_html}


def test_every_theory_tab_mounted_topic_is_in_theory_toc():
    toc_targets = _theory_toc_targets()
    mounted = _topics_mounted_inside_theory_tab()

    missing = sorted(mounted - toc_targets)
    assert not missing, (
        f"Топики с явным mount-якорем внутри вкладки ТЕОРИЯ отсутствуют в "
        f"renderTOC('theory-toc', [...]): {missing} — читатель не увидит их "
        f"в «📑 СОДЕРЖАНИЕ», хотя панель реально существует на странице"
    )


def test_theory_toc_has_no_dangling_targets():
    """Обратная проверка: каждая строка TOC должна указывать на существующую панель/mount в index.html."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    for target in _theory_toc_targets():
        assert (f'id="{target}"' in html) or (f'id="{target}-mount"' in html), (
            f"renderTOC('theory-toc', ...) ссылается на '{target}', для которого "
            f"нет ни статичной панели id=\"{target}\", ни точки монтирования "
            f"id=\"{target}-mount\" в index.html — мёртвая ссылка в оглавлении"
        )


def test_theory_toc_currently_includes_dice_seed_and_quantum():
    """
    Точечная регрессия на реальный, найденный пользователем кейс — не
    только на общее правило выше. Явно называет обе панели, чтобы при
    случайном ослаблении общей проверки тест всё равно ловил именно этот
    инцидент по имени.
    """
    toc_targets = _theory_toc_targets()
    assert "theory-dice-seed" in toc_targets
    assert "theory-quantum" in toc_targets
