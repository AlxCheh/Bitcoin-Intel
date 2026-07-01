"""
scripts/cache_diff_check.py
Bitcoin Intel — определяет, есть ли содержательная разница между двумя
версиями synthesis_cache.json, игнорируя волатильные поля, которые
меняются при каждом запуске synthesizer.py независимо от того, изменились
ли входные сигналы (generated_at, synthesis_id, detected_at).

Без этой проверки synthesize job в CI создавал бы новый sync-PR на КАЖДЫЙ
push в main, даже если ни один сигнал не менялся — потому что raw git diff
всегда находит разницу в timestamp-полях. Обнаружено при верификации
IRP v1 Wave 1 / M05: без нормализации auto-merge зациклился (PR #10-#17
за ~5 минут, остановлено вручную отключением Actions).

Использование:
    python3 scripts/cache_diff_check.py old.json new.json
    exit code 0 — нет содержательной разницы (можно пропустить commit)
    exit code 1 — есть содержательная разница (нужен commit + PR)

Если old.json не существует (первый запуск) — считается пустым {}.
"""
import sys
import json

VOLATILE_KEYS = {"generated_at", "synthesis_id", "detected_at"}


def normalize(obj):
    """Рекурсивно убирает волатильные ключи из dict/list структуры."""
    if isinstance(obj, dict):
        return {
            k: normalize(v)
            for k, v in obj.items()
            if k not in VOLATILE_KEYS
        }
    if isinstance(obj, list):
        return [normalize(v) for v in obj]
    return obj


def has_meaningful_diff(old: dict, new: dict) -> bool:
    return normalize(old) != normalize(new)


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: cache_diff_check.py <old.json> <new.json>", file=sys.stderr)
        sys.exit(2)

    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            old = json.load(f)
    except FileNotFoundError:
        old = {}

    with open(sys.argv[2], encoding="utf-8") as f:
        new = json.load(f)

    if has_meaningful_diff(old, new):
        print("MEANINGFUL_DIFF=true")
        sys.exit(1)
    else:
        print("MEANINGFUL_DIFF=false")
        sys.exit(0)


if __name__ == "__main__":
    main()
