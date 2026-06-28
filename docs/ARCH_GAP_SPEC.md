# ARCH_GAP_SPEC — Полная спека незакрытых пробелов ARR
## Bitcoin Intel Narrative Intelligence Platform
## Версия: 3.0 · Дата: 2026-06-28 · Статус: ГОТОВО К РЕАЛИЗАЦИИ

> **Основание:** Сверка каждого FAIL/PARTIAL из ARR_REPORT (Этап 11) с реальным состоянием репозитория  
> **Метод:** GitHub API проверка + анализ содержимого файлов  
> **Результат:** 26 реальных пробелов не покрытых ни трекером, ни предыдущей версией спеки

---

## Что уже закрыто — не входит в эту спеку

| Артефакт | Закрывает |
|----------|-----------|
| `SECURITY.md` | B3, Auth MVP, XSS, Secrets |
| `DISASTER_RECOVERY.md` | B4, RTO/RPO, Backup, Recovery |
| `DEPLOYMENT.md` | B5, CI/CD, Environments, Rollback |
| `GLOSSARY.md` | Ubiquitous Language |
| `config/settings.py` | MAX_POSSIBLE_SCORE, DATE_POLICY, ENCODING, LEGACY_LINKS |
| `domain/events.py` | Domain Events (5 типов), EventLog |
| `infrastructure/file_lock.py` | Race condition, Atomic write, safe_read_json |
| `scripts/add_signal.py` | CLI add signal |
| IMPLEMENTATION_TRACKER B1 | hash() детерминизм → seed % len() |
| IMPLEMENTATION_TRACKER B2 | semantic_inverse_score алгоритм |
| IMPLEMENTATION_TRACKER TD6 | Tiebreaker 4-й уровень |

---

## Приоритеты реализации

Все 26 пробелов разделены на 4 уровня:

| Уровень | Критерий | Пробелов |
|---------|----------|---------|
| 🔴 **P1 — Блокирует старт** | без этого нельзя запустить систему или написать тест | 6 |
| 🟠 **P2 — До конца Фазы 0** | без этого архитектура неполна, риск переработки | 10 |
| 🟡 **P3 — До MVP** | улучшает качество и надёжность, не блокирует старт | 7 |
| ⚪ **P4 — После MVP** | требует Backend или реальных пользователей | 3 |

---

# 🔴 P1 — БЛОКИРУЕТ СТАРТ (реализовать первыми)

---

## §1. Error Handling Philosophy

**ARR:** «Error handling philosophy — не определена системно»  
**Проблема:** команда принимает разные решения — одни компоненты падают, другие молча глотают ошибки.

**Добавить в `config/settings.py`:**

```python
# ─── Error Handling Philosophy ───────────────────────────────────────────────
#
# Правило системы: FAIL LOUD на границах, DEGRADE GRACEFULLY внутри.
#
# FAIL LOUD (raise исключение) — когда:
#   - Входные данные нарушают инвариант (невалидный ID, отсутствует обязательное поле)
#   - Системная ошибка которую нельзя обойти (файл заблокирован >5 сек, диск полон)
#   - Нарушение архитектурного контракта (synthesizer пытается писать в signals.json)
#
# DEGRADE GRACEFULLY (log + return default) — когда:
#   - Один сигнал из кластера повреждён → пропустить его, синтезировать без него
#   - synthesis_cache устарел → перестроить на лету, не падать
#   - relationships.json отсутствует → работать только с links.* (LEGACY_LINKS_ENABLED)
#   - Одно поле сигнала невалидно → логировать warning, использовать default
#
# НИКОГДА:
#   - Не глотать исключения молча (except: pass) — только except Exception as e: logger.warning(...)
#   - Не падать при чтении данных если есть разумный fallback
#   - Не продолжать запись если файл повреждён при чтении

ERROR_PHILOSOPHY = {
    "fail_loud": [
        "invalid_signal_id_format",
        "missing_required_field",
        "architectural_contract_violation",
        "disk_full",
        "lock_timeout",
    ],
    "degrade_gracefully": [
        "single_signal_corrupt",
        "cache_stale",
        "relationships_missing",
        "optional_field_invalid",
    ],
    "lock_timeout_seconds": 5,
}

# Исключения системы — единая иерархия
# Все кастомные исключения наследуются от BitcoinIntelError
# чтобы можно было поймать все ошибки системы одним except
```

**Добавить `domain/exceptions.py`:**

```python
"""
domain/exceptions.py
Единая иерархия исключений Bitcoin Intel.

Правило: все кастомные исключения наследуются от BitcoinIntelError.
Это позволяет поймать любую ошибку системы через except BitcoinIntelError.
"""


class BitcoinIntelError(Exception):
    """Базовый класс всех исключений системы."""
    pass


# ─── Валидация ───────────────────────────────────────────────────────────────

class ValidationError(BitcoinIntelError):
    """Сигнал не прошёл валидацию."""
    def __init__(self, field: str, value, reason: str):
        self.field = field
        self.value = value
        self.reason = reason
        super().__init__(f"Validation failed for '{field}': {reason} (got: {value!r})")


class DuplicateSignalError(BitcoinIntelError):
    """Сигнал с таким ID уже существует."""
    def __init__(self, signal_id: str):
        self.signal_id = signal_id
        super().__init__(f"Signal '{signal_id}' already exists in signals.json")


class InvalidSignalIdError(ValidationError):
    """Неверный формат ID сигнала."""
    def __init__(self, signal_id: str):
        super().__init__("id", signal_id,
                         "must match PREFIX-YYYY-MMDD-NNN (e.g. STR-2026-0628-001)")


# ─── Синтез ──────────────────────────────────────────────────────────────────

class SynthesizerError(BitcoinIntelError):
    """Базовый класс ошибок синтезатора."""
    pass


class SynthesizerConfigError(SynthesizerError):
    """Невалидная онтология или конфигурация синтезатора."""
    pass


class SynthesizerVersionError(SynthesizerError):
    """Несовместимая версия алгоритма."""
    pass


class EmptyClusterError(SynthesizerError):
    """Кластер не содержит активных сигналов в окне WINDOW_DAYS."""
    def __init__(self, cluster_key: str, window_days: int):
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
        super().__init__(
            f"Relationship '{rel_id}' references non-existent signal '{missing_signal_id}'"
        )


class CorruptedFileError(DataIntegrityError):
    """Файл повреждён и не может быть прочитан."""
    def __init__(self, path: str, reason: str):
        self.path = path
        super().__init__(f"File '{path}' is corrupted: {reason}")


# ─── Архитектурные контракты ─────────────────────────────────────────────────

class ArchitecturalViolationError(BitcoinIntelError):
    """Нарушение архитектурного контракта (запрещённая зависимость, запрещённая операция)."""
    pass
```

**Acceptance:** `from domain.exceptions import ValidationError` работает без ошибок. Все компоненты используют эту иерархию.

---

## §2. Logging Strategy

**ARR:** «только логирование упоминается но формат, уровни, destination не определены»

**Добавить `infrastructure/logger.py`:**

