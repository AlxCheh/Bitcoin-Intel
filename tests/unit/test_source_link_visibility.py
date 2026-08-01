"""
tests/unit/test_source_link_visibility.py
Bitcoin Intel — регрессия: ссылки в ИСТОЧНИК-подвале должны визуально
отличаться от декоративного текста (2026-08-01).

КОНТЕКСТ: найдено пользователем на реальном скриншоте — ссылка на
21ideas.org/dice-seed/ технически рендерилась как рабочий <a href>,
но text-decoration:none + тот же оранжевый (--btc), что у ДЕСЯТКОВ чисто
декоративных элементов на странице (заголовки, теги, рамки) — ничем не
отличалась от нередактируемого текста. Пользователь спросил "где ссылка"
про ссылку, которая физически была на экране и работала.

Не только моя правка (js/app-main.js, sourceFooterHtml) — тот же паттерн
"none" использовался в двух статичных ссылках в index.html. Все три
исправлены разом на тот же dotted-underline+offset, что уже применялся
для других кликабельных элементов сайта (halving-block-link,
treasury-panel-link) — не изобретён новый стиль, взят существующий.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
APP_MAIN_JS = REPO_ROOT / "js" / "app-main.js"


def _find_anchor_styles(html: str) -> list[str]:
    """Возвращает style-атрибуты всех <a ...> с color:var(--btc) в них."""
    styles = []
    for m in re.finditer(r'<a\s[^>]*style="([^"]*)"[^>]*>', html):
        if "color:var(--btc)" in m.group(1).replace(" ", ""):
            styles.append(m.group(1))
    return styles


def test_no_anchor_with_btc_color_lacks_underline_in_index_html():
    html = INDEX_HTML.read_text(encoding="utf-8")
    styles = _find_anchor_styles(html)
    assert styles, "Ожидались хотя бы статичные ссылки с color:var(--btc) в index.html"
    offenders = [s for s in styles if "text-decoration:none" in s.replace(" ", "")]
    assert not offenders, (
        f"Найдены ссылки с color:var(--btc) и text-decoration:none — визуально "
        f"неотличимы от декоративного оранжевого текста на странице: {offenders}"
    )


def test_source_footer_link_in_app_main_js_has_underline():
    """js/app-main.js — динамическая ссылка в renderAccItem()'s source footer."""
    src = APP_MAIN_JS.read_text(encoding="utf-8")
    m = re.search(r'target="_blank"\s+style="([^"]*color:var\(--btc\)[^"]*)"', src)
    assert m, "Динамическая ссылка на источник (target=\"_blank\", color:var(--btc)) не найдена"
    style = m.group(1).replace(" ", "")
    assert "text-decoration:none" not in style, (
        "Ссылка в ИСТОЧНИК-подвале снова визуально неотличима от декоративного "
        "текста (см. находку 2026-08-01, PR со сравнением 'где ссылка на статью?')"
    )
    assert "text-decoration:underline" in style
