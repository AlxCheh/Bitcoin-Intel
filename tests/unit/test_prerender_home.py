"""
tests/unit/test_prerender_home.py
Bitcoin Intel — regression: scripts/prerender_home.py must inject a real,
readable snapshot of the top narrative between the PRERENDER:HOME markers
in index.html, so a crawler that doesn't execute JS still sees content —
see docs/superpowers/specs/2026-08-16-home-page-reorg-design.md Часть 2.4.
Same marker-replace principle as scripts/update_js_cache_bust.py.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def _write_fixture_files(tmp_path):
    synthesis_cache = {
        "btc_treasury_competition": {
            "tension": "трекер показывает рост баланса vs МВФ заявляет консолидацию",
            "narrative": "Казначейства эволюционируют от пассивного баланса к операционному движку.",
            "strength": "strong",
            "phase": "active",
            "generated_at": "2026-08-16T10:00:00Z"
        }
    }
    signals = [
        {"id": "STR-2026-0801-001", "cluster": "btc_treasury_competition", "dir": "pos",
         "date": "2026-08-15", "weight": "primary", "narrative_role": "trigger",
         "links": {"contradicts": ["STR-2026-0801-002"]}, "tension": "x"},
        {"id": "STR-2026-0801-002", "cluster": "btc_treasury_competition", "dir": "neg",
         "date": "2026-08-15", "weight": "media", "narrative_role": "complication",
         "links": {}, "tension": ""},
    ]
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "synthesis_cache.json").write_text(json.dumps(synthesis_cache), encoding="utf-8")
    (tmp_path / "signals.json").write_text(json.dumps({"signals": signals}), encoding="utf-8")
    index_html = tmp_path / "index.html"
    index_html.write_text(
        '<div id="dash-narratives-list">'
        '<!-- PRERENDER:HOME:START --><!-- PRERENDER:HOME:END -->'
        '</div>',
        encoding="utf-8",
    )
    return index_html


def test_prerender_writes_top_narrative_text_between_markers(tmp_path, monkeypatch):
    _write_fixture_files(tmp_path)
    monkeypatch.chdir(tmp_path)
    script = REPO_ROOT / "scripts" / "prerender_home.py"
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert result.returncode == 0, f"prerender_home.py failed:\n{result.stderr}"

    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    start = html.find("PRERENDER:HOME:START")
    end = html.find("PRERENDER:HOME:END")
    snapshot = html[start:end]
    assert "трекер показывает рост" in snapshot or "Казначейства" in snapshot, (
        "Снимок обязан содержать реальный текст топ-нарратива, не пустой"
    )


def test_prerender_is_idempotent_no_duplication_on_rerun(tmp_path, monkeypatch):
    _write_fixture_files(tmp_path)
    monkeypatch.chdir(tmp_path)
    script = REPO_ROOT / "scripts" / "prerender_home.py"
    subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=True)
    first = (tmp_path / "index.html").read_text(encoding="utf-8")
    subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=True)
    second = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert first == second, "Повторный прогон не должен дублировать/менять контент при неизменных данных"
    assert second.count("PRERENDER:HOME:START") == 1, "Маркер не должен задваиваться"
