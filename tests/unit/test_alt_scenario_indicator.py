"""
tests/unit/test_alt_scenario_indicator.py
Bitcoin Intel — тесты отбора и отрисовки alternative_scenario (AD-4, BAMS Р8).

КОНТЕКСТ
--------
BAMS Р8 требует полноценный альтернативный сценарий, когда уверенность вывода
НИЖЕ ВЫСОКОЙ. ADR-015 (2026-07-04) закрыла AD-4 только частично: поле
`alternative_scenario` на уровне сигнала добавили, а отбор в карточке
отложили — формальной границы «уверенность не высокая» не существовало, и
изобретать временный порог означало бы повторить ошибку, уже отклонённую
ADR-011.

Граница появилась вместе с закрытием AD-1 (`confidence_tier`,
config/settings.py, 2026-08-15) — эта пара тестов покрывает вторую половину
AD-4: Python отбирает (_select_alternative_scenario), JS отрисовывает
(buildAltScenarioHtml).

РАЗДЕЛЕНИЕ ОТВЕТСТВЕННОСТИ (важно при правках)
-----------------------------------------------
Решение «показывать или нет» принимает ТОЛЬКО Python: при confidence_tier
== "high" он возвращает пустую строку, и JS просто не находит что рисовать.
JS не дублирует логику отбора и не проверяет tier сам — тот же принцип, что
уже действует для uncertainty (см. комментарий в app-main.js). Тест
test_high_tier_yields_nothing_to_render ниже фиксирует именно этот контракт.
"""
import json
import shutil
from pathlib import Path

import pytest

from scripts.synthesizer import _select_alternative_scenario
from tests.conftest import extract_js_function, run_node_js

REPO_ROOT    = Path(__file__).parent.parent.parent
APP_EARLY_JS = REPO_ROOT / "js" / "app-early.js"
APP_MAIN_JS  = REPO_ROOT / "js" / "app-main.js"
NODE_AVAILABLE = shutil.which("node") is not None


def _sig(sid: str, scenario: str = "") -> dict:
    s = {"id": sid}
    if scenario:
        s["alternative_scenario"] = scenario
    return s


# ═══════════════════════════════════════════════════════════════════════
# Python: отбор (_select_alternative_scenario)
# ═══════════════════════════════════════════════════════════════════════

class TestSelectAlternativeScenario:

    def test_high_tier_never_selects_even_when_scenarios_exist(self):
        """
        BAMS Р8 привязывает требование к уверенности НИЖЕ высокой — при high
        сценарий не показывается, даже если у сигналов он написан. Это не
        оптимизация, а соответствие методологии.
        """
        anchor = _sig("A-1", "Сценарий у якоря")
        text, source = _select_alternative_scenario(anchor, [anchor], "high")
        assert text == ""
        assert source == ""

    def test_takes_from_anchor_when_anchor_has_scenario(self):
        anchor = _sig("A-1", "Сценарий якоря")
        other  = _sig("B-2", "Сценарий другого сигнала")
        text, source = _select_alternative_scenario(anchor, [anchor, other], "low")
        assert text == "Сценарий якоря"
        assert source == "A-1"

    def test_falls_back_to_next_ranked_signal_when_anchor_has_none(self):
        """
        Реальный кейс layer2_programmability (корпус 2026-08-15): у anchor
        INF-2026-0609-001 поля нет, у INF-2026-0706-001 есть. Строгий
        «только anchor» потерял бы этот кластер целиком.
        """
        anchor = _sig("A-1")
        first  = _sig("B-2", "Сценарий первого по рангу")
        second = _sig("C-3", "Сценарий второго по рангу")
        text, source = _select_alternative_scenario(anchor, [anchor, first, second], "low")
        assert text == "Сценарий первого по рангу"
        assert source == "B-2"

    def test_returns_empty_when_no_signal_has_scenario(self):
        anchor = _sig("A-1")
        text, source = _select_alternative_scenario(anchor, [anchor, _sig("B-2")], "low")
        assert text == ""
        assert source == ""

    def test_medium_tier_also_selects(self):
        """«Ниже высокой» — это и medium, и low, не только low."""
        anchor = _sig("A-1", "Сценарий")
        text, _ = _select_alternative_scenario(anchor, [anchor], "medium")
        assert text == "Сценарий"

    def test_whitespace_only_scenario_treated_as_empty(self):
        """Пробельная строка не должна давать пустой блок в карточке."""
        anchor = _sig("A-1", "   \n  ")
        real   = _sig("B-2", "Настоящий сценарий")
        text, source = _select_alternative_scenario(anchor, [anchor, real], "low")
        assert text == "Настоящий сценарий"
        assert source == "B-2"

    def test_anchor_none_still_scans_ranked_signals(self):
        """DEGRADE GRACEFULLY: отсутствие anchor не должно ронять отбор."""
        text, source = _select_alternative_scenario(None, [_sig("B-2", "Сценарий")], "low")
        assert text == "Сценарий"
        assert source == "B-2"

    def test_anchor_not_duplicated_in_candidates(self):
        """
        anchor добавляется в начало списка кандидатов и не должен
        рассматриваться повторно из ranked_signals — иначе при пустом
        сценарии у anchor он бы проверялся дважды впустую.
        """
        anchor = _sig("A-1")
        other  = _sig("B-2", "Сценарий другого")
        text, source = _select_alternative_scenario(anchor, [anchor, other], "low")
        assert source == "B-2"


