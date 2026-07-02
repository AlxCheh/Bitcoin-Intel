"""
scripts/generate_dashboard.py
Bitcoin Intel — MON05 (Dashboards — было: "Нет").

Найден при пред-Wave-5 аудите (docs/IRP_v1.md §12): FAIL из оригинального
IRR_REPORT_v1.md без назначенной волны и без Residual Risk. Реализовано
по решению пользователя вместо принятия как RR.

Не строится с нуля — переиспользует scripts/quality_report.py::
compute_quality_report() (уже считает health score, coverage, freshness,
distribution, calibration) и просто рендерит результат в Markdown-файл,
который живёт в репозитории и обновляется автоматически (weekly workflow,
см. .github/workflows/quality-dashboard.yml), а не только доступен
человеку, который сам запустил quality_report.py локально (MON02:
"только ручной запуск" — тот же корень проблемы, что и у MON05).

Это НЕ полноценный BI-дашборд (Grafana и т.п. — Technical Debt After MVP,
нет backend, тот же принцип что у MON06 distributed tracing) — это
статический Markdown-снимок текущего состояния, обновляемый по расписанию.
История/тренды за пределами git-истории самого файла не хранятся отдельно.

Использование:
    python3 scripts/generate_dashboard.py
    python3 scripts/generate_dashboard.py --output /tmp/preview.md
"""
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import SIGNALS_PATH  # noqa: E402
from infrastructure.file_lock import safe_read_json  # noqa: E402
from scripts.quality_report import compute_quality_report  # noqa: E402

DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "QUALITY_DASHBOARD.md"


def _bar(fraction: float, width: int = 20) -> str:
    filled = round(fraction * width)
    return "█" * filled + "░" * (width - filled)


def render_dashboard_markdown(report: dict) -> str:
    """
    Рендерит структурированный отчёт compute_quality_report() в Markdown.
    Чистая функция от dict → str — тестируется без файлового I/O
    (см. tests/unit/test_generate_dashboard.py).
    """
    if "error" in report:
        return (
            "# Bitcoin Intel — Quality Dashboard\n\n"
            f"⚠ {report['error']} (cluster_filter={report.get('cluster')})\n"
        )

    health = report["health"]
    grade_emoji = {"A": "🟢", "B": "🟡", "C": "🟠", "D": "🔴"}.get(health["grade"], "⚪")
    cov = report["coverage"]
    fresh = report["freshness"]
    qual = report["quality"]
    dist = report["distribution"]
    calib = report["calibration"]

    lines = [
        "# Bitcoin Intel — Quality Dashboard",
        "",
        f"> Автогенерируется еженедельно из `scripts/quality_report.py` "
        f"(MON05). Не редактировать вручную — правки затрутся следующим "
        f"запуском `.github/workflows/quality-dashboard.yml`.",
        "",
        f"**Сгенерировано:** {report['generated_at']} · "
        f"**Сигналов:** {report['total_signals']}",
        "",
        f"## {grade_emoji} Health Score: {health['score']}/{health['max']} "
        f"(Grade {health['grade']})",
        "",
        "### Покрытие полей",
        "",
        "| Поле | Покрытие |",
        "|------|----------|",
    ]
    for field, value in cov.items():
        lines.append(f"| {field} | `{_bar(value)}` {value*100:.0f}% |")

    lines += [
        "",
        "### Свежесть",
        "",
        "| Период | Доля |",
        "|--------|------|",
    ]
    for field, value in fresh.items():
        lines.append(f"| {field} | `{_bar(value)}` {value*100:.0f}% |")

    lines += [
        "",
        "### Качество",
        "",
        "| Метрика | Доля |",
        "|---------|------|",
    ]
    for field, value in qual.items():
        lines.append(f"| {field} | `{_bar(value)}` {value*100:.0f}% |")

    lines += [
        "",
        "### Распределение",
        "",
    ]
    for label, counts in [
        ("По направлению (dir)", dist["by_dir"]),
        ("По кластеру", dist["by_cluster"]),
        ("По весу источника (weight)", dist["by_weight"]),
        ("По роли (narrative_role)", dist["by_narrative_role"]),
    ]:
        lines.append(f"**{label}:** " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
        lines.append("")

    calib_status = "✅ готово" if calib["ready"] else f"{calib['remaining']} до порога"
    lines += [
        "### Calibration Readiness (ADR-011)",
        "",
        f"{calib['synthesis_count']}/{calib['threshold']} синтезов ({calib_status})",
        "",
    ]

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT_PATH,
        help=f"Куда писать (default: {DEFAULT_OUTPUT_PATH})"
    )
    args = parser.parse_args()

    raw = safe_read_json(SIGNALS_PATH, default={"signals": []})
    signals = raw.get("signals", raw) if isinstance(raw, dict) else raw

    report = compute_quality_report(signals)
    markdown = render_dashboard_markdown(report)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    print(f"✓ Dashboard записан: {args.output} ({len(markdown)} символов)")
    sys.exit(0)


if __name__ == "__main__":
    main()
