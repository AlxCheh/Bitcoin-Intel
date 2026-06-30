# Coding Standards — Bitcoin Intel

> Обязателен к соблюдению для всех PR. Часть Condition 2 из [`IRR_REPORT.md`](../archive/IRR_REPORT.md) (закрыто, см. архив).

---

## Python style

- **PEP 8** как база, форматирование — **Black** (`line-length = 100`).
- Перед коммитом: `black .` и `flake8 .` должны проходить без ошибок.
- Конфигурация инструментов — единая, в [`pyproject.toml`](../pyproject.toml).

## Naming conventions

| Сущность | Конвенция | Пример |
|----------|-----------|--------|
| Файлы и модули | `snake_case.py` | `contradiction_detector.py` |
| Классы | `PascalCase` | `BitcoinIntelError`, `RelationshipStore` |
| Функции и переменные | `snake_case` | `validate_signal()`, `signal_id` |
| Константы | `UPPER_CASE` | `MAX_POSSIBLE_SCORE`, `LEGACY_LINKS_ENABLED` |
| Тестовые файлы | `test_{component}_{scenario}.py` | `test_synthesizer_tension_formula.py` |

## Docstring формат

Google style. Каждый модуль начинается с docstring с путём и одной строкой назначения,
функции с нетривиальной логикой — с описанием параметров и возвращаемого значения:

```python
"""
scripts/add_signal.py
Bitcoin Intel — добавление нового сигнала в базу.

Делает четыре вещи атомарно:
  1. Валидирует объект сигнала (через исключения)
  2. Проверяет State Machine (draft → active)
  3. Добавляет в signals.json (с блокировкой)
  4. Испускает SignalAdded событие + lifecycle hook
"""
```

## Импорты

Порядок: **stdlib → domain → infrastructure → scripts**. Без циклических импортов между слоями.

```python
import json
import os

from domain.exceptions import ValidationError
from domain.state_machine import transition
from infrastructure.file_lock import atomic_write
from infrastructure.logger import get_logger
```

`scripts/` может импортировать из `domain/`, `infrastructure/`, `config/`.
`domain/` и `infrastructure/` **не должны** импортировать из `scripts/`.

## Обработка ошибок

Все кастомные исключения наследуются от `BitcoinIntelError` (`domain/exceptions.py`).
Это позволяет ловить любую системную ошибку через `except BitcoinIntelError`.

Принцип проекта — **FAIL LOUD**: запрещённый переход состояния или невалидные данные
должны кидать исключение, а не молча деградировать.

```python
from domain.exceptions import ForbiddenStateTransitionError

if not is_valid_transition(current, target):
    raise ForbiddenStateTransitionError(f"{current} → {target} запрещён")
```

## Куда добавлять новые компоненты

| Тип кода | Директория | README с правилами |
|----------|-----------|---------------------|
| Доменная логика (события, исключения, валидация, state machine) | `domain/` | [`domain/README.md`](../domain/README.md) |
| Инфраструктурный код (logging, file locking, хранилища) | `infrastructure/` | [`infrastructure/README.md`](../infrastructure/README.md) |
| CLI-инструменты аналитика | `scripts/` | [`scripts/README.md`](../scripts/README.md) |
| Настройки и константы | `config/settings.py` | — |
| Тесты | `tests/unit/` или `tests/integration/` | — |

## Детерминизм

Синтезатор и связанные с ним компоненты должны быть **детерминированными**:
`PYTHONHASHSEED=0` обязателен при запуске `scripts/synthesizer.py` и тестов, которые его вызывают.
Не использовать `hash()` для выбора между вариантами без фиксированного seed — это нарушение
архитектурного контракта (см. историю Blocker IRB-B1 в [`ARR_STATUS_REPORT.md`](../archive/ARR_STATUS_REPORT.md)).

## Логирование

Через `infrastructure/logger.py`, не через `print()`. Уровни:

- `DEBUG` — детали алгоритма (score per signal, bridge selection)
- `INFO` — значимые действия (signal added, synthesis created)
- `WARNING` — деградация без падения (corrupt signal skipped, cache stale)
- `ERROR` — операция не выполнена

## Линтер в CI

`flake8` запускается в `validate` job (`.github/workflows/deploy.yml`) и проверяет только
критические ошибки (`E9`, `F63`, `F7`, `F82`) — синтаксис, неопределённые имена, опасные
сравнения. Стилевые предупреждения не блокируют CI, но обязательны к исправлению локально
перед PR.

## Чтение fixture-файлов в тестах

`tests/conftest.py` содержит `autouse`-фикстуру `isolated_environment`, которая на каждом
тесте переключает рабочую директорию во временную песочницу (`monkeypatch.chdir`). Это
значит, что путь к файлу, который тест должен **прочитать** из репозитория (golden dataset,
fixture с эталонными данными), нельзя резолвить от текущей директории — он всегда будет
указывать в пустую песочницу.

```python
# НЕПРАВИЛЬНО — в песочнице файла нет, тест либо упадёт, либо тихо skip()
pairs_file = Path("tests/golden/fixtures/contradiction_pairs.json")

# ПРАВИЛЬНО — резолвится от расположения тестового файла, не зависит от cwd
pairs_file = Path(__file__).parent.parent / "golden" / "fixtures" / "contradiction_pairs.json"
```

Если fixture обязателен для смысла теста — отсутствие файла должно быть `assert` (hard
failure), а не `pytest.skip()`. `pytest.skip()` допустим только для по-настоящему
опциональных артефактов, которые ещё не были созданы на момент написания теста (например,
`golden_synthesis.json` до выполнения шага G2 — см. `tests/golden/test_golden.py`), и не
должен использоваться, чтобы скрыть бажный путь к файлу.
