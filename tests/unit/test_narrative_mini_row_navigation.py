"""
tests/unit/test_narrative_mini_row_navigation.py
Bitcoin Intel — regression: клик по свёрнутой строке "ещё нарративы" на
ОБЗОРЕ обязан вести к уже готовому синтезированному нарративу кластера
(вкладка ВСЕ НАРРАТИВЫ, renderClusterFullAnalytics()), не к сырому списку
сигналов (ДАЙДЖЕСТ) — 2026-08-18, найдено пользователем: "Переход приведет
на весь кластер целиком, пользователь не увидит именно главный нарратив,
ему придется листать все N сигналов" — противоречит самой цели механизма
синтеза (одна карточка вместо ручной реконструкции из сырых сигналов).
"""
import shutil
from pathlib import Path

import pytest
from tests.conftest import extract_js_function, run_node_js

REPO_ROOT = Path(__file__).parent.parent.parent
APP_MAIN_JS = REPO_ROOT / "js" / "app-main.js"
NODE_AVAILABLE = shutil.which("node") is not None


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
def test_go_to_narrative_shows_base_tab_and_scrolls_to_cluster_card():
    src = APP_MAIN_JS.read_text(encoding="utf-8")
    fn = extract_js_function(src, "goToNarrative")
    js = f"""
const calls = {{ showTab: null, scrolledCard: null }};
function showTab(id, btn) {{ calls.showTab = {{ id, btn }}; }}
const cards = {{
  'etf_institutional_flow': {{ scrollIntoView: function(opts) {{ calls.scrolledCard = {{ key: 'etf_institutional_flow', opts }}; }} }}
}};
const document = {{
  querySelector: function(sel) {{
    const m = sel.match(/data-cluster="([^"]+)"/);
    return m ? (cards[m[1]] || null) : null;
  }}
}};
{fn}
goToNarrative('etf_institutional_flow');
console.log(JSON.stringify(calls));
"""
    result = run_node_js(js)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"
    import json
    out = json.loads(result.stdout)
    assert out["showTab"] == {"id": "base", "btn": None}, (
        "goToNarrative() обязана открывать вкладку ВСЕ НАРРАТИВЫ (base), не ДАЙДЖЕСТ"
    )
    assert out["scrolledCard"]["key"] == "etf_institutional_flow"
    assert out["scrolledCard"]["opts"]["behavior"] == "smooth"


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
def test_go_to_narrative_does_nothing_if_card_not_found():
    """Кластер за пределами топ-3 и не попавший в 'остальные' (édge-case,
    напр. синтез ещё не готов) — не должно бросать исключение."""
    src = APP_MAIN_JS.read_text(encoding="utf-8")
    fn = extract_js_function(src, "goToNarrative")
    js = f"""
let shown = null;
function showTab(id, btn) {{ shown = id; }}
const document = {{ querySelector: function() {{ return null; }} }};
{fn}
goToNarrative('unknown_cluster');
console.log(JSON.stringify({{ shown }}));
"""
    result = run_node_js(js)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"
    import json
    out = json.loads(result.stdout)
    assert out["shown"] == "base"


def test_mini_row_click_wiring_uses_go_to_narrative_not_go_to_digest():
    """
    Структурная проверка исходника: обработчик клика на свёрнутых строках
    "ещё нарративы" обязан вызывать goToNarrative(), не goToDigest() — сама
    функция вызова живёт внутри renderDashboard() (замыкание), извлекать
    целиком непрактично, поэтому проверяется прямо по исходнику рядом с
    известным якорем (тем же принципом, что site_map/CLAUDE.md sync-тесты
    в этом проекте).
    """
    src = APP_MAIN_JS.read_text(encoding="utf-8")
    anchor = "miniListEl.querySelectorAll('[data-cl]').forEach(function(el) {"
    start = src.find(anchor)
    assert start != -1, "Обработчик клика по мини-строкам не найден — переименован?"
    end = src.find("});", start)
    handler_body = src[start:end]
    assert "goToNarrative(" in handler_body, (
        "Клик по свёрнутой строке нарратива обязан вести к синтезированному "
        "нарративу (goToNarrative), не к сырому списку сигналов (goToDigest)"
    )
    assert "goToDigest(" not in handler_body


def test_render_cluster_full_analytics_cards_have_data_cluster_attribute():
    """
    goToNarrative() ищет карточку по [data-cluster="key"] — обе секции
    (featured топ-3 и "остальные кластеры") обязаны проставлять этот
    атрибут, иначе клик по кластеру за пределами топ-3 не найдёт цель.
    """
    src = APP_MAIN_JS.read_text(encoding="utf-8")
    start = src.find("function renderClusterFullAnalytics()")
    assert start != -1
    end = src.find("\n// ── TABS ──", start)
    assert end != -1
    body = src[start:end]
    assert body.count("setAttribute('data-cluster'") == 2, (
        "Ожидались ровно 2 простановки data-cluster — featured-карточки и "
        "'остальные кластеры'; если структура функции изменилась, обнови "
        "этот тест осознанно, не просто подгони число"
    )
