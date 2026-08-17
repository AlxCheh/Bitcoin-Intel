"""
scripts/prerender_home.py
Bitcoin Intel — генерирует статический текстовый снимок топ-нарратива
между маркерами <!-- PRERENDER:HOME:START/END --> в index.html, чтобы
краулер без исполнения JS видел реальный контент вместо пустого
<div id="dash-narratives-list">.

Запускается в CI (deploy.yml, job "synthesize") сразу после synthesizer.py,
на том же актуальном data/synthesis_cache.json — коммитится тем же sync-PR.
Тот же принцип маркер-замены, что scripts/update_js_cache_bust.py.

Дублирует ТОЛЬКО отбор топ-1 кластера (сортировка по тому же полю score,
что и клиентский renderDashboard() в js/app-main.js) — не весь алгоритм
скоринга (freshness/weight/tension/roles), который живёт только в JS и
scripts/synthesizer.py. Снимок читает уже готовый tension/narrative из
synthesis_cache.json, вычисляет только счётчик сигналов и грубую
сортировку по числу сигналов кластера (прокси для score.total, который
в остальном требует SIGNALS-специфичных данных недоступных здесь без
дублирования всей клиентской формулы — приемлемое упрощение: снимок
существует для краулеров, не для точного паритета с длиной live UI).
"""
import json
import re
import sys
from pathlib import Path

START_MARKER = "<!-- PRERENDER:HOME:START -->"
END_MARKER = "<!-- PRERENDER:HOME:END -->"


def build_snapshot_html(synthesis_cache: dict, signals: list) -> str:
    clusters = {}
    for s in signals:
        cl = s.get("cluster") or s.get("theme") or "narrative"
        clusters.setdefault(cl, []).append(s)

    if not clusters:
        return ""

    top_key = max(clusters, key=lambda k: len(clusters[k]))
    synthesis = synthesis_cache.get(top_key, {})
    tension = synthesis.get("tension", "")
    narrative = synthesis.get("narrative", "")
    n = len(clusters[top_key])

    if not tension and not narrative:
        return ""

    parts = ['<div class="dash-narrative-item">']
    if tension:
        parts.append('<div class="dash-narrative-tension">' + tension + "</div>")
    if narrative:
        parts.append('<div class="dash-narrative-macro">' + narrative + "</div>")
    parts.append('<div style="font-size:10px;color:var(--dim)">' + str(n) + " сигналов</div>")
    parts.append("</div>")
    return "".join(parts)


def main() -> int:
    synthesis_cache_path = Path("data/synthesis_cache.json")
    signals_path = Path("signals.json")
    index_path = Path("index.html")

    synthesis_cache = json.loads(synthesis_cache_path.read_text(encoding="utf-8")) if synthesis_cache_path.exists() else {}
    signals_data = json.loads(signals_path.read_text(encoding="utf-8")) if signals_path.exists() else {"signals": []}
    signals = signals_data.get("signals", signals_data) if isinstance(signals_data, dict) else signals_data

    snapshot = build_snapshot_html(synthesis_cache, signals)

    html = index_path.read_text(encoding="utf-8")
    pattern = re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER)
    replacement = START_MARKER + snapshot + END_MARKER
    if not re.search(pattern, html, flags=re.DOTALL):
        print("PRERENDER:HOME маркеры не найдены в index.html — пропущено", file=sys.stderr)
        return 1
    new_html = re.sub(pattern, replacement, html, count=1, flags=re.DOTALL)
    index_path.write_text(new_html, encoding="utf-8")
    print("OK: prerender_home.py — снимок обновлён (" + str(len(snapshot)) + " символов)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
