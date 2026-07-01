# Implementation Remediation Program — IRP v1.0
## Bitcoin Intel Narrative Intelligence Platform
## 2026-07-01 · WORKING DOCUMENT

> **Основание:** IRR v1.0 (docs/IRR_REPORT_v1.md · 2026-07-01)
> **Вердикт IRR:** NOT READY
> **Цель IRP:** преобразовать 31 FAIL-критерий и 6 Blockers/Criticals в устранённые, верифицированные, закрытые замечания до открытия Sprint 0
> **Метод:** минимально достаточные изменения — не архитектурный рефакторинг, а устранение конкретных пробелов
> **Горизонт:** 2 недели (10 рабочих дней) до Sprint 0 Gate

---

## 1. Executive Summary

IRR v1.0 зафиксировал 31 FAIL-критерий. Ни один из них не вызван фундаментальным изъяном архитектуры — все они являются **пробелами между задокументированным намерением и текущим артефактом**. Blueprint и ADDENDUM технически верны и полны. Проблема не в том, что было спроектировано, а в том, что часть спроектированного не была реализована или зафиксирована.

Три Root Cause охватывают 80% замечаний:

1. **Фаза 0 не завершена** — `relationships.json` не создан, миграция `links.*` не выполнена, `LEGACY_LINKS_ENABLED = True` остаётся переходным флагом которого переход так и не произошёл.
2. **«Документ как артефакт» vs «Документ как инструкция»** — JSON Schema описаны в ADDENDUM §17 как implementation-ready спецификация, но физические файлы не созданы. Разработчик видит схему, но не может запустить валидацию.
3. **«Один человек = вся команда»** — среда, процессы и CI были достаточны для одного аналитика. Для команды из 10 они недостаточны: нет Staging, нет Branch Protection, нет Staging-деплоя.

IRP организован в 5 волн (14 рабочих дней). После Wave 5 проект получает статус **READY WITH CONDITIONS**, а затем — **READY TO IMPLEMENT** после Sprint 0 Gate.

**Общая трудоёмкость IRP: ~42 часа** (из них ~8 часов — Wave 1, которая устраняет все Blockers).

---

## 2. Общая оценка результатов IRR

| Категория | Кол-во | Sprint 0 блокируют? | В IRP |
|-----------|--------|---------------------|-------|
| Blockers (B) | 3 | ✅ ДА | Wave 1–2 |
| Critical (C) | 3 | ✅ ДА | Wave 1–2 |
| Major (M) | 9 | Частично | Wave 2–3 |
| Documentation FAIL | 8 | Нет | Wave 3–4 |
| Testing FAIL | 6 | Нет | Wave 3–4 |
| DevOps/Ops FAIL | 7 | Нет | Wave 2–3 |
| Scalability FAIL | 3 | Нет | Wave 4 |
| AI/Causal FAIL | 1 | Нет | Tech Debt |
| **ИТОГО FAIL** | **31** | | **Wave 1–4** |

Замечания, которые IRR отметил как «Technical Debt After MVP» и явно принятые как «out of scope» (MON06 Distributed tracing, TST13 Mutation Tests, TST14 Load Tests, TST15 Acceptance Tests, AI08 Causal Reasoning) — **в IRP не включены как обязательные**. Они попадают в раздел 12 (Residual Risks) с явным обоснованием допустимости.

---

## 3. Реестр замечаний

### 3.1 Blockers

| ID | Замечание IRR | Первопричина | Волна |
|----|---------------|-------------|-------|
| B1 | §23 ADDENDUM описывает целевую структуру `src/domain/`, не текущую `domain/` | Документ не был обновлён при отклонении от целевой структуры | Wave 1 |
| B2 | `data/relationships.json` не создан; Фаза 0 не завершена; `LEGACY_LINKS_ENABLED=True` | Миграция откладывалась по соображениям safe rollout, но флаг перевода так и не был выставлен | Wave 1 |
| B3 | JSON Schema файлы (`schemas/*.json`) не созданы; Contract Tests отсутствуют | Schema была написана как часть спецификации, но не как артефакт — нет шага «create the file» в DoD | Wave 2 |

### 3.2 Critical

| ID | Замечание IRR | Первопричина | Волна |
|----|---------------|-------------|-------|
| C1 | `golden_synthesis.json` отсутствует; `test_golden.py` делает `pytest.skip()` | DoD §28.6 содержит чеклист, но нет конкретной команды для генерации файла | Wave 2 |
| C2 | Precision gap: BLUEPRINT требует >85%, тесты проверяют ≥60%; нет ADR | Целевой порог был в Blueprint на этапе проектирования; при реализации его снизили без документации решения | Wave 1 |
| C3 | S2 скрипт DISASTER_RECOVERY читает `signals.json` как плоский список, а не `{meta, signals}` | Скрипт написан до добавления `{meta, signals}` обёртки и не был обновлён | Wave 1 |

### 3.3 Major

| ID | Замечание IRR | Волна |
|----|---------------|-------|
| M01 | `synthesis_cache_builder.py` задокументирован §18.4 как отдельный файл, функция — в `rebuild_synthesis.py` | Wave 3 |
| M02 | `rebuild_cache.py` упомянут в DEPLOYMENT.md, не существует | Wave 1 |
| M03 | deploy-job стабильно красный (alarm fatigue) | Wave 2 |
| M04 | Нет Staging/Preview environment для команды | Wave 2 |
| M05 | Branch Protection на `main` не настроен | Wave 1 |
| M06 | Веса scoring в settings.py AND в ontology.json — два источника истины | Wave 3 |
| M07 | `ALGORITHM_VERSION` не реализован как semver-константа в `synthesizer.py` | Wave 3 |
| M08 | add_signal.py не имеет DoD | Wave 3 |
| M09 | Performance Tests отсутствуют; критерий `synthesize(42 signals) < 100ms` не автоматизирован | Wave 4 |

### 3.4 Documentation FAIL

| ID | Критерий IRR | Документ | Волна |
|----|--------------|----------|-------|
| D01 | API08: Пагинация для GET не описана | docs/API.md | Wave 3 |
| D02 | DOM08: Anti-Corruption Layers не описаны | docs/BLUEPRINT_ADDENDUM.md | Wave 3 (реестр ошибочно указывал Wave 4 — таблица задач Wave 3 включает D02 с самого начала, см. §6.1 план документации) |
| D03 | DOC02: BLUEPRINT_ADDENDUM.md §23 описывает целевую структуру | docs/BLUEPRINT_ADDENDUM.md | Wave 1 |
| D04 | DOC11: DISASTER_RECOVERY S2 сломан | DISASTER_RECOVERY.md | Wave 1 |
| D05 | DOC12: rebuild_cache.py упомянут в DEPLOYMENT.md | DEPLOYMENT.md | Wave 1 |
| D06 | COM05: add_signal.py не имеет DoD | docs/BLUEPRINT_ADDENDUM.md §28 | Wave 3 |
| D07 | COM09: rebuild_cache.py упомянут, не существует | scripts/README.md | Wave 1 |
| D08 | REL: Release Strategy не описана | docs/DEPLOYMENT.md | Wave 4 |

### 3.5 Missing Contracts

