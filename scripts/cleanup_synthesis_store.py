"""
scripts/cleanup_synthesis_store.py
Bitcoin Intel — очистка устаревших синтезов в synthesis_store/ (M1 ARR v3).

КОНТЕКСТ
--------
ARR v3 Major #1: synthesis_store/ не чистится — каждый запуск
synthesizer.py добавляет файл (см. _save_synthesis в scripts/synthesizer.py),
ничего не удаляется. На 2026-06-30 — 10 файлов / 44K, не критично, но
архитектурно это unbounded growth без механизма очистки.

ПОЛИТИКА УДАЛЕНИЯ
------------------
Источник правды — SYNTHESIS_RETENTION в config/settings.py (P2 §11,
определена ДО этого скрипта, но раньше нигде не применялась):

    "generated":  30,    # неутверждённые — удалять через 30 дней
    "reviewed":   30,
    "approved":   None,  # бессрочно
    "published":  None,  # бессрочно
    "superseded": 730,   # RETAIN_SYNTHESIS_DAYS — 2 года
    "archived":   None,  # бессрочно

Возраст файла считается от поля `generated_at` (ISO8601, пишется
synthesizer.py при каждом сохранении) — НЕ от mtime файла на диске,
потому что mtime не переживает git clone/checkout и не воспроизводим
(нарушало бы тот же принцип детерминизма, что и PYTHONHASHSEED, см.
config/settings.py assert_deterministic_env).

БЕЗОПАСНОСТЬ
------------
Как и rebuild_synthesis.py (C08 ARR v3 — "diff перед --apply") — по
умолчанию dry-run. Удаление синтезов необратимо (Audit Trail в
events.jsonl логирует факт удаления, но не восстанавливает файл), поэтому
--apply обязателен явно, и каждое удаление логируется в events.jsonl
ДО физического удаления файла (fail loud, не наоборот).

Использование:
    python scripts/cleanup_synthesis_store.py              # dry-run, печатает план
    python scripts/cleanup_synthesis_store.py --apply       # реально удаляет
    python scripts/cleanup_synthesis_store.py --verbose     # подробный вывод

Exit codes:
    0 — успех (включая "нечего удалять")
    1 — ошибка бизнес-логики (повреждённый файл синтеза)
    2 — системная ошибка
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import SYNTHESIS_STORE_PATH, SYNTHESIS_RETENTION, ERROR_EXIT_CODES
from infrastructure.logger import get_logger
from domain.events import EventLog, SynthesisStoreCleaned
from config.settings import EVENTS_LOG_PATH

logger = get_logger("cleanup_synthesis_store")


def _age_days(generated_at: str) -> int:
    """Возраст в днях от ISO8601 generated_at до сейчас (UTC)."""
    dt = datetime.fromisoformat(generated_at)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - dt).days


def find_expired(store_path: str = SYNTHESIS_STORE_PATH) -> tuple[list[dict], list[str]]:
    """
    Сканирует synthesis_store/ и возвращает (expired, warnings).

    expired — список {"path": Path, "id": str, "status": str, "age_days": int,
                       "retention_days": int}
    warnings — повреждённые/нечитаемые файлы (DEGRADE GRACEFULLY: пропустить
               файл, не падать на всём скане — ERROR_PHILOSOPHY в settings.py)
    """
    store = Path(store_path)
    expired: list[dict] = []
    warnings: list[str] = []

    if not store.exists():
        return expired, warnings

    for f in sorted(store.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            warnings.append(f"{f.name}: не удалось прочитать ({e}) — пропущен")
            continue

        status = data.get("status", "generated")
        retention_days = SYNTHESIS_RETENTION.get(status)

        if retention_days is None:
            continue  # бессрочное хранение для этого статуса

        generated_at = data.get("generated_at")
        if not generated_at:
            warnings.append(
                f"{f.name}: status='{status}' требует retention-проверки, "
                f"но generated_at отсутствует — пропущен (не можем определить возраст)"
            )
            continue

        try:
            age = _age_days(generated_at)
        except ValueError as e:
            warnings.append(f"{f.name}: невалидный generated_at ({e}) — пропущен")
            continue

        if age > retention_days:
            expired.append({
                "path": f,
                "id": data.get("id", f.stem),
                "cluster": data.get("cluster", "?"),
                "status": status,
                "age_days": age,
                "retention_days": retention_days,
            })

    return expired, warnings


def cleanup(apply: bool = False, verbose: bool = False) -> dict:
    """Выполняет (или симулирует, если apply=False) очистку synthesis_store/."""
    expired, warnings = find_expired()

    if warnings:
        print(f"⚠  {len(warnings)} предупреждений:")
        for w in warnings:
            print(f"   - {w}")

    if not expired:
        print("✓ Нет синтезов, превысивших retention policy — очистка не требуется")
        return {"expired": 0, "deleted": 0, "warnings": len(warnings)}

    print(f"\n{'УДАЛЕНО' if apply else 'БУДЕТ УДАЛЕНО (dry-run)'}: {len(expired)} файлов")
    print(f"{'─'*60}")
    for item in expired:
        print(
            f"  {item['id']} | cluster={item['cluster']} | "
            f"status={item['status']} | age={item['age_days']}d "
            f"(retention={item['retention_days']}d)"
        )

    if not apply:
        print(f"\nℹ  Это dry-run. Запусти с --apply, чтобы выполнить удаление.")
        return {"expired": len(expired), "deleted": 0, "warnings": len(warnings)}

    # Реальное удаление: сначала пишем в Audit Trail, потом удаляем файл
    # (fail loud — если логирование не удалось, файл остаётся на диске,
    # а не наоборот, чтобы Audit Trail никогда не лгал об удалённом,
    # которое на самом деле осталось).
    event_log = EventLog(EVENTS_LOG_PATH)
    deleted = 0
    for item in expired:
        event_log.emit(SynthesisStoreCleaned(
            synthesis_id=item["id"],
            cluster=item["cluster"],
            status=item["status"],
            age_days=item["age_days"],
            retention_days=item["retention_days"],
        ))
        item["path"].unlink()
        deleted += 1
        if verbose:
            print(f"  ✓ deleted {item['path'].name}")

    print(f"\n✓ Удалено {deleted} файлов, записано в {EVENTS_LOG_PATH}")
    return {"expired": len(expired), "deleted": deleted, "warnings": len(warnings)}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Очистка synthesis_store/ по retention policy (M1 ARR v3)"
    )
    parser.add_argument("--apply", action="store_true",
                         help="Реально удалить файлы (по умолчанию — dry-run)")
    parser.add_argument("--verbose", action="store_true",
                         help="Подробный вывод при удалении")
    args = parser.parse_args()

    try:
        stats = cleanup(apply=args.apply, verbose=args.verbose)
        sys.exit(ERROR_EXIT_CODES["success"])
    except Exception as e:
        logger.exception("Unexpected error in cleanup_synthesis_store")
        print(f"💥 {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["system_error"])


if __name__ == "__main__":
    main()