```python
"""
infrastructure/logger.py
Централизованная стратегия логирования Bitcoin Intel.

Формат: структурированный JSON (machine-readable) в stderr.
Уровни:
  DEBUG   — детали алгоритма (score per signal, bridge selection)
  INFO    — значимые действия (signal added, synthesis created)
  WARNING — деградация без падения (corrupt signal skipped, cache stale)
  ERROR   — ошибка компонента (файл не записан, невалидный JSON)
  CRITICAL — системная ошибка (диск полон, signals.json corrupted)

Правило destination:
  Локально (ENVIRONMENT=local):  stderr + цветной вывод
  CI / Production:               stderr, JSON формат, без цвета
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    """JSON-форматтер для machine-readable логов."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "msg": record.getMessage(),
        }
        # Дополнительные поля если переданы через extra={}
        for key in ("signal_id", "cluster", "synthesis_id", "duration_ms", "error"):
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        return json.dumps(entry, ensure_ascii=False)


class HumanFormatter(logging.Formatter):
    """Читаемый форматтер для локальной разработки."""
    COLORS = {
        "DEBUG": "\033[36m",    # cyan
        "INFO": "\033[32m",     # green
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",    # red
        "CRITICAL": "\033[35m", # magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        return f"{color}[{ts}] {record.levelname:<8} {record.name}: {record.getMessage()}{self.RESET}"


def get_logger(component: str) -> logging.Logger:
    """
    Возвращает настроенный logger для компонента.

    Использование:
        from infrastructure.logger import get_logger
        logger = get_logger("synthesizer")
        logger.info("Synthesis started", extra={"cluster": "strategy_model_stress"})
    """
    logger = logging.getLogger(f"bitcoin_intel.{component}")

    if logger.handlers:
        return logger  # уже настроен

    handler = logging.StreamHandler(sys.stderr)
    env = os.environ.get("ENVIRONMENT", "local")

    if env == "local":
        handler.setFormatter(HumanFormatter())
        logger.setLevel(logging.DEBUG)
    else:
        handler.setFormatter(StructuredFormatter())
        logger.setLevel(logging.INFO)

    logger.addHandler(handler)
    logger.propagate = False
    return logger


# Уровни логирования по компонентам
COMPONENT_LOG_LEVELS = {
    "validator":             logging.INFO,
    "synthesizer":           logging.DEBUG,   # детали алгоритма нужны при отладке
    "contradiction_detector": logging.INFO,
    "cache_builder":         logging.INFO,
    "add_signal":            logging.INFO,
    "lifecycle":             logging.INFO,
    "file_lock":             logging.WARNING,  # только проблемы
}
```

---

## §3. Validation на уровне чтения (Corrupted File)

**ARR:** «Нет валидации на уровне чтения — Corrupted file при чтении = crash?»  
**Факт:** `safe_read_json()` в `file_lock.py` уже возвращает `default` при JSONDecodeError. Проблема в том что после этого компонент продолжает работу с `None` — не логирует, не эскалирует.

**Добавить в `infrastructure/file_lock.py`** (дополнение к существующему `safe_read_json`):

```python
from infrastructure.logger import get_logger
from domain.exceptions import CorruptedFileError

logger = get_logger("file_lock")

def safe_read_json(path: str, default=None, raise_on_corrupt: bool = False):
    """
    Читает JSON с защитой от повреждения.

    raise_on_corrupt=False (default): log WARNING + return default  → DEGRADE GRACEFULLY
    raise_on_corrupt=True:            raise CorruptedFileError       → FAIL LOUD

    Правило выбора:
      False — для synthesis_cache (можно перестроить), relationships.json (можно работать без)
      True  — для signals.json (без него система не работает)
    """
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding=ENCODING) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.warning(f"Corrupted JSON at '{path}': {e}. Returning default.")
        if raise_on_corrupt:
            raise CorruptedFileError(path, str(e))
        return default


def read_signals(raise_on_corrupt: bool = True) -> list:
    """signals.json — критический файл, corrupt = FAIL LOUD по умолчанию."""
    return safe_read_json(SIGNALS_PATH, default=[], raise_on_corrupt=raise_on_corrupt)
```

---

## §4. Component Initialization Order

**ARR:** «Порядок инициализации при запуске не определён»

**Добавить в `config/settings.py`:**

```python
# ─── Порядок инициализации компонентов ───────────────────────────────────────
#
# При запуске любого скрипта соблюдать этот порядок:
#
# 1. assert_deterministic_env()          — проверить PYTHONHASHSEED
# 2. assert_required_files_exist()       — проверить signals.json, ENTITIES.json
# 3. load ontology (если нужна)          — ontology.json через singleton
# 4. Инициализировать компонент          — validator / synthesizer / etc.
# 5. EventLog(EVENTS_LOG_PATH)           — готов к записи событий
#
# Онтология передаётся через параметр функции, не через глобальный singleton:
#   def synthesize(cluster_key, signals, ontology: dict) → SynthesisResult
# Причина: тестируемость (в тестах подменяем ontology без monkey-patching)

INITIALIZATION_ORDER = [
    "assert_deterministic_env",
    "assert_required_files_exist",
    "load_ontology",
    "init_component",
    "init_event_log",
]


def assert_required_files_exist() -> None:
    """
    Проверяет наличие критических файлов перед запуском.
    Вызывать в начале каждого скрипта после assert_deterministic_env().
    """
    import os
    required = [SIGNALS_PATH, ENTITIES_PATH]
    missing = [p for p in required if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError(
            f"Required files missing: {missing}. "
            f"Run from project root or check file paths."
        )
```

**Dependency Injection онтологии — правило:**

```python
# ✅ ПРАВИЛЬНО — онтология как параметр
def synthesize(cluster_key: str, signals: list, ontology: dict) -> dict:
    clusters = ontology.get("clusters", {})
    ...

# ❌ НЕПРАВИЛЬНО — глобальный singleton
_ONTOLOGY = None
def get_ontology():
    global _ONTOLOGY
    if _ONTOLOGY is None:
        _ONTOLOGY = json.load(open("ontology.json"))
    return _ONTOLOGY

# Причина: singleton не тестируется изолированно,
# тест меняет глобальное состояние для следующего теста
```

---

## §5. Graceful Shutdown при записи

**ARR:** «Что происходит при прерывании процесса в процессе записи в файл»  
**Факт:** `atomic_write_json()` в `file_lock.py` уже использует temp→rename. Проблема: `SIGINT` во время `os.fsync()` оставляет `.tmp` файл.

**Добавить в `infrastructure/file_lock.py`:**

```python
import signal
import atexit

_active_temp_files: set[str] = set()

def _cleanup_temp_files(signum=None, frame=None):
    """Удаляет незавершённые temp файлы при выходе."""
    for tmp_path in list(_active_temp_files):
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
    if signum:
        sys.exit(128 + signum)

# Регистрируем cleanup при старте модуля
atexit.register(_cleanup_temp_files)
signal.signal(signal.SIGINT, _cleanup_temp_files)
signal.signal(signal.SIGTERM, _cleanup_temp_files)

# В atomic_write_json — добавить трекинг temp файла:
def atomic_write_json(path: str, data, indent: int = 2) -> None:
    tmp_path = path + ".tmp"
    _active_temp_files.add(tmp_path)  # ← добавить
    try:
        with open(tmp_path, "w", encoding=ENCODING) as f:
            json.dump(data, f, ensure_ascii=JSON_ENSURE_ASCII, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        _active_temp_files.discard(tmp_path)  # ← добавить
```

---

## §6. Duplicate Signal Handling

**ARR:** «Два сигнала про одно событие с разными источниками — поведение не определено»

**Правило (добавить в `config/settings.py`):**