| ID | Критерий IRR | Волна |
|----|--------------|-------|
| MC01 | CON01: schemas/signal/v1.json не создан | Wave 2 |
| MC02 | CON02: schemas/relationship/v1.json не создан | Wave 2 |
| MC03 | CON03: schemas/synthesis/v1.json не создан | Wave 2 |
| MC04 | CON05: Contract Validation шаг в CI отсутствует | Wave 2 |
| MC05 | CON06: migration/v1_to_v2.py не создан | Wave 4 |
| MC06 | SCL04: Performance baseline не измерен | Wave 4 |
| MC07 | SCL06: Paging strategy для UI не описана | Wave 4 |

### 3.6 Missing Tests

| ID | Критерий IRR | Статус | Волна |
|----|--------------|--------|-------|
| MT01 | TST03: Contract Tests | FAIL | Wave 2 |
| MT02 | TST04: golden_synthesis.json для Golden Tests | PARTIAL/skip | Wave 2 |
| MT03 | TST07: Performance Tests | FAIL | Wave 4 |

### 3.7 Missing Operational Procedures

| ID | Критерий IRR | Волна |
|----|--------------|-------|
| OP01 | DEV07: Staging/Preview environment | Wave 2 |
| OP02 | DEV08: Branch Protection (описан, не настроен) | Wave 1 |
| OP03 | DEV09: Secrets rotation policy | Wave 3 |
| OP04 | DEV10: Dependency update policy / Dependabot | Wave 3 |
| OP05 | MON03: Alerting при деградации synthesis | Wave 4 |
| OP06 | SCL05: signals.json size monitoring | Wave 4 |

---

## 4. Root Cause Analysis

### RCA-1: «Фаза 0 объявлена, но не завершена»

**Проблемы:** B2, MC01–MC03, CON07, LEGACY_LINKS_ENABLED.

**Five Whys:**
1. *Почему `relationships.json` не существует?* → Миграция требовала ручного запуска скрипта + проверки + смены флага — многошаговая операция.
2. *Почему многошаговая операция не была выполнена?* → Не было явного Transition Checklist с ответственным и дедлайном.
3. *Почему не было Transition Checklist?* → DoD §28.4 содержит чеклист артефакта, но не чеклист завершения перехода (смена флага, удаление legacy-кода).
4. *Почему DoD не включает завершение перехода?* → DoD написан с фокусом на «создать файл», не на «завершить миграцию».
5. *Почему фокус на «создать», а не «завершить»?* → Переходный период (`LEGACY_LINKS_ENABLED`) был спроектирован как safety net, который предполагался временным — но без явной даты/условия отключения он стал постоянным.

**Вывод:** Каждый transition-флаг должен иметь явный Completion Trigger: условие + команда + ответственный. `LEGACY_LINKS_ENABLED` его не имел.

**Исправление:** Добавить в settings.py комментарий с Completion Trigger + создать `data/relationships.json` + выставить флаг `False`.

---

### RCA-2: «Спецификация написана, артефакт не создан»

**Проблемы:** B3, MC01–MC03, C1, COM04, COM09.

**Five Whys:**
1. *Почему JSON Schema файлы не созданы?* → ADDENDUM §17 содержит JSON Schema как inline-документацию, не как инструкцию «создать файл по этому пути».
2. *Почему DoD не требует создания файла?* → DoD §28 описывает компоненты Python, но не данные/схемы как самостоятельные артефакты.
3. *Почему схемы воспринимались как документация, а не артефакты?* → Нет чёткого разграничения между «описать схему» и «создать schema file».
4. *Почему нет такого разграничения?* → ADDENDUM писался одновременно со спецификацией; создание файлов воспринималось как «само собой разумеется».
5. *Почему «само собой разумеется» стало источником пробела?* → Отсутствие Definition of Done для каждого Artifact, не только для каждого Component.

**Вывод:** DoD должен существовать для каждого физического артефакта (файла), а не только для каждого программного компонента.

**Исправление:** Создать физические файлы `schemas/*.json`. Дополнить DoD §28 разделом «Артефакты». Добавить Contract Validation в CI.

---

### RCA-3: «Среда одного аналитика масштабируется для команды»

**Проблемы:** M04, M05, OP01–OP04, M03.

**Five Whys:**
1. *Почему нет Staging?* → Один человек в main — Staging без смысла.
2. *Почему Branch Protection не настроен?* → Один человек не имеет «своего» PR чтобы его блокировать.
3. *Почему процессы не масштабировались при переходе к команде?* → Документация описывает «что должно быть» (DEPLOYMENT.md), но не была синхронизирована с «что настроено сейчас».
4. *Почему нет синхронизации?* → Нет Infrastructure as Code для GitHub-настроек (Branch Protection, Environments) — они ручные.
5. *Почему ручные настройки не задокументированы как «настроить перед онбордингом»?* → Они воспринимались как «настроим когда понадобится» — а понадобились они только при появлении команды.

**Вывод:** Организационная инфраструктура (Branch Protection, Staging, Secrets) должна быть зафиксирована как Prerequisite для Sprint 0, а не как «настроим потом».

**Исправление:** Настроить Branch Protection, создать `develop` ветку как Staging, задокументировать в DEPLOYMENT.md с конкретными шагами настройки GitHub.

---

### RCA-4: «Целевая архитектура документа vs текущая реализация»

**Проблемы:** B1, M01, M07, M06.

**Cause–Effect:**
- BLUEPRINT_ADDENDUM §23 написан как «целевая архитектура» (куда придём)
- Текущая реализация (`domain/`, `scripts/`, `infrastructure/`) — промежуточная, рабочая, технически корректная
- Документ не разграничивает «сейчас» и «целевое» — читатель не знает, что игнорировать
- Результат: независимый разработчик получает ложные ориентиры

**Исправление:** Добавить в §23 ADDENDUM явный раздел «Текущая vs Целевая структура» с датой перехода.

---

### RCA-5: «Решения принимались без ADR»

**Проблемы:** C2 (Precision gap без ADR), M06 (два источника весов без ADR).

**Dependency Analysis:** ADR-008, ADR-009, ADR-010, ADR-011 описывают последние решения. Более ранние решения (снижение Precision target, splitting scoring weights) приняты без фиксации.

**Исправление:** ADR-012 (Precision target), обновление ontology.json или settings.py для единого источника весов.

---

## 5. План исправлений (Remediation Cards)

### REM-B1 | §23 ADDENDUM: Current vs Target Structure

| Атрибут | Значение |
|---------|---------|
| **ID** | REM-B1 |
| **Категория** | Blocker / Documentation |
| **Описание** | ADDENDUM §23 описывает `src/domain/`, `src/application/`, `src/infrastructure/` — структуру которой нет |
| **Первопричина** | RCA-4 |
| **Влияние** | 10+ разработчиков создадут код в разных местах; конфликт через 3 месяца |
| **Риск** | CRITICAL — немедленно при онбординге |
| **Компоненты** | docs/BLUEPRINT_ADDENDUM.md §23 |
| **Связанные документы** | BLUEPRINT.md §6 (Roadmap) |
| **Приоритет** | P0 |
| **Сложность** | LOW — только документация |
| **Трудоёмкость** | 1 час |
| **Владелец** | Principal Architect |
| **Зависимости** | Нет |
| **Стратегия** | Добавить в §23 два подраздела: «Текущая структура (2026-07-01)» и «Целевая структура (Фаза 4, ~2028)». Сделать разграничение визуально очевидным — emoji-маркер, цвет, заголовок |
| **Ожидаемый результат** | Разработчик видит реальную директорию, понимает куда добавлять код |

