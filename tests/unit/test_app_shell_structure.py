"""
tests/unit/test_app_shell_structure.py
Bitcoin Intel — структурный фикс "меню уезжает под панель браузера /
дёргается" (2026-08-03, пятый и финальный заход).

ИСТОРИЯ: четыре JS-реактивных попытки (GPU-слой, body{100dvh}, три
варианта JS-оверрайда через window.visualViewport) не дали полного
результата - симптомы менялись, но не исчезали (то уезжание под панель,
то серая полоска, то просвет с контентом - в зависимости от направления
скролла). Корень: JS в принципе не может идеально успевать за покадровой
нативной анимацией показа/скрытия панели браузера - resize-событие
всегда приходит post-factum.

Решение - структурное: .app-shell (flex-колонка, min-height:100dvh)
содержит ровно два flex-потомка - .app-scroll (flex:1, единственный
реально скроллящийся элемент, весь контент сайта внутри) и .clusterbar
(flex:0 0 auto, ПОСЛЕДНИЙ потомок, обычный элемент потока - не
position:fixed и не position:sticky). Синхронизация с реальной видимой
областью полностью на стороне браузера (100dvh - нативная единица,
тот же рендер-пайплайн, что и анимация панели браузера), без JS
посередине вообще.
"""
import re
from pathlib import Path
from html.parser import HTMLParser

REPO_ROOT = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
APP_EARLY_JS = REPO_ROOT / "js" / "app-early.js"
APP_MAIN_JS = REPO_ROOT / "js" / "app-main.js"


def _css_rule_body(selector: str) -> str:
    html = INDEX_HTML.read_text(encoding="utf-8")
    pattern = re.escape(selector) + r"\s*\{([^}]*)\}"
    m = re.search(pattern, html)
    assert m, f"{selector} CSS-правило не найдено"
    return m.group(1)


class TestAppShellCSS:

    def test_app_shell_is_flex_column_with_dvh(self):
        rule = _css_rule_body(".app-shell")
        normalized = re.sub(r"\s+", "", rule)
        assert "display:flex" in normalized
        assert "flex-direction:column" in normalized
        assert "min-height:100dvh" in normalized

    def test_app_scroll_is_the_scrolling_flex_child(self):
        rule = _css_rule_body(".app-scroll")
        normalized = re.sub(r"\s+", "", rule)
        assert "flex:1" in normalized
        assert "overflow-y:auto" in normalized

    def test_clusterbar_is_no_longer_fixed_or_sticky(self):
        """
        Ключевое условие структурного фикса - .clusterbar больше НЕ
        position:fixed и НЕ position:sticky, обычный flex-потомок.
        """
        rule = _css_rule_body(".clusterbar")
        normalized = re.sub(r"\s+", "", rule)
        assert "position:fixed" not in normalized, (
            ".clusterbar снова position:fixed - структурный фикс требует, "
            "чтобы это был обычный flex-потомок .app-shell, не позиционированный элемент"
        )
        assert "position:sticky" not in normalized
        assert "flex:0" in normalized or "flex:00auto" in normalized