```python
# ─── Duplicate Signal Policy ─────────────────────────────────────────────────
#
# Два сигнала про одно событие с разными источниками — допустимо при условии:
#   1. ID различаются (разные NNN или разные PREFIX)
#   2. source различается (разные источники)
#   3. Аналитик осознанно добавляет оба — это не баг, это кросс-верификация
#
# Дубликатом считается сигнал с ОДИНАКОВЫМ id (блокируется DuplicateSignalError).
# Сигналы с одинаковым событием но разными ID — ЛЕГАЛЬНЫ.
#
# Детектор близких сигналов (не блокирует, только предупреждает):
#   Если два сигнала имеют одинаковый date + одинаковый actor + одинаковый cluster
#   → validator.py выводит WARNING: «Possible duplicate — verify intentional»
#   → аналитик принимает решение

DUPLICATE_WARNING_FIELDS = ["date", "actor", "cluster"]
# При совпадении всех трёх полей — предупреждение (не ошибка)
```

**Добавить в `validator.py` (предупреждение):**

```python
def check_possible_duplicate(new_signal: dict, existing_signals: list) -> str | None:
    """
    Возвращает warning string если новый сигнал похож на существующий.
    Не блокирует добавление — только информирует аналитика.
    """
    from config.settings import DUPLICATE_WARNING_FIELDS
    for s in existing_signals:
        if all(new_signal.get(f) == s.get(f) for f in DUPLICATE_WARNING_FIELDS):
            return (
                f"⚠ Possible duplicate of {s['id']}: "
                f"same date={s['date']}, actor={s['actor']}, cluster={s['cluster']}. "
                f"Intentional cross-verification? Add different source."
            )
    return None
```

---

# 🟠 P2 — ДО КОНЦА ФАЗЫ 0

---

## §7. State Machine — запрещённые переходы

**ARR:** «Нет обработки ошибочных переходов — что происходит при попытке запрещённого перехода?»

**Добавить `domain/state_machine.py`:**

```python
"""
domain/state_machine.py
Явная обработка запрещённых переходов для всех State Machines.
"""

from domain.exceptions import ArchitecturalViolationError


# Signal: draft → active → archived
SIGNAL_TRANSITIONS = {
    "draft":    {"active"},
    "active":   {"archived"},
    "archived": set(),          # финальный — переходов нет
    "invalid":  {"draft"},      # fix_and_resubmit: invalid → draft (не в active!)
}

# Synthesis: generated → reviewed → approved → published → superseded → archived
SYNTHESIS_TRANSITIONS = {
    "generated":  {"reviewed", "archived"},
    "reviewed":   {"approved", "generated"},  # можно вернуть на доработку
    "approved":   {"published", "archived"},
    "published":  {"superseded"},
    "superseded": {"archived"},
    "archived":   set(),
}

# Cluster: proposed → active → deprecated → archived
CLUSTER_TRANSITIONS = {
    "proposed":   {"active", "archived"},
    "active":     {"deprecated"},
    "deprecated": {"archived"},
    "archived":   set(),
}

# Relationship: proposed → active → retracted
RELATIONSHIP_TRANSITIONS = {
    "proposed": {"active", "retracted"},
    "active":   {"retracted"},
    "retracted": set(),
}

_MACHINES = {
    "signal":       SIGNAL_TRANSITIONS,
    "synthesis":    SYNTHESIS_TRANSITIONS,
    "cluster":      CLUSTER_TRANSITIONS,
    "relationship": RELATIONSHIP_TRANSITIONS,
}


def transition(entity_type: str, entity_id: str,
               from_state: str, to_state: str) -> None:
    """
    Выполняет переход состояния с проверкой допустимости.
    Бросает ArchitecturalViolationError при запрещённом переходе.

    Использование:
        transition("signal", "STR-2026-0628-001", "active", "archived")
        # → OK

        transition("signal", "STR-2026-0628-001", "archived", "active")
        # → ArchitecturalViolationError: Signal archived→active is forbidden
    """
    machine = _MACHINES.get(entity_type)
    if machine is None:
        raise ValueError(f"Unknown entity type: '{entity_type}'")

    allowed = machine.get(from_state, set())

    if to_state not in allowed:
        if not allowed:
            raise ArchitecturalViolationError(
                f"{entity_type.capitalize()} '{entity_id}' is in final state "
                f"'{from_state}' — no transitions allowed"
            )
        raise ArchitecturalViolationError(
            f"{entity_type.capitalize()} '{entity_id}': "
            f"transition '{from_state}' → '{to_state}' is forbidden. "
            f"Allowed from '{from_state}': {sorted(allowed)}"
        )

    # Специальное правило: invalid → active никогда (только через draft)
    if entity_type == "signal" and from_state == "invalid" and to_state == "active":
        raise ArchitecturalViolationError(
            f"Signal '{entity_id}': cannot go invalid → active directly. "
            f"Must go invalid → draft → active via fix_and_resubmit()"
        )


def get_allowed_transitions(entity_type: str, current_state: str) -> set:
    """Возвращает допустимые следующие состояния."""
    machine = _MACHINES.get(entity_type, {})
    return machine.get(current_state, set())
```

---

## §8. history_query.py

**ARR:** «history_query.py — не специфицирован вообще»

**Файл `scripts/history_query.py`:**

```python
"""
scripts/history_query.py
Исторические запросы к synthesis_store.

Позволяет аналитику:
  - Найти все синтезы по кластеру
  - Посмотреть как менялся tension кластера во времени
  - Воспроизвести конкретный синтез
  - Найти синтезы по дате

Использование:
  python scripts/history_query.py --cluster strategy_model_stress
  python scripts/history_query.py --cluster strategy_model_stress --since 2026-01-01
  python scripts/history_query.py --id syn-strategy_model_stress-20260628-001
  python scripts/history_query.py --tension-history strategy_model_stress
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import SYNTHESIS_STORE_PATH  # добавить в settings.py


def load_synthesis_store() -> list[dict]:
    """Загружает все файлы синтезов из synthesis_store/."""
    store = Path(SYNTHESIS_STORE_PATH)
    if not store.exists():
        return []
    syntheses = []
    for f in sorted(store.glob("synthesis_*.json")):
        try:
            syntheses.append(json.loads(f.read_text()))
        except json.JSONDecodeError:
            pass  # повреждённый файл — пропускаем
    return syntheses


def query_by_cluster(cluster_key: str, since: str | None = None) -> list[dict]:
    """Все синтезы кластера, опционально с фильтром по дате."""
    results = [
        s for s in load_synthesis_store()
        if s.get("cluster") == cluster_key
    ]
    if since:
        results = [s for s in results if s.get("computed_at", "") >= since]
    return sorted(results, key=lambda s: s.get("computed_at", ""))


def query_by_id(synthesis_id: str) -> dict | None:
    """Конкретный синтез по ID."""
    for s in load_synthesis_store():
        if s.get("id") == synthesis_id:
            return s
    return None


def tension_history(cluster_key: str) -> list[dict]:
    """
    История изменений tension для кластера.
    Возвращает список {date, tension, strength, status} в хронологическом порядке.
    """
    syntheses = query_by_cluster(cluster_key)
    return [
        {
            "computed_at": s.get("computed_at", "")[:10],
            "tension": s.get("tension", ""),
            "strength": s.get("strength", ""),
            "status": s.get("status", ""),
            "id": s.get("id", ""),
        }
        for s in syntheses
    ]


def main():
    parser = argparse.ArgumentParser(description="Исторические запросы к synthesis_store")
    parser.add_argument("--cluster", help="Кластер для поиска")
    parser.add_argument("--since", help="Дата с (YYYY-MM-DD)")
    parser.add_argument("--id", help="ID конкретного синтеза")
    parser.add_argument("--tension-history", metavar="CLUSTER",
                        help="История изменений tension кластера")
    parser.add_argument("--format", choices=["json", "table"], default="table")
    args = parser.parse_args()

    results = None

    if args.tension_history:
        results = tension_history(args.tension_history)
        if args.format == "table":
            print(f"\nTension history: {args.tension_history}")
            print(f"{'Date':<12} {'Status':<12} {'Tension'}")
            print("-" * 80)
            for r in results:
                tension_short = r["tension"][:50] + "…" if len(r["tension"]) > 50 else r["tension"]
                print(f"{r['computed_at']:<12} {r['status']:<12} {tension_short}")
            return

    elif args.id:
        s = query_by_id(args.id)
        results = [s] if s else []

    elif args.cluster:
        results = query_by_cluster(args.cluster, args.since)

    else:
        parser.print_help()
        return

    if args.format == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"\nFound {len(results)} synthesis records")
        for s in results:
            print(f"\n  ID:       {s.get('id')}")
            print(f"  Status:   {s.get('status')}")
            print(f"  Date:     {s.get('computed_at', '')[:10]}")
            print(f"  Strength: {s.get('strength')}")
            print(f"  Tension:  {s.get('tension', '')[:60]}")


if __name__ == "__main__":
    main()
```

