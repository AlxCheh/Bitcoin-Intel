"""
tests/unit/test_ontology_settings_consistency.py
Bitcoin Intel — единый источник истины для freshness-порогов (M3 ARR v3).

КОНТЕКСТ
--------
ARR v3 §2.2 / M3: JS-скоринг в index.html использует пороги
`days<=7?3:days<=30?1:0`, которые ARR v3 посчитала расходящимися с
ontology.json (`fresh_days: 7, recent_days: 90`).

При реализации M3 выяснилось, что расхождение было ОБРАТНЫМ тому, что
предполагала ARR v3: JS-пороги (7/30) совпадали с РЕАЛЬНЫМ порогом
скоринга в Python — `config/settings.py.STALE_THRESHOLD = 30`, который
используется в `scripts/synthesizer.py::_freshness()`. Расходился сам
`ontology.json` (recent_days был 90, как WINDOW_DAYS_DEFAULT — другой,
несвязанный порог: окно включения сигнала в синтез, а не freshness-тир
внутри окна). `ontology.json` исправлен на 30/30.

Дальше M3 закрыт не точечной синхронизацией литералов, а структурно:
`index.html::loadSignals()` теперь загружает `ontology.json` в рантайме и
обновляет глобальные `FRESHNESS_FRESH_DAYS`/`FRESHNESS_RECENT_DAYS`,
которые читают оба места JS-скоринга. Хардкоженных литералов `<=7`/`<=30`
в местах freshness-скоринга в index.html больше нет — есть только дефолты
на случай недоступности `ontology.json` (DEGRADE GRACEFULLY), которые этот
файл проверяет на совпадение со `STALE_THRESHOLD`.

Этот тест — не разовая проверка, а страж против повторного дрейфа: любое
будущее изменение `STALE_THRESHOLD` в `settings.py` без синхронного
изменения `ontology.json` И JS-дефолтов теперь падает в CI, а не остаётся
незамеченным до следующего ARR (тот же класс риска, что и сам M3).
"""
import json
from pathlib import Path

from config.settings import STALE_THRESHOLD

REPO_ROOT    = Path(__file__).parent.parent.parent
ONTOLOGY_PATH = REPO_ROOT / "ontology.json"


def _load_ontology() -> dict:
    return json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))


def test_ontology_fresh_days_matches_freshness_scoring_breakpoint():
    """fresh_days в ontology.json == порог '<=7' в _freshness() (захардкожен в коде)."""
    ontology = _load_ontology()
    assert ontology["freshness_windows"]["fresh_days"] == 7, (
        "_freshness() в scripts/synthesizer.py использует литерал 7 — "
        "если меняешь, обнови и здесь, и в ontology.json синхронно"
    )


def test_ontology_recent_days_matches_stale_threshold():
    """
    recent_days/stale_after в ontology.json должны равняться STALE_THRESHOLD
    из config/settings.py — единственному месту в Python-коде, которое
    реально используется в _freshness() как порог 'recent' vs 'stale'.
    """
    ontology = _load_ontology()
    fw = ontology["freshness_windows"]
    assert fw["recent_days"] == STALE_THRESHOLD, (
        f"ontology.json.freshness_windows.recent_days={fw['recent_days']} != "
        f"config/settings.py.STALE_THRESHOLD={STALE_THRESHOLD} — это и есть "
        f"M3 ARR v3 drift. Обнови один из двух файлов, не игнорируй тест."
    )
    assert fw["stale_after"] == STALE_THRESHOLD


def test_js_reads_freshness_thresholds_from_ontology_json():
    """
    M3 ARR v3 (полное закрытие, не только тест-страж): index.html больше не
    хардкодит '<=7'/'<=30' в местах freshness-скоринга — вместо этого
    объявлены глобальные FRESHNESS_FRESH_DAYS/FRESHNESS_RECENT_DAYS с
    дефолтами, которые loadSignals() обновляет значениями из ontology.json
    при загрузке (DEGRADE GRACEFULLY на дефолтах, если fetch не удался).
    Дефолты всё ещё должны совпадать с STALE_THRESHOLD на случай, если
    ontology.json недоступен — иначе деградация будет тихо неверной.
    """
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")

    assert "let FRESHNESS_FRESH_DAYS  = 7;" in html or "let FRESHNESS_FRESH_DAYS = 7;" in html, (
        "FRESHNESS_FRESH_DAYS default missing or changed — "
        "should default to 7, matching ontology.json fresh_days"
    )
    assert "let FRESHNESS_RECENT_DAYS = 30;" in html, (
        f"FRESHNESS_RECENT_DAYS default должен совпадать с "
        f"STALE_THRESHOLD={STALE_THRESHOLD} на случай недоступности ontology.json"
    )
    assert "fetch('ontology.json" in html, (
        "loadSignals() должен загружать ontology.json — иначе FRESHNESS_* "
        "никогда не обновляются после дефолтов, и единый источник истины "
        "снова становится фикцией (M3 ARR v3)"
    )
    # Старые литералы-дубликаты больше не должны существовать ни в одном
    # из двух исторических мест (synthesizeNarrativeAdvanced и renderDashStatus
    # breakdown) — обе точки скоринга теперь читают переменные.
    assert "days <= 7 ? 3 : days <= 30 ? 1 : 0" not in html, (
        "Найден захардкоженный литерал freshness-скоринга — он должен был "
        "быть заменён на 'days <= FRESHNESS_FRESH_DAYS ? 3 : "
        "days <= FRESHNESS_RECENT_DAYS ? 1 : 0' (M3 ARR v3). Если это "
        "новое, третье место — добавь его в замену, не оставляй дубликат."
    )
    freshness_var_usages = html.count("days <= FRESHNESS_FRESH_DAYS")
    assert freshness_var_usages >= 2, (
        f"Ожидалось минимум 2 места использования FRESHNESS_FRESH_DAYS в "
        f"скоринге, найдено {freshness_var_usages}"
    )