---

### REM-B2 | Завершение Фазы 0: relationships.json

| Атрибут | Значение |
|---------|---------|
| **ID** | REM-B2 |
| **Категория** | Blocker / Phase 0 Completion |
| **Описание** | `data/relationships.json` не существует; `LEGACY_LINKS_ENABLED = True`; новые связи пишутся в `links.*` |
| **Первопричина** | RCA-1 |
| **Влияние** | Нарушение immutability сигналов; невозможность построить Relationship Graph для Backend |
| **Риск** | CRITICAL |
| **Компоненты** | `scripts/migrate_relationships.py`, `infrastructure/relationship_store.py`, `config/settings.py`, `data/` |
| **Связанные документы** | ADR-002, BLUEPRINT §7 (Migration Plan), ADDENDUM §28.4 |
| **Приоритет** | P0 |
| **Сложность** | LOW — скрипт уже написан |
| **Трудоёмкость** | 2 часа (запуск + верификация + коммит) |
| **Владелец** | Staff Backend Engineer |
| **Зависимости** | Нет предшественников |
| **Стратегия** | 1. `PYTHONHASHSEED=0 python3 scripts/migrate_relationships.py` 2. Верифицировать: все `from_id`/`to_id` существуют в `signals.json` 3. `LEGACY_LINKS_ENABLED = False` в settings.py 4. Добавить Completion Trigger комментарий в settings.py: «Флаг выставлен в False 2026-07-NN при завершении Фазы 0» |
| **Ожидаемый результат** | `data/relationships.json` существует, `validate_relationships.py` проходит, `LEGACY_LINKS_ENABLED = False` |

---

### REM-B3 | JSON Schema файлы + Contract Tests в CI

| Атрибут | Значение |
|---------|---------|
| **ID** | REM-B3 |
| **Категория** | Blocker / Missing Contracts |
| **Описание** | Три JSON Schema (`schemas/signal/v1.json`, `schemas/relationship/v1.json`, `schemas/synthesis/v1.json`) описаны в ADDENDUM §17, физически не существуют |
| **Первопричина** | RCA-2 |
| **Влияние** | Невалидные поля добавляются без обнаружения; schema деградирует |
| **Риск** | CRITICAL для многолетней разработки |
| **Компоненты** | `schemas/` (новая директория), `.github/workflows/deploy.yml` |
| **Связанные документы** | ADDENDUM §17.1–17.3, §28 DoD |
| **Приоритет** | P0 |
| **Сложность** | MEDIUM — нужен jsonschema шаг в CI |
| **Трудоёмкость** | 4 часа |
| **Владелец** | Staff Backend Engineer |
| **Зависимости** | REM-B2 (relationship schema нужен `relationships.json` существующим) |
| **Стратегия** | 1. Создать `schemas/signal/v1.json` — копия из §17.1. 2. Создать `schemas/relationship/v1.json` из §17.2. 3. Создать `schemas/synthesis/v1.json` из §17.3. 4. Добавить `jsonschema>=4.0.0` в requirements.txt (dev). 5. Добавить шаг `Contract Tests` в `.github/workflows/deploy.yml`: `python3 -m jsonschema --instance signals.json schemas/signal/v1.json` для каждого сигнала. 6. Обновить DoD §28 |
| **Ожидаемый результат** | CI green на Contract Tests; новое невалидное поле блокирует CI |

---

### REM-C1 | golden_synthesis.json: создать и убрать skip

| Атрибут | Значение |
|---------|---------|
| **ID** | REM-C1 |
| **Категория** | Critical / Missing Tests |
| **Описание** | `tests/golden/expected/golden_synthesis.json` не создан; `test_golden.py` делает `pytest.skip()` |
| **Первопричина** | RCA-2 |
| **Влияние** | Изменения synthesizer.py не защищены Golden Test |
| **Риск** | MAJOR — тихий провал без уведомления |
| **Компоненты** | `tests/golden/expected/`, `tests/golden/test_golden.py` |
| **Связанные документы** | ADDENDUM §26, §28.6 DoD |
| **Приоритет** | P1 |
| **Сложность** | LOW — генерация текущего вывода |
| **Трудоёмкость** | 2 часа |
| **Владелец** | Principal QA Architect |
| **Зависимости** | REM-B2 (synthesizer читает relationships) |
| **Стратегия** | 1. `PYTHONHASHSEED=0 python3 scripts/synthesizer.py` → получить текущий `data/synthesis_cache.json`. 2. Запустить synthesizer на golden fixture: `python3 tests/golden/generate_golden_synthesis.py`. 3. Аналитик проверяет tension и narrative для каждого кластера. 4. Утверждённый вывод сохранить в `tests/golden/expected/golden_synthesis.json`. 5. Убрать `pytest.skip()` в `test_golden.py`, заменить на `assert` |
| **Ожидаемый результат** | `test_golden.py` — PASS; изменение synthesizer.py немедленно ломает Golden Test |

---

### REM-C2 | ADR-012: Precision Target 85% → 60%

| Атрибут | Значение |
|---------|---------|
| **ID** | REM-C2 |
| **Категория** | Critical / Missing Decision Record |
| **Описание** | BLUEPRINT §10 требует Contradiction Precision >85%; тесты проверяют ≥60%; разрыв не задокументирован |
| **Первопричина** | RCA-5 |
| **Влияние** | Команда будет оптимизировать разные цели |
| **Риск** | MAJOR — архитектурный дрейф без единого ориентира |
| **Компоненты** | `docs/ADR-012-contradiction-precision-target.md` (новый) |
| **Связанные документы** | BLUEPRINT §10, config/settings.py, tests/unit/test_contradiction.py |
| **Приоритет** | P0 |
| **Сложность** | LOW — документация |
| **Трудоёмкость** | 1 час |
| **Владелец** | Lead AI Engineer |
| **Зависимости** | Нет |
| **Стратегия** | Создать ADR-012 со структурой: Контекст (BLUEPRINT §10 задавал 85% как aspirational target при N=0 реальных парах), Решение (снизить до 60% как реалистичный порог при текущей выборке из 20 тестовых пар), Обоснование (ADR-011 паттерн: статистическая калибровка требует holdout-датасета), Дальнейшая работа (gate 30 пар → пересмотреть 85% по реальной precision). Обновить комментарий `CONTRADICTION_PROPOSAL_THRESHOLD` в settings.py |
| **Ожидаемый результат** | Все члены команды понимают почему 60%, а не 85%; чёткий gate для пересмотра |

---

### REM-C3 | DISASTER_RECOVERY S2: исправить flat-list чтение