**Добавить в `config/settings.py`:**
```python
SYNTHESIS_STORE_PATH = "synthesis_store"
```

---

## §9. Error Propagation между компонентами

**ARR:** «Как ошибка в компоненте передаётся пользователю — не определено»

**Правило (добавить в `config/settings.py`):**

```python
# ─── Error Propagation Rules ─────────────────────────────────────────────────
#
# Каждый скрипт-точка-входа (add_signal.py, synthesizer.py) отвечает за:
#   1. Поймать BitcoinIntelError → вывести читаемое сообщение в stderr → exit(1)
#   2. Поймать Exception         → вывести traceback → exit(2)
#   3. Успех                     → вывести подтверждение в stdout → exit(0)
#
# Компоненты (validator.py, synthesizer.py как библиотека) — только raise.
# Скрипты (add_signal.py, history_query.py) — только catch + user message.
#
# Пример паттерна для всех скриптов:

ERROR_EXIT_CODES = {
    "success":              0,
    "business_logic_error": 1,   # ValidationError, DuplicateSignalError
    "system_error":         2,   # непредвиденное исключение
    "data_integrity_error": 3,   # CorruptedFileError, OrphanRelationshipError
}
```

**Шаблон точки входа (применить во всех скриптах):**

```python
# В каждом scripts/*.py — стандартный main():

def main():
    from domain.exceptions import BitcoinIntelError, ValidationError
    from infrastructure.logger import get_logger
    logger = get_logger("add_signal")  # имя скрипта

    try:
        # ... логика ...
        print("✓ Done")
        sys.exit(0)

    except ValidationError as e:
        print(f"⛔ Validation error: {e}", file=sys.stderr)
        sys.exit(1)

    except BitcoinIntelError as e:
        print(f"⛔ Error: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        logger.exception("Unexpected error")
        print(f"💥 Unexpected error: {e}", file=sys.stderr)
        sys.exit(2)
```

---

## §10. migrate_relationships.py

**ARR:** «migrate_relationships.py упомянут, не специфицирован»

**Файл `scripts/migrate_relationships.py`:**

```python
"""
scripts/migrate_relationships.py
Миграция: links.* из signals.json → relationships.json

Запускать ОДИН РАЗ при переходе в Фазу C (конец LEGACY_LINKS_ENABLED).

Что делает:
  1. Читает все сигналы из signals.json
  2. Для каждого сигнала с непустым links.* создаёт Relationship объекты
  3. Записывает в data/relationships.json (append, не перезаписывает)
  4. Для rationale старых связей устанавливает "" (нет ретроспективных данных)
  5. Логирует каждую созданную связь в events.jsonl

Когда запускать:
  После того как ВСЕ новые связи пишутся напрямую в relationships.json.
  До этого момента — LEGACY_LINKS_ENABLED = True.

После запуска:
  Установить LEGACY_LINKS_ENABLED = False в config/settings.py
  Проверить: python scripts/validate_relationships.py
"""

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import (
    SIGNALS_PATH, RELATIONSHIPS_PATH, EVENTS_LOG_PATH, ENCODING, JSON_ENSURE_ASCII
)
from infrastructure.file_lock import atomic_write_json, safe_read_json
from domain.events import EventLog, RelationshipRetracted


def migrate(dry_run: bool = True) -> dict:
    """
    Выполняет миграцию.
    dry_run=True — только показать что будет создано, не писать.
    Возвращает статистику.
    """
    signals = safe_read_json(SIGNALS_PATH, default=[])
    existing_rels = safe_read_json(RELATIONSHIPS_PATH, default=[])
    existing_pairs = {
        (r["from_id"], r["to_id"], r["type"])
        for r in existing_rels
    }

    new_relationships = []
    stats = {"created": 0, "skipped_duplicate": 0, "signals_processed": 0}

    for signal in signals:
        signal_id = signal.get("id")
        if not signal_id:
            continue

        links = signal.get("links", {})
        if not links:
            continue

        stats["signals_processed"] += 1

        for rel_type, targets in [
            ("confirms",      links.get("confirms", [])),
            ("contradicts",   links.get("contradicts", [])),
            ("context_chain", links.get("context_chain", [])),
        ]:
            for target_id in targets:
                if not target_id:
                    continue
                pair = (signal_id, target_id, rel_type)
                if pair in existing_pairs:
                    stats["skipped_duplicate"] += 1
                    continue

                rel = {
                    "id":         str(uuid.uuid4()),
                    "from_id":    signal_id,
                    "to_id":      target_id,
                    "type":       rel_type,
                    "rationale":  "",   # нет ретроспективных данных
                    "created":    datetime.now(timezone.utc).isoformat(),
                    "created_by": "migration_script",
                    "migrated_from": "links.*",
                    "status":     "active",
                }
                new_relationships.append(rel)
                existing_pairs.add(pair)
                stats["created"] += 1
                print(f"  {'[DRY]' if dry_run else '[CREATE]'} "
                      f"{signal_id} --{rel_type}--> {target_id}")

    print(f"\nStats: {stats}")

    if not dry_run and new_relationships:
        all_rels = existing_rels + new_relationships
        atomic_write_json(RELATIONSHIPS_PATH, all_rels)
        print(f"✓ Written {len(new_relationships)} relationships to {RELATIONSHIPS_PATH}")
        print("Next step: set LEGACY_LINKS_ENABLED = False in config/settings.py")
    elif dry_run:
        print("\nDRY RUN — no files written. Run with --apply to execute.")

    return stats


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate links.* to relationships.json")
    parser.add_argument("--apply", action="store_true",
                        help="Actually write (default: dry run)")
    args = parser.parse_args()
    migrate(dry_run=not args.apply)
```

---

## §11. Data Retention для synthesis_store

**ARR:** «Нет для synthesis_store (только 180 дней для сигналов)»

**Добавить в `config/settings.py`:**

```python
# ─── Data Retention Policy ────────────────────────────────────────────────────
ARCHIVE_SIGNAL_DAYS    = 180   # уже определено
RETAIN_SYNTHESIS_DAYS  = 730   # 2 года — approved синтезы не удаляются, только архивируются
RETAIN_EVENTS_DAYS     = 365   # 1 год events.jsonl (ротация)
RETAIN_SNAPSHOTS_COUNT = 7     # локальных backup снапшотов

# Правила для synthesis_store:
#   superseded синтезы — хранить RETAIN_SYNTHESIS_DAYS, затем перемещать в archive/
#   approved/published — хранить бессрочно (git history как backup)
#   generated/reviewed (не утверждённые) — удалять через 30 дней
SYNTHESIS_RETENTION = {
    "generated": 30,
    "reviewed":  30,
    "approved":  None,    # бессрочно
    "published": None,    # бессрочно
    "superseded": RETAIN_SYNTHESIS_DAYS,
    "archived":  None,    # бессрочно в archive/
}
```

