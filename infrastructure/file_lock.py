"""
infrastructure/file_lock.py
Bitcoin Intel — атомарная запись файлов с блокировкой

Проблема: synthesizer.py и add_signal.py могут запускаться параллельно
и одновременно писать в signals.json или synthesis_cache.json.
Без блокировки — race condition → повреждённый JSON.

Решение:
  1. fcntl-based advisory lock (Unix-only, см. примечание)
  2. Атомарная запись через temp file → os.replace()

Примечание: работает только на Unix (Linux/macOS).
На Windows использовать msvcrt.locking или запускать скрипты последовательно.
"""

import os
import json
import fcntl
import tempfile
from contextlib import contextmanager
from typing import Any

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import ENCODING, JSON_ENSURE_ASCII


# ─── File Lock ────────────────────────────────────────────────────────────────
@contextmanager
def file_lock(path: str, timeout: float = 10.0):
    """
    Контекстный менеджер: эксклюзивная блокировка файла.

    Использование:
        with file_lock("signals.json"):
            # только один процесс здесь одновременно
            data = json.load(open("signals.json"))
            data["signals"].append(new_signal)
            atomic_write_json("signals.json", data)

    Args:
        path:    путь к файлу который нужно заблокировать
        timeout: максимальное время ожидания в секундах (не реализован таймаут
                 в базовом fcntl — используем LOCK_EX блокирующий вызов)

    Raises:
        OSError: если файл недоступен
    """
    lock_path = path + ".lock"
    lock_fd = open(lock_path, "w")
    try:
        # LOCK_EX — эксклюзивная блокировка, блокирует до освобождения
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
        # Убираем .lock файл после снятия блокировки
        try:
            os.unlink(lock_path)
        except FileNotFoundError:
            pass


# ─── Атомарная запись ─────────────────────────────────────────────────────────
def atomic_write_json(path: str, data: Any, indent: int = 2) -> None:
    """
    Атомарная запись JSON файла: temp file → os.replace().

    Гарантирует что читатель никогда не увидит частично записанный файл.
    Если процесс упадёт во время записи — оригинальный файл не повреждён.

    Args:
        path:   целевой путь файла
        data:   данные для сериализации в JSON
        indent: отступ для форматирования

    Алгоритм:
        1. Записать в temp файл рядом с целевым (тот же filesystem → os.replace атомарен)
        2. os.replace(temp, path) — атомарная операция на уровне ОС
    """
    dir_name = os.path.dirname(os.path.abspath(path))
    os.makedirs(dir_name, exist_ok=True)

    # Создаём temp файл в той же директории (важно для атомарности os.replace)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=ENCODING) as f:
            json.dump(data, f, ensure_ascii=JSON_ENSURE_ASCII, indent=indent)
            f.flush()
            os.fsync(f.fileno())   # гарантируем запись на диск до replace

        os.replace(tmp_path, path)
    except Exception:
        # Если что-то пошло не так — удаляем temp и пробрасываем ошибку
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


def atomic_append_jsonl(path: str, data: dict) -> None:
    """
    Атомарная запись одной строки в JSONL файл.

    Для events.jsonl: каждая строка независима,
    поэтому достаточно блокировки без temp-файла.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with file_lock(path):
        with open(path, "a", encoding=ENCODING) as f:
            f.write(json.dumps(data, ensure_ascii=JSON_ENSURE_ASCII) + "\n")
            f.flush()
            os.fsync(f.fileno())


# ─── Безопасное чтение ────────────────────────────────────────────────────────
def safe_read_json(path: str, default: Any = None) -> Any:
    """
    Читает JSON файл с защитой от повреждения.

    Если файл повреждён (невалидный JSON) — возвращает default
    вместо падения. Логирует ошибку в stderr.
    """
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding=ENCODING) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        import sys
        print(f"⚠ Повреждён JSON {path}: {e}", file=sys.stderr)
        return default


# ─── P1 §3: Corrupted file handling ──────────────────────────────────────────

import sys as _sys

def safe_read_json(path: str, default: Any = None,
                   raise_on_corrupt: bool = False) -> Any:
    """
    Читает JSON файл с защитой от повреждения.

    raise_on_corrupt=False (default): log WARNING + return default
        → DEGRADE GRACEFULLY (для synthesis_cache, relationships.json)
    raise_on_corrupt=True: raise CorruptedFileError
        → FAIL LOUD (для signals.json — без него система не работает)

    Выбор:
        False — synthesis_cache (можно перестроить), relationships.json (есть fallback)
        True  — signals.json (критический файл, нет разумного fallback)
    """
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding=ENCODING) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        from infrastructure.logger import get_logger as _get_logger
        _logger = _get_logger("file_lock")
        _logger.warning(f"Corrupted JSON at '{path}': {e}. Returning default.")
        if raise_on_corrupt:
            from domain.exceptions import CorruptedFileError
            raise CorruptedFileError(path, str(e))
        return default


def read_signals(raise_on_corrupt: bool = True) -> list:
    """
    Читает signals.json.
    По умолчанию FAIL LOUD — signals.json критический, нет разумного fallback.
    """
    from config.settings import SIGNALS_PATH
    return safe_read_json(SIGNALS_PATH, default=[], raise_on_corrupt=raise_on_corrupt)


# ─── P1 §5: Graceful shutdown — cleanup temp files on SIGINT/SIGTERM ─────────

import atexit
import signal

_active_temp_files: set = set()


def _cleanup_temp_files(signum=None, frame=None) -> None:
    """Удаляет незавершённые .tmp файлы при выходе процесса."""
    for tmp_path in list(_active_temp_files):
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
    if signum is not None:
        _sys.exit(128 + signum)


atexit.register(_cleanup_temp_files)
try:
    signal.signal(signal.SIGINT,  _cleanup_temp_files)
    signal.signal(signal.SIGTERM, _cleanup_temp_files)
except (OSError, ValueError):
    pass  # в некоторых средах (потоки) сигналы недоступны


def atomic_write_json_safe(path: str, data: Any, indent: int = 2) -> None:
    """
    Расширенная версия atomic_write_json с трекингом temp файла.
    Гарантирует удаление .tmp при SIGINT/SIGTERM/atexit.
    Использовать вместо atomic_write_json для критических файлов.
    """
    dir_name = os.path.dirname(os.path.abspath(path))
    os.makedirs(dir_name, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    _active_temp_files.add(tmp_path)
    try:
        with os.fdopen(fd, "w", encoding=ENCODING) as f:
            json.dump(data, f, ensure_ascii=JSON_ENSURE_ASCII, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise
    finally:
        _active_temp_files.discard(tmp_path)
