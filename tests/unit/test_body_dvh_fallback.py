"""
tests/unit/test_body_dvh_fallback.py
Bitcoin Intel — регрессия на 100dvh-фолбэк для body (2026-08-03).

КОНТЕКСТ: пользователь показал скриншот, где .clusterbar (position:fixed;
bottom:0) визуально взаимодействует с собственной динамической нижней
панелью мобильного браузера (Chrome Android). Первый фикс
(transform:translateZ(0), см. test_clusterbar_scroll_jitter.py) не помог -
причина оказалась не в композитинге, а в том, что body { min-height:
100vh } считает высоту от "большого" viewport (панели браузера всегда
скрыты по этому определению), не от фактически видимой области, которая
меняется в реальном времени вместе с показом/скрытием панелей браузера.

100dvh (Baseline Widely Available с июня 2025) отслеживает реальный
видимый viewport. 100vh оставлен как фолбэк для браузеров без поддержки
dvh - порядок объявлений важен (dvh должен идти ПОСЛЕ vh, чтобы
переопределить его там, где понимается, и не сломать старые браузеры,
которые просто проигнорируют непонятную единицу).
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _body_rule_body() -> str:
    html = INDEX_HTML.read_text(encoding="utf-8")
    m = re.search(r"\bbody\s*\{([^}]*)\}", html)
    assert m, "body {} CSS-правило не найдено"
    return m.group(1)


def test_body_has_both_vh_and_dvh_min_height():
    rule_body = _body_rule_body()
    normalized = re.sub(r"\s+", "", rule_body)
    assert "min-height:100vh" in normalized, (
        "min-height:100vh (фолбэк для браузеров без поддержки dvh) отсутствует в body"
    )
    assert "min-height:100dvh" in normalized, (
        "min-height:100dvh отсутствует в body - без него высота body считается от "
        "'большого' viewport, не от фактически видимой области, и фиксированные "
        "элементы (.clusterbar) рискуют рассинхронизироваться с панелями мобильного "
        "браузера при их показе/скрытии (см. находку 2026-08-03)"
    )


def test_dvh_declared_after_vh_fallback():
    """Порядок важен - dvh должен идти ПОСЛЕ vh, чтобы корректно его переопределять."""
    rule_body = _body_rule_body()
    vh_pos = rule_body.find("100vh")
    dvh_pos = rule_body.find("100dvh")
    assert vh_pos != -1 and dvh_pos != -1
    assert vh_pos < dvh_pos, (
        "min-height:100dvh должен идти ПОСЛЕ min-height:100vh в исходнике - "
        "иначе fallback-декларация окажется последней и перекроет dvh в "
        "браузерах, которые его поддерживают"
    )
