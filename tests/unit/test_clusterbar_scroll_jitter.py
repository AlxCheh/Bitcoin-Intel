"""
tests/unit/test_clusterbar_scroll_jitter.py
Bitcoin Intel — регрессия на "мелькание" нижней навигации во время
активного скролла на мобильном (2026-08-03).

КОНТЕКСТ: пользователь сообщил, что .clusterbar (нижнее меню LIVE/
ECOSYSTEM/FUNDAMENTAL/ANALYSIS) перестало быть по-настоящему
стационарным - визуально дёргается/мелькает именно во время активного
скролла (не отклеивается насовсем). Классическая причина на мобильном
WebKit/Blink - position:fixed элемент без собственного композитного
GPU-слоя перерисовывается вместе с остальной страницей на каждый кадр
скролла. transform:translateZ(0) принудительно выносит его на отдельный
слой - стандартный, безопасный фикс именно для этого симптома.

Не проверяем реальную плавность скролла в браузере (для этого нужен
headless-браузер с профилированием рендера, которого в проекте
намеренно нет) - только статический факт: свойство присутствует и не
исчезнет незамеченным при будущей правке этого CSS-блока.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _clusterbar_rule_body() -> str:
    html = INDEX_HTML.read_text(encoding="utf-8")
    m = re.search(r"\.clusterbar\s*\{([^}]*)\}", html)
    assert m, ".clusterbar CSS-правило не найдено"
    return m.group(1)


def test_clusterbar_stays_position_fixed():
    """Базовое условие - панель должна оставаться реально фиксированной, не просто GPU-ускоренной."""
    rule_body = _clusterbar_rule_body()
    normalized = re.sub(r"\s+", "", rule_body)
    assert "position:fixed" in normalized


def test_clusterbar_has_gpu_layer_promotion():
    """
    Регрессия на находку 2026-08-03 - без собственного композитного слоя
    панель дёргается при активном скролле на мобильном.
    """
    rule_body = _clusterbar_rule_body()
    normalized = re.sub(r"\s+", "", rule_body)
    assert "transform:translateZ(0)" in normalized, (
        "transform:translateZ(0) отсутствует в .clusterbar - панель снова "
        "рискует мелькать/дёргаться при активном скролле на мобильных "
        "WebKit/Blink браузерах (см. находку 2026-08-03)"
    )
