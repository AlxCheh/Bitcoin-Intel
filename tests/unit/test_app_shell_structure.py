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
import json
import re
import shutil
import subprocess
from pathlib import Path
from html.parser import HTMLParser

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
APP_EARLY_JS = REPO_ROOT / "js" / "app-early.js"
APP_MAIN_JS = REPO_ROOT / "js" / "app-main.js"


def _css_rule_body(selector: str) -> str:
    """
    Возвращает тело CSS-правила БЕЗ комментариев - объясняющие комментарии
    в этом файле нередко упоминают убранные/отклонённые значения по имени
    как часть истории находки (напр. "убран min-height:100dvh, теперь
    100svh") - без вырезания комментариев проверки "X не должен
    встречаться" ложно срабатывают на собственном же объясняющем тексте.
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    pattern = re.escape(selector) + r"\s*\{([^}]*)\}"
    m = re.search(pattern, html)
    assert m, f"{selector} CSS-правило не найдено"
    return re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)


class TestAppShellCSS:

    def test_app_shell_is_flex_column_with_svh(self):
        """
        2026-08-03 (второй раунд структурного фикса): переключено с dvh на
        svh - dvh не пересчитывался плавно синхронно с анимацией панели
        браузера на части устройств (широко задокументированная проблема,
        не специфичная для этого проекта - см. комментарий в CSS), меню
        периодически "залипало" до явного взаимодействия. svh - статичное
        значение (худший случай, панель браузера всегда считается
        показанной) - не пытается динамически догонять анимацию, поэтому
        нечему рассинхронизироваться.
        """
        rule = _css_rule_body(".app-shell")
        normalized = re.sub(r"\s+", "", rule)
        assert "display:flex" in normalized
        assert "flex-direction:column" in normalized
        assert "height:100svh" in normalized

    def test_app_shell_does_not_use_dvh(self):
        """
        Регрессия - dvh не должен вернуться без явного, осознанного
        решения (см. находку про залипание/рассинхронизацию выше).
        """
        rule = _css_rule_body(".app-shell")
        normalized = re.sub(r"\s+", "", rule)
        assert "100dvh" not in normalized, (
            "100dvh вернулась в .app-shell - если это осознанное решение "
            "попробовать снова (напр. после исправления браузерами известного "
            "бага пересчёта), обнови этот тест явно вместе с изменением"
        )

    def test_app_shell_uses_height_not_min_height_for_dvh(self):
        """
        Регрессия на реальный, подтверждённый через headless-браузер баг
        (2026-08-03) - min-height задаёт только МИНИМУМ, не потолок.
        Контент .app-scroll (все вкладки) естественно выше 100dvh -
        .app-shell с min-height честно рос под этот контент вместо того,
        чтобы остаться ровно 100dvh и заставить .app-scroll включить свой
        внутренний overflow-y:auto. Результат: .clusterbar рендерилась
        корректно (не display:none, не нулевой высоты), но на 200+px ниже
        видимой области - пользователь описал это как "меню отсутствует".
        Playwright-тест (реальный Chromium) подтвердил: с height (не
        min-height) .app-shell === window.innerHeight ровно, .clusterbar
        остаётся в видимой области при любой прокрутке .app-scroll.
        """
        rule = _css_rule_body(".app-shell")
        normalized = re.sub(r"\s+", "", rule)
        assert "min-height:100dvh" not in normalized and "min-height:100svh" not in normalized, (
            "min-height вместо height вернулась в .app-shell - "
            "контейнер снова сможет расти выше видимой области под давлением "
            "контента .app-scroll, .clusterbar снова окажется ниже экрана "
            "(см. находку 2026-08-03, подтверждено реальным Playwright-рендером)"
        )

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


# ─── Реальный рендер через Playwright (2026-08-03) ──────────────────────
# Найдено: в этой среде разработки установлен настоящий Chromium
# (/opt/pw-browsers/) через playwright, вопреки более раннему допущению
# в других тестах "headless-браузера в проекте намеренно нет". Именно
# реальный рендер (не статический анализ CSS) поймал реальный баг -
# min-height:100dvh на .app-shell позволяла контейнеру расти ВЫШЕ
# видимой области под давлением контента .app-scroll, .clusterbar
# оказывалась на 200+px ниже экрана при видимом (не display:none)
# состоянии - статический CSS-анализ такое не ловит в принципе, только
# реальные computed-размеры после реального рендера.
#
# Тест опционален (пропускается, если playwright/chromium недоступны -
# напр. в CI, где playwright не в requirements.txt) - для CI остаётся
# статическая проверка выше (test_app_shell_uses_height_not_min_height_for_dvh),
# этот тест - дополнительная, более сильная гарантия для локальной разработки.
try:
    from playwright.sync_api import sync_playwright
    import glob
    _chromium_paths = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")
    PLAYWRIGHT_AVAILABLE = bool(_chromium_paths)
    _CHROMIUM_PATH = _chromium_paths[0] if _chromium_paths else None
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    _CHROMIUM_PATH = None


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright/Chromium недоступны в этой среде")
class TestAppShellRealRender:

    def test_clusterbar_stays_within_viewport_after_real_render(self, tmp_path):
        """
        Реальный рендер (не статический анализ) - .app-shell не должна
        визуально превышать высоту viewport, .clusterbar обязана
        оставаться внутри видимой области. Локальный HTTP-сервер вместо
        file:// - относительные fetch() к JSON-файлам сайта требуют
        HTTP-контекста, не файлового.
        """
        import http.server
        import socketserver
        import threading

        handler = http.server.SimpleHTTPRequestHandler
        original_cwd = str(REPO_ROOT)

        class Handler(handler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=original_cwd, **kwargs)
            def log_message(self, *args):
                pass  # без лишнего вывода в лог теста

        # порт 0 - ОС сама выбирает свободный эфемерный порт, не завязываемся
        # на конкретный номер (устойчиво к повторным запускам без ожидания
        # освобождения сокета от предыдущего прогона)
        httpd = socketserver.TCPServer(("", 0), Handler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=_CHROMIUM_PATH)
                page = browser.new_page(viewport={"width": 390, "height": 844})
                page.goto(f"http://localhost:{port}/index.html", wait_until="load", timeout=15000)
                page.wait_for_timeout(1000)

                shell_height = page.evaluate(
                    "() => document.querySelector('.app-shell').getBoundingClientRect().height"
                )
                bar_rect = page.evaluate(
                    "() => document.querySelector('.clusterbar').getBoundingClientRect()"
                )
                viewport_height = page.evaluate("() => window.innerHeight")

                browser.close()
        finally:
            httpd.shutdown()

        # 4px допуск - известный, пред-существующий отступ под декоративную
        # градиентную полосу сверху страницы (position:fixed;top:0, высота
        # 4px) + такой же по высоте spacer-div ПЕРЕД .app-shell в обычном
        # потоке - сдвигает всю страницу на эти 4px вниз, не связано с
        # данным структурным фиксом, было так и до него.
        KNOWN_TOP_SPACER_PX = 4
        assert shell_height <= viewport_height + KNOWN_TOP_SPACER_PX, (
            f".app-shell высотой {shell_height}px превышает viewport {viewport_height}px "
            f"(с учётом известного отступа {KNOWN_TOP_SPACER_PX}px) - "
            f"min-height вместо height могла вернуться (см. находку 2026-08-03)"
        )
        assert bar_rect["bottom"] <= viewport_height + KNOWN_TOP_SPACER_PX, (
            f".clusterbar (bottom={bar_rect['bottom']}) выходит за пределы видимой области "
            f"({viewport_height}px + известный отступ {KNOWN_TOP_SPACER_PX}px) - "
            f"меню невидимо без скролла всей страницы"
        )
        assert bar_rect["top"] >= 0


# ─── Одноразовая коррекция начальной высоты (2026-08-03, продолжение) ───
class TestInitialHeightCorrection:
    """
    Пользователь описал точный, воспроизводимый симптом: меню
    "полускрыто" именно на СВЕЖЕЙ загрузке страницы, до первого реального
    скролл-взаимодействия. Первая версия фикса (once:true на первый
    scroll) сняла необходимость доскролливать именно до конца - хватало
    любого свайпа - но не решила саму суть жалобы: между загрузкой и
    первым взаимодействием пользователь всё равно видел сломанное
    состояние. Финальная версия - тройная защита: немедленный
    синхронный вызов + двойной requestAnimationFrame + прежний
    once-слушатель как последняя страховка - корректирует высоту ДО
    первой видимой отрисовки, без участия пользователя вообще.
    """

    def test_correction_function_exists_and_sets_app_shell_height(self):
        src = APP_EARLY_JS.read_text(encoding="utf-8")
        assert "function correctInitialAppShellHeight()" in src
        assert "appShell.style.height = window.innerHeight + 'px'" in src

    def test_correction_called_immediately_not_only_on_interaction(self):
        """
        Регрессия на находку "фикс снимает симптом, но не саму жалобу" -
        функция обязана вызываться СРАЗУ (синхронно), не только через
        слушатель события, ожидающий действия пользователя.
        """
        src = APP_EARLY_JS.read_text(encoding="utf-8")
        assert re.search(r"^correctInitialAppShellHeight\(\);\s*$", src, re.MULTILINE), (
            "Немедленный синхронный вызов correctInitialAppShellHeight() отсутствует - "
            "без него коррекция сработает только по взаимодействию пользователя, "
            "оставляя видимое сломанное состояние на загрузке (см. находку 2026-08-03)"
        )

    def test_double_raf_present(self):
        """Двойной requestAnimationFrame - страховка на случай, если немедленный синхронный вызов застаёт неустоявшееся значение."""
        src = APP_EARLY_JS.read_text(encoding="utf-8")
        normalized = re.sub(r"\s+", "", src)
        assert "requestAnimationFrame(function(){requestAnimationFrame(correctInitialAppShellHeight);})" in normalized

    def test_listener_uses_once_true_not_continuous_tracking(self):
        """
        Регрессия на класс ошибки четырёх предыдущих провалившихся
        попыток - НЕ должно быть непрерывного отслеживания (once:true
        обязателен, иначе это снова "покадровая погоня").
        """
        src = APP_EARLY_JS.read_text(encoding="utf-8")
        m = re.search(
            r"addEventListener\('scroll',\s*correctInitialAppShellHeight,\s*\{([^}]*)\}\)",
            src
        )
        assert m, "Регистрация слушателя correctInitialAppShellHeight не найдена"
        options = m.group(1)
        assert "once:true" in re.sub(r"\s+", "", options), (
            "once:true отсутствует - без него это снова непрерывное отслеживание "
            "каждого scroll-события, тот же класс проблемы, что уже провалился "
            "четыре раза (см. историю 2026-08-03)"
        )

    def test_listener_attached_to_app_scroll_not_window(self):
        """
        Слушатель должен быть на .app-scroll (реальный скроллящийся
        элемент после структурного фикса), не на window - иначе может
        вообще не сработать.
        """
        src = APP_EARLY_JS.read_text(encoding="utf-8")
        assert "scrollElForInitFix = document.querySelector('.app-scroll')" in src
        assert "scrollElForInitFix.addEventListener('scroll', correctInitialAppShellHeight" in src

    @pytest.mark.skipif(not shutil.which("node"), reason="Node.js не найден в PATH")
    def test_correction_logic_sets_correct_pixel_height(self):
        """Проверка самой логики через минимальный DOM-мок - не полагаемся только на текстовые grep-проверки."""
        src = APP_EARLY_JS.read_text(encoding="utf-8")
        start = src.index("function correctInitialAppShellHeight()")
        brace_open = src.index("{", start)
        depth, i = 0, brace_open
        while i < len(src):
            if src[i] == "{":
                depth += 1
            elif src[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        fn_source = src[start:i + 1]

        js = f"""
const appShellEl = {{ style: {{ height: '' }} }};
const document = {{ querySelector: (sel) => sel === '.app-shell' ? appShellEl : null }};
window = {{ innerHeight: 812 }};
{fn_source}
correctInitialAppShellHeight();
console.log(JSON.stringify({{ height: appShellEl.style.height }}));
"""
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        assert json.loads(result.stdout)["height"] == "812px"
