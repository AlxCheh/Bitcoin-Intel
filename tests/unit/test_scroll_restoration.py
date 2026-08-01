"""
tests/unit/test_scroll_restoration.py
Bitcoin Intel — регрессионный тест на history.scrollRestoration = 'manual'
(2026-08-01).

КОНТЕКСТ: найдено пользователем на реальном скриншоте — после обновления
страницы контент виден, но обрезан посередине, под ним пустота ("надо
скроллить вверх"). Причина: нативное восстановление скролла браузером
(scrollRestoration='auto', дефолт) пытается вернуть точный пиксельный
оффсет с прошлого визита — но контент вкладки рендерится асинхронно (см.
PR #635), и итоговая высота страницы на момент восстановления не совпадает
с финальной. 'manual' должен стоять максимально рано — первым инлайн-
скриптом в <head>, до Chart.js/data/holders.js и тем более до
app-early.js/app-main.js (внешние файлы ждут сетевой запрос, отключать
восстановление скролла оттуда уже поздно).

Не тестируем реальное поведение браузера (для этого нужен headless-браузер,
которого в проекте намеренно нет — см. test_show_tab_resilience.py) —
только статический факт: строка присутствует и стоит раньше остальных
<script> тегов, чтобы будущая правка head не отодвинула её случайно вниз.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def test_scroll_restoration_manual_present():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "history.scrollRestoration = 'manual'" in html, (
        "history.scrollRestoration = 'manual' отсутствует в index.html — "
        "без неё браузер снова начнёт восстанавливать пиксельную позицию "
        "скролла асинхронно рендерящегося контента (см. PR за 2026-08-01)"
    )


def test_scroll_restoration_is_the_first_script_tag():
    """
    Должен стоять РАНЬШЕ Chart.js/data/holders.js и любых других <script> —
    иначе часть смысла фикса теряется (браузер уже мог применить
    восстановление, пока грузился более ранний скрипт).
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    scroll_restoration_pos = html.find("history.scrollRestoration = 'manual'")
    assert scroll_restoration_pos != -1

    first_script_open = html.find("<script")
    assert first_script_open != -1

    # Позиция строки должна попадать в САМЫЙ ПЕРВЫЙ <script>-тег документа —
    # т.е. между первым <script> и его закрывающим </script>, а не в каком-то
    # более позднем блоке.
    first_script_close = html.find("</script>", first_script_open)
    assert first_script_open < scroll_restoration_pos < first_script_close, (
        "history.scrollRestoration должен быть внутри самого первого "
        "<script> тега в <head> — до Chart.js/data/holders.js и других "
        "скриптов, иначе часть окна для гонки со встроенным восстановлением "
        "скролла браузера остаётся открытой"
    )


def test_scroll_restoration_guarded_by_feature_check():
    """
    'scrollRestoration' in history — старые браузеры без этого API не
    должны падать с ReferenceError на голом присваивании.
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "'scrollRestoration' in history" in html
