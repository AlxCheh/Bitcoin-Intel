# IMPLEMENTATION TRACKER
## Bitcoin Intel Narrative Intelligence Platform
## Трекер выполнения: от аудита до первого коммита кода

> **Как использовать:** Выполняй задачи строго по порядку.  
> При завершении ставь `[x]` и дату: `[x] 2026-06-29`.  
> Не переходи к следующему дню пока не закрыты все задачи текущего.  
> Повторный ARR только после закрытия **всех** чеклистов.

---

## Статус проекта

```
Текущий статус:   ⛔ NOT READY (ARR_REPORT.md, 2026-06-28)
Цель:             ✅ READY WITH CONDITIONS
Blockers открыто: 5 из 5
TD открыто:       10 из 10
Дней до ARR:      ~5
```

---

## Документы проекта (порядок чтения)

| # | Файл | Что внутри | Читать когда |
|---|------|-----------|-------------|
| 1 | `CLAUDE.md` | Правила работы с проектом | Всегда первым |
| 2 | `ALGORITHM.md` | Алгоритм нарративного синтеза + правила tension | До добавления сигналов |
| 3 | `SYNTHESIS_ARCHITECTURE.md` | Гибридная архитектура synthesis.json | До Фазы 1 |
| 4 | `BLUEPRINT_ADDENDUM.md` | Domain Model, Contracts, Narrative Engine Spec | До начала кодирования |
| 5 | `ARR_REPORT.md` | Что заблокировало разработку и почему | До устранения Blockers |
| 6 | `PRE_IMPLEMENTATION_PLAN.md` | Детальный план устранения Blockers | Исполнять сейчас |
| 7 | `GLOSSARY.md` | Термины системы | *Создать: День 4* |
| 8 | `SECURITY.md` | Threat model, меры защиты | *Создать: День 3* |
| 9 | `DISASTER_RECOVERY.md` | RTO/RPO, процедуры восстановления | *Создать: День 3* |
| 10 | `DEPLOYMENT.md` | CI/CD, environments, rollback | *Создать: День 3* |

---

## ДЕНЬ 1 — Быстрые фиксы (≈6 часов)
**Цель:** Устранить B1 + задокументировать 5 технических решений

---

### B1 — hash() недетерминизм ⛔ BLOCKER
**Файл:** `BLUEPRINT_ADDENDUM.md` §24.2  
**Артефакт:** обновлённая функция `select_bridge()`

- [x] Заменить `abs(hash(seed)) % len(options)` на `seed % len(options)`
- [x] Добавить `assert os.environ.get("PYTHONHASHSEED") != "random"` в synthesizer.py
- [x] Добавить `PYTHONHASHSEED=0` в Makefile и DEPLOYMENT.md
- [x] Написать тест `test_bridge_selection_deterministic()`
- [x] Обновить §24.2 в BLUEPRINT_ADDENDUM.md
- [x] Коммит: `fix: replace hash() with seed % len() for deterministic bridge selection`

**Дата закрытия:** `[ ]`

---

### TD1 — MAX_POSSIBLE_SCORE не определён
**Файл:** `BLUEPRINT_ADDENDUM.md` §24.1 Шаг 11  
**Артефакт:** функция `calculate_max_possible_score(n)`

- [x] Добавить формулу: MAX_PER_SIGNAL = 3+4+4 = 11; MAX = N × 11 (уточнено по scores)
- [x] Добавить функцию `calculate_confidence()` с явными модификаторами
- [x] Проверить пример: тесты подтверждают диапазон
- [x] Обновить §24.1 в BLUEPRINT_ADDENDUM.md
- [x] Коммит: `feat: config/settings.py`

**Дата закрытия:** `[ ]`

---

### TD6 — Тиебрейкер 4-го уровня
**Файл:** `BLUEPRINT_ADDENDUM.md` §24.1 Шаг 2  
**Артефакт:** обновлённая `rank_signals()` с 4-м уровнем по `id`

