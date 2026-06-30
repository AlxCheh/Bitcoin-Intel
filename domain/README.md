# domain/

Доменная логика Bitcoin Intel: бизнес-правила, не зависящие от способа хранения данных
или интерфейса. Чистый Python, минимум внешних зависимостей.

См. naming conventions и порядок импортов в [`docs/CODING_STANDARDS.md`](../docs/CODING_STANDARDS.md).

## Файлы

| Файл | Назначение |
|------|-----------|
| `exceptions.py` | Единая иерархия исключений. Все кастомные ошибки наследуются от `BitcoinIntelError` |
| `events.py` | Domain Events — audit trail. Каждое значимое действие пишется в `data/events.jsonl` (append-only) |
| `lifecycle.py` | Lifecycle hooks — реакции на события (инвалидация cache, пересчёт), вызываются после записи события |
| `state_machine.py` | Явные переходы состояний для Signal / Synthesis / Cluster / Relationship. Запрещённый переход → `ForbiddenStateTransitionError` |
| `validator.py` | Валидация сигналов и синтезов: `validate_signal()`, `check_possible_duplicate()`, `validate_rationale_quality()` |

## Что добавлять сюда

Логику, которая отвечает на вопрос «что разрешено системе» независимо от того, откуда
пришли данные и куда они пойдут: правила переходов состояний, инварианты данных, бизнес-исключения,
доменные события.

## Что НЕ добавлять сюда

- Работу с файловой системой напрямую (блокировки, чтение/запись) → `infrastructure/`
- CLI-обвязку, argparse, точки входа для аналитика → `scripts/`
- Константы и пороги конфигурации → `config/settings.py`

## Правило именования нового файла

`domain/{концепция}.py`, например `domain/scoring.py` для правил подсчёта score.
Не создавать файл с именем существующего класса — один файл может содержать несколько
связанных по смыслу сущностей (как `exceptions.py` содержит всю иерархию).

## Куда добавить новый exception

Открыть `domain/exceptions.py`, найти подходящую категорию (`ValidationError`,
`SynthesizerError`, `DataIntegrityError`, `ArchitecturalViolation`) и унаследовать новое
исключение от неё. Если ни одна категория не подходит — обсудить с командой создание новой
категории, а не добавлять прямого потомка `BitcoinIntelError` в обход категорий.