---

## §12. Null Handling спецификация

**ARR:** «nullable указан в схеме, но обработка не специфицирована»

**Добавить в `config/settings.py`:**

```python
# ─── Null Handling Rules ─────────────────────────────────────────────────────
#
# Поля могут быть null/отсутствовать. Правила обработки:
#
# Текстовые поля (tension, context, caveat, macro_implication):
#   None → пустая строка "" при рендере
#   "" → отображать как отсутствующее (не рендерить блок)
#
# Числовые поля (confidence):
#   None → вычислить на лету если возможно, иначе 0.5 (нейтральное)
#
# Списки (links.confirms, data):
#   None → пустой список []
#   Никогда не итерировать без проверки: for x in (field or [])
#
# ID поля (actor, flow — необязательные enum):
#   None → "unknown" при рендере, не участвует в фильтрации
#
# Правило в коде:
#   signal.get("tension") or ""       — текстовые
#   signal.get("data") or []          — списки
#   signal.get("confidence") or 0.5   — числа

NULL_DEFAULTS = {
    "tension":           "",
    "context":           "",
    "caveat":            "",
    "macro_implication": "",
    "data":              [],
    "links":             {"confirms": [], "contradicts": [], "context_chain": []},
    "confidence":        0.5,
    "actor":             "unknown",
    "flow":              "neutral",
    "rationale":         "",
}
```

---

## §13. Quality Report алгоритм

**ARR:** «quality_report.py — поля описаны, алгоритм не определён»

**Спека `scripts/quality_report.py`:**

```python
"""
scripts/quality_report.py
Отчёт о качестве базы сигналов.

Метрики:
  - Покрытие обязательных полей (% сигналов с заполненным tension, macro_implication)
  - Свежесть (% сигналов за последние 30/90 дней)
  - Разнообразие (распределение по cluster, dir, weight)
  - Качество tension (% содержащих конструкцию vs/несмотря на)
  - Связность (% сигналов с хотя бы одной связью)
  - Кластеры без сигналов (потенциально устаревшие)

Алгоритм расчёта каждой метрики:
"""

from datetime import date, timedelta

def compute_quality_report(signals: list[dict]) -> dict:
    """
    Вычисляет отчёт качества для списка сигналов.
    Все метрики — от 0.0 до 1.0 (доля, не процент).
    """
    if not signals:
        return {"error": "no signals", "total": 0}

    total = len(signals)
    today = date.today()
    tension_markers = ["vs", "несмотря на", "при условии", "вопреки", "—"]

    # 1. Покрытие обязательных полей
    has_tension = sum(1 for s in signals if s.get("tension", "").strip())
    has_macro   = sum(1 for s in signals if s.get("macro_implication", "").strip())
    has_context = sum(1 for s in signals if s.get("context", "").strip())
    has_caveat  = sum(1 for s in signals if s.get("caveat", "").strip())

    # 2. Свежесть
    def age(s):
        try:
            return (today - date.fromisoformat(s.get("date", "1970-01-01"))).days
        except ValueError:
            return 9999

    fresh_30  = sum(1 for s in signals if age(s) <= 30)
    fresh_90  = sum(1 for s in signals if age(s) <= 90)

    # 3. Качество tension (формула соблюдена?)
    def tension_valid(s):
        t = s.get("tension", "")
        if not t:
            return False
        if not t[0].isupper():
            return False
        return any(m in t for m in tension_markers)

    tension_quality = sum(1 for s in signals if tension_valid(s))

    # 4. Связность
    def has_links(s):
        links = s.get("links", {})
        return any(links.get(k) for k in ["confirms", "contradicts", "context_chain"])

    connected = sum(1 for s in has_links(s) for s in signals)
    connected = sum(1 for s in signals if has_links(s))

    # 5. Распределение по dir
    dir_counts = {}
    for s in signals:
        d = s.get("dir", "unknown")
        dir_counts[d] = dir_counts.get(d, 0) + 1

    # 6. Кластеры
    cluster_counts = {}
    for s in signals:
        c = s.get("cluster", "unknown")
        cluster_counts[c] = cluster_counts.get(c, 0) + 1

    return {
        "total_signals": total,
        "generated_at": today.isoformat(),
        "coverage": {
            "tension":           round(has_tension / total, 3),
            "macro_implication": round(has_macro / total, 3),
            "context":           round(has_context / total, 3),
            "caveat":            round(has_caveat / total, 3),
        },
        "freshness": {
            "last_30_days": round(fresh_30 / total, 3),
            "last_90_days": round(fresh_90 / total, 3),
        },
        "quality": {
            "tension_formula_valid": round(tension_quality / total, 3),
            "signals_with_links":    round(connected / total, 3),
        },
        "distribution": {
            "by_dir":     dir_counts,
            "by_cluster": cluster_counts,
        },
        "health": _compute_health_score(has_tension, has_macro, tension_quality,
                                         fresh_30, connected, total),
    }


def _compute_health_score(has_tension, has_macro, tension_quality,
                           fresh_30, connected, total) -> dict:
    """
    Итоговая оценка здоровья базы [0–100].
    Веса: tension coverage 30%, macro coverage 20%,
          tension quality 20%, freshness 15%, connectivity 15%.
    """
    score = (
        (has_tension / total) * 30 +
        (has_macro / total) * 20 +
        (tension_quality / total) * 20 +
        (fresh_30 / total) * 15 +
        (connected / total) * 15
    )
    score = round(score, 1)
    grade = "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D"
    return {"score": score, "grade": grade, "max": 100}
```

---

## §14. Backward Compatibility механизм

**ARR:** «Backward compatibility описана концептуально, механизм не определён»

**Добавить в `config/settings.py`:**

```python
# ─── Schema Versioning ────────────────────────────────────────────────────────
SIGNAL_SCHEMA_VERSION = "1.0"
# При изменении схемы — увеличить версию и добавить migration в scripts/

# Backward Compatibility правила:
#   PATCH (1.0.x → 1.0.y): добавление необязательного поля — обратно совместимо
#     → читать через signal.get("new_field", default) — старые файлы работают
#   MINOR (1.0 → 1.1): переименование поля или изменение enum значений
#     → добавить migration script: scripts/migrate_schema_1_0_to_1_1.py
#     → читать оба варианта: signal.get("new_name") or signal.get("old_name")
#   MAJOR (1.x → 2.x): удаление поля или изменение формата ID
#     → полная миграция всех файлов перед деплоем
#     → grace_period: поддерживать старый формат 30 дней параллельно

SCHEMA_BACKWARD_COMPAT = {
    "deprecated_fields": {
        "links": {
            "replaced_by": "relationships.json",
            "read_until":  "phase_c_migration",
            "flag":        "LEGACY_LINKS_ENABLED",
        }
    }
}
```

---

## §15. Idempotency всех компонентов

**ARR:** «Idempotency — только validator и cache_builder; synthesizer — да; остальные не проверены»

**Правило + матрица (добавить в `config/settings.py`):**

