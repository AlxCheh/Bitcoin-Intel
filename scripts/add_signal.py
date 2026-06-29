"""
scripts/add_signal.py
Bitcoin Intel — добавление нового сигнала в базу.

Путь 2: подключены новые модули — exceptions, logger, lifecycle, state_machine.

Делает четыре вещи атомарно:
  1. Валидирует объект сигнала (через исключения)
  2. Проверяет State Machine (draft → active)
  3. Добавляет в signals.json (с блокировкой)
  4. Испускает SignalAdded событие + lifecycle hook

§9 Error Propagation шаблон:
  BitcoinIntelError → stderr + exit(1)
  Exception         → stderr + exit(2)

Запускать:
    python3 scripts/add_signal.py --file new_signal.json
    python3 scripts/add_signal.py --stdin
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    SIGNALS_PATH, ENCODING, JSON_ENSURE_ASCII, DATE_FORMAT,
    ERROR_EXIT_CODES, DUPLICATE_WARNING_FIELDS, NULL_DEFAULTS,
)
from infrastructure.file_lock import file_lock, atomic_write_json, safe_read_json
from infrastructure.logger import get_logger
from domain.events import EventLog, SignalAdded
from domain.exceptions import (
    BitcoinIntelError,
    ValidationError,
    InvalidSignalIdError,
    DuplicateSignalError,
    MissingRequiredFieldError,
)
from domain.state_machine import transition, validate_state
from domain.lifecycle import on_signal_archived

logger = get_logger("add_signal")

# ─── Константы валидации ──────────────────────────────────────────────────────
REQUIRED_FIELDS = [
    "id", "date", "cat", "catLabel", "dir", "horizon",
    "theme", "weight", "actor", "flow", "signal",
    "narrative_role", "cluster", "tension", "macro_implication",
]

VALID_DIR    = {"pos", "neg", "neu"}
VALID_HORIZON= {"short", "mid", "long"}
VALID_WEIGHT = {"onchain", "primary", "market", "media"}
VALID_ROLE   = {"trigger", "complication", "resolution", "background"}
VALID_CAT    = {"onchain", "ta", "macro", "mining", "narrative", "layer2", "ownership"}
VALID_ACTOR  = {"etf", "corporate", "government", "defi", "retail", "miner"}
VALID_FLOW   = {"inflow", "outflow", "internal", "neutral"}

import re as _re
_ID_PATTERN = _re.compile(r'^[A-Z]{2,5}-\d{4}-\d{4}-\d{3}$')


# ─── Валидация ────────────────────────────────────────────────────────────────

def validate_signal(signal: dict) -> None:
    """
    Валидирует сигнал. FAIL LOUD — бросает исключения из иерархии BitcoinIntelError.

    Raises:
        MissingRequiredFieldError — отсутствует обязательное поле
        InvalidSignalIdError      — неверный формат ID
        ValidationError           — прочие нарушения инвариантов
    """
    # Обязательные поля
    for field in REQUIRED_FIELDS:
        if not signal.get(field):
            raise MissingRequiredFieldError(field, signal.get("id", "?"))

    # Формат ID
    sid = signal["id"]
    if not _ID_PATTERN.match(sid):
        raise InvalidSignalIdError(sid)

    # Enum значения
    enum_checks = [
        ("dir",            signal.get("dir"),            VALID_DIR),
        ("horizon",        signal.get("horizon"),        VALID_HORIZON),
        ("weight",         signal.get("weight"),         VALID_WEIGHT),
        ("narrative_role", signal.get("narrative_role"), VALID_ROLE),
        ("cat",            signal.get("cat"),            VALID_CAT),
        ("actor",          signal.get("actor"),          VALID_ACTOR),
        ("flow",           signal.get("flow"),           VALID_FLOW),
    ]
    for field_name, value, valid_set in enum_checks:
        if value and value not in valid_set:
            raise ValidationError(
                field=field_name,
                value=value,
                reason=f"must be one of {sorted(valid_set)}"
            )

    # Формат даты
    date_str = signal.get("date", "")
    try:
        datetime.strptime(date_str, DATE_FORMAT)
    except ValueError:
        raise ValidationError(
            field="date",
            value=date_str,
            reason=f"must be YYYY-MM-DD format"
        )

    # tension — заглавная буква
    tension = signal.get("tension", "")
    if tension and not tension[0].isupper():
        raise ValidationError(
            field="tension",
            value=tension[:40],
            reason="must start with capital letter (CLAUDE.md rule)"
        )

    # macro_implication — минимальная длина (не пересказ события)
    macro = signal.get("macro_implication", "")
    if macro and len(macro) < 50:
        raise ValidationError(
            field="macro_implication",
            value=macro,
            reason=f"too short ({len(macro)} chars) — must be structural change, not event description"
        )

    logger.debug(f"Signal {sid} passed validation")


def check_possible_duplicate(signal: dict, existing: list) -> str | None:
    """
    Проверяет похожие сигналы по DUPLICATE_WARNING_FIELDS.
    Возвращает warning string или None. Не блокирует добавление.
    """
    for s in existing:
        if all(signal.get(f) == s.get(f) for f in DUPLICATE_WARNING_FIELDS):
            return (
                f"Possible duplicate of {s['id']}: "
                f"same {', '.join(DUPLICATE_WARNING_FIELDS)}. "
                f"Intentional cross-verification? Ensure different source."
            )
    return None


# ─── Добавление ───────────────────────────────────────────────────────────────

def add_signal(signal: dict, signals_path: str = SIGNALS_PATH) -> dict:
    """
    Добавляет сигнал в signals.json атомарно.

    Порядок (§4 init order):
      1. validate_signal()              — FAIL LOUD при нарушении инварианта
      2. State Machine transition()     — draft → active
      3. file_lock + duplicate check    — DuplicateSignalError если id уже есть
      4. atomic_write_json              — запись
      5. EventLog.emit(SignalAdded)     — audit trail
      6. on_signal_archived hook guard  — lifecycle готов к работе

    Raises:
        ValidationError         — поле не прошло проверку
        InvalidSignalIdError    — неверный формат ID
        DuplicateSignalError    — id уже существует
        MissingRequiredFieldError — обязательное поле отсутствует
    """
    # Шаг 1: Валидация
    validate_signal(signal)

    # Шаг 2: State Machine — новый сигнал всегда draft → active
    signal_state = signal.get("status", "draft")
    if signal_state in ("draft", ""):
        transition("signal", signal["id"], "draft", "active")
        signal["status"] = "active"
    elif signal_state == "active":
        pass  # уже active — допустимо при повторном добавлении через скрипт
    else:
        from domain.exceptions import ArchitecturalViolationError
        raise ArchitecturalViolationError(
            f"Signal {signal['id']}: unexpected status '{signal_state}' on add. "
            f"Expected 'draft' or 'active'."
        )

    # Шаг 3-4: Запись с блокировкой
    with file_lock(signals_path):
        raw = safe_read_json(signals_path, default=[], raise_on_corrupt=True)
        signals = raw.get("signals", []) if isinstance(raw, dict) else raw

        # Проверка уникальности ID
        existing_ids = {s.get("id") for s in signals}
        if signal["id"] in existing_ids:
            raise DuplicateSignalError(signal["id"])

        # Предупреждение о похожем сигнале (не блокирует)
        warn = check_possible_duplicate(signal, signals)
        if warn:
            logger.warning(warn, extra={"signal_id": signal["id"]})

        signals.append(signal)

        if isinstance(raw, dict):
            raw["signals"] = signals
            raw.setdefault("meta", {})["last_updated"] = (
                datetime.now(timezone.utc).strftime(DATE_FORMAT)
            )
            atomic_write_json(signals_path, raw)
        else:
            atomic_write_json(signals_path, signals)

    logger.info(
        f"Signal added: {signal['id']}",
        extra={"signal_id": signal["id"], "cluster": signal.get("cluster", "")}
    )

    # Шаг 5: Audit event
    log = EventLog()
    log.emit(SignalAdded(
        signal_id=signal["id"],
        cluster=signal.get("cluster", ""),
        theme=signal.get("theme", ""),
        dir=signal.get("dir", ""),
        narrative_role=signal.get("narrative_role", ""),
        source=signal.get("source", ""),
    ))

    return signal


# ─── CLI (§9 Error Propagation шаблон) ───────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Добавить сигнал в Bitcoin Intel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python3 scripts/add_signal.py --file signal.json
  cat signal.json | python3 scripts/add_signal.py --stdin
  python3 scripts/add_signal.py --file signal.json --dry-run
        """
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file",  help="Путь к JSON файлу с сигналом")
    group.add_argument("--stdin", action="store_true", help="Читать из stdin")
    parser.add_argument("--dry-run", action="store_true",
                        help="Только валидировать, не записывать")
    args = parser.parse_args()

    # §9: стандартный try/except для точек входа
    try:
        if args.file:
            with open(args.file, encoding=ENCODING) as f:
                signal = json.load(f)
        else:
            signal = json.load(sys.stdin)

        if args.dry_run:
            validate_signal(signal)
            print(f"✓ DRY RUN: Signal {signal['id']} passed validation (not written)")
            sys.exit(ERROR_EXIT_CODES["success"])

        result = add_signal(signal)
        print(f"✓ Signal {result['id']} added to {SIGNALS_PATH}")
        sys.exit(ERROR_EXIT_CODES["success"])

    except (MissingRequiredFieldError, InvalidSignalIdError, ValidationError) as e:
        print(f"⛔ Validation error: {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["business_logic_error"])

    except DuplicateSignalError as e:
        print(f"⛔ {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["business_logic_error"])

    except BitcoinIntelError as e:
        print(f"⛔ {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["business_logic_error"])

    except json.JSONDecodeError as e:
        print(f"⛔ Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["business_logic_error"])

    except FileNotFoundError as e:
        print(f"⛔ File not found: {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["business_logic_error"])

    except Exception as e:
        logger.exception("Unexpected error in add_signal")
        print(f"💥 Unexpected error: {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["system_error"])


if __name__ == "__main__":
    main()
