"""
domain/state_machine.py
Bitcoin Intel — явная обработка State Machine переходов.

Все сущности системы имеют конечные состояния и допустимые переходы.
Попытка запрещённого перехода → ForbiddenStateTransitionError (FAIL LOUD).

State Machines:
  Signal:       draft → active → archived
  Synthesis:    generated → reviewed → approved → published → superseded → archived
  Cluster:      proposed → active → deprecated → archived
  Relationship: proposed → active → retracted
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.exceptions import ForbiddenStateTransitionError
from infrastructure.logger import get_logger

logger = get_logger("state_machine")

# ─── Матрицы допустимых переходов ────────────────────────────────────────────

SIGNAL_TRANSITIONS: dict[str, set] = {
    "draft":    {"active"},
    "active":   {"archived"},
    "archived": set(),       # финальный
    "invalid":  {"draft"},   # только через fix_and_resubmit — не напрямую в active
}

SYNTHESIS_TRANSITIONS: dict[str, set] = {
    "generated":  {"reviewed", "archived"},
    "reviewed":   {"approved", "generated"},   # можно вернуть на доработку
    "approved":   {"published", "archived"},
    "published":  {"superseded"},
    "superseded": {"archived"},
    "archived":   set(),
}

CLUSTER_TRANSITIONS: dict[str, set] = {
    "proposed":   {"active", "archived"},
    "active":     {"deprecated"},
    "deprecated": {"archived"},
    "archived":   set(),
}

RELATIONSHIP_TRANSITIONS: dict[str, set] = {
    "proposed":  {"active", "retracted"},
    "active":    {"retracted"},
    "retracted": set(),
}

_MACHINES: dict[str, dict] = {
    "signal":       SIGNAL_TRANSITIONS,
    "synthesis":    SYNTHESIS_TRANSITIONS,
    "cluster":      CLUSTER_TRANSITIONS,
    "relationship": RELATIONSHIP_TRANSITIONS,
}


# ─── API ──────────────────────────────────────────────────────────────────────

def transition(entity_type: str, entity_id: str,
               from_state: str, to_state: str) -> None:
    """
    Проверяет и выполняет переход состояния.
    Бросает ForbiddenStateTransitionError при запрещённом переходе.

    Использование:
        transition("signal", "STR-2026-0628-001", "active", "archived")   # OK
        transition("signal", "STR-2026-0628-001", "archived", "active")   # → Error

    Args:
        entity_type: "signal" | "synthesis" | "cluster" | "relationship"
        entity_id:   ID сущности (для сообщения об ошибке)
        from_state:  текущее состояние
        to_state:    желаемое следующее состояние
    """
    machine = _MACHINES.get(entity_type)
    if machine is None:
        raise ValueError(
            f"Unknown entity type: '{entity_type}'. "
            f"Must be one of: {sorted(_MACHINES.keys())}"
        )

    allowed = machine.get(from_state, set())

    # Специальное правило: invalid → active запрещён напрямую
    if (entity_type == "signal"
            and from_state == "invalid"
            and to_state == "active"):
        raise ForbiddenStateTransitionError(
            entity_type, entity_id, from_state, to_state,
            allowed={"draft (then draft → active)"}
        )

    if to_state not in allowed:
        raise ForbiddenStateTransitionError(
            entity_type, entity_id, from_state, to_state, allowed
        )

    logger.info(
        f"{entity_type} '{entity_id}': {from_state} → {to_state}",
        extra={"signal_id": entity_id if entity_type == "signal" else None}
    )


def get_allowed_transitions(entity_type: str, current_state: str) -> set:
    """Возвращает допустимые следующие состояния."""
    return _MACHINES.get(entity_type, {}).get(current_state, set())


def is_final_state(entity_type: str, state: str) -> bool:
    """Возвращает True если состояние финальное (переходов нет)."""
    return len(get_allowed_transitions(entity_type, state)) == 0


def validate_state(entity_type: str, state: str) -> bool:
    """Возвращает True если состояние допустимо для данного типа сущности."""
    machine = _MACHINES.get(entity_type, {})
    # Состояние допустимо если оно есть как ключ ИЛИ как значение в transitions
    all_states: set = set(machine.keys())
    for targets in machine.values():
        all_states |= targets
    return state in all_states
