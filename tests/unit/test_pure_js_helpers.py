"""
tests/unit/test_pure_js_helpers.py
Bitcoin Intel — тесты чистых JS-хелперов из index.html (JS-аудит, шаг 4.2).

Механика та же, что в test_xss_sanitization.py: извлекаем РЕАЛЬНЫЙ исходник
функции из index.html по балансу скобок и исполняем через Node.js — тестируется
именно задеплоенный код, а не отдельная копия логики.

Выбор функций — по карте покрытия 4.1 (JS_AUDIT_REPORT.md):
- calcTotalMined  — халвинг-математика эмиссии; протокольно-критичная.
  Контекст: предыдущая статичная версия этого расчёта в разметке молча
  разошлась с реальностью на ~1.1M BTC (Oct 2024 → July 2026).
- calcCyclePhase  — пороги фаз цикла на дашборде (ratio-границы);
  тест фиксирует границы: их сдвиг без осознанного решения ломает тест.
- ruPlural        — русские плюралы; классические ловушки 11–14, 21, 111.

Требует Node.js в PATH (доступен на GitHub Actions ubuntu-latest).
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"

NODE_AVAILABLE = shutil.which("node") is not None


def _extract_function(html: str, name: str) -> str:
    """Извлекает `function <name>(...) {...}` по балансу фигурных скобок."""
    start = html.find(f"function {name}")
    assert start != -1, f"Function '{name}' not found in index.html — renamed or removed?"
    brace_open = html.find("{", start)
    depth = 0
    i = brace_open
    while i < len(html):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                return html[start:i + 1]
        i += 1
    raise AssertionError(f"Unbalanced braces while extracting '{name}'")


def _run_js(js_code: str) -> dict:
    result = subprocess.run(
        ["node", "-e", js_code],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, f"Node execution failed:\n{result.stderr}"
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def html_source() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════
# calcTotalMined(height) — эмиссия по высоте блока
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def calc_total_mined_fn(html_source):
    return _extract_function(html_source, "calcTotalMined")


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestCalcTotalMined:

    @pytest.fixture
    def fn(self, calc_total_mined_fn):
        return calc_total_mined_fn

    def test_era_boundaries_exact(self, fn):
        """
        Точные протокольные значения на границах эр:
        эра 1 (210 000 блоков × 50) = 10 500 000;
        эра 2 (+210 000 × 25)       = 15 750 000;
        эра 3 (+210 000 × 12.5)     = 18 375 000.
        """
        js = fn + """
console.log(JSON.stringify({
  h0: calcTotalMined(0),
  era1: calcTotalMined(210000),
  era2: calcTotalMined(420000),
  era3: calcTotalMined(630000),
}));
"""
        r = _run_js(js)
        assert r["h0"] == 0
        assert r["era1"] == 10_500_000
        assert r["era2"] == 15_750_000
        assert r["era3"] == 18_375_000

    def test_never_exceeds_21m_cap(self, fn):
        """Асимптотический предел: даже на абсурдной высоте сумма < 21M."""
        js = fn + """
console.log(JSON.stringify({
  far: calcTotalMined(10_000_000),
  absurd: calcTotalMined(100_000_000),
}));
"""
        r = _run_js(js)
        assert r["far"] < 21_000_000
        assert r["absurd"] < 21_000_000
        # и при этом асимптотически близко к 21M
        assert r["absurd"] > 20_999_999

    def test_monotone_in_height(self, fn):
        """Больше блоков — не меньше монет (монотонность)."""
        js = fn + """
const hs = [1, 1000, 210000, 210001, 500000, 840000, 903000, 2000000];
const vals = hs.map(calcTotalMined);
console.log(JSON.stringify({ vals }));
"""
        r = _run_js(js)
        vals = r["vals"]
        assert all(a <= b for a, b in zip(vals, vals[1:])), vals

    def test_current_era_sanity(self, fn):
        """
        Высота ~903 000 (июль 2026, 5-я эра, награда 3.125):
        840 000 блоков первых 4 эр = 19 687 500;
        + 63 000 × 3.125 = 196 875 → 19 884 375.
        Согласуется с 'осталось добыть ~1.1M' из контекста в index.html.
        """
        js = fn + """
