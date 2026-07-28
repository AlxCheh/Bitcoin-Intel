"""
scripts/check_new_tension.py
Bitcoin Intel — обязательная проверка нового tension перед записью сигнала
(Шаг 7 CLAUDE.md, 2026-07-27).

КОНТЕКСТ: tests/golden/test_tension_benchmarks.py — агрегатный, неблокирующий
монитор (падает только при >20% провалов по всей базе). Он НЕ проверяет
отдельный новый сигнал в момент его написания — только задним числом, когда
накопится достаточно нарушений. Смоделировано на реальных данных (2026-07-27,
обсуждение в чате): дрейф длины tension не линейный, а взрывной — несколько
длинных tension подряд в одной сессии (напр. 4 сигнала 2 июля 2026) толкают
общий процент к порогу за считанные сигналы, не месяцы. Три недели подряд
показатель держался на плато 16-18,5%, ни разу не снижаясь — сам факт
дальнейшей работы не самоисправляет проблему.

РЕШЕНИЕ: тот же принцип, что уже применён к Фазе 1 ADR-018 (обязательный
запускаемый скрипт, не просто пункт в тексте инструкции) — эта проверка
даёт немедленный PASS/FAIL для ЧЕРНОВИКА tension ДО того, как сигнал
записан, вместо того чтобы полагаться на память о числовом ориентире.

Переиспользует ту же логику проверки, что golden-тест (has_two_distinct_mechanisms) —
не дублирует её, импортирует напрямую, чтобы правило проверялось
ОДИНАКОВО в обоих местах.

Использование (Шаг 7, для каждого нового сигнала, до записи в signals.json):
    python3 scripts/check_new_tension.py "Текст черновика tension здесь"
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests" / "golden"))

from test_tension_benchmarks import has_two_distinct_mechanisms, MIN_LENGTH, MAX_LENGTH  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("Использование: python3 scripts/check_new_tension.py \"текст tension\"")
        return 1

    tension = sys.argv[1]
    length = len(tension)
    passed, reason = has_two_distinct_mechanisms(tension)

    print(f"Длина: {length} символов (допустимо: {MIN_LENGTH}-{MAX_LENGTH})")
    if passed:
        print(f"✓ OK — {reason}")
        return 0
    else:
        print(f"✗ ПРОВАЛ — {reason}")
        print("Переформулировать до записи сигнала — не игнорировать и не откладывать.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