| Атрибут | Значение |
|---------|---------|
| **ID** | REM-C3 |
| **Категория** | Critical / Broken Operational Procedure |
| **Описание** | Скрипт S2 в DISASTER_RECOVERY.md читает `signals.json` как плоский список; реальная структура `{meta, signals: [...]}` |
| **Первопричина** | Скрипт написан до добавления `{meta, signals}` обёртки |
| **Влияние** | `AttributeError` при production-инциденте, именно когда нужна скорость |
| **Риск** | HIGH |
| **Компоненты** | `DISASTER_RECOVERY.md` |
| **Связанные документы** | signals.json schema |
| **Приоритет** | P0 |
| **Сложность** | LOW — однострочное исправление |
| **Трудоёмкость** | 30 минут |
| **Владелец** | DevOps Architect |
| **Зависимости** | Нет |
| **Стратегия** | Изменить в S2: `signals = json.load(f)` → `raw = json.load(f); signals = raw.get('signals', raw) if isinstance(raw, dict) else raw`. Добавить рядом тест-однострочник для проверки: `python3 -c "import json; d=json.load(open('signals.json')); s=d.get('signals',d); print(len(s))"` |
| **Ожидаемый результат** | Скрипт S2 выполняется без ошибки на текущем `signals.json` |

---

### REM-M01 | synthesis_cache_builder: разрешить неоднозначность

| Атрибут | Значение |
|---------|---------|
| **ID** | REM-M01 |
| **Категория** | Major / Documentation Gap |
| **Описание** | ADDENDUM §18.4 называет `synthesis_cache_builder.py` отдельным компонентом; в коде — функция внутри `rebuild_synthesis.py` |
| **Приоритет** | P1 |
| **Сложность** | LOW |
| **Трудоёмкость** | 45 минут |
| **Стратегия** | ~~Обновить ADDENDUM §18.4: переименовать «synthesis_cache_builder.py» → «rebuild_synthesis.py (функция build_cache())».~~ **Исправлено при реализации (2026-07-01):** эта формулировка сама была неточной — `build_cache()` с такой сигнатурой не существует; `"build_cache"` это метка `@measure_performance` на `synthesizer.py::main()`, а `rebuild_synthesis.py::rebuild()` — отдельный инструмент с другим назначением (diff/dry-run при MAJOR, без approved-фильтрации, без CacheBuilderError). §18.4 переписан под фактическое поведение обоих файлов, см. `docs/BLUEPRINT_ADDENDUM.md` §18.4 |

---

### REM-M02 | DEPLOYMENT.md: убрать несуществующий rebuild_cache.py

| Атрибут | Значение |
|---------|---------|
| **ID** | REM-M02 |
| **Категория** | Major / Documentation Gap |
| **Описание** | `DEPLOYMENT.md` раздел S3 ссылается на `scripts/rebuild_cache.py` которого нет |
| **Приоритет** | P0 |
| **Сложность** | LOW |
| **Трудоёмкость** | 30 минут |
| **Стратегия** | Заменить в S3: `python3 scripts/rebuild_cache.py` → `PYTHONHASHSEED=0 python3 scripts/synthesizer.py`. Обновить `scripts/README.md` аналогично |

---

### REM-M03 | Deploy-job: устранить alarm fatigue

| Атрибут | Значение |
|---------|---------|
| **ID** | REM-M03 |
| **Категория** | Major / DevOps |
| **Описание** | deploy-job стабильно красный из-за `build_type: "legacy"` в GitHub Pages; сайт работает, но CI noise |
| **Приоритет** | P1 |
| **Сложность** | LOW |
| **Трудоёмкость** | 30 минут |
| **Стратегия** | Переключить GitHub Pages: Settings → Pages → Source → «GitHub Actions» (build_type: workflow). Провести тестовый push и верифицировать deploy-job green. Если риск переключения неприемлем — задокументировать как «accepted known issue» в DEPLOYMENT.md с датой следующего пересмотра |

---

### REM-M04 | Staging environment: ветка develop

| Атрибут | Значение |
|---------|---------|
| **ID** | REM-M04 |
| **Категория** | Major / DevOps |
| **Описание** | Нет Staging; все пуши идут в `main` → Production |
| **Приоритет** | P1 |
| **Сложность** | LOW–MEDIUM |
| **Трудоёмкость** | 3 часа |
| **Стратегия** | 1. Создать ветку `develop` от `main`. 2. Настроить GitHub Pages для `develop` как отдельный environment (или gh-pages-develop). 3. CI: добавить job `deploy-staging` для `develop` ветки. 4. Обновить DEPLOYMENT.md: добавить Staging section |

---

### REM-M05 | Branch Protection на main

| Атрибут | Значение |
|---------|---------|
| **ID** | REM-M05 |
| **Категория** | Major / DevOps |
| **Описание** | Branch Protection не настроен; прямой push в main возможен для любого |
| **Приоритет** | P0 |
| **Сложность** | LOW |
| **Трудоёмкость** | 30 минут |
| **Стратегия** | GitHub Settings → Branches → main: `✓ Require a pull request`, `✓ Require status checks: validate`, `✓ Dismiss stale reviews`. Исключение: `github-actions[bot]` для синтезатора. Задокументировать в DEPLOYMENT.md |

---

### REM-M06 | Единый источник scoring weights

| Атрибут | Значение |
|---------|---------|
| **ID** | REM-M06 |
| **Категория** | Major / Architecture |
| **Описание** | Веса в `config/settings.py` (WEIGHT_SCORE, ROLE_SCORE) И в `ontology.json` (weight_scores) — два источника истины |
| **Приоритет** | P1 |
| **Сложность** | LOW — выбор источника |
| **Трудоёмкость** | 1 час |
| **Стратегия** | Принятое решение (ADR-014 — на момент написания IRP ссылка была на ADR-013, но этот номер к Wave 3 занят несвязанным решением B3/Wave 2; см. docs/ADR-014-single-source-of-truth-scoring-weights.md): `config/settings.py` остаётся единственным runtime-источником весов для Python. `ontology.json` секция `weight_scores` помечается как `"_note": "display only, не используется в вычислениях — единственный источник: config/settings.py"`. Добавлен тест `test_ontology_weight_scores_matches_settings` в уже существующий `test_ontology_settings_consistency.py`. Уточнение: `ROLE_SCORE` дублирования в `ontology.json` не имеет (там только текстовые описания ролей) — правка касается только `weight_scores` |

---

### REM-M07 | ALGORITHM_VERSION как semver-константа

| Атрибут | Значение |
|---------|---------|
| **ID** | REM-M07 |
| **Категория** | Major / Missing Specification |
| **Описание** | `synthesizer.py` не имеет `ALGORITHM_VERSION = "2.1.0"` как semver-константы; ADDENDUM §25.3 описывает версионирование |
| **Приоритет** | P1 |
| **Сложность** | LOW |
| **Трудоёмкость** | 1 час |
| **Стратегия** | Добавить в начало `scripts/synthesizer.py`: `ALGORITHM_VERSION = "2.1.0"`. Добавить в `SynthesisResult` поле `algorithm_version: str = ALGORITHM_VERSION`. Добавить тест на наличие и формат (semver regex). Обновить ALGORITHM.md §25.3 |

---

### REM-M08 | DoD для add_signal.py

