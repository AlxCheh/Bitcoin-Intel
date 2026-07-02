"""
migration/v1_to_v2.py
Bitcoin Intel — IRP v1 Wave 4 / MC05 (CON06: migration scripts при breaking change).

╔══════════════════════════════════════════════════════════════════════╗
║ STUB — НЕФУНКЦИОНАЛЕН. Не запускать, кроме --dry-run для проверки CLI. ║
╚══════════════════════════════════════════════════════════════════════╝

Versioning Policy (§17.4 ADDENDUM) требует, чтобы breaking change в схеме
сопровождался миграционным скриптом `migration/v1_to_v2.py`. На
2026-07-02 **никакой schema v2 не существует** — все три схемы
(`schemas/signal/v1.json`, `schemas/relationship/v1.json`,
`schemas/synthesis/v1.json`) стабильны на v1. Мигрировать не из чего и не
во что.

Этот файл — не функциональная миграция, а **структурный шаблон**:
показывает, каким CLI и каким набором шагов должна обладать реальная
миграция, когда она понадобится, скопирован с реального прецедента в
проекте — `scripts/migrate_relationships.py` (links.* → relationships.json,
Фаза B→C) — тот же паттерн `--apply`/dry-run/идемпотентность/event log,
просто без содержательного шага 3 (трансформация), потому что схему v2
пока никто не спроектировал.

Когда появится реальный breaking change (§17.4 говорит: новая версия
схемы создаётся, старая помечается deprecated, 180 дней поддержки):
  1. Спроектировать `schemas/{signal,relationship,synthesis}/v2.json`
     (какой именно из трёх — зависит от конкретного breaking change)
  2. Заполнить `_transform_record()` ниже реальной логикой перевода
     v1 → v2 полей
  3. Убрать `raise NotImplementedError` и оговорку выше в docstring
  4. Написать golden-тест: v1 фикстура → migrate() → сравнить с
     ожидаемой v2 структурой

Использование (сейчас работает только --dry-run, --apply падает явно):
    python3 migration/v1_to_v2.py            # dry run: печатает что БУДЕТ
                                              # мигрировано (сейчас: 0 записей,
                                              # т.к. нет v2 схемы для сверки)
    python3 migration/v1_to_v2.py --apply    # NotImplementedError — явно,
                                              # не тихий no-op
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import ERROR_EXIT_CODES  # noqa: E402
from infrastructure.logger import get_logger  # noqa: E402

logger = get_logger("migration.v1_to_v2")

# Схема-источник (существует) и схема-цель (НЕ существует — заполнить
# путь, когда v2 будет спроектирована; см. docstring выше).
SOURCE_SCHEMA_VERSION = "v1"
TARGET_SCHEMA_VERSION = "v2"
TARGET_SCHEMA_EXISTS = False  # единственный флаг, который делает stub stub'ом


def _transform_record(record: dict) -> dict:
    """
    Место для реальной логики трансформации v1 → v2 одной записи
    (сигнал, relationship или synthesis — в зависимости от того, что
    именно потребует breaking change). Пока не заполнено — см. docstring
    модуля, пункт 2.
    """
    raise NotImplementedError(
        "_transform_record() не реализован — schema v2 не спроектирована "
        "(TARGET_SCHEMA_EXISTS = False). Это ожидаемо для stub'а, см. "
        "docstring migration/v1_to_v2.py."
    )


def migrate(dry_run: bool = True) -> dict:
    """
    Возвращает статистику миграции — тот же контракт, что у
    scripts/migrate_relationships.py::migrate(), для консистентности
    паттерна между миграциями.

    dry_run=True  — безопасно запускать многократно, ничего не пишет
    dry_run=False — реальная запись (когда появится, что писать)
    """
    stats = {
        "source_version": SOURCE_SCHEMA_VERSION,
        "target_version": TARGET_SCHEMA_VERSION,
        "target_schema_exists": TARGET_SCHEMA_EXISTS,
        "records_migrated": 0,
        "records_skipped": 0,
        "errors": 0,
    }

    if not TARGET_SCHEMA_EXISTS:
        logger.info(
            "TARGET_SCHEMA_EXISTS=False — schema v2 не спроектирована. "
            "Нечего мигрировать. Это stub, см. §17.4 ADDENDUM и docstring файла."
        )
        if not dry_run:
            raise NotImplementedError(
                "--apply вызван для stub-миграции без целевой schema v2. "
                "Заполните migration/v1_to_v2.py по инструкции в его docstring "
                "прежде чем запускать реальную миграцию."
            )
        return stats

    # Реальная миграция появится здесь: чтение источника, цикл по записям
    # через _transform_record(), валидация против schema v2, атомарная
    # запись (atomic_write_json_safe, как в остальном проекте), event log.
    # См. scripts/migrate_relationships.py как образец полной структуры.
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="Реальная миграция (сейчас всегда NotImplementedError — stub)"
    )
    args = parser.parse_args()

    try:
        stats = migrate(dry_run=not args.apply)
    except NotImplementedError as e:
        print(f"✗ {e}")
        sys.exit(ERROR_EXIT_CODES["business_logic_error"])

    print(
        f"{'[DRY RUN] ' if not args.apply else ''}"
        f"v1 → v2 миграция: {stats['records_migrated']} мигрировано, "
        f"{stats['records_skipped']} пропущено, "
        f"target_schema_exists={stats['target_schema_exists']}"
    )
    sys.exit(ERROR_EXIT_CODES["success"])


if __name__ == "__main__":
    main()