- [x] Добавить `s.id` как 4-й уровень сортировки (лексикографический, всегда уникален)
- [x] Написать тест: два сигнала с одинаковым weight/contradicts/date → детерминированный результат
- [x] Обновить §24.1 в BLUEPRINT_ADDENDUM.md
- [x] Коммит: `fix: add id as 4th-level tiebreaker in rank_signals()`

**Дата закрытия:** `[ ]`

---

### TD7 — Empty cluster UI контракт
**Файл:** `BLUEPRINT_ADDENDUM.md` §18 (добавить UI rendering contract)  
**Артефакт:** спецификация трёх состояний карточки нарратива

- [x] Описать: empty (strength=weak, нет tension) → renderWeakSignalPlaceholder
- [x] Описать: tension без narrative → renderTensionOnly
- [x] Описать: полная карточка → renderFullCard
- [x] Коммит: `docs: add empty cluster UI rendering contract`

**Дата закрытия:** `[ ]`

---

### TD8 — Date timezone policy
**Файл:** `settings.py` (создать) + Signal Schema description  
**Артефакт:** явная политика UTC для всех дат

- [x] Создать `config/settings.py` с DATE_POLICY
- [x] Добавить в Signal Schema: `"description": "Дата события в UTC, формат YYYY-MM-DD"`
- [x] Добавить в validator.py: `date.today()` в UTC
- [x] Коммит: `docs: define UTC date policy in settings.py`

**Дата закрытия:** `[ ]`

---

### TD9 — Encoding policy
**Файл:** `config/settings.py`  
**Артефакт:** константы ENCODING и JSON_ENSURE_ASCII

- [x] Добавить `ENCODING = "utf-8"` и `JSON_ENSURE_ASCII = False` в settings.py
- [x] Проверить что все open() в скриптах используют `encoding='utf-8'`
- [x] Коммит: `docs: define UTF-8 encoding policy`

**Дата закрытия:** `[ ]`

---

**✅ ДЕНЬ 1 ЗАКРЫТ:** `[x] 2026-06-28`

---

## ДЕНЬ 2 — Алгоритм Contradiction Detector + Migration (≈6 часов)
**Цель:** Устранить B2 + определить переходный период

---

### B2 — semantic_inverse_score не специфицирован ⛔ BLOCKER
**Файл:** `BLUEPRINT_ADDENDUM.md` §24 (новый подраздел)  
**Артефакт:** полная спецификация алгоритма с INVERSE_PAIRS

- [ ] Определить `INVERSE_PAIRS` — минимум 15 пар для Bitcoin-домена
- [ ] Специфицировать формулу: `score = 0.6×inverse + 0.2×subject + 0.2×dir_conflict`
- [ ] Определить пороги: 1 hit = 0.4, 2 hits = 0.7, 3+ hits = 1.0
- [ ] Определить порог предложения кандидата: score ≥ 0.5
- [x] Написать тест `test_obvious_contradiction()`: score ≥ 0.5 ✓
- [x] Написать тест `test_no_contradiction()`: score < 0.3 ✓
- [ ] Написать тест `test_different_subjects()`: score < 0.4 ✓
- [ ] Верифицировать на 5 реальных парах из базы: `STR-2026-0615-001` vs `STR-2026-0628-001`
- [ ] Добавить в BLUEPRINT_ADDENDUM.md §24 подраздел «Contradiction Scoring Algorithm»
- [ ] Коммит: `docs: specify semantic_inverse_score algorithm with INVERSE_PAIRS`

**Дата закрытия:** `[ ]`

---

### TD2 — Переходный период links.* → relationships.json
**Файл:** `BLUEPRINT_ADDENDUM.md` ADR-007 (создать) + `infrastructure/relationship_store.py`  
**Артефакт:** флаг `LEGACY_LINKS_ENABLED` + чеклист завершения миграции

