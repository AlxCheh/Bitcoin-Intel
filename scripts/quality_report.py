"""
scripts/quality_report.py
Bitcoin Intel — отчёт о качестве базы сигналов.

Метрики:
  - Покрытие обязательных полей (tension, macro_implication, context, caveat)
  - Свежесть (доля сигналов за 30 / 90 дней)
  - Качество tension (формула vs/несмотря на соблюдена?)
  - Связность (доля сигналов с хотя бы одной связью)
  - Распределение по dir и cluster
  - Итоговый Health Score [0–100] с оценкой A/B/C/D

Использование:
    python scripts/quality_report.py
    python scripts/quality_report.py --format json
    python scripts/quality_report.py --cluster strategy_model_stress
"""

import os
import sys
import json
import argparse
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    SIGNALS_PATH, ENCODING, ERROR_EXIT_CODES, WINDOW_DAYS_DEFAULT
)
from infrastructure.file_lock import safe_read_json
from infrastructure.logger import get_logger, measure_performance
from domain.exceptions import BitcoinIntelError

logger = get_logger("quality_report")

TENSION_MARKERS = ["vs", "несмотря на", "при условии", "вопреки", " — ", "—"]


# ─── Вычисление метрик ────────────────────────────────────────────────────────

@measure_performance("quality_report")
def compute_quality_report(signals: list[dict],
                            cluster_filter: str | None = None) -> dict:
    """
    Вычисляет отчёт качества для списка сигналов.
    Все доли — от 0.0 до 1.0.
    """
    if cluster_filter:
        signals = [s for s in signals if s.get("cluster") == cluster_filter]

    if not signals:
        return {
            "error":   "no signals",
            "total":   0,
            "cluster": cluster_filter,
        }

    total = len(signals)
    today = date.today()

    def signal_age(s: dict) -> int:
        try:
            return (today - date.fromisoformat(s.get("date", "1970-01-01"))).days
        except ValueError:
            return 9999

    def tension_valid(s: dict) -> bool:
        t = s.get("tension", "")
        if not t or not t[0].isupper():
            return False
        return any(m in t for m in TENSION_MARKERS)

    def has_links(s: dict) -> bool:
        links = s.get("links", {}) or {}
        return any(links.get(k) for k in ["confirms", "contradicts", "context_chain"])

    # Покрытие полей
    has_tension   = sum(1 for s in signals if (s.get("tension") or "").strip())
    has_macro     = sum(1 for s in signals if (s.get("macro_implication") or "").strip())
    has_context   = sum(1 for s in signals if (s.get("context") or "").strip())
    has_caveat    = sum(1 for s in signals if (s.get("caveat") or "").strip())

    # Свежесть
    fresh_30 = sum(1 for s in signals if signal_age(s) <= 30)
    fresh_90 = sum(1 for s in signals if signal_age(s) <= 90)

    # Качество tension
    tension_ok = sum(1 for s in signals if tension_valid(s))

    # Связность
    connected = sum(1 for s in signals if has_links(s))

    # Распределение
    dir_counts: dict[str, int] = {}
    cluster_counts: dict[str, int] = {}
    weight_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    for s in signals:
        for field, counter in [
            ("dir",            dir_counts),
            ("cluster",        cluster_counts),
            ("weight",         weight_counts),
            ("narrative_role", role_counts),
        ]:
            val = s.get(field, "unknown") or "unknown"
            counter[val] = counter.get(val, 0) + 1

    # Health Score [0–100]
    # Веса: tension coverage 25%, macro coverage 20%,
    #        tension quality 20%, freshness_30 15%, connectivity 20%
    score = round(
        (has_tension  / total) * 25 +
        (has_macro    / total) * 20 +
        (tension_ok   / total) * 20 +
        (fresh_30     / total) * 15 +
        (connected    / total) * 20,
        1
    )
    grade = (
        "A" if score >= 80 else
        "B" if score >= 60 else
        "C" if score >= 40 else
        "D"
    )

    return {
        "generated_at":   today.isoformat(),
        "cluster_filter": cluster_filter,
        "total_signals":  total,
        "coverage": {
            "tension":           round(has_tension / total, 3),
            "macro_implication": round(has_macro   / total, 3),
            "context":           round(has_context / total, 3),
            "caveat":            round(has_caveat  / total, 3),
        },
        "freshness": {
            "last_30_days": round(fresh_30 / total, 3),
            "last_90_days": round(fresh_90 / total, 3),
        },
        "quality": {
            "tension_formula_valid": round(tension_ok  / total, 3),
            "signals_with_links":    round(connected   / total, 3),
        },
        "distribution": {
            "by_dir":            dir_counts,
            "by_cluster":        cluster_counts,
            "by_weight":         weight_counts,
            "by_narrative_role": role_counts,
        },
        "health": {
            "score": score,
            "grade": grade,
            "max":   100,
        },
    }


def _print_report(report: dict) -> None:
    """Человекочитаемый вывод отчёта."""
    if "error" in report:
        print(f"⚠ {report['error']}")
        return

    h = report["health"]
    grade_icon = {"A": "🟢", "B": "🟡", "C": "🟠", "D": "🔴"}.get(h["grade"], "⚪")
    cluster_info = f" (кластер: {report['cluster_filter']})" if report.get("cluster_filter") else ""

    print(f"\n{'═'*55}")
    print(f"  Bitcoin Intel — Quality Report{cluster_info}")
    print(f"  {report['generated_at']} · {report['total_signals']} сигналов")
    print(f"{'═'*55}")
    print(f"\n  {grade_icon} Health Score: {h['score']}/100 (Grade {h['grade']})")

    print(f"\n  Покрытие полей:")
    for field, val in report["coverage"].items():
        bar = "█" * int(val * 20) + "░" * (20 - int(val * 20))
        print(f"    {field:<22} {bar} {val:.0%}")

    print(f"\n  Свежесть:")
    for period, val in report["freshness"].items():
        bar = "█" * int(val * 20) + "░" * (20 - int(val * 20))
        print(f"    {period:<22} {bar} {val:.0%}")

    print(f"\n  Качество:")
    for key, val in report["quality"].items():
        bar = "█" * int(val * 20) + "░" * (20 - int(val * 20))
        print(f"    {key:<22} {bar} {val:.0%}")

    print(f"\n  Распределение по dir: {report['distribution']['by_dir']}")
    print(f"  Распределение по role: {report['distribution']['by_narrative_role']}")
    print(f"{'─'*55}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Отчёт о качестве базы сигналов")
    parser.add_argument("--format",  choices=["table", "json"], default="table")
    parser.add_argument("--cluster", help="Фильтр по кластеру")
    args = parser.parse_args()

    try:
        signals = safe_read_json(SIGNALS_PATH, default=[], raise_on_corrupt=True)
        report  = compute_quality_report(signals, cluster_filter=args.cluster)

        if args.format == "json":
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            _print_report(report)

        # Exit code отражает Health grade
        grade = report.get("health", {}).get("grade", "D")
        sys.exit(0 if grade in ("A", "B") else 1)

    except BitcoinIntelError as e:
        print(f"⛔ {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["data_integrity_error"])
    except Exception as e:
        logger.exception("Unexpected error in quality_report")
        print(f"💥 {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["system_error"])


if __name__ == "__main__":
    main()