console.log(JSON.stringify({ v: calcTotalMined(903000) }));
"""
        r = _run_js(js)
        assert r["v"] == 19_884_375


# ═══════════════════════════════════════════════════════════════════════
# calcCyclePhase(price, prodCost) — фазы цикла на дашборде
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def calc_cycle_phase_fn(html_source):
    return _extract_function(html_source, "calcCyclePhase")


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestCalcCyclePhase:

    @pytest.fixture
    def fn(self, calc_cycle_phase_fn):
        return calc_cycle_phase_fn

    def test_phase_thresholds_and_segments(self, fn):
        """
        Фиксация порогов: <1.0 ДНО / <1.15 НАКОПЛЕНИЕ / <2.0 РОСТ / ≥2.0
        ЭЙФОРИЯ — включая точные значения НА границах (граница принадлежит
        верхней фазе: ratio=1.0 — уже НАКОПЛЕНИЕ, ratio=2.0 — уже ЭЙФОРИЯ).
        Сдвиг любого порога без осознанного решения ломает этот тест.
        """
        js = fn + """
const cases = [
  [99, 100], [100, 100], [114, 100], [115, 100],
  [199, 100], [200, 100], [1000, 100],
];
console.log(JSON.stringify(cases.map(([p, c]) => {
  const r = calcCyclePhase(p, c);
  return { ratio: p / c, phase: r.phase, seg: r.seg, cls: r.cls };
})));
"""
        r = _run_js(js)
        expected = [
            ("ДНО", 0, "danger"),        # 0.99
            ("НАКОПЛЕНИЕ", 1, ""),       # 1.00 — граница
            ("НАКОПЛЕНИЕ", 1, ""),       # 1.14
            ("РОСТ", 2, "warn"),         # 1.15 — граница
            ("РОСТ", 2, "warn"),         # 1.99
            ("ЭЙФОРИЯ", 3, "danger"),    # 2.00 — граница
            ("ЭЙФОРИЯ", 3, "danger"),    # 10.0
        ]
        for got, (phase, seg, cls) in zip(r, expected):
            assert got["phase"] == phase, got
            assert got["seg"] == seg, got
            assert got["cls"] == cls, got

    def test_missing_data_returns_loading(self, fn):
        """Нет цены или себестоимости → ЗАГРУЗКА, не исключение и не NaN-фаза."""
        js = fn + """
console.log(JSON.stringify({
  noPrice: calcCyclePhase(null, 100).phase,
  noCost: calcCyclePhase(100, 0).phase,
  none: calcCyclePhase(undefined, undefined).phase,
}));
"""
        r = _run_js(js)
        assert r["noPrice"] == "ЗАГРУЗКА..."
        assert r["noCost"] == "ЗАГРУЗКА..."
        assert r["none"] == "ЗАГРУЗКА..."


# ═══════════════════════════════════════════════════════════════════════
# ruPlural(n, one, few, many) — русские плюралы
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def ru_plural_fn(html_source):
    return _extract_function(html_source, "ruPlural")


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestRuPlural:

    @pytest.fixture
    def fn(self, ru_plural_fn):
        return ru_plural_fn

    def test_classic_traps(self, fn):
        """
        Полный набор ловушек: 11–14 — всегда 'many' (не 'one'/'few',
        несмотря на mod10); 21/22 — снова 'one'/'few'; 111 — 'many'.
        """
        js = fn + """
const f = n => ruPlural(n, 'сигнал', 'сигнала', 'сигналов');
const ns = [0, 1, 2, 4, 5, 10, 11, 12, 14, 15, 20, 21, 22, 24, 25, 100, 101, 102, 111, 112, 121, 122];
console.log(JSON.stringify(Object.fromEntries(ns.map(n => [n, f(n)]))));
"""
        r = _run_js(js)
        expected = {
            "0": "сигналов", "1": "сигнал", "2": "сигнала", "4": "сигнала",
            "5": "сигналов", "10": "сигналов",
            "11": "сигналов", "12": "сигналов", "14": "сигналов",  # ловушка 11–14
            "15": "сигналов", "20": "сигналов",
            "21": "сигнал", "22": "сигнала", "24": "сигнала",      # 2x — снова one/few
            "25": "сигналов",
            "100": "сигналов", "101": "сигнал", "102": "сигнала",
            "111": "сигналов", "112": "сигналов",                  # ловушка 111–114
            "121": "сигнал", "122": "сигнала",
        }
        assert r == expected, {k: (r[k], expected[k]) for k in expected if r[k] != expected[k]}
