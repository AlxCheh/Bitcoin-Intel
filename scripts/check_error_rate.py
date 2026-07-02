"""
scripts/check_error_rate.py
Bitcoin Intel — MON07 (Error rate monitoring — было: "Только logs в stdout").

Найден при пред-Wave-5 аудите (docs/IRP_v1.md §12): FAIL из оригинального
IRR_REPORT_v1.md без назначенной волны и без Residual Risk. Реализовано
по решению пользователя вместо принятия как RR.

Проблема в исходной формулировке точна: infrastructure/logger.py уже умеет
писать структурированные JSON-логи (StructuredFormatter, ENVIRONMENT=
production), но CI никогда не устанавливал ENVIRONMENT=production —
по умолчанию "local", HumanFormatter, цветной текст в stderr раннера,
который никто системно не просматривает. graceful degradation в
synthesizer.py (§9 EXIT CODES) означает, что job может быть зелёным
(exit 0), пока отдельные кластеры логируют WARNING/ERROR — эта деградация
была невидима.

Это НЕ историческая аналитика/тренды (нужна БД, Technical Debt After MVP,
тот же принцип что MON06 distributed tracing) — это проверка ОДНОГО
прогона: сколько ERROR/CRITICAL записей в структурированном логе этого
конкретного запуска synthesizer.py в CI.

Использование:
    ENVIRONMENT=production python3 scripts/synthesizer.py 2> /tmp/synth.log
    python3 scripts/check_error_rate.py /tmp/synth.log
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ERROR_LEVELS = {"ERROR", "CRITICAL"}


def count_log_levels(log_lines: list[str]) -> dict:
    """
    Считает уровни логов из структурированных JSON-строк
    (infrastructure/logger.py::StructuredFormatter).

    Строки, которые не парсятся как JSON с полем 'level' — HumanFormatter-
    вывод, посторонний текст CI-раннера — молча пропускаются: это не
    структурированный лог-ивент, не считается ни в total, ни в errors.
    Не поднимает исключение на не-JSON строке — вход заведомо смешанный
    (CI stderr содержит не только логи logger.py).
    """
    counts: Counter = Counter()
    for line in log_lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        level = entry.get("level")
        if level:
            counts[level] += 1

    total = sum(counts.values())
    errors = sum(counts.get(lvl, 0) for lvl in ERROR_LEVELS)
    error_rate = errors / total if total else 0.0

    return {
        "total_log_entries": total,
        "by_level": dict(counts),
        "error_count": errors,
        "error_rate": round(error_rate, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "logfile", type=Path,
        help="Файл с захваченным stderr (структурированные JSON-строки, ENVIRONMENT=production)"
    )
    args = parser.parse_args()

    try:
        lines = args.logfile.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        print(f"✗ Лог-файл не найден: {args.logfile}")
        sys.exit(2)  # system_error, см. config/settings.py ERROR_EXIT_CODES

    result = count_log_levels(lines)

    if result["total_log_entries"] == 0:
        # Явно отличается от "0 ошибок из N": 0 структурированных записей
        # может значить и тихий прогон, и то что ENVIRONMENT=production не
        # был установлен для этого шага — не маскировать одним и тем же
        # сообщением "всё чисто".
        print(
            "::warning::check_error_rate.py: 0 структурированных JSON-записей "
            f"найдено в {args.logfile} — либо прогон ничего не логировал, либо "
            "ENVIRONMENT=production не был установлен для проверяемого шага"
        )
    elif result["error_count"] > 0:
        print(
            f"::warning::ERROR/CRITICAL в логах synthesizer: "
            f"{result['error_count']}/{result['total_log_entries']} записей "
            f"(error_rate={result['error_rate']}), by_level={result['by_level']}"
        )
    else:
        print(
            f"✓ Ошибок нет: {result['total_log_entries']} структурированных "
            f"записей, 0 ERROR/CRITICAL, by_level={result['by_level']}"
        )

    sys.exit(0)  # non-blocking мониторинг, тот же принцип что check_signals_size.py (OP06)


if __name__ == "__main__":
    main()