| Атрибут | Значение |
|---------|---------|
| **ID** | REM-M08 |
| **Категория** | Major / Missing Specification |
| **Описание** | ADDENDUM §28 не содержит DoD для `add_signal.py` |
| **Приоритет** | P2 |
| **Сложность** | LOW |
| **Трудоёмкость** | 45 минут |
| **Стратегия** | Добавить §28.7 в ADDENDUM: `add_signal.py` DoD — validate → state_machine → atomic_write → EventLog → dry-run флаг → integration test зелёный |

---

### REM-M09 | Performance Tests baseline

| Атрибут | Значение |
|---------|---------|
| **ID** | REM-M09 |
| **Категория** | Major / Missing Tests |
| **Описание** | Критерий DoD §28.2: `synthesize(42 signals) < 100ms` — не автоматизирован |
| **Приоритет** | P2 |
| **Сложность** | LOW |
| **Трудоёмкость** | 2 часа |
| **Стратегия** | Добавить `tests/performance/test_synthesizer_perf.py`: `time.perf_counter()` вокруг `synthesize_cluster()` на 42 реальных сигналах. Порог: 100ms. Добавить в pyproject.toml отдельный marker `perf` — не в основной CI, запускается еженедельно |

---

## 6. План обновления документации

### 6.1 BLUEPRINT_ADDENDUM.md

**Изменить:**
- §23: добавить раздел «Текущая структура репозитория (2026-07-01)» с реальными директориями и раздел «Целевая структура (Фаза 4, ~2028)» — сохранить `src/` описание как целевое
- §18.4: переименовать `synthesis_cache_builder.py` → описать как `build_cache()` внутри `rebuild_synthesis.py`
- §28: добавить §28.7 `add_signal.py` DoD, §28.8 `index.html` DoD

**Добавить:**
- §28.9: DoD для `schemas/*.json` артефактов — «JSON Schema файлы существуют как физические файлы по указанным путям и проходят `jsonschema --validate` с хотя бы одним реальным примером»
- §30: Anti-Corruption Layers (краткое описание границы между Python-слоями; не полноценный Context Map — он в Technical Debt After MVP)

**Не трогать:**
- §15 Domain Model — полный и верный
- §17 Data Contracts — содержание верное, только не было физических файлов
- §20 Sequence Diagrams — актуальны
- §21 State Machines — реализованы в коде
- §24 Narrative Engine — реализован и верен

---

### 6.2 docs/API.md

**Добавить:**
- Секция «Пагинация» для GET /signals.json: `?page=N&limit=50` как описание будущего Backend-поведения (Phase 4). Для текущего статического API — примечание «полный список, пагинация — при переходе на Backend»

**Не трогать:**
- POST-схемы (добавлены в ARR v3)
- Error codes таблица
- Auth описание

---

### 6.3 DEPLOYMENT.md

**Изменить:**
- S3: `rebuild_cache.py` → `python3 scripts/synthesizer.py`
- Environments section: добавить «Staging (`develop` ветка)»
- Branch Strategy: уточнить — данные (`signal:` commits) и hotfix — прямой push в main разрешён (exempted from Branch Protection для DataOps роли). Код — только через PR

**Добавить:**
- «Настройка GitHub перед Sprint 0»: пошаговый чеклист настройки Branch Protection, Staging

---

### 6.4 DISASTER_RECOVERY.md

**Изменить:**
- S2 скрипт: `json.load(f)` → `data.get('signals', data)` паттерн (REM-C3)

**Добавить:**
- S5 (новый): «Восстановление при несуществующем relationships.json» — инструкция запуска `migrate_relationships.py`

---

### 6.5 docs/ALGORITHM.md

**Добавить:**
- §25.3bis: фактическое значение `ALGORITHM_VERSION = "2.1.0"` теперь в `synthesizer.py` как константа

---

### 6.6 config/settings.py

**Изменить:**
- `LEGACY_LINKS_ENABLED = False` (REM-B2)
- Добавить Completion Trigger comment: `# Выставлено в False YYYY-MM-DD при завершении Фазы 0. Не изменять без ADR`

**Добавить:**
- `ALGORITHM_VERSION = "2.1.0"` → но нет, это должно быть в `scripts/synthesizer.py` (не в config). В settings.py добавить только комментарий к `CONTRADICTION_PROPOSAL_THRESHOLD`

---

### 6.7 Новые ADR

| ADR | Тема | Волна |
|-----|------|-------|
| ADR-012 | Precision target снижен с 85% до 60% с gate на 30 пар | Wave 1 |
| ADR-013 | Единственный источник scoring weights — settings.py; ontology.json — display only | Wave 3 |

---

### 6.8 Новые артефакты (не документы, а файлы)

| Файл | Волна |
|------|-------|
| `data/relationships.json` | Wave 1 |
| `schemas/signal/v1.json` | Wave 2 |
| `schemas/relationship/v1.json` | Wave 2 |
| `schemas/synthesis/v1.json` | Wave 2 |
| `tests/golden/expected/golden_synthesis.json` | Wave 2 |
| `.github/CODEOWNERS` (для Branch Protection) | Wave 2 |

---

## 7. План обновления компонентов

### 7.1 scripts/synthesizer.py

**Необходимые изменения:**
- Добавить константу `ALGORITHM_VERSION = "2.1.0"` в начало файла (после docstring)
- Убедиться что `SynthesisResult` включает `algorithm_version: str` поле (уже есть в dataclass, нужно убедиться что заполняется)

**Запрещённые изменения:**
- 12-шаговый алгоритм — не трогать (Golden Tests защищают)
- Bridge Semantics — не трогать
- `PYTHONHASHSEED` assert — не трогать

**Затронутые тесты:**
- Добавить `test_algorithm_version_is_semver()` в test_synthesizer.py

---

### 7.2 config/settings.py

**Необходимые изменения:**
- `LEGACY_LINKS_ENABLED = False`
- Комментарий к `CONTRADICTION_PROPOSAL_THRESHOLD` со ссылкой на ADR-012

**Запрещённые изменения:**
- Формулы scoring — не трогать (тесты на них)
- Константы WINDOW_DAYS, STALE_THRESHOLD — не трогать (M3 ARR v3 закрыт)

**Затронутые тесты:**
- `test_ontology_settings_consistency.py` — проверить что по-прежнему green после изменения флага

---

### 7.3 infrastructure/relationship_store.py

**Необходимые изменения:**
- Убрать legacy-ветку чтения из `links.*` в `signals.json` после выставления `LEGACY_LINKS_ENABLED = False`
- Или оставить ветку но с явным `if LEGACY_LINKS_ENABLED: raise DeprecatedError(...)` — fail loud при попытке использовать legacy

**Затронутые тесты:**
- Добавить тест что legacy-путь недоступен при `LEGACY_LINKS_ENABLED = False`

---

### 7.4 .github/workflows/deploy.yml

**Необходимые изменения:**
- Добавить job `contract-tests` до `Run tests`:
  ```yaml
  - name: Contract Tests (JSON Schema)
    run: |
      pip install jsonschema --quiet
      python3 scripts/validate_contracts.py
  ```
- Добавить job `deploy-staging` при push в `develop`

**Запрещённые изменения:**
- validate → synthesize → deploy цепочка — не менять порядок
- `PYTHONHASHSEED: "0"` — не убирать

---

### 7.5 tests/golden/test_golden.py

