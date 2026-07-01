"""
scripts/migrate_relationships.py
Bitcoin Intel — миграция links.* из signals.json → relationships.json

Запускать ОДИН РАЗ при переходе в Фазу C (когда LEGACY_LINKS_ENABLED → False).

Алгоритм:
  1. Читает все сигналы из signals.json
  2. Для каждого signals[*].links.{confirms,contradicts,context_chain}
     создаёт Relationship объект
  3. Пропускает уже существующие пары (идемпотентен)
  4. Записывает в data/relationships.json
  5. Логирует каждую созданную связь в events.jsonl

После запуска:
  Установить LEGACY_LINKS_ENABLED = False в config/settings.py
  Запустить: python scripts/validate_relationships.py

Использование:
    python scripts/migrate_relationships.py            # dry run (ничего не пишет)
    python scripts/migrate_relationships.py --apply    # реальная миграция
"""

import os
import sys
import json
import uuid
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    SIGNALS_PATH, RELATIONSHIPS_PATH, EVENTS_LOG_PATH,
    ENCODING, JSON_ENSURE_ASCII, ERROR_EXIT_CODES,
)
from infrastructure.file_lock import safe_read_json, atomic_write_json_safe
from infrastructure.logger import get_logger
from domain.exceptions import BitcoinIntelError

logger = get_logger("migrate_relationships")


def migrate(dry_run: bool = True) -> dict:
    """
    Выполняет миграцию links.* → relationships.json.

    dry_run=True  — только показать что будет создано (безопасно запускать многократно)
    dry_run=False — реальная запись (идемпотентна: дубликаты пропускаются)

    Returns:
        dict со статистикой: created, skipped_duplicate, signals_processed, errors
    """
    raw = safe_read_json(SIGNALS_PATH, default=[], raise_on_corrupt=True)
    signals = raw.get("signals", raw) if isinstance(raw, dict) else raw
    existing_rels = safe_read_json(RELATIONSHIPS_PATH, default=[])

    # Индекс существующих пар для быстрой проверки дубликатов
    existing_pairs: set = {
        (r["from_id"], r["to_id"], r["type"])
        for r in existing_rels
        if "from_id" in r and "to_id" in r and "type" in r
    }

    new_relationships: list[dict] = []
    stats = {
        "created":            0,
        "skipped_duplicate":  0,
        "signals_processed":  0,
        "errors":             0,
    }

    rel_type_map = {
        "confirms":      "confirms",
        "contradicts":   "contradicts",
        "context_chain": "context_chain",
    }

    for signal in signals:
        signal_id = signal.get("id")
        if not signal_id:
            continue

        links = signal.get("links", {})
        if not any(links.get(k) for k in rel_type_map):
            continue

        stats["signals_processed"] += 1

        for links_key, rel_type in rel_type_map.items():
            targets = links.get(links_key, []) or []
            for target_id in targets:
                if not target_id or not isinstance(target_id, str):
                    continue

                pair = (signal_id, target_id, rel_type)
                if pair in existing_pairs:
                    stats["skipped_duplicate"] += 1
                    logger.debug(f"Skip duplicate: {signal_id} --{rel_type}--> {target_id}")
                    continue

                rel = {
                    "id":           str(uuid.uuid4()),
                    "from_id":      signal_id,
                    "to_id":        target_id,
                    "type":         rel_type,
                    "rationale":    "",
                    "created":      datetime.now(timezone.utc).isoformat(),
                    "created_by":   "migrate_relationships.py",
                    "migrated_from": "links.*",
                    "status":       "active",
                }
                new_relationships.append(rel)
                existing_pairs.add(pair)
                stats["created"] += 1

                action = "[DRY]" if dry_run else "[CREATE]"
                print(f"  {action} {signal_id} --{rel_type}--> {target_id}")

    # Итог
    print(f"\n{'─'*50}")
    print(f"  Signals processed: {stats['signals_processed']}")
    print(f"  Relationships to create: {stats['created']}")
    print(f"  Skipped (duplicates): {stats['skipped_duplicate']}")
    print(f"  Errors: {stats['errors']}")

    if dry_run:
        print("\n⚠ DRY RUN — файлы не изменены.")
        print("  Запустить реальную миграцию: python scripts/migrate_relationships.py --apply")
        return stats

    if not new_relationships:
        print("\n✓ Нечего мигрировать — все связи уже в relationships.json")
        return stats

    # Записываем
    all_rels = existing_rels + new_relationships
    os.makedirs(os.path.dirname(os.path.abspath(RELATIONSHIPS_PATH)), exist_ok=True)
    atomic_write_json_safe(RELATIONSHIPS_PATH, all_rels)
    logger.info(f"Migrated {len(new_relationships)} relationships to {RELATIONSHIPS_PATH}")

    print(f"\n✓ Записано {len(new_relationships)} связей в {RELATIONSHIPS_PATH}")
    print("  Следующий шаг: установить LEGACY_LINKS_ENABLED = False в config/settings.py")
    print("  Проверка: python scripts/validate_relationships.py")

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Миграция links.* из signals.json → relationships.json"
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Выполнить реальную миграцию (по умолчанию: dry run)"
    )
    args = parser.parse_args()

    try:
        migrate(dry_run=not args.apply)
        sys.exit(ERROR_EXIT_CODES["success"])
    except BitcoinIntelError as e:
        print(f"⛔ {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["data_integrity_error"])
    except Exception as e:
        logger.exception("Unexpected error in migrate_relationships")
        print(f"💥 {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["system_error"])


if __name__ == "__main__":
    main()
