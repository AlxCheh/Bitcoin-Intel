"""
scripts/build_facts.py
Bitcoin Intel — сборка data/facts.json из структурированного поля `facts`
сигналов signals.json.

Архитектурная роль (см. CLAUDE.md, раздел "FACTS — машиночитаемые факты"):
signals.json остаётся единственным источником истины (BDKS: Single Source
of Truth, "производные ссылаются, не копируют"). data/facts.json —
ПРОИЗВОДНЫЙ, механически регенерируемый индекс: последнее по `as_of`
значение на каждый `key` среди всех сигналов, где он встречается.

data/facts.json НИКОГДА не редактируется руками — только этим скриптом,
по тому же принципу, что SIGNALS.md регенерируется из signals.json.
Ручная правка будет молча перезаписана следующим прогоном CI.

Правило разрешения: при нескольких сигналах с одним `key` побеждает тот,
у кого `as_of` позже (не дата сигнала, не порядок в файле).

Использование:
    python3 scripts/build_facts.py
    python3 scripts/build_facts.py --out data/facts.json
"""
import argparse
import json
import sys
from collections import OrderedDict
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SIGNALS_PATH = REPO_ROOT / "signals.json"
DEFAULT_OUT = REPO_ROOT / "data" / "facts.json"


def load_signals() -> list[dict]:
    with open(SIGNALS_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("signals", raw) if isinstance(raw, dict) else raw


def resolve_facts(signals: list[dict]) -> dict[str, dict]:
    """Для каждого встреченного key оставляет запись с максимальным as_of.
    При равенстве as_of — оставляет ту, что встретилась раньше в signals.json
    и печатает предупреждение (двусмысленность должна быть исправлена в
    данных, не молча замаскирована)."""
    resolved: dict[str, dict] = {}
    for sig in signals:
        for fact in sig.get("facts", []) or []:
            key = fact["key"]
            as_of = fact["as_of"]
            entry = {
                "value": fact["value"],
                "unit": fact["unit"],
                "as_of": as_of,
                "signal_id": sig["id"],
            }
            existing = resolved.get(key)
            if existing is None or as_of > existing["as_of"]:
                resolved[key] = entry
            elif as_of == existing["as_of"] and existing["signal_id"] != sig["id"]:
                print(
                    f"::warning::facts key '{key}' has two signals with the same "
                    f"as_of={as_of} ({existing['signal_id']} vs {sig['id']}) — "
                    f"keeping first encountered, resolve ambiguity in source data",
                    file=sys.stderr,
                )
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    signals = load_signals()
    resolved = resolve_facts(signals)

    payload = OrderedDict([
        ("_generated_by", "scripts/build_facts.py — не редактировать руками"),
        ("_source", "signals.json (facts[] по каждому сигналу)"),
        ("generated_at", date.today().isoformat()),
        ("facts", OrderedDict(sorted(resolved.items()))),
    ])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"OK: {args.out} — {len(resolved)} фактов из {len(signals)} сигналов")
    return 0


if __name__ == "__main__":
    sys.exit(main())
