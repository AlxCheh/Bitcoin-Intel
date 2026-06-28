"""
scripts/add_signal.py
Bitcoin Intel — добавление нового сигнала в базу

Делает три вещи атомарно:
  1. Валидирует объект сигнала
  2. Добавляет в signals.json (с блокировкой)
  3. Испускает SignalAdded событие в events.jsonl

Запускать:
    python3 scripts/add_signal.py --file new_signal.json
    python3 scripts/add_signal.py --stdin  (читает из stdin)
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    SIGNALS_PATH, ENCODING, JSON_ENSURE_ASCII, DATE_FORMAT,
)
from infrastructure.file_lock import file_lock, atomic_write_json, safe_read_json
from domain.events import EventLog, SignalAdded

# Обязательные поля сигнала
REQUIRED_FIELDS = [
    "id", "date", "cat", "catLabel", "dir", "horizon",
    "theme", "weight", "actor", "flow", "signal",
    "narrative_role", "cluster", "tension", "macro_implication",
]

VALID_DIR       = {"pos", "neg", "neu"}
VALID_HORIZON   = {"short", "mid", "long"}
VALID_WEIGHT    = {"onchain", "primary", "market", "media"}
VALID_ROLE      = {"trigger", "complication", "resolution", "background"}
VALID_CAT       = {"onchain", "ta", "macro", "mining", "narrative", "layer2", "ownership"}
VALID_ACTOR     = {"etf", "corporate", "government", "defi", "retail", "miner"}
VALID_FLOW      = {"inflow", "outflow", "internal", "neutral"}


def validate_signal(signal: dict) -> list[str]:
    """
    Валидирует объект сигнала.
    Возвращает список ошибок (пустой = валиден).
    """
    errors = []

    # Обязательные поля
    for f in REQUIRED_FIELDS:
        if not signal.get(f):
            errors.append(f"Отсутствует обязательное поле: {f}")

    # Форматы значений
    if signal.get("dir") and signal["dir"] not in VALID_DIR:
        errors.append(f"dir должен быть одним из {VALID_DIR}, получено: {signal['dir']}")

    if signal.get("horizon") and signal["horizon"] not in VALID_HORIZON:
        errors.append(f"horizon должен быть одним из {VALID_HORIZON}")

    if signal.get("weight") and signal["weight"] not in VALID_WEIGHT:
        errors.append(f"weight должен быть одним из {VALID_WEIGHT}")

    if signal.get("narrative_role") and signal["narrative_role"] not in VALID_ROLE:
        errors.append(f"narrative_role должен быть одним из {VALID_ROLE}")

    if signal.get("cat") and signal["cat"] not in VALID_CAT:
        errors.append(f"cat должен быть одним из {VALID_CAT}")

    if signal.get("actor") and signal["actor"] not in VALID_ACTOR:
        errors.append(f"actor должен быть одним из {VALID_ACTOR}")

    if signal.get("flow") and signal["flow"] not in VALID_FLOW:
        errors.append(f"flow должен быть одним из {VALID_FLOW}")

    # Формат даты
    if signal.get("date"):
        try:
            datetime.strptime(signal["date"], DATE_FORMAT)
        except ValueError:
            errors.append(f"date должна быть в формате YYYY-MM-DD, получено: {signal['date']}")

    # tension — заглавная буква
    tension = signal.get("tension", "")
    if tension and not tension[0].isupper():
        errors.append(f"tension должен начинаться с заглавной буквы: '{tension[:30]}'")

    return errors


def add_signal(signal: dict, signals_path: str = SIGNALS_PATH) -> dict:
    """
    Добавляет сигнал в signals.json с блокировкой и испускает событие.

    Returns:
        Добавленный сигнал (с подтверждением id)

    Raises:
        ValueError: если сигнал не прошёл валидацию
        ValueError: если id уже существует в базе
    """
    # 1. Валидация
    errors = validate_signal(signal)
    if errors:
        raise ValueError("Валидация не пройдена:\n" + "\n".join(f"  • {e}" for e in errors))

    # 2. Добавление с блокировкой
    with file_lock(signals_path):
        data = safe_read_json(signals_path, default={"meta": {}, "signals": []})
        signals = data.get("signals", []) if isinstance(data, dict) else data

        # Проверка уникальности id
        existing_ids = {s.get("id") for s in signals}
        if signal["id"] in existing_ids:
            raise ValueError(f"Сигнал с id={signal['id']} уже существует в базе")

        signals.append(signal)

        if isinstance(data, dict):
            data["signals"] = signals
            data.setdefault("meta", {})["last_updated"] = datetime.now(timezone.utc).strftime(DATE_FORMAT)
        else:
            data = {"meta": {"last_updated": datetime.now(timezone.utc).strftime(DATE_FORMAT)}, "signals": signals}

        atomic_write_json(signals_path, data)

    # 3. Audit event
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


def main():
    parser = argparse.ArgumentParser(description="Добавить сигнал в Bitcoin Intel")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file",  help="Путь к JSON файлу с сигналом")
    group.add_argument("--stdin", action="store_true", help="Читать сигнал из stdin")
    args = parser.parse_args()

    if args.file:
        with open(args.file, encoding=ENCODING) as f:
            signal = json.load(f)
    else:
        signal = json.load(sys.stdin)

    try:
        result = add_signal(signal)
        print(f"✓ Сигнал {result['id']} добавлен в {SIGNALS_PATH}")
    except ValueError as e:
        print(f"✗ Ошибка: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