**Необходимые изменения:**
- Убрать `pytest.skip()` при отсутствии `golden_synthesis.json`
- Заменить на `assert Path(EXPECTED_PATH).exists(), "golden_synthesis.json must be created per DoD §28.6"`

**Запрещённые изменения:**
- Логика сравнения синтезов — не менять до утверждения нового golden

---

### 7.6 Новый компонент: scripts/validate_contracts.py

**Назначение:** Contract Validation для CI — валидация всех записей в `signals.json` против `schemas/signal/v1.json`.

**Контракт:**
```python
def validate_all_signals(signals_path: str, schema_path: str) -> list[ContractError]
def validate_relationships(rel_path: str, schema_path: str) -> list[ContractError]

# Exit 0 если все валидны; Exit 3 (DATA_INTEGRITY_ERROR) при первом нарушении
# Принты в stdout: "OK: 48 signals valid" или "FAIL: signal STR-2026-0630-001: missing field X"
```

---

## 8. Dependency Map

```
НЕМЕДЛЕННЫЕ (нет предшественников):
  REM-C3  ──── DISASTER_RECOVERY S2 fix (30 мин)
  REM-C2  ──── ADR-012 Precision (1 час)
  REM-M02 ──── DEPLOYMENT.md rebuild_cache fix (30 мин)
  REM-M05 ──── Branch Protection (30 мин)

ПОСЛЕДОВАТЕЛЬНЫЕ (строгий порядок):
  REM-B2 (migrate relationships)
    └──→ REM-B3 (JSON Schema: relationship schema needs relationships.json)
           └──→ REM-B3-CI (Contract Tests в CI: нужны созданные schemas)
                  └──→ REM-C1 (Golden Tests: нужен completed synthesizer)

НЕЗАВИСИМЫЕ (параллельно после B2):
  REM-B1  ──── §23 ADDENDUM (не зависит от кода)
  REM-M03 ──── Deploy-job fix
  REM-M04 ──── Staging environment
  REM-M07 ──── ALGORITHM_VERSION (независимо)
  REM-M06 ──── Scoring weights (независимо)

ЗАВИСЯТ ОТ WAVE 1+2:
  REM-M01 ──── ADDENDUM §18.4 fix (нужен ясный статус relationships)
  REM-M08 ──── DoD add_signal.py
  ADR-013 ──── Scoring weights ADR

ПОСЛЕДНЯЯ ВОЛНА (зависят от всего):
  REM-M09 ──── Performance Tests
  OP03    ──── Secrets rotation
  OP04    ──── Dependabot
  D01     ──── API.md Pagination
```

**Критический путь:**
```
REM-B2 → REM-B3 → REM-B3-CI → REM-C1 → Wave 5 Validation
(~9 рабочих дней)
```

---

## 9. Roadmap реализации

### Wave 1 — Blockers & Immediate Fixes
**Дни: 1–3 | Трудоёмкость: ~8 часов**

**Цель:** Устранить все блокирующие замечания B-уровня и Critical-замечания, не требующие технической работы.

| Задача | ID | Исполнитель | Оценка |
|--------|----|------------|--------|
| Исправить S2 в DISASTER_RECOVERY | REM-C3 | DevOps Architect | 30 мин |
| Создать ADR-012 (Precision target) | REM-C2 | Lead AI Engineer | 1 час |
| Исправить DEPLOYMENT.md rebuild_cache | REM-M02 | Technical Writer | 30 мин |
| Настроить Branch Protection | REM-M05 | DevOps Architect | 30 мин |
| Завершить Фазу 0: migrate_relationships | REM-B2 | Staff Backend | 2 часа |
| Обновить §23 ADDENDUM (Current vs Target) | REM-B1 | Principal Architect | 1 час |

**Definition of Done Wave 1:**
- [ ] `python3 DISASTER_RECOVERY_S2_test.py` выполняется без ошибки
- [ ] `data/relationships.json` существует, `validate_relationships.py` green
- [ ] `LEGACY_LINKS_ENABLED = False` в settings.py
- [ ] `docs/ADR-012-contradiction-precision-target.md` создан
- [ ] Branch Protection активен: PR required для merge в `main`
- [ ] DEPLOYMENT.md не содержит `rebuild_cache.py`
- [ ] ADDENDUM §23 содержит разделы «Текущая» и «Целевая»

**Критерий перехода к Wave 2:** Все 6 DoD выполнены, CI green.

---

### Wave 2 — Critical & Contract Infrastructure
**Дни: 3–7 | Трудоёмкость: ~12 часов**

**Цель:** Создать контрактную инфраструктуру (JSON Schema, Contract Tests) и Golden Dataset.

| Задача | ID | Исполнитель | Оценка |
|--------|----|------------|--------|
| Создать schemas/signal/v1.json | REM-B3 | Staff Backend | 1.5 часа |
| Создать schemas/relationship/v1.json | REM-B3 | Staff Backend | 1 час |
| Создать schemas/synthesis/v1.json | REM-B3 | Staff Backend | 1 час |
| Создать scripts/validate_contracts.py | REM-B3 | Staff Backend | 2 часа |
| Добавить Contract Tests в CI | REM-B3-CI | DevOps Architect | 1 час |
| Создать golden_synthesis.json | REM-C1 | QA Architect + Analyst | 2 часа |
| Убрать pytest.skip() из test_golden.py | REM-C1 | QA Architect | 30 мин |
| Deploy-job: fix alarm fatigue | REM-M03 | DevOps Architect | 30 мин |
| Создать Staging (develop branch) | REM-M04 | DevOps Architect | 3 часа |

**Definition of Done Wave 2:**
- [ ] `python3 scripts/validate_contracts.py` → «OK: 48 signals valid»
- [ ] CI: шаг «Contract Tests» green на любом PR
- [ ] `tests/golden/test_golden.py` — PASS (не skip)
- [ ] Изменение тестового сигнала в golden_signals.json → Golden Test FAIL (регрессия поймана)
- [ ] deploy-job green (или задокументирован как accepted)
- [ ] `develop` ветка существует и деплоится в Staging URL

**Критерий перехода к Wave 3:** Все 7 DoD выполнены, 149+ тестов green (golden больше не skip).

---

### Wave 3 — Major Issues & Documentation Alignment
**Дни: 7–10 | Трудоёмкость: ~8 часов**

**Цель:** Устранить Major-замечания, выровнять документацию с кодом.

| Задача | ID | Исполнитель | Оценка |
|--------|----|------------|--------|
| ADDENDUM §18.4: synthesis_cache_builder | REM-M01 | Technical Writer | 45 мин |
| ALGORITHM_VERSION как semver-константа | REM-M07 | Staff Backend | 1 час |
| ADR-013: единственный источник весов | REM-M06 | Principal Architect | 1 час |
| DoD §28.7 для add_signal.py | REM-M08 | Technical Writer | 45 мин |
| Secrets rotation policy | OP03 | DevOps Architect | 1 час |
| Dependabot настройка | OP04 | DevOps Architect | 30 мин |
| Anti-Corruption Layers §30 ADDENDUM | D02 | Principal Architect | 2 часа |
| API.md: Pagination для GET | D01 | Technical Writer | 30 мин |