```python
# ─── Idempotency Contract ────────────────────────────────────────────────────
#
# Компонент идемпотентен если многократный вызов с одинаковыми данными
# не меняет результат и не имеет нежелательных побочных эффектов.
#
# Матрица:
#   validator.py                → ✅ идемпотентен (только читает + проверяет)
#   synthesizer.py              → ✅ идемпотентен (не пишет, только возвращает)
#   synthesis_cache_builder.py  → ✅ идемпотентен (temp→rename)
#   contradiction_detector.py  → ✅ идемпотентен (только предлагает)
#   add_signal.py               → ⚠ НЕ идемпотентен — второй вызов = DuplicateSignalError
#                                   это ПРАВИЛЬНО: добавление сигнала — side effect
#   history_query.py            → ✅ идемпотентен (только читает)
#   migrate_relationships.py    → ✅ идемпотентен (пропускает дубликаты через existing_pairs)
#   validate_relationships.py   → ✅ идемпотентен (только читает + валидирует)
#   quality_report.py           → ✅ идемпотентен (только читает)
#   backup.py                   → ⚠ создаёт новый снапшот — side effect (ожидаемый)
#
# Правило для новых компонентов:
#   Если компонент пишет в файл — использовать atomic_write_json (idempotent write)
#   Если компонент добавляет запись — проверять дубликат перед записью
```

---

## §16. Noise Filtering — дубликаты сигналов

**ARR:** «Noise filtering — только возрастной фильтр. Нет фильтра дубликатов»

Уже частично закрыто в §6 (Duplicate Signal Handling — предупреждение от validator).  
Дополнение: фильтрация при синтезе (в `synthesizer.py`):

```python
# domain/synthesizer.py — добавить шаг дедупликации перед синтезом

def deduplicate_signals(signals: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Удаляет дублирующие сигналы перед синтезом.
    Дубликат при синтезе = одинаковый (date, actor, cluster, dir).
    
    Возвращает: (deduplicated_signals, ignored_ids)
    Из дублирующей группы оставляет сигнал с наибольшим weight_score.
    """
    from config.settings import WEIGHT_SCORE
    seen: dict[tuple, dict] = {}
    ignored_ids: list[str] = []

    for signal in signals:
        key = (
            signal.get("date", ""),
            signal.get("actor", ""),
            signal.get("cluster", ""),
            signal.get("dir", ""),
        )
        if key in seen:
            existing = seen[key]
            existing_score = WEIGHT_SCORE.get(existing.get("weight", ""), 0)
            new_score = WEIGHT_SCORE.get(signal.get("weight", ""), 0)
            if new_score > existing_score:
                ignored_ids.append(existing["id"])
                seen[key] = signal
            else:
                ignored_ids.append(signal["id"])
        else:
            seen[key] = signal

    return list(seen.values()), ignored_ids
```

---

## §17. Structural Change Detection — противоречие контракту

**ARR:** «synthesizer.py по контракту "не читает файлы напрямую" — противоречие с необходимостью доступа к synthesis_store»

**Решение — разделить ответственность:**

```python
# Контракт synthesizer.py (§18.2) нарушается если он сам читает synthesis_store.
# Решение: предыдущий синтез передаётся как параметр.

# ❌ БЫЛО (нарушает контракт):
# def synthesize(cluster_key, signals):
#     prev = json.load(open(f"synthesis_store/{cluster_key}_latest.json"))
#     ...

# ✅ СТАЛО (контракт соблюдён):
def synthesize(
    cluster_key: str,
    signals: list[dict],
    ontology: dict,
    previous_synthesis: dict | None = None,   # ← передаётся снаружи
) -> dict:
    """
    previous_synthesis — загружается вызывающим кодом (scripts/run_synthesis.py),
    а не внутри synthesizer.py.
    Synthesizer не читает файлы — только принимает данные через параметры.
    """
    ...
    # Structural change detection
    if previous_synthesis:
        prev_phase = previous_synthesis.get("phase")
        if prev_phase != current_phase:
            result["structural_change"] = {
                "detected": True,
                "from_phase": prev_phase,
                "to_phase": current_phase,
            }
    ...

# scripts/run_synthesis.py — загружает previous_synthesis перед вызовом:
def run_synthesis_for_cluster(cluster_key: str) -> dict:
    from infrastructure.file_lock import safe_read_json
    signals = safe_read_json(SIGNALS_PATH, default=[])
    ontology = safe_read_json("ontology.json", default={})
    
    # Загружаем предыдущий синтез (вне synthesizer.py!)
    latest_file = find_latest_synthesis(cluster_key)
    previous = safe_read_json(latest_file) if latest_file else None
    
    from domain.synthesizer import synthesize
    return synthesize(cluster_key, signals, ontology, previous)
```

---

# 🟡 P3 — ДО MVP

---

## §18. Uncertainty Handling

**ARR:** «Не специфицировано поведение при 50/50 pos/neg, два trigger, устаревший tension»

**Добавить в `config/settings.py`:**

```python
# ─── Uncertainty Handling Rules ──────────────────────────────────────────────

UNCERTAINTY_RULES = {
    # 50/50 pos/neg в кластере → направление = "contested"
    "pos_neg_balance_threshold": 0.6,  # если pos/(pos+neg) < 0.6 → contested
    "contested_strength_penalty": 0.7, # умножить strength score на 0.7

    # Два trigger в кластере → выбрать более свежий
    "multiple_triggers_resolution": "most_recent",

    # Устаревший tension (победитель кластера старше N дней)
    "tension_staleness_days": 90,      # tension старше 90 дней → добавить метку STALE
    "tension_stale_label": "⚠ Нарратив устарел — tension не обновлялся более 90 дней",
}
```

**Логика в `synthesizer.py`:**

```python
def handle_uncertainty(signals: list[dict], phase: str) -> dict:
    """
    Обрабатывает неопределённые ситуации перед синтезом нарратива.
    Возвращает dict с корректировками для результата синтеза.
    """
    from config.settings import UNCERTAINTY_RULES
    from datetime import date

    adjustments = {}

    # 1. Проверка баланса pos/neg
    pos = sum(1 for s in signals if s.get("dir") == "pos")
    neg = sum(1 for s in signals if s.get("dir") == "neg")
    total_directional = pos + neg
    if total_directional > 0:
        ratio = pos / total_directional
        threshold = UNCERTAINTY_RULES["pos_neg_balance_threshold"]
        if threshold > ratio > (1 - threshold):
            adjustments["direction"] = "contested"
            adjustments["score_multiplier"] = UNCERTAINTY_RULES["contested_strength_penalty"]

    # 2. Два trigger → более свежий
    triggers = [s for s in signals if s.get("narrative_role") == "trigger"]
    if len(triggers) > 1:
        triggers.sort(key=lambda s: s.get("date", ""), reverse=True)
        adjustments["anchor_trigger"] = triggers[0]["id"]
        adjustments["ignored_triggers"] = [s["id"] for s in triggers[1:]]

    # 3. Устаревший tension
    winner = max(signals,
                 key=lambda s: len(s.get("links", {}).get("contradicts", [])),
                 default=None)
    if winner:
        try:
            tension_age = (date.today() - date.fromisoformat(winner.get("date", ""))).days
            if tension_age > UNCERTAINTY_RULES["tension_staleness_days"]:
                adjustments["tension_stale"] = True
                adjustments["tension_stale_label"] = UNCERTAINTY_RULES["tension_stale_label"]
        except ValueError:
            pass

    return adjustments
```

---

## §19. Explanation Quality

**ARR:** «rationale генерируется но quality не проверяется»

**Добавить в `validator.py`:**

