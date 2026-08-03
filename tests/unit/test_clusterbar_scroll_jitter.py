"""
tests/unit/test_clusterbar_scroll_jitter.py
Bitcoin Intel — .clusterbar (нижнее меню LIVE/ECOSYSTEM/FUNDAMENTAL/
ANALYSIS), история находки и отката (2026-08-03).

ИСТОРИЯ: пользователь сообщил о "мелькании"/"дёрганье" панели и уезжании
под панель мобильного браузера. Последовательно испробованы четыре
фикса за один день: transform:translateZ(0) (GPU-слой),
body{min-height:100dvh}, JS-оверрайд через window.visualViewport,
CSS transition сглаживающий этот оверрайд. Ни один не решил проблему
до конца, а пользователь прямо указал: "раньше всё было идеально" - до
ЛЮБЫХ из этих фиксов простой CSS (position:fixed;bottom:0) работал
корректно сам по себе.

Все четыре надстройки убраны полностью 2026-08-03 - .clusterbar
вернулась к исходному, минимальному виду. Если проблема воспроизводится
и на этой версии - причина не в самой .clusterbar, и её стоит искать
в другом месте (см. историю коммитов для полного списка испробованного
и откаченного).
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
    """Базовое условие - панель должна оставаться реально фиксированной."""
    rule_body = _clusterbar_rule_body()
    normalized = re.sub(r"\s+", "", rule_body)
    assert "position:fixed" in normalized


def test_clusterbar_has_no_leftover_experimental_overrides():
    """
    Регрессия на неполный откат - ни один из четырёх испробованных и
    отвергнутых фиксов (translateZ, backface-visibility, transition,
    JS bottom-оверрайд) не должен незаметно вернуться без явного,
    осознанного решения повторить попытку.
    """
    rule_body = _clusterbar_rule_body()
    normalized = re.sub(r"\s+", "", rule_body)
    leftovers = [
        prop for prop in ("transform:translateZ", "backface-visibility", "transition:bottom")
        if prop in normalized
    ]
    assert not leftovers, (
        f"Найдены остатки откаченных 2026-08-03 экспериментов в .clusterbar: {leftovers} - "
        f"если это осознанное повторное решение, а не случайный откат отката, "
        f"обнови этот тест явно вместе с изменением"
    )