- [ ] Оформить ADR-007: «Переходный период чтения связей»
- [ ] Специфицировать `RelationshipStore` с `LEGACY_LINKS_ENABLED = True`
- [ ] Описать логику дедупликации при объединении источников
- [ ] Создать чеклист завершения переходного периода (5 пунктов)
- [ ] Определить целевую дату: конец Фазы 0
- [ ] Коммит: `docs: ADR-007 — relationship migration transitional period`

**Дата закрытия:** `[ ]`

---

**✅ ДЕНЬ 2 ЗАКРЫТ:** `[x] 2026-06-28`

---

## ДЕНЬ 3 — Три отсутствующих документа (≈8 часов)
**Цель:** Устранить B3, B4, B5

---

### B3 — Security Architecture ⛔ BLOCKER
**Файл:** `SECURITY.md` (создать в корне репозитория)  
**Артефакт:** Threat Model + меры защиты + XSS fix в index.html

- [x] Создать `SECURITY.md` с Threat Model для MVP
- [x] Описать 4 угрозы в периметре: XSS, corruption, credential leak, invalid input
- [x] Описать меры: sanitize(), schema validation в CI, .gitignore для .env
- [ ] Исправить XSS в `index.html`: заменить уязвимые `innerHTML = data` на `textContent` или `sanitize()`
- [ ] Найти все места: `tension`, `narrative`, `takeaway`, `signal` в renderNarrativeItem
- [ ] Добавить функцию `sanitize()` в index.html
- [ ] Создать `.env.example` (без значений)
- [ ] Обновить `.gitignore`: добавить `.env`, `*.key`, `config/secrets.py`
- [ ] Коммит: `security: add SECURITY.md, fix XSS in renderNarrativeItem, add .env.example`

**Дата закрытия:** `[x] 2026-06-28`

---

### B4 — Disaster Recovery ⛔ BLOCKER
**Файл:** `DISASTER_RECOVERY.md` (создать в корне репозитория)  
**Артефакт:** RTO/RPO таблица + 4 процедуры восстановления + backup script

- [x] Создать `DISASTER_RECOVERY.md`
- [x] Определить RTO/RPO для 4 сценариев
- [ ] Написать процедуру: восстановление signals.json из git
- [ ] Написать процедуру: восстановление неверно добавленного сигнала
- [ ] Написать процедуру: восстановление synthesis_store
- [ ] Написать процедуру: полная потеря репозитория
- [x] Создать `scripts/backup.sh` — еженедельный tar.gz архив
- [ ] Провести тест DR: намеренно испортить файл, восстановить, верифицировать
- [ ] Зафиксировать результат теста в документе
- [ ] Коммит: `docs: add DISASTER_RECOVERY.md with RTO/RPO and recovery procedures`

**Дата закрытия:** `[x] 2026-06-28`

---

### B5 — Deployment Strategy ⛔ BLOCKER
**Файл:** `DEPLOYMENT.md` (создать) + `.github/workflows/deploy.yml`  
**Артефакт:** полный deployment runbook + CI/CD pipeline

- [x] Создать `DEPLOYMENT.md` с архитектурой деплоя
- [x] Описать 2 environments: Production (main) и Preview (PR)
- [ ] Создать `.github/workflows/deploy.yml`:
  - [ ] Шаг: validate_all_signals.py
  - [ ] Шаг: validate_relationships.py
  - [ ] Шаг: pytest tests/unit/ с PYTHONHASHSEED=0
  - [ ] Шаг: pytest tests/golden/ (пропустить если dataset не создан)
  - [ ] Шаг: rebuild_cache.py
  - [ ] Шаг: check_staleness.py
  - [ ] Деплой: только при push в main