```python
def validate_rationale_quality(rationale: str, synthesis: dict) -> list[str]:
    """
    Проверяет качество rationale синтеза.
    Возвращает список предупреждений (не блокирует утверждение).

    Критерии:
      1. Не пустой (если synthesis approved)
      2. Длина > 50 символов (слишком короткий = бессодержательный)
      3. Упоминает хотя бы один ID сигнала из signals_used
      4. Не идентичен tension (rationale ≠ tension — это разные поля)
    """
    warnings = []

    if not rationale or not rationale.strip():
        if synthesis.get("status") == "approved":
            warnings.append("Rationale is empty for approved synthesis — explain the choice")
        return warnings  # если пустой — остальные проверки бессмысленны

    if len(rationale) < 50:
        warnings.append(f"Rationale too short ({len(rationale)} chars) — add more context")

    signals_used = synthesis.get("signals_used", [])
    if signals_used:
        mentions_signal = any(sid in rationale for sid in signals_used)
        if not mentions_signal:
            warnings.append(
                "Rationale doesn't mention any signal ID — "
                "reference specific signals to explain the choice"
            )

    tension = synthesis.get("tension", "")
    if tension and rationale.strip() == tension.strip():
        warnings.append("Rationale is identical to tension — rationale should explain WHY this tension was chosen")

    return warnings
```

---

## §20. Performance Baselines

**ARR:** «synthesize(42 signals) < 100ms как единственная метрика; нет baseline для других операций»

**Добавить в `config/settings.py`:**

```python
# ─── Performance Baselines ────────────────────────────────────────────────────
# Все операции измеряются в миллисекундах.
# Нарушение baseline = WARNING в логах (не ошибка, не падение).

PERFORMANCE_BASELINES_MS = {
    "validate_signal":          10,    # один сигнал
    "synthesize_cluster":      100,    # до 100 сигналов
    "detect_contradictions":    50,    # на паре сигналов
    "build_cache":             500,    # все кластеры
    "read_signals_json":        50,    # cold read
    "write_atomic_json":        20,    # атомарная запись
    "health_check":            200,    # полная проверка
    "quality_report":          300,    # полный отчёт
    "history_query_cluster":   100,    # запрос по кластеру
}
```

**Декоратор для измерения (добавить в `infrastructure/logger.py`):**

```python
import time
import functools
from config.settings import PERFORMANCE_BASELINES_MS

def measure_performance(operation: str):
    """
    Декоратор: измеряет время выполнения и логирует WARNING при превышении baseline.

    Использование:
        @measure_performance("synthesize_cluster")
        def synthesize(cluster_key, signals, ontology):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            result = func(*args, **kwargs)
            elapsed_ms = (time.monotonic() - start) * 1000
            baseline = PERFORMANCE_BASELINES_MS.get(operation)
            logger = get_logger("performance")
            if baseline and elapsed_ms > baseline:
                logger.warning(
                    f"{operation} took {elapsed_ms:.0f}ms "
                    f"(baseline: {baseline}ms)",
                    extra={"duration_ms": elapsed_ms, "operation": operation}
                )
            else:
                logger.debug(f"{operation}: {elapsed_ms:.0f}ms")
            return result
        return wrapper
    return decorator
```

---

## §21. Test Environment Isolation

**ARR:** «Нет изоляции тестового окружения»

**Добавить `tests/conftest.py`:**

```python
"""
tests/conftest.py
Глобальные fixtures для pytest — изоляция тестового окружения.
"""

import json
import os
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    """
    Автоматически применяется ко всем тестам.
    Изолирует файловую систему: тесты не читают/пишут в реальные файлы проекта.
    """
    # Минимальные файлы для работы компонентов
    (tmp_path / "signals.json").write_text("[]")
    (tmp_path / "ENTITIES.json").write_text("[]")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "events.jsonl").write_text("")
    (tmp_path / "synthesis_store").mkdir()

    # Переключаем рабочую директорию
    monkeypatch.chdir(tmp_path)

    # PYTHONHASHSEED=0 для детерминизма
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    monkeypatch.setenv("ENVIRONMENT", "test")

    yield tmp_path


@pytest.fixture
def sample_signal() -> dict:
    """Валидный тестовый сигнал для переиспользования в тестах."""
    return {
        "id": "STR-2026-0101-001",
        "date": "2026-01-01",
        "signal": "Тестовый сигнал",
        "cat": "narrative", "catLabel": "📰 Нарратив",
        "dir": "pos", "horizon": "mid",
        "theme": "institutionalization",
        "weight": "media", "actor": "corporate", "flow": "inflow",
        "tension": "Тест vs контроль",
        "macro_implication": "Интеграционный тест подтверждает корректность архитектуры системы",
        "narrative_role": "background",
        "cluster": "test_cluster",
        "source": "Test Suite (январь 2026)",
        "links": {"confirms": [], "contradicts": [], "context_chain": []},
        "data": [], "context": "", "caveat": "",
    }


@pytest.fixture
def sample_cluster_signals(sample_signal) -> list[dict]:
    """Набор из 3 сигналов для тестирования синтеза."""
    import copy
    signals = []
    for i, (role, direction) in enumerate([
        ("trigger", "pos"),
        ("complication", "neg"),
        ("background", "neu"),
    ]):
        s = copy.deepcopy(sample_signal)
        s["id"] = f"STR-2026-0101-00{i+1}"
        s["narrative_role"] = role
        s["dir"] = direction
        s["links"]["contradicts"] = (
            [f"STR-2026-0101-00{i}"] if role == "complication" else []
        )
        signals.append(s)
    return signals
```

---

## §22. Graceful Degradation (не только UI)

**ARR:** «Fallback описан для UI, нет для других компонентов»

**Добавить в `config/settings.py`:**

```python
# ─── Graceful Degradation Matrix ─────────────────────────────────────────────
#
# Компонент         │ При сбое                    │ Поведение
# ──────────────────┼─────────────────────────────┼─────────────────────────────
# validator.py      │ один сигнал невалиден        │ skip + WARNING, продолжить
# synthesizer.py    │ один сигнал corrupt          │ skip + WARNING, синтез без него
# synthesizer.py    │ пустой кластер               │ EmptyClusterError (ожидаемое)
# cache_builder.py  │ synthesis_store пуст         │ пустой cache, не падать
# cache_builder.py  │ один файл в store corrupt    │ skip + WARNING
# contradiction_    │ один сигнал без macro_impl   │ пропустить пару, продолжить
# detector.py       │                              │
# history_query.py  │ corrupt файл в store         │ skip + WARNING, продолжить
# quality_report.py │ любая ошибка поля            │ считать как отсутствующее
# add_signal.py     │ дубликат ID                  │ DuplicateSignalError (FAIL LOUD)
# add_signal.py     │ disk full                    │ CorruptedFileError (FAIL LOUD)
```

---

# ⚪ P4 — ПОСЛЕ MVP

---

## §23. Observability / Monitoring

**ARR:** «Только /health endpoint. Мониторинг, трейсинг, алерты отсутствуют»  
**Почему P4:** требует Backend (FastAPI/SQLite). GitHub Pages не поддерживает серверный мониторинг.

**Минимум который можно сделать сейчас (без Backend):**

```python
# scripts/health_check.py — уже упомянут в ARCH_GAP_SPEC v2.0
# Запускать в CI после каждого деплоя:
#   python scripts/health_check.py → exit 0 если ОК

# SLI/SLO для будущего Backend:
FUTURE_SLI = {
    "synthesis_freshness_days": 7,   # синтез не старше 7 дней
    "signal_freshness_days":   14,   # новые сигналы не реже чем раз в 2 недели
    "data_validity_percent":   99,   # 99% сигналов проходят validator.py
}
```

---

## §24. Property Tests (Hypothesis)