class TestAppShellHTMLStructure:

    def test_full_html_tag_balance(self):
        """
        Реструктуризация переместила три крупных блока (sitemap-overlay,
        re-detail-overlay, clusterbar) - проверяем баланс тегов настоящим
        парсером на ВСЁМ файле, не только визуально.
        """
        html = INDEX_HTML.read_text(encoding="utf-8")
        VOID_ELEMENTS = {"br", "img", "input", "hr", "meta", "link"}

        class BalanceChecker(HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack = []
                self.errors = []

            def handle_starttag(self, tag, attrs):
                if tag not in VOID_ELEMENTS:
                    self.stack.append((tag, self.getpos()))

            def handle_endtag(self, tag):
                if not self.stack:
                    self.errors.append(f"empty stack at {self.getpos()} for </{tag}>")
                    return
                expected_tag, pos = self.stack[-1]
                if expected_tag == tag:
                    self.stack.pop()
                else:
                    # известные, пред-существующие (не связанные с этой
                    # реструктуризацией) особенности парсинга - не считаем
                    # ошибкой, но ВСЁ РАВНО восстанавливаем стек тем же
                    # способом, что и для настоящих несовпадений - иначе
                    # рассинхронизация каскадно даёт ложные ошибки дальше
                    is_known_quirk = tag in ("input", "colgroup")
                    if not is_known_quirk:
                        self.errors.append(f"mismatch at {self.getpos()}: expected </{expected_tag}>, got </{tag}>")
                    for i in range(len(self.stack) - 1, -1, -1):
                        if self.stack[i][0] == tag:
                            self.stack = self.stack[:i]
                            break

        checker = BalanceChecker()
        checker.feed(html)
        assert not checker.stack, f"Незакрытые теги: {checker.stack}"
        assert not checker.errors, f"Несовпадения тегов: {checker.errors}"

    def test_header_and_sections_are_inside_app_scroll(self):
        """
        header и все <section> вкладок должны физически находиться МЕЖДУ
        открытием .app-scroll и его закрытием - иначе они не будут
        реально скроллиться внутри контейнера.
        """
        html = INDEX_HTML.read_text(encoding="utf-8")
        scroll_start = html.index('<div class="app-scroll">')
        scroll_end = html.index('</div><!-- /.app-scroll -->')
        scroll_content = html[scroll_start:scroll_end]

        assert "<header>" in scroll_content
        # хотя бы несколько ключевых вкладок должны быть внутри
        for tab_id in ("tab-home", "tab-theory", "tab-market", "tab-tech"):
            assert f'id="{tab_id}"' in scroll_content, f"{tab_id} не найден внутри .app-scroll"

    def test_clusterbar_is_sibling_of_app_scroll_not_inside_it(self):
        """
        .clusterbar должна быть ПОСЛЕ закрытия .app-scroll (сестра, не
        потомок) - иначе она будет скроллиться вместе с контентом, а не
        оставаться видимой всегда.
        """
        html = INDEX_HTML.read_text(encoding="utf-8")
        scroll_end = html.index('</div><!-- /.app-scroll -->')
        clusterbar_pos = html.index('<div class="clusterbar">')
        shell_end = html.index('</div><!-- /.app-shell -->')
        assert scroll_end < clusterbar_pos < shell_end, (
            ".clusterbar должна быть между закрытием .app-scroll и закрытием .app-shell "
            "(сестра .app-scroll, последний flex-потомок .app-shell)"
        )

    def test_fullscreen_overlays_are_outside_app_shell(self):
        """
        Полноэкранные оверлеи (карта сайта, детали движка) - position:fixed,
        не зависят от структуры .app-shell/.app-scroll - должны остаться
        снаружи, не внутри .app-scroll (где они больше не нужны и могли бы
        случайно попасть под flex-раскладку).
        """
        html = INDEX_HTML.read_text(encoding="utf-8")
        scroll_start = html.index('<div class="app-scroll">')
        scroll_end = html.index('</div><!-- /.app-scroll -->')
        scroll_content = html[scroll_start:scroll_end]
        assert 'class="sitemap-overlay"' not in scroll_content
        assert 'class="re-detail-overlay"' not in scroll_content


class TestScrollListenersRetargeted:

    def test_inst_sticky_top_listens_on_app_scroll(self):
        """
        window.addEventListener('scroll', ...) для sticky-заголовков таблиц
        должен быть переориентирован на .app-scroll - иначе перестанет
        срабатывать (или сработает лишь частично) после структурного фикса.
        """
        src = APP_EARLY_JS.read_text(encoding="utf-8")
        assert "querySelector('.app-scroll')" in src
        assert "appScrollEl.addEventListener('scroll'" in src

    def test_scroll_to_top_helper_targets_app_scroll(self):
        """
        window.scrollTo(0,0) для сброса позиции при переходе на новую
        вкладку больше не действует на реальную прокрутку - должен
        использоваться общий хелпер, целящийся в .app-scroll.
        """
        src = APP_MAIN_JS.read_text(encoding="utf-8")
        assert "function scrollAppToTop()" in src
        assert "appScroll.scrollTo(0, 0)" in src
        # все три реальных места использования переведены на хелпер
        assert src.count("scrollAppToTop();") >= 3


def test_no_leftover_visual_viewport_js():
    """
    Регрессия - четыре предыдущих JS-реактивных попытки (translateZ,
    dvh-на-body-само-по-себе, visualViewport-оверрайды) убраны полностью,
    заменены структурным решением. Ни одна не должна вернуться незаметно.
    """
    src = APP_EARLY_JS.read_text(encoding="utf-8")
    assert "updateClusterbarBottomOffset" not in src
    # вырезаем строчные комментарии перед проверкой - собственный
    # объясняющий комментарий упоминает visualViewport по имени как
    # часть истории находки, это не то же самое, что реальный код
    src_no_comments = re.sub(r"//[^\n]*", "", src)
    assert "visualViewport" not in src_no_comments, (
        "window.visualViewport вернулся в активный код (не в комментарии) - "
        "см. историю четырёх неудачных JS-реактивных попыток 2026-08-03"
    )