**Definition of Done Wave 3:**
- [x] `synthesizer.py` содержит `ALGORITHM_VERSION = "2.1.0"`
- [x] `test_algorithm_version_is_semver()` — PASS
- [x] ADDENDUM §18.4 описывает реальный файл
- [x] ADR-014 создан и ссылается из settings.py и ontology.json (в исходном тексте DoD стояло «ADR-013» — номер уже занят Wave 2/B3, см. ADR-014 «Уточнение к IRR/IRP»)
- [x] Dependabot PR для outdated зависимостей создаётся автоматически
- [x] Secrets rotation policy описана в SECURITY.md
- [x] `docs/API.md` документирует `limit`/`offset` пагинацию для GET-эндпоинтов Backend-фазы (D01); `docs/BLUEPRINT_ADDENDUM.md` §19 (источник контракта) обновлён синхронно
- [x] `docs/BLUEPRINT_ADDENDUM.md` §30 описывает три реальных ACL-границы проекта (D02); RR-04 уточнён — заявленного CI-контроля (flake8 layer rules) не существует

---

### Wave 4 — Monitoring, Performance, Scalability
**Дни: 10–13 | Трудоёмкость: ~8 часов**

**Цель:** Закрыть замечания из операционных и scalability категорий. Это не критический путь — Wave 4 может идти параллельно с Wave 3 частично.

| Задача | ID | Исполнитель | Оценка |
|--------|----|------------|--------|
| Performance test: synthesize < 100ms | REM-M09 | QA Architect | 2 часа |
| Alerting: synthesis freshness check | OP05 | DevOps Architect | 2 часа |
| signals.json size monitoring | OP06 | DevOps Architect | 1 час |
| Release Strategy в DEPLOYMENT.md | D08 | Technical Writer | 1 час |
| Scalability: Paging strategy документация | MC07 | Principal Architect | 45 мин |
| migration/v1_to_v2.py stub | MC05 | Staff Backend | 30 мин |

**Definition of Done Wave 4:**
- [ ] `pytest -m perf` → synthesize < 100ms на 42 сигналах
- [ ] GitHub Actions scheduled job проверяет freshness synthesis_cache еженедельно
- [ ] `signals.json` size проверяется в CI: WARNING при > 4MB
- [ ] Release Strategy секция в DEPLOYMENT.md

---

### Wave 5 — Validation & Sprint 0 Gate
**День: 14 | Трудоёмкость: ~4 часа**

**Цель:** Валидация полноты программы, прогон IRR Checklist, принятие решения о Sprint 0.

| Задача | Исполнитель | Оценка |
|--------|------------|--------|
| Прогон обновлённого IRR Checklist | QA Architect | 2 часа |
| Верификация каждого FAIL → PASS | Principal Architect | 1 час |
| Sprint 0 Gate Meeting | Вся команда | 1 час |

**Definition of Done Wave 5 = Sprint 0 Gate Criteria** (см. раздел 11).

---

## 10. Acceptance Criteria

Для каждого замечания — измеримый критерий по SMART.

| ID | SMART Критерий |
|----|---------------|
| B1 | ADDENDUM §23 содержит H2-заголовок «Текущая структура (действует с 2026-07-NN)» с реальными директориями, и H2-заголовок «Целевая структура (Фаза 4)» с `src/`. Проверка: `grep "Текущая структура" docs/BLUEPRINT_ADDENDUM.md && grep "Целевая структура" docs/BLUEPRINT_ADDENDUM.md` — оба выходят |
| B2 | `ls data/relationships.json` — файл существует. `python3 scripts/validate_relationships.py` — exit code 0. `python3 -c "from config.settings import LEGACY_LINKS_ENABLED; assert not LEGACY_LINKS_ENABLED"` — проходит |
| B3 | `ls schemas/signal/v1.json schemas/relationship/v1.json schemas/synthesis/v1.json` — все три файла существуют. `python3 scripts/validate_contracts.py` → «OK: 48 signals valid». CI Contract Tests шаг — зелёный |
| C1 | `ls tests/golden/expected/golden_synthesis.json` — файл существует. `PYTHONHASHSEED=0 pytest tests/golden/test_golden.py -v` → PASS (не skip). Изменение одного поля в `golden_signals.json` → Golden Test FAIL |
| C2 | `ls docs/ADR-012-contradiction-precision-target.md` — файл существует. ADR содержит секции Context, Decision, Rationale, Gate для пересмотра. `grep "60" docs/ADR-012*.md` — находит обоснование 60% |
| C3 | Запуск S2 скрипта из DISASTER_RECOVERY.md на текущем `signals.json` → exit code 0, число удалённых сигналов выводится корректно |
| M01 | `grep "synthesis_cache_builder" docs/BLUEPRINT_ADDENDUM.md` — описывает `rebuild_synthesis.py`, не отдельный файл |
| M02 | `grep "rebuild_cache.py" DEPLOYMENT.md scripts/README.md` — ни одного результата |
| M03 | GitHub Actions: последние 5 runs deploy-job — все зелёные (или OP записана как accepted known issue с датой) |
| M04 | Ветка `develop` существует. `git fetch; git branch -r | grep develop` — выводит. Staging URL отвечает на запрос |
| M05 | GitHub Settings → Branches → `main` → «Require a pull request before merging» — checked. Тест: попытка прямого push от non-admin → blocked |
| M06 | `grep "scoring_rules\|weight_scores" ontology.json` — секция помечена `"_note": "display only"`. `python3 -c "from config.settings import WEIGHT_SCORE"` — значения совпадают с ontology.json display |
| M07 | `grep "ALGORITHM_VERSION" scripts/synthesizer.py` → `ALGORITHM_VERSION = "2.1.0"`. `python3 -c "import re; v='2.1.0'; assert re.match(r'^\d+\.\d+\.\d+$', v)"` — проходит |
| M08 | `grep "28.7\|add_signal" docs/BLUEPRINT_ADDENDUM.md` — DoD для add_signal.py найден |
| M09 | `PYTHONHASHSEED=0 pytest tests/performance/ -m perf -v` → PASS; synthesize(42) < 100ms |

---

## 11. Verification Plan

| Замечание | Метод верификации | Кто верифицирует |
|-----------|-----------------|-----------------|
| B1 (§23 ADDENDUM) | Ревью документа: независимый разработчик, не участвовавший в IRP, читает §23 и называет реальную директорию для нового кода | Principal Architect (не автор) |
| B2 (relationships.json) | Автоматический: `validate_relationships.py` в CI | CI (автомат) + Staff Backend |
| B3 (JSON Schema) | Автоматический: Contract Tests в CI на каждом PR | CI (автомат) |
| C1 (golden_synthesis.json) | Автоматический: `pytest tests/golden/` — PASS | CI (автомат) |
| C2 (ADR-012) | Ревью документа: ADR содержит все обязательные секции и ссылается из settings.py | Lead AI Engineer |
| C3 (S2 script) | Ручной тест: выполнить S2 скрипт из DISASTER_RECOVERY в тестовом окружении; проверить, что скрипт завершается с exit 0 и верным числом сигналов | DevOps Architect |
| M03 (deploy-job) | Наблюдение: 5 последовательных CI runs после fix — все deploy зелёные | DevOps Architect |
| M04 (Staging) | Ручной: открыть Staging URL; убедиться что он отражает последний commit в `develop` | Technical PM |
| M05 (Branch Protection) | Ручной тест: попытаться запушить напрямую в `main` от non-admin → ожидается rejection | DevOps Architect |
| M07 (ALGORITHM_VERSION) | Автоматический: `test_algorithm_version_is_semver()` — PASS | CI (автомат) |
| Все остальные | Прогон обновлённого IRR Checklist из IRR_REPORT_v1.md: каждый FAIL → PASS | Principal QA Architect |

