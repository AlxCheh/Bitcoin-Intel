"""
tests/integration/test_signal_workflow.py
Интеграционный тест: полный цикл добавления сигнала.
Тестирует взаимодействие: file_lock + domain/events + state_machine.
"""
import json
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_file_lock_atomic_write(tmp_path, monkeypatch):
    """
    atomic_write_json_safe пишет корректный JSON и не оставляет .tmp файлов.
    """
    monkeypatch.chdir(tmp_path)
    from infrastructure.file_lock import atomic_write_json_safe

    test_file = str(tmp_path / "test_output.json")
    data = [{"id": "STR-2026-0101-001", "signal": "test"}]
    atomic_write_json_safe(test_file, data)

    # Файл создан и валиден
    assert Path(test_file).exists()
    result = json.loads(Path(test_file).read_text(encoding="utf-8"))
    assert result == data

    # Нет .tmp файлов
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert not tmp_files, f"Found .tmp files: {tmp_files}"


def test_safe_read_json_returns_default_on_missing(tmp_path, monkeypatch):
    """safe_read_json возвращает default если файл не существует."""
    monkeypatch.chdir(tmp_path)
    from infrastructure.file_lock import safe_read_json

    result = safe_read_json("nonexistent.json", default=[])
    assert result == []


def test_safe_read_json_raises_on_corrupt_when_requested(tmp_path, monkeypatch):
    """safe_read_json(raise_on_corrupt=True) бросает CorruptedFileError."""
    monkeypatch.chdir(tmp_path)
    from infrastructure.file_lock import safe_read_json
    from domain.exceptions import CorruptedFileError

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{invalid json{{", encoding="utf-8")

    with pytest.raises(CorruptedFileError):
        safe_read_json(str(corrupt), raise_on_corrupt=True)


def test_safe_read_json_returns_default_on_corrupt_graceful(tmp_path, monkeypatch):
    """safe_read_json(raise_on_corrupt=False) возвращает default при повреждении."""
    monkeypatch.chdir(tmp_path)
    from infrastructure.file_lock import safe_read_json

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{invalid json{{", encoding="utf-8")

    result = safe_read_json(str(corrupt), default=[], raise_on_corrupt=False)
    assert result == []


def test_state_machine_valid_transition():
    """transition() не бросает исключение при допустимом переходе."""
    from domain.state_machine import transition
    # Не должно бросить
    transition("signal", "STR-2026-0101-001", "draft", "active")


def test_state_machine_forbidden_transition():
    """transition() бросает ForbiddenStateTransitionError при запрещённом переходе."""
    from domain.state_machine import transition
    from domain.exceptions import ForbiddenStateTransitionError

    with pytest.raises(ForbiddenStateTransitionError):
        transition("signal", "STR-2026-0101-001", "archived", "active")


def test_state_machine_final_state():
    """Из финального состояния нет переходов."""
    from domain.state_machine import transition, is_final_state
    from domain.exceptions import ForbiddenStateTransitionError

    assert is_final_state("signal", "archived") is True
    with pytest.raises(ForbiddenStateTransitionError):
        transition("signal", "STR-2026-0101-001", "archived", "draft")


def test_exceptions_hierarchy():
    """Все кастомные исключения наследуются от BitcoinIntelError."""
    from domain.exceptions import (
        BitcoinIntelError, ValidationError, DuplicateSignalError,
        CorruptedFileError, EmptyClusterError, ForbiddenStateTransitionError,
    )
    for exc_class in [ValidationError, DuplicateSignalError,
                      CorruptedFileError, EmptyClusterError,
                      ForbiddenStateTransitionError]:
        assert issubclass(exc_class, BitcoinIntelError), (
            f"{exc_class.__name__} must inherit from BitcoinIntelError"
        )


def test_logger_returns_logger_instance():
    """get_logger возвращает стандартный Logger."""
    import logging
    from infrastructure.logger import get_logger
    logger = get_logger("test_component")
    assert isinstance(logger, logging.Logger)


def test_logger_idempotent():
    """Повторный get_logger возвращает тот же объект (не дублирует handlers)."""
    from infrastructure.logger import get_logger
    l1 = get_logger("idempotent_test")
    l2 = get_logger("idempotent_test")
    assert l1 is l2
    assert len(l1.handlers) == 1
