# scripts/

CLI-инструменты для аналитика и для CI. Каждый скрипт — точка входа, вызываемая напрямую
(`python3 scripts/имя.py [аргументы]`), которая использует `domain/` и `infrastructure/`
для самой логики.

См. naming conventions и порядок импортов в [`docs/CODING_STANDARDS.md`](../docs/CODING_STANDARDS.md).

## Файлы

| Файл | Назначение |
|------|-----------|
| `add_signal.py` | Добавление нового сигнала: валидация → state machine → запись с блокировкой → событие |
| `synthesizer.py` | Детерминированный синтезатор нарративов (12-шаговый алгоритм, `PYTHONHASHSEED=0` обязателен) |
| `approve_synthesis.py` | Утверждение синтеза аналитиком: review tension → rationale → `generated → approved` |
| `contradiction_detector.py` | Предлагает кандидатов на `links.contradicts` по семантическому анализу `macro_implication` |
| `quality_report.py` | Health Score базы сигналов: покрытие полей, свежесть, качество tension, связность |
| `rebuild_synthesis.py` | Пересчёт синтезов при major-изменении алгоритма, diff перед `--apply` |
| `history_query.py` | Запросы к `synthesis_store`: история кластера, tension-history, список кластеров |
| `validate_integrity.py` | Проверка целостности `signals.json`, `ENTITIES.json`, `synthesis_cache.json`, checksums |
| `validate_relationships.py` | Проверка `relationships.json`: orphan-связи, дубликаты, contradiction-циклы |
| `migrate_relationships.py` | Разовая миграция `links.*` из `signals.json` в `data/relationships.json` |
| `cleanup_synthesis_store.py` | Очистка `synthesis_store/` по retention policy (`SYNTHESIS_RETENTION`), dry-run по умолчанию, `--apply` для реального удаления (M1 ARR v3) |

## Что добавлять сюда

Новый CLI-инструмент для аналитика или для CI-пайплайна: принимает аргументы командной
строки, использует `domain/` для бизнес-правил и `infrastructure/` для I/O, печатает
результат в stdout/stderr.

## Что НЕ добавлять сюда

- Бизнес-правила и инварианты → `domain/`
- Низкоуровневый I/O (file locking, логирование) → `infrastructure/`
- Скрипт без чёткого CLI-интерфейса, который по сути библиотека → соответствующий слой

## Правило именования нового файла

`scripts/{глагол}_{объект}.py`, например `scripts/export_signals.py`. Имя должно отражать
действие, которое выполняет скрипт при запуске — не существительное-описание модуля.

Каждый скрипт начинается с docstring с путём, одной строкой назначения и примером запуска
(см. формат в [`docs/CODING_STANDARDS.md`](../docs/CODING_STANDARDS.md)).