# ═══════════════════════════════════════════════════════════════════════
# JS: отрисовка (buildAltScenarioHtml)
# ═══════════════════════════════════════════════════════════════════════

def _run(js_source: str, call: str):
    script = js_source + f"\nconsole.log(JSON.stringify({call}));"
    result = run_node_js(script)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def alt_scenario_source() -> str:
    """buildAltScenarioHtml зависит от sanitize() — извлекаем обе функции."""
    src = APP_EARLY_JS.read_text(encoding="utf-8") + chr(10) + APP_MAIN_JS.read_text(encoding="utf-8")
    return (
        extract_js_function(src, "sanitize")
        + chr(10)
        + extract_js_function(src, "buildAltScenarioHtml")
    )


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestBuildAltScenarioHtml:

    def test_no_synthesis_renders_nothing(self, alt_scenario_source):
        assert _run(alt_scenario_source, "buildAltScenarioHtml(null)") == ""
        assert _run(alt_scenario_source, "buildAltScenarioHtml(undefined)") == ""

    def test_high_tier_yields_nothing_to_render(self, alt_scenario_source):
        """
        Контракт разделения ответственности: при high Python кладёт пустую
        строку, JS ничего не рисует. JS НЕ проверяет tier сам — если кто-то
        в будущем начнёт передавать сюда непустой сценарий при high, это
        ошибка Python-слоя, и ловить её надо там (см. TestSelect... выше).
        """
        result = _run(
            alt_scenario_source,
            "buildAltScenarioHtml({confidence_tier: 'high', alternative_scenario: ''})",
        )
        assert result == ""

    def test_missing_field_renders_nothing(self, alt_scenario_source):
        """JS live-фоллбэк не считает alternative_scenario — отсутствие поля не должно падать."""
        result = _run(alt_scenario_source, "buildAltScenarioHtml({tension: 'X vs Y'})")
        assert result == ""

    def test_whitespace_only_renders_nothing(self, alt_scenario_source):
        result = _run(alt_scenario_source, "buildAltScenarioHtml({alternative_scenario: '   '})")
        assert result == ""

    def test_renders_label_and_text(self, alt_scenario_source):
        result = _run(
            alt_scenario_source,
            "buildAltScenarioHtml({alternative_scenario: 'Если протокол не запустится вовремя'})",
        )
        assert "ЕСЛИ ИНТЕРПРЕТАЦИЯ НЕВЕРНА" in result
        assert "Если протокол не запустится вовремя" in result
        assert "dash-narrative-alt-scenario" in result

    def test_text_is_sanitized(self, alt_scenario_source):
        """
        Тот же контракт, что проверяет test_xss_sanitization.py для остальных
        текстовых полей сигнала — сценарий приходит из signals.json, значит
        обязан проходить через sanitize().
        """
        result = _run(
            alt_scenario_source,
            "buildAltScenarioHtml({alternative_scenario: '<script>alert(1)</script>'})",
        )
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
