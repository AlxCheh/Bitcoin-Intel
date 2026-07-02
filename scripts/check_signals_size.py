"""
scripts/check_signals_size.py
Bitcoin Intel — IRP v1 Wave 4 / OP06 (SCL05: signals.json size monitoring).

Не блокирует CI — только предупреждает (GitHub Actions ::warning::
annotation) при превышении порога. Причина не-блокирующего поведения:
рост signals.json — ожидаемое, желаемое событие (больше сигналов = продукт
работает), а не баг; порог существует чтобы дать заблаговременный сигнал
для планирования шардинга (docs/BLUEPRINT.md §9: "1000 сигналов —
signals.json разбивается на signals/YYYY/MM/*.json"), а не чтобы
останавливать работу.

Порог 4MB (не 5MB, как в исходной формулировке SCL05 в
docs/IRR_REPORT_v1.md — историческая нестыковка между IRR и итоговым
DoD Wave 4 в IRP_v1.md; 4MB используется как операционный порог, т.к.
это формулировка непосредственно в DoD, под который пишется этот скрипт).

Использование:
    python3 scripts/check_signals_size.py
    python3 scripts/check_signals_size.py --threshold-mb 4.0
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SIGNALS_PATH = REPO_ROOT / "signals.json"

THRESHOLD_MB_DEFAULT = 4.0
BYTES_PER_MB = 1024 * 1024

# docs/BLUEPRINT.md §9: следующая архитектурная веха — шардинг при ~1000 сигналов
SHARDING_MILESTONE_SIGNAL_COUNT = 1000


def check_size(signals_path: Path, threshold_mb: float) -> dict:
    """
    Возвращает структурированный результат проверки — не печатает и не
    делает sys.exit сам, чтобы быть тестируемым без file I/O side effects
    в тесте (см. tests/unit/test_check_signals_size.py).
    """
    size_bytes = signals_path.stat().st_size
    size_mb = size_bytes / BYTES_PER_MB

    with open(signals_path, encoding="utf-8") as f:
        signal_count = len(json.load(f)["signals"])

    avg_bytes_per_signal = size_bytes / signal_count if signal_count else 0
    projected_signals_at_threshold = (
        int((threshold_mb * BYTES_PER_MB) / avg_bytes_per_signal)
        if avg_bytes_per_signal else None
    )

    return {
        "size_bytes": size_bytes,
        "size_mb": round(size_mb, 3),
        "signal_count": signal_count,
        "avg_bytes_per_signal": round(avg_bytes_per_signal),
        "threshold_mb": threshold_mb,
        "over_threshold": size_mb > threshold_mb,
        "projected_signals_at_threshold": projected_signals_at_threshold,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--threshold-mb", type=float, default=THRESHOLD_MB_DEFAULT,
        help=f"Порог в MB (default: {THRESHOLD_MB_DEFAULT})"
    )
    args = parser.parse_args()

    try:
        result = check_size(SIGNALS_PATH, args.threshold_mb)
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"✗ Не удалось прочитать {SIGNALS_PATH}: {e}")
        sys.exit(2)  # system_error, см. config/settings.py ERROR_EXIT_CODES

    if result["over_threshold"]:
        # Non-blocking: GitHub Actions ::warning:: annotation, не sys.exit(1).
        print(
            f"::warning::signals.json = {result['size_mb']}MB "
            f"(порог {result['threshold_mb']}MB), {result['signal_count']} сигналов. "
            f"Планировать шардинг по docs/BLUEPRINT.md §9 "
            f"(~{SHARDING_MILESTONE_SIGNAL_COUNT} сигналов) — MC05/MC07."
        )
    else:
        remaining_mb = round(result["threshold_mb"] - result["size_mb"], 3)
        print(
            f"✓ signals.json = {result['size_mb']}MB / {result['threshold_mb']}MB "
            f"({result['signal_count']} сигналов, ~{result['avg_bytes_per_signal']}B/сигнал, "
            f"запас {remaining_mb}MB)"
        )
        if result["projected_signals_at_threshold"]:
            print(
                f"  При текущем среднем размере порог {result['threshold_mb']}MB "
                f"достигается примерно на {result['projected_signals_at_threshold']} сигналах"
            )

    sys.exit(0)  # всегда 0 — предупреждение, не блокировка CI


if __name__ == "__main__":
    main()