**Финальная верификация (Wave 5):** Независимый прогон IRR Checklist из IRR_REPORT_v1.md. Целевой результат:
- Blockers: 0
- Critical: 0
- Major FAIL: 0
- Итого FAIL: ≤ 5 (только принятые Residual Risks)

---

## 12. Residual Risks

После выполнения всех волн IRP следующие риски остаются **осознанно принятыми**:

| Risk ID | Риск | Почему допустимо | Контроль во время реализации |
|---------|------|-----------------|------------------------------|
| RR-01 | **AI08: Causal Reasoning** — конкатенация `macro_implication`, не настоящий анализ | ARR v3 зафиксировал явно, ARR Execution Status: «Tech Debt After MVP». Не влияет на корректность текущего нарратива | Ревью при добавлении каждого нового кластера |
| RR-02 | **TST13–TST15: Mutation/Load/Acceptance Tests** | Technical Debt After MVP по ADDENDUM §29.3 | Добавить в backlog как P3 задачи Sprint 1+ |
| RR-03 | **MON06: Distributed tracing** | Technical Debt After MVP; нет backend | Метрики через events.jsonl и quality_report.py до Backend |
| RR-04 | **DOM08: Anti-Corruption Layers** (формальный Context Map) | §30 добавлен (D02, Wave 3, 2026-07-01) — краткое описание трёх реальных ACL-границ по факту кода. Полноценный Context Map остаётся Technical Debt After MVP, до масштабирования к 5+ bounded contexts | ~~Ревью импортов в CI (flake8 layer rules)~~ **Уточнено (D02):** такого CI-механизма не существует на 2026-07-01 — `pyproject.toml` не содержит import-linter/layer-plugin. Границы держатся review-дисциплиной (README.md слоёв), не автоматикой |
| RR-05 | **SCL06: UI Paging при 500+ сигналах** | Сейчас 48 сигналов. Документация добавлена в Wave 4; реализация при достижении 300+ | Автоматический мониторинг размера signals.json (OP06) |
| RR-06 | **Confidence калибровка** (ADR-011) | 10/30 синтезов до gate; quality_report.py отслеживает | Инкрементальный счётчик в каждом quality_report run |
| RR-07 | **PAT в истории переписки с ассистентом** (формулировка «PAT в git history» была неточной — см. SECURITY.md «Secrets Rotation Policy», OP03: `git rev-list --all` + `git grep` по всему репозиторию не находит реального токена ни в одном блобе) | Токен несколько раз вставлялся открытым текстом в чат в разных сессиях реализации Wave 1–3, риск компрометации. Политика ротации (OP03 Wave 3, SECURITY.md) описывает это явно как триггер внеплановой ротации | После ротации новый токен — только в GitHub Secrets |
| RR-08 | **JS Fallback без window-filtering** (ADR-010) | Задокументирован в ADR-010 «Дальнейшая работа»; тест держит gap видимым | test_known_gap_js_lacks_window_filtering не удалять |

---

## 13. Повторная процедура проверки (Re-IRR Gate)

По завершении Wave 5 проводится **Sprint 0 Gate Review** — не полноценный новый IRR (14 этапов), а целевая проверка по зафиксированным замечаниям.

### Обязательные документы для Re-IRR Gate

| Документ | Что проверяется |
|----------|----------------|
| `docs/BLUEPRINT_ADDENDUM.md` | §23 содержит Current vs Target; §18.4 описывает реальный файл; §28 содержит DoD для всех компонентов |
| `docs/IRR_REPORT_v1.md` | Каждый FAIL из чеклиста должен иметь запись «→ PASS: [способ верификации]» |
| `data/relationships.json` | Файл существует, непустой, прошёл validate_relationships.py |
| `schemas/*.json` | Три файла существуют, CI Contract Tests green |
| `tests/golden/expected/golden_synthesis.json` | Файл существует, test_golden.py PASS |
| `docs/ADR-012-contradiction-precision-target.md` | Файл существует |
| `docs/ADR-013-scoring-weights-single-source.md` | Файл существует |
| `DEPLOYMENT.md` | Содержит Staging section, Branch Protection setup |
| `DISASTER_RECOVERY.md` | S2 скрипт прошёл ручной тест |
| `.github/workflows/deploy.yml` | Contract Tests шаг присутствует |

### Критерии успешного Re-IRR Gate

```
ОБЯЗАТЕЛЬНЫЕ (все должны быть PASS):
  □ IRR Checklist: FAIL ≤ 5 (только из RR-01–RR-08 выше)
  □ CI: все шаги green на main после последнего IRP-коммита
  □ pytest: ≥ 155 тестов passing (было 149 + новые из IRP)
  □ Contract Tests в CI: существуют и green
  □ Golden Tests: PASS (не skip)
  □ Branch Protection: активен на main
  □ data/relationships.json: существует

РЕКОМЕНДУЕМЫЕ (PASS желательны, не блокируют):
  □ Staging URL: отвечает
  □ deploy-job: green (или явный accepted-статус)
  □ Dependabot: настроен
```

---

## 14. Финальное решение о готовности к Sprint 0

### Условие получения статуса READY TO IMPLEMENT

Проект получает статус **READY TO IMPLEMENT** при одновременном выполнении:

1. **Re-IRR Gate passed** — все обязательные критерии п.13 выполнены
2. **Команда онбордирована** — каждый разработчик прочитал ONBOARDING.md и может ответить на 3 вопроса: «Куда добавлять новый Python-компонент?», «Что такое PYTHONHASHSEED и зачем?», «Как добавить новый кластер?»
3. **Sprint 0 backlog сформирован** — первые 2 недели Sprint 0 декомпозированы в GitHub Issues с привязкой к BLUEPRINT Фазам

### Ответственные за Gate Decision

| Роль | Ответственность |
|------|----------------|
| Principal Architect | Подтверждает архитектурную корректность изменений IRP |
| Principal QA Architect | Подтверждает что тест-сьют защищает ключевые инварианты |
| Technical PM | Подтверждает что команда готова и backlog сформирован |
| DevOps Architect | Подтверждает что инфраструктура поддерживает многопользовательскую разработку |

**При несогласии одного из четырёх** — Sprint 0 не открывается до устранения разногласия. Нет права вето у одного человека, но нет и принципа большинства: каждая роль покрывает свой домен, и разногласие означает незакрытый риск в этом домене.

---

*Документ: IRP v1.0 · Bitcoin Intel Narrative Intelligence Platform · 2026-07-01*
*Основание: IRR v1.0 (docs/IRR_REPORT_v1.md)*
*Следующее обновление: после Wave 3 — промежуточный статус выполнения*