**ARR:** «Примеры есть, library не в dependencies»

```
# requirements.txt — добавить:
hypothesis>=6.100.0

# Минимальный property test:
# tests/test_properties.py
from hypothesis import given, strategies as st
from domain.exceptions import ValidationError

@given(st.text(min_size=0, max_size=10))
def test_signal_id_validator_never_crashes(random_id):
    """Validator не падает с непредвиденным исключением на любом вводе"""
    from domain.validator import validate_signal_id
    try:
        validate_signal_id(random_id)
    except ValidationError:
        pass  # ожидаемо
    except Exception as e:
        raise AssertionError(f"Unexpected exception for id={random_id!r}: {e}")
```

---

## §25. Contract Tests — version compatibility

**ARR:** «Schema validation есть, version compat нет»

```python
# tests/test_contracts.py — добавить после реализации Schema v2

def test_signal_v1_readable_by_v2_parser():
    """
    Сигнал в формате v1 (с полем links) должен читаться v2 парсером
    через get("new_field") or get("old_field") паттерн.
    Тест фиксирует backward compatibility при смене версии схемы.
    """
    # Реализовать при переходе Signal Schema → v2
    pass
```

---

# Полная матрица покрытия ARR

| ARR пункт | Закрыт | Где |
|-----------|--------|-----|
| Bounded Contexts | ✅ | ARCH_GAP_SPEC v2.0 G3 |
| Deployment Architecture | ✅ | DEPLOYMENT.md |
| Security Architecture | ✅ | SECURITY.md |
| Disaster Recovery | ✅ | DISASTER_RECOVERY.md |
| Environment Strategy | ✅ | DEPLOYMENT.md |
| Observability / Monitoring | ⚪ P4 | §23 — после Backend |
| Race condition JSON | ✅ | file_lock.py |
| Error handling philosophy | 🟠 P1 | §1 этой спеки |
| Запрещённые переходы State Machine | 🟠 P2 | §7 этой спеки |
| Domain Events | ✅ | domain/events.py |
| Value Objects vs Entities | ✅ | ARCH_GAP_SPEC v2.0 G4 |
| Lifecycle Hooks | ✅ | ARCH_GAP_SPEC v2.0 G5 |
| Cross-aggregate consistency | ⚪ P4 | требует Backend |
| Orphan detection | ✅ | ARCH_GAP_SPEC v2.0 G6 |
| Backup strategy | ✅ | DISASTER_RECOVERY.md |
| Recovery procedure | ✅ | DISASTER_RECOVERY.md |
| Validation на уровне чтения | 🔴 P1 | §3 этой спеки |
| Date timezone | ✅ | config/settings.py |
| Encoding policy | ✅ | config/settings.py |
| semantic_inverse_score | ✅ | IMPLEMENTATION_TRACKER B2 |
| history_query.py | 🟠 P2 | §8 этой спеки |
| Error propagation | 🟠 P2 | §9 этой спеки |
| Logging strategy | 🔴 P1 | §2 этой спеки |
| Dependency injection онтологии | 🔴 P1 | §4 этой спеки |
| Component initialization порядок | 🔴 P1 | §4 этой спеки |
| Graceful shutdown при записи | 🔴 P1 | §5 этой спеки |
| hash() детерминизм | ✅ | IMPLEMENTATION_TRACKER B1 |
| MAX_POSSIBLE_SCORE | ✅ | config/settings.py |
| Duplicate signal handling | 🔴 P1 | §6 этой спеки |
| Explanation quality rationale | 🟡 P3 | §19 этой спеки |
| Uncertainty handling | 🟡 P3 | §18 этой спеки |
| Acceptance Tests | ⚪ P4 | после MVP |
| Narrative Quality Tests | ⚪ P4 | после MVP |
| Chaos Tests | ⚪ P4 | после MVP |
| Test environment isolation | 🟡 P3 | §21 этой спеки |
| Authentication | ✅ | SECURITY.md |
| Authorization | ✅ | SECURITY.md |
| XSS input sanitization | ✅ | SECURITY.md |
| Secrets management | ✅ | SECURITY.md |
| Dependency vulnerability scanning | ✅ | SECURITY.md |
| Runbook | ✅ | DEPLOYMENT.md |
| Glossary | ✅ | GLOSSARY.md |
| Onboarding guide | ⚪ P4 | после MVP |
| Performance baselines | 🟡 P3 | §20 этой спеки |
| Graceful degradation | 🟡 P3 | §22 этой спеки |
| synthesis_cache vs store два источника | 🟠 P2 | §17 этой спеки |
| State Machine Quality Report и History | 🟠 P2 | §7 этой спеки |
| migrate_relationships.py | 🟠 P2 | §10 этой спеки |
| Backward compatibility механизм | 🟠 P2 | §14 этой спеки |
| Data retention для synthesis_store | 🟠 P2 | §11 этой спеки |
| Null handling спецификация | 🟠 P2 | §12 этой спеки |
| Quality Report алгоритм | 🟠 P2 | §13 этой спеки |
| Idempotency всех компонентов | 🟠 P2 | §15 этой спеки |
| Noise filtering дубликаты | 🟠 P2 | §16 этой спеки |
| Structural change detection vs контракт | 🟠 P2 | §17 этой спеки |
| Property Tests (Hypothesis) | ⚪ P4 | §24 этой спеки |
| Contract Tests version compat | ⚪ P4 | §25 этой спеки |
| API Contracts (auth, rate limit) | ⚪ P4 | требует Backend |

**Итого: 31 закрыто ранее + 25 в этой спеке = 56 из 64 пунктов ARR**  
**Остаток 8 пунктов — ⚪ P4, требуют Backend или реальных пользователей**

---

# Порядок реализации

| День | Задачи | Пункты |
|------|--------|--------|
| **День 1** | §1 exceptions.py + error philosophy, §2 logger.py | P1: §1, §2 |
| **День 2** | §3 corrupted file, §4 init order + DI, §5 graceful shutdown, §6 duplicate policy | P1: §3–§6 |
| **День 3** | §7 state machines, §8 history_query.py, §9 error propagation | P2: §7–§9 |
| **День 4** | §10 migrate_relationships, §11 retention, §12 null handling, §13 quality_report | P2: §10–§13 |
| **День 5** | §14 backward compat, §15 idempotency, §16 noise filter, §17 structural change | P2: §14–§17 |
| **День 6** | §18 uncertainty, §19 explanation quality, §20 performance baselines | P3: §18–§20 |
| **День 7** | §21 test isolation (conftest.py), §22 degradation matrix, тесты | P3: §21–§22 |

**Итого: 7 дней → повторный ARR → ожидаемый статус READY**

---

# Definition of Done

- [ ] `domain/exceptions.py` создан, все компоненты используют иерархию
- [ ] `infrastructure/logger.py` создан, все скрипты логируют через него
- [ ] `domain/state_machine.py` создан, `transition()` проверяет допустимость
- [ ] `scripts/history_query.py` создан, `--tension-history` работает
- [ ] `scripts/migrate_relationships.py` создан, dry-run проходит без ошибок
- [ ] `scripts/quality_report.py` создан, выводит health score
- [ ] `tests/conftest.py` создан, `isolated_environment` fixture применяется автоматически
- [ ] `python -m pytest tests/ -v` — все тесты зелёные
- [ ] `python scripts/validate_relationships.py` — exit 0
- [ ] `python scripts/health_check.py` — overall: ok

---

*ARCH_GAP_SPEC v3.0 · 2026-06-28*  
*Покрывает 56 из 64 пунктов ARR. Остаток 8 — P4, требуют Backend.*
