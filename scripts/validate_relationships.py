"""
scripts/validate_relationships.py
Bitcoin Intel — валидация целостности relationships.json.

Проверяет:
  1. Orphan relationships — ссылки на несуществующие signal_id
  2. Self-references — from_id == to_id
  3. Дубликаты — одна и та же пара (from, to, type) дважды
  4. Ретрактованные связи без rationale — аномалия
  5. Contradiction cycles — A contradicts B contradicts A (предупреждение)

Использование:
    python scripts/validate_relationships.py
    python scripts/validate_relationships.py --fix    # удалить orphans
    python scripts/validate_relationships.py --verbose

Exit codes:
    0 — всё в порядке (или исправлено с --fix)
    1 — найдены ошибки
    3 — ошибка целостности данных
"""

import os
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    SIGNALS_PATH, RELATIONSHIPS_PATH, ENCODING, ERROR_EXIT_CODES
)
from infrastructure.file_lock import safe_read_json, atomic_write_json_safe
from infrastructure.logger import get_logger
from domain.exceptions import BitcoinIntelError

logger = get_logger("validate_relationships")


def validate_relationships(fix: bool = False,
                            verbose: bool = False) -> tuple[bool, dict]:
    """
    Валидирует relationships.json.

    fix=True — автоматически удалить orphan связи.
    Возвращает (ok: bool, stats: dict).
    """
    rel_file = Path(RELATIONSHIPS_PATH)
    sig_file = Path(SIGNALS_PATH)

    # Переходный период — relationships.json может не существовать
    if not rel_file.exists():
        print("ℹ  relationships.json не существует — переходный период (links.* в signals.json)")
        return True, {"mode": "legacy"}

    relationships = safe_read_json(RELATIONSHIPS_PATH, default=[])
    raw           = safe_read_json(SIGNALS_PATH, default=[]) if sig_file.exists() else []
    signals       = raw.get("signals", raw) if isinstance(raw, dict) else raw
    signal_ids    = {s["id"] for s in signals if "id" in s}

    errors:   list[str] = []
    warnings: list[str] = []
    orphan_indices: list[int] = []
    seen_pairs: dict = {}

    for i, rel in enumerate(relationships):
        rel_id   = rel.get("id", f"[index {i}]")
        from_id  = rel.get("from_id", "")
        to_id    = rel.get("to_id", "")
        rel_type = rel.get("type", "")
        status   = rel.get("status", "")

        # 1. Orphan — from_id
        if from_id and from_id not in signal_ids:
            errors.append(f"Orphan: {rel_id} → from_id '{from_id}' not in signals.json")
            orphan_indices.append(i)

        # 2. Orphan — to_id
        if to_id and to_id not in signal_ids:
            errors.append(f"Orphan: {rel_id} → to_id '{to_id}' not in signals.json")
            if i not in orphan_indices:
                orphan_indices.append(i)

        # 3. Self-reference
        if from_id and to_id and from_id == to_id:
            errors.append(f"Self-reference: {rel_id} — from_id == to_id == '{from_id}'")

        # 4. Дубликат пары
        pair_key = (from_id, to_id, rel_type)
        if pair_key in seen_pairs:
            warnings.append(
                f"Duplicate pair: {rel_id} duplicates "
                f"relationship at index {seen_pairs[pair_key]}"
            )
        else:
            seen_pairs[pair_key] = i

        # 5. Ретракция без rationale
        if status == "retracted" and not rel.get("retraction_rationale"):
            warnings.append(f"Retracted without rationale: {rel_id}")

    # 6. Contradiction cycles
    contradicts_map: dict[str, set] = {}
    for rel in relationships:
        if rel.get("type") == "contradicts" and rel.get("status") != "retracted":
            from_id = rel.get("from_id", "")
            to_id   = rel.get("to_id", "")
            if from_id and to_id:
                contradicts_map.setdefault(from_id, set()).add(to_id)

    reported_cycles: set = set()
    for a, targets in contradicts_map.items():
        for b in targets:
            cycle_key = tuple(sorted([a, b]))
            if a in contradicts_map.get(b, set()) and cycle_key not in reported_cycles:
                warnings.append(
                    f"Contradiction cycle: {a} ↔ {b} "
                    f"(may be intentional — verify with analyst)"
                )
                reported_cycles.add(cycle_key)

    # Вывод
    total = len(relationships)
    print(f"\nValidating {RELATIONSHIPS_PATH} ({total} relationships, {len(signal_ids)} signals)")
    print(f"{'─'*55}")

    if errors:
        print(f"⛔ {len(errors)} error(s):")
        for e in errors:
            print(f"   - {e}")
    if warnings:
        print(f"⚠  {len(warnings)} warning(s):")
        for w in warnings:
            print(f"   - {w}")

    if verbose and not errors and not warnings:
        print(f"✓  All {total} relationships are valid")
        for rel in relationships[:5]:
            print(f"   {rel.get('from_id')} --{rel.get('type')}--> {rel.get('to_id')}")
        if total > 5:
            print(f"   ... and {total-5} more")

    stats = {
        "total":          total,
        "errors":         len(errors),
        "warnings":       len(warnings),
        "orphans":        len(orphan_indices),
        "cycles":         len(reported_cycles),
    }

    # --fix: удалить orphans
    if fix and orphan_indices:
        cleaned = [r for i, r in enumerate(relationships) if i not in orphan_indices]
        atomic_write_json_safe(RELATIONSHIPS_PATH, cleaned)
        print(f"\n✓ Removed {len(orphan_indices)} orphan relationship(s)")
        print(f"  Remaining: {len(cleaned)} relationships")
        # После fix — ошибок нет если только были orphans
        if len(errors) == len(orphan_indices):
            return True, stats

    ok = len(errors) == 0
    if ok and not warnings:
        print(f"\n✓ relationships.json is valid ({total} relationships)")
    elif ok:
        print(f"\n✓ No errors (but {len(warnings)} warning(s) to review)")

    return ok, stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Валидация relationships.json"
    )
    parser.add_argument("--fix",     action="store_true",
                        help="Автоматически удалить orphan связи")
    parser.add_argument("--verbose", action="store_true",
                        help="Подробный вывод при отсутствии ошибок")
    args = parser.parse_args()

    try:
        ok, stats = validate_relationships(fix=args.fix, verbose=args.verbose)
        sys.exit(ERROR_EXIT_CODES["success"] if ok else ERROR_EXIT_CODES["business_logic_error"])
    except BitcoinIntelError as e:
        print(f"⛔ {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["data_integrity_error"])
    except Exception as e:
        logger.exception("Unexpected error in validate_relationships")
        print(f"💥 {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["system_error"])


if __name__ == "__main__":
    main()