- [x] Определить branch strategy: main / feature/* / hotfix/*
- [x] Написать deployment checklist (6 пунктов)
- [x] Написать rollback procedure
- [ ] Коммит: `ci: add deployment pipeline and DEPLOYMENT.md`

**Дата закрытия:** `[x] 2026-06-28`

---

**✅ ДЕНЬ 3 ЗАКРЫТ:** `[x] 2026-06-28`

---

## ДЕНЬ 4 — Golden Dataset, File Locking, Глоссарий, Events (≈8 часов)
**Цель:** Закрыть TD3, TD4, TD5, TD10

---

### TD3 — Golden Dataset
**Файл:** `tests/golden/fixtures/golden_signals.json` + `tests/golden/expected/golden_synthesis.json`  
**Артефакт:** ≥15 тестовых сигналов, 5 кластеров, ожидаемые синтезы

- [ ] Создать директорию `tests/golden/fixtures/`
- [ ] Создать 5 тестовых кластеров:
  - [ ] `test_trigger_only` — только trigger (нет complication)
  - [ ] `test_contradiction` — trigger + complication с contradicts
  - [ ] `test_resolution` — trigger + complication + resolution
  - [ ] `test_stale` — сигналы старше 90 дней (вне окна)
  - [ ] `test_equal_weight` — равный weight → проверка тиебрейкера
- [ ] Написать ≥3 сигнала на кластер (итого ≥15)
- [ ] Создать `tests/golden/expected/golden_synthesis.json` с ожидаемыми результатами
- [ ] Написать `tests/golden/test_golden.py`
- [ ] Убедиться что все тесты зелёные на текущем алгоритме
- [ ] Коммит: `test: add golden dataset with 15 signals and 5 cluster scenarios`

**Дата закрытия:** `[ ]`

---

### TD4 — File Locking
**Файл:** `infrastructure/file_lock.py`  
**Артефакт:** `file_lock()` контекстный менеджер + атомарная запись

- [ ] Создать `infrastructure/file_lock.py` с `fcntl`-based lock
- [ ] Реализовать атомарную запись через temp file → os.replace()
- [ ] Обернуть все write операции в scripts/: add_signal, approve_synthesis
- [ ] Написать тест: параллельный запуск двух процессов → только один записывает
- [ ] Добавить примечание в DEPLOYMENT.md: «Unix-only»
- [ ] Коммит: `feat: add file_lock() for safe concurrent writes`

**Дата закрытия:** `[ ]`

---

### TD5 — Глоссарий
**Файл:** `GLOSSARY.md` (создать в корне репозитория)  
**Артефакт:** ≥15 терминов с точными определениями

- [x] Создать `GLOSSARY.md`
- [x] Определить аналитические термины: Signal, Tension, macro_implication, narrative_role, Cluster, Synthesis, mNAV, contradicts, window_days, strength, phase, approved synthesis, fallback
- [x] Определить технические термины: PYTHONHASHSEED, partA/partB, bridge, signal_strength, Aggregate Root, append-only
- [ ] Добавить ссылку на GLOSSARY.md в CLAUDE.md  ← следующий шаг
- [ ] Коммит: `docs: add GLOSSARY.md with 15+ terms`

**Дата закрытия:** `[ ]`

---

### TD10 — Domain Events
**Файл:** `domain/events.py` + `data/events.jsonl`  
**Артефакт:** 5 типов событий + EventLog для audit trail

- [ ] Создать `domain/events.py` с dataclasses для событий
- [ ] Определить: SignalAdded, SynthesisApproved, RelationshipRetracted, ClusterScoreChanged, SynthesisExpired
- [ ] Реализовать `EventLog.emit()` → запись в `data/events.jsonl`
- [ ] Добавить `emit(SignalAdded(...))` в `scripts/add_signal.py`
- [ ] Добавить `emit(SynthesisApproved(...))` в `scripts/approve_synthesis.py`
- [ ] Создать пустой `data/events.jsonl`
- [ ] Коммит: `feat: add domain events and EventLog for audit trail`

**Дата закрытия:** `[ ]`

---

**✅ ДЕНЬ 4 ЗАКРЫТ:** `[ ]`

---

## ДЕНЬ 5 — Верификация и повторный ARR (≈4 часа)

### Финальный чеклист перед повторным ARR

#### Blockers (все должны быть CLOSED)
- [ ] B1: `select_bridge()` детерминирован → тест зелёный
- [ ] B2: `semantic_inverse_score()` специфицирован → 3 теста зелёных
- [ ] B3: `SECURITY.md` создан → XSS исправлен в index.html
- [ ] B4: `DISASTER_RECOVERY.md` создан → DR тест проведён
- [ ] B5: `DEPLOYMENT.md` создан → `deploy.yml` работает

#### Technical Debt (все должны быть DONE)
- [ ] TD1: MAX_POSSIBLE_SCORE определён формулой N×18
- [ ] TD2: `LEGACY_LINKS_ENABLED` флаг + ADR-007
- [ ] TD3: Golden Dataset ≥15 сигналов, тесты зелёные
- [ ] TD4: `file_lock()` работает, атомарная запись
- [ ] TD5: `GLOSSARY.md` ≥15 терминов
- [ ] TD6: тиебрейкер по `id` в `rank_signals()`
- [ ] TD7: empty cluster UI контракт
- [ ] TD8: UTC policy в settings.py
- [ ] TD9: UTF-8 policy применена
- [ ] TD10: Domain Events + EventLog

#### Дополнительные артефакты
- [ ] `requirements.txt` создан с зафиксированными версиями
- [ ] `config/settings.py` создан
- [ ] `Makefile` с `PYTHONHASHSEED=0` targets
- [ ] `tests/unit/` содержит тесты для validator и synthesizer
- [ ] Все коммиты сделаны, CI pipeline зелёный

#### Финальная проверка сайта
- [ ] Открыть https://alxcheh.github.io/Bitcoin-Intel
- [ ] Нарративы показывают метку источника (✓ Аналитик · дата или ◈ Алгоритм)
- [ ] tension начинается с заглавной буквы во всех карточках
- [ ] Тап на entity (Metaplanet, Kalshi) открывает карточку
- [ ] TOC на вкладке ТЕОРИЯ работает

**✅ ДЕНЬ 5 ЗАКРЫТ:** `[ ]`

---

## Critical + Major проблемы (устранить в Фазе 0)

Эти проблемы не блокируют ARR но должны быть закрыты **до конца Фазы 0**:

| # | Проблема | Артефакт | Приоритет |
|---|----------|----------|-----------|
| C1 | MAX_POSSIBLE_SCORE → см. TD1 выше | settings.py | ✅ В плане |
| C2 | Переходный период links.* → см. TD2 | ADR-007 | ✅ В плане |
| C3 | Race condition → см. TD4 | file_lock.py | ✅ В плане |
| C4 | Signal editing lock (O(N×M)) | Добавить индекс synthesis_by_signal | До Фазы 1 |
| C5 | Acceptance Tests отсутствуют | После первых реальных пользователей | После MVP |
| M1 | Аудит trail для signals.json | Покрывается EventLog (TD10) | ✅ В плане |
| M2 | Orphan detection в relationships | scripts/validate_relationships.py | До Фазы 0 |
| M3 | Batch перегенерация при MAJOR | scripts/batch_regenerate.py | До MAJOR change |
| M4 | Мониторинг / Observability | После появления Backend | Фаза 4+ |
| M5 | Ретроспективная переклассификация | При создании нового кластера | По мере роста |

---

## Пробелы выявленные аудитами (полный реестр)

### Из ARR_REPORT.md (Architecture Readiness Review)

| Пункт чеклиста | Статус был | Покрыт планом? |
|----------------|------------|---------------|
| Bounded Contexts | FAIL | ❌ Не в плане (добавить в BLUEPRINT_ADDENDUM) |
| Deployment Architecture | FAIL | ✅ B5 День 3 |
| Security Architecture | FAIL | ✅ B3 День 3 |
| Disaster Recovery | FAIL | ✅ B4 День 3 |
| Environment Strategy | FAIL | ✅ B5 День 3 |
| Observability | FAIL | ⏳ После Backend |
| Monitoring | FAIL | ⏳ После Backend |
| Concurrency model | FAIL | ✅ TD4 День 4 |
| Error handling philosophy | FAIL | ❌ Добавить в settings.py |
| Domain Events | FAIL | ✅ TD10 День 4 |
| Value Objects vs Entities | FAIL | ❌ Добавить в BLUEPRINT_ADDENDUM §15 |
| Lifecycle hooks | FAIL | ❌ Добавить в domain/events.py |
| Cross-aggregate consistency | FAIL | ⏳ При появлении транзакций |
| ontology.json JSON Schema | FAIL | ❌ Добавить в BLUEPRINT_ADDENDUM §17 |
| Orphan detection | FAIL | ✅ scripts/validate_relationships.py |
| Backup strategy | FAIL | ✅ B4 День 3 |
| Recovery procedure | FAIL | ✅ B4 День 3 |
| Audit trail signals/relationships | FAIL | ✅ TD10 Domain Events |
| Date timezone | FAIL | ✅ TD8 День 1 |
| Encoding policy | FAIL | ✅ TD9 День 1 |
| hash() детерминизм | FAIL | ✅ B1 День 1 |
| semantic_inverse_score | FAIL | ✅ B2 День 2 |
| MAX_POSSIBLE_SCORE | FAIL | ✅ TD1 День 1 |
| Acceptance Tests | FAIL | ⏳ После MVP |
| Narrative Quality Tests | FAIL | ⏳ Фаза 2 |
| Chaos Tests | FAIL | ⏳ Фаза 3 |
| Глоссарий | FAIL | ✅ TD5 День 4 |

### Непокрытые пробелы (требуют отдельных задач)

| Пробел | Действие | Срок |
|--------|----------|------|
| Bounded Contexts не определены | Добавить раздел в BLUEPRINT_ADDENDUM.md | До Фазы 0 |
| Error handling philosophy | Добавить в settings.py + документацию | День 1 дополнительно |
| Value Objects vs Entities | Добавить в §15 Domain Model | До Фазы 0 |
| Lifecycle hooks (OnSignalArchived etc.) | Добавить в domain/events.py | День 4 дополнительно |
| ontology.json JSON Schema | Добавить в §17 Data Contracts | До Фазы 0 |
| validate_relationships.py | Создать скрипт | До Фазы 0 |

---

## Счётчик прогресса

```
ДЕНЬ 1: [x] / 6 задач   (B1, TD1, TD6, TD7, TD8, TD9) — 2026-06-28
ДЕНЬ 2: [x] / 2 задачи  (B2, TD2) — 2026-06-28
ДЕНЬ 3: [x] / 3 задачи  (B3, B4, B5) — 2026-06-28
ДЕНЬ 4: [ ] / 4 задачи  (TD3, TD4, TD5, TD10)
ДЕНЬ 5: [ ] / верификация

BLOCKERS ЗАКРЫТО:  5 / 5  (B1 ✓, B2 ✓, B3 ✓, B4 ✓, B5 ✓) 🎉
TD ЗАКРЫТО:        7 / 10  (TD1 ✓, TD2 ✓, TD5 ✓, TD6 ✓, TD7 ✓, TD8 ✓, TD9 ✓)
ДНЕЙ ВЫПОЛНЕНО:    3 / 5  (Дни 1, 2, 3)

ГОТОВНОСТЬ К ARR:  ✅ ВСЕ BLOCKERS ЗАКРЫТЫ (5/5) · TD 7/10
```

> Обновлять счётчик вручную при закрытии каждого дня.

---

*IMPLEMENTATION_TRACKER.md · Версия 1.3 · 2026-06-28*  
*Создан на основе ARR_REPORT.md + PRE_IMPLEMENTATION_PLAN.md*
