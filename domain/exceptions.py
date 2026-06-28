"""
domain/exceptions.py
Bitcoin Intel — единая иерархия исключений системы.

Правило: все кастомные исключения наследуются от BitcoinIntelError.
Это позволяет поймать любую ошибку системы через except BitcoinIntelError.

Категории:
  ValidationError         — невалидные входные данные
  SynthesizerError        — ошибки синтезатора
  DataIntegrityError      — повреждение / несогласованность данных
  ArchitecturalViolation  — нарушение архитектурных контрактов
"""


class BitcoinIntelError(Exception):
    """Базовый класс всех исключений системы."""
    pass


# ─── Валидация ───────────────────────────────────────────────────────────────

class ValidationError(BitcoinIntelError):
    """Сигнал или объект не прошёл валидацию."""
    def __init__(self, field: str, value=None, reason: str = ""):
        self.field  = field
        self.value  = value
        self.reason = reason
        msg = f"Validation failed for '{field}'"
        if reason:
            msg += f": {reason}"
        if value is not None:
            msg += f" (got: {value!r})"
        super().__init__(msg)


class InvalidSignalIdError(ValidationError):
    """Неверный формат ID сигнала."""
    def __init__(self, signal_id: str):
        super().__init__(
            field="id",
            value=signal_id,
            reason="must match PREFIX-YYYY-MMDD-NNN (e.g. STR-2026-0628-001)"
        )


class DuplicateSignalError(BitcoinIntelError):
    """Сигнал с таким ID уже существует."""
    def __init__(self, signal_id: str):
        self.signal_id = signal_id
        super().__init__(f"Signal '{signal_id}' already exists in signals.json")


class MissingRequiredFieldError(ValidationError):
    """Отсутствует обязательное поле сигнала."""
    def __init__(self, field: str, signal_id: str = ""):
        ctx = f" in signal '{signal_id}'" if signal_id else ""
        super().__init__(field=field, reason=f"required field missing{ctx}")


# ─── Синтез ──────────────────────────────────────────────────────────────────

class SynthesizerError(BitcoinIntelError):
    """Базовый класс ошибок синтезатора."""
    pass


class SynthesizerConfigError(SynthesizerError):
    """Невалидная онтология или конфигурация синтезатора."""
    pass


class SynthesizerVersionError(SynthesizerError):
    """Несовместимая версия алгоритма."""
    def __init__(self, expected: str, actual: str):
        super().__init__(
            f"Algorithm version mismatch: expected {expected}, got {actual}"
        )


class EmptyClusterError(SynthesizerError):
    """Кластер не содержит активных сигналов в окне WINDOW_DAYS."""
    def __init__(self, cluster_key: str, window_days: int = 90):
        self.cluster_key = cluster_key
        super().__init__(
            f"Cluster '{cluster_key}' has no active signals "
            f"within {window_days}-day window"
        )


# ─── Данные ──────────────────────────────────────────────────────────────────

class DataIntegrityError(BitcoinIntelError):
    """Нарушение целостности данных."""
    pass


class OrphanRelationshipError(DataIntegrityError):
    """Связь ссылается на несуществующий сигнал."""
    def __init__(self, rel_id: str, missing_signal_id: str):
        self.rel_id           = rel_id
        self.missing_signal_id = missing_signal_id
        super().__init__(
            f"Relationship '{rel_id}' references "
            f"non-existent signal '{missing_signal_id}'"
        )


class CorruptedFileError(DataIntegrityError):
    """Файл повреждён и не может быть прочитан."""
    def __init__(self, path: str, reason: str = ""):
        self.path = path
        msg = f"File '{path}' is corrupted"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class DuplicateRelationshipError(DataIntegrityError):
    """Связь с такой же парой (from, to, type) уже существует."""
    def __init__(self, from_id: str, to_id: str, rel_type: str):
        super().__init__(
            f"Duplicate relationship: {from_id} --{rel_type}--> {to_id} already exists"
        )


# ─── Архитектурные контракты ─────────────────────────────────────────────────

class ArchitecturalViolationError(BitcoinIntelError):
    """
    Нарушение архитектурного контракта:
      - запрещённая зависимость между компонентами
      - запрещённая операция (например synthesizer пишет в signals.json)
      - запрещённый переход State Machine
    """
    pass


class ForbiddenStateTransitionError(ArchitecturalViolationError):
    """Попытка выполнить запрещённый переход State Machine."""
    def __init__(self, entity_type: str, entity_id: str,
                 from_state: str, to_state: str, allowed: set):
        self.entity_type = entity_type
        self.entity_id   = entity_id
        self.from_state  = from_state
        self.to_state    = to_state
        if allowed:
            hint = f"Allowed from '{from_state}': {sorted(allowed)}"
        else:
            hint = f"'{from_state}' is a final state — no transitions allowed"
        super().__init__(
            f"{entity_type.capitalize()} '{entity_id}': "
            f"transition '{from_state}' → '{to_state}' is forbidden. {hint}"
        )
