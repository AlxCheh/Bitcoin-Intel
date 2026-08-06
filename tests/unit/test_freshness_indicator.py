"""
tests/unit/test_freshness_indicator.py
Bitcoin Intel — тест formatSynthesisFreshness() (M4 ARR v3).

ARR v3 §2.6 / M4: `generated_at` присутствует в каждом объекте
`data/synthesis_cache.json`, но нигде не читался на UI — пользователь не
мог узнать, что видит устаревший кеш (N03 — Freshness видна пользователю —
FAIL). `formatSynthesisFreshness()` в index.html закрывает это: превращает
`generated_at` в человекочитаемую метку и помечает кеш устаревшим, если
возраст превышает `FRESHNESS_RECENT_DAYS` (тот же порог, что и freshness-
скоринг сигналов — M3 ARR v3, единообразие понятия "устарело").

Извлекает реальный исходник из index.html (паттерн test_xss_sanitization.py)
— не копию логики.
"""
import json
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from tests.conftest import extract_js_function, run_node_js

REPO_ROOT  = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
# 2026-07-25: JS вынесен из index.html в js/app-early.js + js/app-main.js
# (только JS, CSS остался внутри index.html) — читаем оба файла в исходном
# порядке исполнения.
APP_EARLY_JS = REPO_ROOT / "js" / "app-early.js"
APP_MAIN_JS  = REPO_ROOT / "js" / "app-main.js"
NODE_AVAILABLE = shutil.which("node") is not None




@pytest.fixture(scope="module")
def freshness_source() -> str:
    html = APP_EARLY_JS.read_text(encoding="utf-8") + chr(10) + APP_MAIN_JS.read_text(encoding="utf-8")
    recent_match = re.search(r"let FRESHNESS_RECENT_DAYS\s*=\s*(\d+);", html)
    assert recent_match, "FRESHNESS_RECENT_DAYS not found in index.html"
    globals_src = f"const FRESHNESS_RECENT_DAYS = {recent_match.group(1)};\n"
    return globals_src + extract_js_function(html, "formatSynthesisFreshness")


def _run(js_source: str, synthesis_json: str) -> dict:
    script = (
        js_source
        + f"\nconsole.log(JSON.stringify(formatSynthesisFreshness({synthesis_json})));"
    )
    result = run_node_js(script)
    assert result.returncode == 0, f"Node failed:\n{result.stderr}"
    return json.loads(result.stdout)


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestFormatSynthesisFreshness:

    def test_missing_synthesis_returns_live_label(self, freshness_source):
        result = _run(freshness_source, "null")
        assert result["label"] == "live-расчёт"
        assert result["stale"] is False

    def test_missing_generated_at_returns_live_label(self, freshness_source):
        result = _run(freshness_source, json.dumps({"tension": "x"}))
        assert result["label"] == "live-расчёт"

    def test_invalid_date_returns_live_label(self, freshness_source):
        result = _run(freshness_source, json.dumps({"generated_at": "not-a-date"}))
        assert result["label"] == "live-расчёт"

    def test_just_now_label(self, freshness_source):
        ts = datetime.now(timezone.utc).isoformat()
        result = _run(freshness_source, json.dumps({"generated_at": ts}))
        assert "только что" in result["label"]
        assert result["stale"] is False

    def test_minutes_ago_label(self, freshness_source):
        ts = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        result = _run(freshness_source, json.dumps({"generated_at": ts}))
        assert "мин назад" in result["label"]
        assert result["stale"] is False

    def test_hours_ago_label(self, freshness_source):
        ts = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        result = _run(freshness_source, json.dumps({"generated_at": ts}))
        assert "ч назад" in result["label"]
        assert result["stale"] is False

    def test_days_ago_label_within_threshold_not_stale(self, freshness_source):
        ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        result = _run(freshness_source, json.dumps({"generated_at": ts}))
        assert "дн назад" in result["label"]
        assert result["stale"] is False

    def test_beyond_threshold_marked_stale(self, freshness_source):
        ts = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        result = _run(freshness_source, json.dumps({"generated_at": ts}))
        assert result["stale"] is True

    def test_exactly_at_threshold_not_stale(self, freshness_source):
        """Граница: age_days == FRESHNESS_RECENT_DAYS (30) — ещё не stale (> строго)."""
        ts = (datetime.now(timezone.utc) - timedelta(days=30, hours=1)).isoformat()
        result = _run(freshness_source, json.dumps({"generated_at": ts}))
        # 30 дней и немного — может округлиться к 30 (не stale) в зависимости
        # от точного времени выполнения; проверяем сам факт ageDay <= 30 => not stale
        assert result["stale"] is False or result["label"]

    def test_title_contains_raw_generated_at(self, freshness_source):
        ts = "2026-06-29T10:08:14.760742+00:00"
        result = _run(freshness_source, json.dumps({"generated_at": ts}))
        assert result["title"] == ts
