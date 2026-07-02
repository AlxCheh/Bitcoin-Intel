"""
scripts/approve_synthesis.py
Bitcoin Intel — утверждение синтеза аналитиком (C08).

Workflow:
  1. Показать список сгенерированных синтезов для кластера
  2. Аналитик проверяет tension и narrative
  3. Ввести rationale (объяснение выбора)
  4. Сменить status: generated → approved
  5. Записать ApprovalEvent в events.jsonl

Использование:
  python scripts/approve_synthesis.py --cluster strategy_model_stress
  python scripts/approve_synthesis.py --id synthesis_strategy_model_stress_20260629_142108
  python scripts/approve_synthesis.py --list
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    SYNTHESIS_STORE_PATH, EVENTS_LOG_PATH, ENCODING,
    ERROR_EXIT_CODES,
)
from infrastructure.file_lock import safe_read_json, atomic_write_json_safe
from infrastructure.logger import get_logger
from domain.exceptions import BitcoinIntelError, SynthesizerError
from domain.state_machine import transition
from domain.events import EventLog, SynthesisApproved
from domain.validator import validate_rationale_quality

logger = get_logger("approve_synthesis")


def list_pending(cluster_key: str | None = None) -> list[dict]:
    """Возвращает синтезы со статусом generated (ожидающие утверждения)."""
    store = Path(SYNTHESIS_STORE_PATH)
    if not store.exists():
        return []

    results = []
    for f in sorted(store.glob("synthesis_*.json"), reverse=True):
        try:
            s = json.loads(f.read_text(encoding=ENCODING))
            if s.get("status") == "generated":
                if cluster_key is None or s.get("cluster") == cluster_key:
                    s["_file"] = str(f)
                    results.append(s)
        except (json.JSONDecodeError, OSError) as e:
            # Sprint 0 / GH Issue #80 (bandit B110): раньше молча пропускался
            # (bare except Exception: pass) — битый файл в synthesis_store/
            # исчезал из списка ожидающих утверждения без единого следа.
            # DEGRADE GRACEFULLY (§9) требует пропуска, не падения всей функции
            # из-за одного файла, но деградация должна быть видимой, не тихой.
            logger.warning(f"Пропущен нечитаемый файл в synthesis_store/: {f} ({e})")
    return results


def show_synthesis(s: dict) -> None:
    """Показывает синтез аналитику для проверки."""
    print(f"\n{'─'*60}")
    print(f"  ID:        {s.get('id','?')}")
    print(f"  Cluster:   {s.get('cluster','?')}")
    print(f"  Phase:     {s.get('phase','?')}")
    print(f"  Strength:  {s.get('strength','?')}")
    print(f"  Confidence:{s.get('confidence','?')}")
    print(f"  Signals:   {s.get('signal_count','?')} used: {s.get('signals_used',[])[:3]}…")
    print(f"\n  TENSION:")
    print(f"  {s.get('tension','—')}")
    print(f"\n  NARRATIVE:")
    print(f"  {s.get('narrative','—')[:200]}")
    if s.get("takeaway"):
        print(f"\n  TAKEAWAY:")
        print(f"  {s.get('takeaway','')[:120]}")
    if s.get("structural_change", {}).get("detected"):
        sc = s["structural_change"]
        print(f"\n  ⚡ STRUCTURAL CHANGE: {sc.get('from_phase')} → {sc.get('to_phase')}")
    print(f"{'─'*60}")


def approve(synthesis_id: str, rationale: str) -> dict:
    """
    Утверждает синтез: generated → approved.

    Raises:
        SynthesizerError если синтез не найден или не в статусе generated
    """
    store = Path(SYNTHESIS_STORE_PATH)
    synthesis_file = store / f"{synthesis_id}.json"

    if not synthesis_file.exists():
        raise SynthesizerError(f"Synthesis '{synthesis_id}' not found in {store}")

    synthesis = json.loads(synthesis_file.read_text(encoding=ENCODING))

    if synthesis.get("status") != "generated":
        raise SynthesizerError(
            f"Cannot approve synthesis '{synthesis_id}': "
            f"status is '{synthesis.get('status')}', expected 'generated'"
        )

    # State Machine transition
    transition("synthesis", synthesis_id, "generated", "approved")

    # Проверить качество rationale (предупреждения, не блокируют)
    warnings = validate_rationale_quality(rationale, synthesis)
    if warnings:
        print(f"\n⚠  Предупреждения по качеству rationale:")
        for w in warnings:
            print(f"   - {w}")
        confirm = input("\nПродолжить утверждение? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Утверждение отменено.")
            sys.exit(0)

    # Обновить синтез
    synthesis["status"]      = "approved"
    synthesis["rationale"]   = rationale
    synthesis["approved_at"] = datetime.now(timezone.utc).isoformat()
    synthesis["approved_by"] = os.environ.get("USER", "analyst")

    atomic_write_json_safe(str(synthesis_file), synthesis)

    # Событие. tension/strength/confidence заполнены из synthesis — данные
    # уже доступны на этом шаге, без этого audit trail терял контекст
    # утверждённого решения (C3 ARR v3).
    log = EventLog(EVENTS_LOG_PATH)
    log.emit(SynthesisApproved(
        cluster=synthesis.get("cluster", ""),
        synthesis_id=synthesis_id,
        tension=synthesis.get("tension", ""),
        strength=synthesis.get("strength", ""),
        confidence=synthesis.get("confidence", 0.0),
        approved_by=synthesis["approved_by"],
        rationale=rationale,
    ))

    logger.info(
        f"Synthesis approved: {synthesis_id}",
        extra={"cluster": synthesis.get("cluster"), "synthesis_id": synthesis_id}
    )

    return synthesis


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Утверждение синтеза нарратива аналитиком"
    )
    parser.add_argument("--cluster", help="Показать синтезы для кластера")
    parser.add_argument("--id",      help="ID конкретного синтеза для утверждения")
    parser.add_argument("--list",    action="store_true",
                        help="Показать все ожидающие утверждения")
    parser.add_argument("--rationale", help="Обоснование (без интерактивного ввода)")
    args = parser.parse_args()

    try:
        # Показать список
        if args.list or (not args.id):
            pending = list_pending(args.cluster)
            if not pending:
                cluster_hint = f" для кластера '{args.cluster}'" if args.cluster else ""
                print(f"Нет синтезов ожидающих утверждения{cluster_hint}")
                return

            print(f"\nОжидают утверждения: {len(pending)} синтезов")
            for s in pending:
                show_synthesis(s)

            if not args.id:
                synthesis_id = input("\nВведите ID для утверждения (или Enter для выхода): ").strip()
                if not synthesis_id:
                    return
                args.id = synthesis_id

        # Утверждение
        if args.id:
            # Показать синтез
            store = Path(SYNTHESIS_STORE_PATH)
            f = store / f"{args.id}.json"
            if f.exists():
                show_synthesis(json.loads(f.read_text(encoding=ENCODING)))

            # Получить rationale
            rationale = args.rationale
            if not rationale:
                print("\nВведите rationale (объяснение выбора этого нарратива):")
                print("Пример: 'Выбран STR-2026-0620-001 как anchor (2 contradicts, weight=primary);")
                print("         tension точно описывает NAV-дисконт как рыночную оценку модели'")
                rationale = input("> ").strip()

            if not rationale:
                print("⛔ Rationale не может быть пустым")
                sys.exit(ERROR_EXIT_CODES["business_logic_error"])

            result = approve(args.id, rationale)
            print(f"\n✓ Синтез {result['id']} утверждён")
            print(f"  Cluster:   {result['cluster']}")
            print(f"  Approved:  {result['approved_at'][:19]}")
            print(f"  By:        {result['approved_by']}")

        sys.exit(ERROR_EXIT_CODES["success"])

    except BitcoinIntelError as e:
        print(f"⛔ {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["business_logic_error"])
    except KeyboardInterrupt:
        print("\nОтменено")
        sys.exit(0)
    except Exception as e:
        logger.exception("Unexpected error in approve_synthesis")
        print(f"💥 {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["system_error"])


if __name__ == "__main__":
    main()
