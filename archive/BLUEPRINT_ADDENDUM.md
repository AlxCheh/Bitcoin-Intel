# BLUEPRINT ADDENDUM — Implementation Specification
## Bitcoin Intel · Версия 1.0 · 2026-06-28
## Дополнение к BLUEPRINT.md · Final Architecture Readiness Review

> **Статус:** Implementation-ready specification  
> **Основание:** Final Architecture Readiness Review  
> **Назначение:** Дополнить Blueprint до уровня полной технической спецификации  
> **Ограничение:** Этот документ только дополняет BLUEPRINT.md — не заменяет и не изменяет его

---

## Раздел 15. Domain Model

### 15.1 Signal

**Назначение:** атомарная единица знания — зафиксированный факт или событие Bitcoin-экосистемы с аналитической интерпретацией  
**Владелец:** аналитик (создание и редактирование до первого утверждённого синтеза)  
**Жизненный цикл:** `draft → active → archived`

```
draft    — создан, не прошёл валидацию или ожидает дополнения
active   — валиден, участвует в синтезе
archived — старше 180 дней или помечен вручную; не участвует в синтезе
```

**Обязательные поля:**

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | string | Формат: `PREFIX-YYYY-MMDD-NNN` |
| `date` | date | Дата события (не добавления) |
| `signal` | string | Заголовок — факт без интерпретации |
| `tension` | string | Противоречие по формуле «X vs Y» с заглавной буквы |
| `macro_implication` | string | Структурный вывод для Bitcoin |
| `narrative_role` | enum | trigger / complication / resolution / background |
| `cluster` | string | ID кластера из ontology |
| `theme` | enum | supply / institutionalization / infrastructure / macro / narrative |
| `weight` | enum | onchain / primary / market / media |
| `dir` | enum | pos / neg / neu |
| `horizon` | enum | short / mid / long |
| `cat` | enum | onchain / ta / macro / mining / narrative / layer2 / ownership |
| `source` | string | Название источника и дата |

**Необязательные поля:**

| Поле | Тип | Описание |
|------|-----|----------|
| `data` | string[] | Список конкретных метрик и фактов |
| `context` | string | Исторический контекст и аналогии |
| `caveat` | string | Ограничения интерпретации |
| `actor` | enum | etf / corporate / government / defi / retail / miner |
| `flow` | enum | inflow / outflow / internal / neutral |
| `confidence` | float | 0.0–1.0; уверенность аналитика в интерпретации |
| `source_url` | string | Прямая ссылка на первоисточник |
| `links` | object | `{confirms, contradicts, context_chain}` — устаревает, переносится в relationships.json |

**Вычисляемые поля (не хранятся, вычисляются при запросе):**

| Поле | Формула |
|------|---------|
| `age_days` | `today - date` |
| `freshness_score` | `3 if age≤7 else 1 if age≤30 else 0` |
| `weight_score` | `{onchain:4, primary:3, market:2, media:1}[weight]` |
| `role_score` | `{trigger:4, complication:3, resolution:2, background:0}[narrative_role]` |
| `status` | `archived if age>180 else active` |

**Инварианты:**
- `id` уникален в пределах всей базы навсегда
- `date` не в будущем
- `tension` начинается с заглавной буквы
- `tension` содержит «vs», «несмотря на», «при условии» или «—»
- `cluster` существует в `ontology.json`
- Сигнал в статусе `archived` не может стать `active` повторно

**Допустимые операции:**
- `create` — только аналитик
- `update` — только до первого утверждённого синтеза использующего этот сигнал
- `archive` — аналитик или автоматически по возрасту
- `read` — все компоненты системы

---

### 15.2 Entity

**Назначение:** именованная сущность Bitcoin-экосистемы (компания, протокол, фонд, биржа)  
**Владелец:** аналитик  
**Жизненный цикл:** `active → deprecated → archived`

**Обязательные поля:** `id`, `name`, `type`, `status`, `summary`  
**Необязательные поля:** `profile`, `signal_refs`, `last_updated`, `aliases[]`, `external_ids{}`, `confidence`  
**Инварианты:** `id` уникален; `name` уникален в пределах `type`; `signal_refs` содержат только существующие Signal.id

---

### 15.3 Cluster

**Назначение:** нарративный контейнер — группа сигналов объединённых общим структурным процессом  
**Владелец:** аналитик (через ontology.json)  
**Жизненный цикл:** `proposed → active → deprecated → archived`

**Обязательные поля:** `id`, `label`, `description`, `created`  
**Необязательные поля:** `parent`, `deprecated`, `successor`, `signal_count`  
**Инварианты:** `id` уникален и неизменен после создания; deprecated кластер не принимает новых сигналов

---

### 15.4 Relationship

**Назначение:** направленная аналитическая связь между двумя сигналами  
**Владелец:** аналитик (ручное решение после предложения Contradiction Detector)  
**Жизненный цикл:** `proposed → active → retracted`

**Обязательные поля:**

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | string | UUID |
| `from_id` | string | Signal.id источника |
| `to_id` | string | Signal.id цели |
| `type` | enum | confirms / contradicts / context_chain |
| `rationale` | string | Объяснение: ПОЧЕМУ это противоречие/подтверждение |
| `created` | datetime | |
| `created_by` | string | Идентификатор аналитика |

**Инварианты:**
- `from_id ≠ to_id` (нет самосвязей)
- Нет дублирующих пар `(from_id, to_id, type)`
- `contradicts` должен пройти тест: «можно ли одновременно быть правым и A, и B?» → нет
- Ретракция не удаляет запись — добавляет `{retracted: datetime, retracted_by, reason}`

---

### 15.5 Synthesis

**Назначение:** аналитический вывод по кластеру — результат синтеза нескольких сигналов  
**Владелец:** Synthesis Engine (генерация) + аналитик (утверждение)  
**Жизненный цикл:** `generated → reviewed → approved → published → superseded → archived`

**Обязательные поля:**

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | string | `syn-{cluster}-{YYYYMMDD}-{version}` |
| `cluster` | string | Cluster.id |
| `status` | enum | generated / reviewed / approved / published / superseded / archived |
| `version` | int | Монотонно возрастающий в рамках кластера |
| `tension` | string | Главное противоречие кластера |
| `narrative` | string | Синтетический текст (partA + bridge + partB) |
| `takeaway` | string | Одно предложение — главная мысль |
| `strength` | enum | structural / strong / moderate / weak |
| `signals_used` | string[] | Signal.id использованных сигналов |
| `signals_ignored` | string[] | Signal.id игнорированных (в окне, но не вошли) |
| `algorithm_version` | string | Версия synthesizer.py |
| `scoring_version` | string | Версия scoring rules из ontology |
| `ontology_version` | string | Версия ontology.json |
| `window_days` | int | Окно релевантности в днях |
| `computed_at` | datetime | |

**Необязательные поля:** `rationale`, `alternatives_rejected[]`, `confidence`, `causal_chain[]`  
**Вычисляемые поля:** `age_days`, `is_expired` (computed_at + expires_days < today)

---

### 15.6 Approval

**Назначение:** запись об акте утверждения синтеза аналитиком  
**Владелец:** аналитик  

**Обязательные поля:**

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | string | UUID |
| `synthesis_id` | string | Synthesis.id |
| `approved_by` | string | |
| `approved_at` | datetime | |
| `rationale` | string | Почему утверждён именно этот вариант |
| `expires_at` | datetime | Когда синтез требует пересмотра |
| `edits_made` | bool | Были ли внесены правки аналитиком |
| `edits_summary` | string? | Что именно изменено |

---

### 15.7 Ontology

**Назначение:** формальное определение всех концептуальных сущностей системы  
**Владелец:** аналитик (только явные операции с обоснованием)  
**Жизненный цикл:** версионированный; `version` инкрементируется при каждом изменении

**Структура:**
```json
{
  "version": "1.0.0",
  "updated": "2026-06-28",
  "clusters": { },
  "themes": ["supply", "institutionalization", "infrastructure", "macro", "narrative"],
  "roles": ["trigger", "complication", "resolution", "background"],
  "weights": {
    "onchain": 4, "primary": 3, "market": 2, "media": 1
  },
  "scoring_rules": {
    "freshness": {"7": 3, "30": 1},
    "contradiction_bonus": 5,
    "tension_bonus": 2
  }
}
```

**Инварианты:** версия только возрастает; deprecated кластер сохраняется навсегда с датой и причиной

---

### 15.8 Quality Report

**Назначение:** автоматически генерируемый отчёт о состоянии базы знаний  
**Владелец:** система (генерируется автоматически)  
**Периодичность:** при каждом коммите + еженедельно

**Поля:** `generated_at`, `signals_total`, `signals_active`, `signals_archived`, `clusters_without_synthesis[]`, `stale_synthesis[]`, `signals_without_tension[]`, `invalid_relationships[]`, `score_distribution{}`, `recommendations[]`

---

### 15.9 Algorithm Version

**Назначение:** версия алгоритма синтеза — необходима для воспроизводимости  
**Хранится в:** каждом Synthesis объекте + `synthesizer.py` как константа

```python
ALGORITHM_VERSION = "2.1.0"  # MAJOR.MINOR.PATCH
# MAJOR — breaking change в логике синтеза
# MINOR — новые правила без изменения существующих
# PATCH — bugfix
```

---

## Раздел 16. ER Model

### 16.1 Полная схема связей

```
Signal ──────────────────────── Cluster
  │  N:1 (каждый сигнал          │
  │  принадлежит одному          │ 1:N
  │  кластеру)                   │
  │                           Synthesis
  │ N:M (через Relationship)     │ N:1
  │                           Approval
  │
  ├── N:M ── Entity
  │   (через signal_refs в Entity)
  │
  └── N:M ── Signal
      (через Relationship)

Cluster ── 1:1 ── Ontology.clusters entry
Cluster ── 1:N ── Synthesis
Cluster ── 1:N ── Signal

Synthesis ── 1:1 ── Approval (при status=approved)
Synthesis ── N:M ── Signal (через signals_used[])

Ontology ── 1:N ── Cluster
Ontology ── 1:1 ── Algorithm Version (scoring_rules)

Quality Report ── читает все сущности (нет ownership)
```

### 16.2 Aggregate Roots

**Aggregate Root: Signal**
- Владеет: своими полями
- НЕ владеет: Relationship (вынесен отдельно)
- Граница: Signal изменяется независимо от связей

**Aggregate Root: Cluster**  
- Владеет: метаданными кластера в ontology
- НЕ владеет: сигналами (они ссылаются на кластер, не наоборот)

**Aggregate Root: Synthesis**
- Владеет: Approval (Approval не существует без Synthesis)
- НЕ владеет: сигналами (только ссылки)

**Aggregate Root: Ontology**
- Владеет: всеми определениями кластеров, тем, весов
- Единственный; изменяется только явно

---

## Раздел 17. Data Contracts

### 17.1 Signal Schema (JSON Schema)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "$id": "https://bitcoin-intel/schemas/signal/v1.json",
  "title": "Signal",
  "type": "object",
  "required": [
    "id", "date", "signal", "tension", "macro_implication",
    "narrative_role", "cluster", "theme", "weight", "dir",
    "horizon", "cat", "catLabel", "source"
  ],
  "additionalProperties": false,
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^(STR|SUP|INF|MAC|NAR)-\\d{4}-\\d{4}-\\d{3}$",
      "readOnly": true,
      "description": "Уникальный идентификатор. Формат: PREFIX-YYYY-MMDD-NNN"
    },
    "date": {
      "type": "string",
      "format": "date",
      "description": "Дата события (не добавления)"
    },
    "signal": {
      "type": "string",
      "minLength": 20,
      "maxLength": 300,
      "description": "Заголовок сигнала — факт без интерпретации"
    },
    "tension": {
      "type": "string",
      "minLength": 30,
      "pattern": "^[А-ЯA-Z]",
      "description": "Начинается с заглавной. Содержит vs/несмотря на/при условии"
    },
    "macro_implication": {
      "type": "string",
      "minLength": 40,
      "description": "Структурный вывод — что изменилось для Bitcoin"
    },
    "narrative_role": {
      "type": "string",
      "enum": ["trigger", "complication", "resolution", "background"]
    },
    "cluster": {
      "type": "string",
      "description": "Должен существовать в ontology.clusters"
    },
    "theme": {
      "type": "string",
      "enum": ["supply", "institutionalization", "infrastructure", "macro", "narrative"]
    },
    "weight": {
      "type": "string",
      "enum": ["onchain", "primary", "market", "media"]
    },
    "dir": {
      "type": "string",
      "enum": ["pos", "neg", "neu"]
    },
    "horizon": {
      "type": "string",
      "enum": ["short", "mid", "long"]
    },
    "cat": {
      "type": "string",
      "enum": ["onchain", "ta", "macro", "mining", "narrative", "layer2", "ownership"]
    },
    "catLabel": {
      "type": "string",
      "description": "Human-readable метка категории с emoji"
    },
    "source": {
      "type": "string",
      "minLength": 5,
      "description": "Название источника и месяц/год"
    },
    "data": {
      "type": "array",
      "items": {"type": "string"},
      "nullable": true
    },
    "context": {
      "type": "string",
      "nullable": true
    },
    "caveat": {
      "type": "string",
      "nullable": true
    },
    "actor": {
      "type": "string",
      "enum": ["etf", "corporate", "government", "defi", "retail", "miner"],
      "nullable": true
    },
    "flow": {
      "type": "string",
      "enum": ["inflow", "outflow", "internal", "neutral"],
      "nullable": true
    },
    "confidence": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "nullable": true,
      "description": "Уверенность аналитика в интерпретации"
    },
    "source_url": {
      "type": "string",
      "format": "uri",
      "nullable": true
    },
    "links": {
      "type": "object",
      "description": "DEPRECATED — переносится в relationships.json",
      "properties": {
        "confirms": {"type": "array", "items": {"type": "string"}},
        "contradicts": {"type": "array", "items": {"type": "string"}},
        "context_chain": {"type": "array", "items": {"type": "string"}}
      },
      "nullable": true
    }
  }
}
```

### 17.2 Relationship Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "$id": "https://bitcoin-intel/schemas/relationship/v1.json",
  "title": "Relationship",
  "type": "object",
  "required": ["id", "from_id", "to_id", "type", "rationale", "created", "created_by"],
  "properties": {
    "id": {"type": "string", "format": "uuid", "readOnly": true},
    "from_id": {"type": "string", "pattern": "^(STR|SUP|INF|MAC|NAR)-"},
    "to_id": {"type": "string", "pattern": "^(STR|SUP|INF|MAC|NAR)-"},
    "type": {"type": "string", "enum": ["confirms", "contradicts", "context_chain"]},
    "rationale": {"type": "string", "minLength": 20,
      "description": "Объяснение почему это отношение реально"},
    "created": {"type": "string", "format": "date-time", "readOnly": true},
    "created_by": {"type": "string"},
    "retracted": {"type": "string", "format": "date-time", "nullable": true},
    "retracted_by": {"type": "string", "nullable": true},
    "retraction_reason": {"type": "string", "nullable": true}
  }
}
```

### 17.3 Synthesis Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "$id": "https://bitcoin-intel/schemas/synthesis/v1.json",
  "title": "Synthesis",
  "type": "object",
  "required": [
    "id", "cluster", "status", "version", "tension", "narrative",
    "takeaway", "strength", "signals_used", "algorithm_version",
    "ontology_version", "window_days", "computed_at"
  ],
  "properties": {
    "id": {"type": "string", "readOnly": true,
      "pattern": "^syn-[a-z_]+-\\d{8}-\\d{3}$"},
    "cluster": {"type": "string"},
    "status": {"type": "string",
      "enum": ["generated", "reviewed", "approved", "published", "superseded", "archived"]},
    "version": {"type": "integer", "minimum": 1, "readOnly": true},
    "tension": {"type": "string", "minLength": 30,
      "pattern": "^[А-ЯA-Z]"},
    "narrative": {"type": "string", "minLength": 50},
    "takeaway": {"type": "string", "minLength": 20},
    "strength": {"type": "string",
      "enum": ["structural", "strong", "moderate", "weak"]},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1, "nullable": true},
    "signals_used": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "signals_ignored": {"type": "array", "items": {"type": "string"}},
    "algorithm_version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
    "scoring_version": {"type": "string"},
    "ontology_version": {"type": "string"},
    "window_days": {"type": "integer", "default": 90},
    "computed_at": {"type": "string", "format": "date-time", "readOnly": true},
    "rationale": {"type": "string", "nullable": true},
    "alternatives_rejected": {"type": "array", "items": {"type": "string"}, "nullable": true},
    "causal_chain": {"type": "array", "items": {"type": "string"}, "nullable": true},
    "expires_at": {"type": "string", "format": "date-time", "nullable": true},
    "superseded_by": {"type": "string", "nullable": true}
  }
}
```

### 17.4 Versioning Policy

```
signals/v1.json     → текущая (stable)
relationships/v1.json → текущая (stable)
synthesis/v1.json   → текущая (stable)

При breaking change:
  - Создаётся новая версия схемы: /v2.json
  - Старая версия помечается deprecated, не удаляется
  - Период поддержки: минимум 180 дней после deprecation
  - Миграционный скрипт: migration/v1_to_v2.py
```

---

## Раздел 18. Component Contracts

### 18.1 validator.py

```python
# Вход
def validate_signal(raw: dict, ontology: Ontology) -> ValidationResult

# Выход
@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationWarning]  # не блокируют, но логируются
    normalized: dict | None  # None если невалиден

# Ошибки
class ValidationError:
    field: str
    code: str  # MISSING_FIELD, INVALID_FORMAT, UNKNOWN_CLUSTER, etc.
    message: str

# Гарантии
# - Детерминирован: одни входные данные → один результат
# - Идемпотентен: многократный вызов не имеет побочных эффектов
# - Не пишет в хранилище
# - Не делает сетевых запросов
# - Завершается за O(1) — не зависит от размера базы

# Коды ошибок
VALIDATION_ERRORS = {
    "MISSING_FIELD": "Обязательное поле отсутствует",
    "INVALID_ID_FORMAT": "ID не соответствует формату PREFIX-YYYY-MMDD-NNN",
    "DUPLICATE_ID": "ID уже существует в базе",
    "FUTURE_DATE": "Дата события в будущем",
    "UNKNOWN_CLUSTER": "Кластер не найден в ontology",
    "TENSION_NO_CAPITAL": "Tension не начинается с заглавной буквы",
    "TENSION_NO_FORMULA": "Tension не содержит vs/несмотря на/при условии",
    "INVALID_ENUM": "Значение не входит в допустимый набор",
    "DEPRECATED_CLUSTER": "Кластер помечен как deprecated",
}
```

### 18.2 synthesizer.py

```python
# Вход
def synthesize(
    cluster: str,
    signals: list[Signal],
    relationships: list[Relationship],
    ontology: Ontology,
    window_days: int = 90,
    algorithm_version: str = ALGORITHM_VERSION
) -> SynthesisResult

# Выход — см. SynthesisResult в BLUEPRINT.md §2.8

# Гарантии
# - Детерминирован: при одинаковых входных данных → одинаковый результат
# - Идемпотентен
# - Не пишет в хранилище (только возвращает результат)
# - При пустом списке сигналов возвращает SynthesisResult с пустыми полями
#   и strength="weak", не бросает исключение
# - При ошибке в отдельном сигнале — пропускает его, логирует warning

# Исключения (только при системных ошибках)
# SynthesizerConfigError — невалидная онтология
# SynthesizerVersionError — несовместимая версия

# Побочные эффекты: только логирование (не влияет на результат)
```

### 18.3 contradiction_detector.py

```python
# Вход
def detect(
    new_signal: Signal,
    existing_signals: list[Signal],
    existing_relationships: list[Relationship]
) -> list[ContraCandidate]

@dataclass
class ContraCandidate:
    signal_id: str
    score: float         # 0.0–1.0
    reason: str          # человекочитаемое объяснение
    inverse_terms: list[str]  # ключевые инвертированные термины
    already_related: bool     # уже есть связь между ними

# Гарантии
# - Возвращает максимум 3 кандидата
# - Score выше 0.6 считается значимым
# - Кандидаты отсортированы по score DESC
# - Не добавляет связи автоматически — только предлагает
# - Детерминирован

# НЕ является источником правды о противоречиях
# Финальное решение всегда за аналитиком
```

### 18.4 synthesis_cache_builder.py

```python
# Вход
def build_cache(
    synthesis_store_path: str,
    output_path: str = "synthesis_cache.json"
) -> BuildResult

# Действие: читает synthesis_store/, находит последний approved синтез
# каждого кластера, записывает в synthesis_cache.json

# Гарантии
# - Идемпотентен: многократный вызов не меняет результат
# - Атомарен: пишет во временный файл, потом переименовывает
# - Не теряет данные: если ни одного approved нет — cluster отсутствует
#   в cache (не падает)

# Ошибки
# CacheBuilderError — если synthesis_store не существует
```

---

## Раздел 19. API Contracts (будущий Backend)

```yaml
openapi: "3.0.0"
info:
  title: Bitcoin Intel Narrative API
  version: "1.0.0"

paths:

  /signals:
    get:
      summary: Список сигналов с фильтрацией
      parameters:
        - name: cluster
          in: query
          schema: {type: string}
        - name: date_from
          in: query
          schema: {type: string, format: date}
        - name: date_to
          in: query
          schema: {type: string, format: date}
        - name: narrative_role
          in: query
          schema: {type: string, enum: [trigger,complication,resolution,background]}
        - name: window_days
          in: query
          schema: {type: integer, default: 90}
        - name: include_archived
          in: query
          schema: {type: boolean, default: false}
      responses:
        "200":
          description: Список сигналов
          content:
            application/json:
              schema:
                type: object
                properties:
                  signals: {type: array, items: {$ref: "#/components/schemas/Signal"}}
                  total: {type: integer}
                  filtered: {type: integer}

    post:
      summary: Добавить сигнал
      requestBody:
        required: true
        content:
          application/json:
            schema: {$ref: "#/components/schemas/SignalCreate"}
      responses:
        "201":
          description: Сигнал создан
          content:
            application/json:
              schema: {$ref: "#/components/schemas/Signal"}
        "422":
          description: Ошибка валидации
          content:
            application/json:
              schema: {$ref: "#/components/schemas/ValidationErrors"}

  /signals/{id}:
    get:
      summary: Получить сигнал по ID
      responses:
        "200": {description: Сигнал}
        "404": {description: Не найден}

    patch:
      summary: Обновить поля сигнала (только до первого approved синтеза)
      responses:
        "200": {description: Обновлён}
        "409": {description: Сигнал заблокирован approved синтезом}

  /signals/{id}/contradictions:
    get:
      summary: Получить предложения от Contradiction Detector
      responses:
        "200":
          content:
            application/json:
              schema:
                type: array
                items: {$ref: "#/components/schemas/ContraCandidate"}

  /relationships:
    get:
      summary: Список связей
      parameters:
        - name: signal_id
          in: query
          description: Все связи где signal_id участвует (from или to)
          schema: {type: string}
        - name: type
          in: query
          schema: {type: string, enum: [confirms, contradicts, context_chain]}
    post:
      summary: Создать связь
      requestBody:
        required: true
        content:
          application/json:
            schema: {$ref: "#/components/schemas/RelationshipCreate"}
      responses:
        "201": {description: Создана}
        "409": {description: Связь уже существует}
        "422": {description: Не прошла валидацию правила contradicts}

  /relationships/{id}/retract:
    post:
      summary: Ретрактовать связь (не удалять)
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [reason]
              properties:
                reason: {type: string}
      responses:
        "200": {description: Ретрактована}

  /synthesis/{cluster}:
    get:
      summary: Актуальный утверждённый синтез кластера
      responses:
        "200":
          content:
            application/json:
              schema: {$ref: "#/components/schemas/Synthesis"}
        "404": {description: Нет утверждённого синтеза}

  /synthesis/{cluster}/generate:
    post:
      summary: Сгенерировать новый черновик синтеза
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                window_days: {type: integer, default: 90}
      responses:
        "200":
          content:
            application/json:
              schema: {$ref: "#/components/schemas/Synthesis"}

  /synthesis/{cluster}/approve:
    post:
      summary: Утвердить черновик синтеза
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [synthesis_id, rationale, expires_at]
              properties:
                synthesis_id: {type: string}
                rationale: {type: string}
                expires_at: {type: string, format: date-time}
                edits: {type: object, nullable: true,
                  properties: {
                    tension: {type: string},
                    narrative: {type: string},
                    takeaway: {type: string}
                  }}
      responses:
        "200": {description: Утверждён}
        "409": {description: Уже есть более свежий approved синтез}

  /synthesis/{cluster}/history:
    get:
      summary: История всех синтезов кластера
      parameters:
        - name: from
          in: query
          schema: {type: string, format: date}
        - name: to
          in: query
          schema: {type: string, format: date}
      responses:
        "200":
          content:
            application/json:
              schema:
                type: array
                items: {$ref: "#/components/schemas/Synthesis"}

  /synthesis/compare:
    post:
      summary: Сравнить два синтеза
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [synthesis_id_a, synthesis_id_b]
              properties:
                synthesis_id_a: {type: string}
                synthesis_id_b: {type: string}
      responses:
        "200":
          content:
            application/json:
              schema: {$ref: "#/components/schemas/SynthesisDiff"}

  /quality/report:
    get:
      summary: Отчёт о качестве базы знаний
      responses:
        "200":
          content:
            application/json:
              schema: {$ref: "#/components/schemas/QualityReport"}

  /ontology:
    get:
      summary: Текущая онтология
      responses:
        "200":
          content:
            application/json:
              schema: {$ref: "#/components/schemas/Ontology"}

  /health:
    get:
      summary: Состояние системы
      responses:
        "200":
          content:
            application/json:
              schema:
                type: object
                properties:
                  status: {type: string, enum: [healthy, degraded, down]}
                  synthesis_cache_age_hours: {type: number}
                  stale_clusters: {type: array, items: {type: string}}
                  signals_count: {type: integer}

  /version:
    get:
      summary: Версии компонентов
      responses:
        "200":
          content:
            application/json:
              schema:
                type: object
                properties:
                  algorithm_version: {type: string}
                  ontology_version: {type: string}
                  schema_version: {type: string}
                  api_version: {type: string}
```

---

## Раздел 20. Sequence Diagrams

### 20.1 Добавление сигнала

```
Аналитик          validator.py      signals.json    contradiction_    relationships.json
                                                    detector.py

    │─── validate(raw) ──────────►│
    │                              │
    │◄── ValidationResult ─────────│
    │    (errors или OK)           │
    │                              │
    │─── write(signal) ────────────────────────────►│
    │                                               │
    │─── detect(signal, existing) ─────────────────────────────────►│
    │                                                                │
    │◄── [candidates] ──────────────────────────────────────────────│
    │
    │─── review candidates (ручной выбор) ─────────────────────────────►
    │
    │─── write(relationship) ──────────────────────────────────────────────────────►│
    │
    [конец — сигнал добавлен, связи установлены]
```

### 20.2 Создание и утверждение синтеза

```
Аналитик     synthesizer.py    signals.json   relationships.json   synthesis_store/   synthesis_cache.json

    │─── synthesize(cluster) ───►│
    │                             │─── get_signals() ─────────────►│
    │                             │◄── signals[] ──────────────────│
    │                             │─── get_relationships() ────────────────────────►│
    │                             │◄── relationships[] ────────────────────────────│
    │                             │
    │                             │ [вычисляет SynthesisResult]
    │◄── SynthesisResult ─────────│
    │    (status: generated)
    │
    │ [проверяет tension, narrative, takeaway]
    │ [вносит правки если нужно]
    │ [заполняет rationale]
    │
    │─── approve(synthesis_id, rationale, expires_at) ────────────────────────────►│
    │                                                                               │ [пишет vN файл]
    │                                                                               │─── rebuild_cache() ────►│
    │                                                                               │                         │ [обновляет]
    │◄── OK ────────────────────────────────────────────────────────────────────────────────────────────────│
```

### 20.3 Fallback при устаревшем синтезе

```
Браузер          synthesis_cache.json    JS Synthesizer    signals.json

    │─── fetch(synthesis_cache.json) ───►│
    │◄── {clusters: {...}} ───────────────│
    │
    │ [проверяет expires_at для каждого кластера]
    │ [strategy_model_stress: expires_at < now → STALE]
    │
    │─── fetch(signals.json) ─────────────────────────────────────►│
    │◄── signals[] ───────────────────────────────────────────────│
    │
    │─── synthesizeAdvanced(cluster, signals) ──────────────────►│
    │◄── SynthesisResult (source: "algo") ───────────────────────│
    │
    │ [рендерит карточку с меткой "◈ Алгоритм · черновик"]
```

### 20.4 Исторический запрос

```
Аналитик     synthesis_store/    history_query.py

    │─── query("strategy_model_stress", on_date="2026-02-01") ──►│
    │                                                              │─── scan synthesis_store/ ───►
    │                                                              │    [находит файлы с cluster=strategy_model_stress]
    │                                                              │    [фильтрует: approved_at <= 2026-02-01 < superseded_at]
    │◄── SynthesisResult (версия на дату) ────────────────────────│
```

---

## Раздел 21. State Machines

### 21.1 Signal State Machine

```
              create (valid)
[new] ──────────────────────► [draft]
                                  │
                    validate OK   │   validate FAIL
                    ┌─────────────┘─────────────────►[invalid]
                    │                                    │
                    ▼                                    │ fix → validate
                [active] ◄───────────────────────────────┘
                    │
                    │ age > 180 days (автоматически)
                    │ ИЛИ archive (вручную)
                    ▼
                [archived]

Переходы:
  new → draft: create()
  draft → active: validate() OK
  draft → invalid: validate() FAIL
  invalid → draft: fix_and_resubmit()
  active → archived: auto (age>180) | manual archive()
  archived → active: ЗАПРЕЩЕНО (необратимо)
```

### 21.2 Synthesis State Machine

```
              synthesize()
[—] ──────────────────────► [generated]
                                  │
                    review        │
                    ┌─────────────┘
                    ▼
                [reviewed]
                    │
          approve() │  reject()
            ┌───────┘──────────────► [rejected]
            ▼                            │
        [approved]                       │ revise → synthesize()
            │                            │
            │ publish()          [generated] ◄───┘
            ▼
        [published]
            │
            │ new version approved
            ▼
        [superseded]
            │
            │ age > 365 days
            ▼
        [archived]

Запрещённые переходы:
  archived → любой (необратимо)
  superseded → approved (нельзя воскресить)
  approved → generated (только вперёд по цепочке)
```

### 21.3 Approval State Machine

```
              create()
[—] ──────────────────────► [pending]
                                 │
                   approve()     │  reject()
              ┌──────────────────┘──────────────► [rejected]
              ▼
          [approved]
              │
              │ expires_at < now
              ▼
          [expired]  ─── renew() ──► [pending]
```

### 21.4 Cluster State Machine

```
              propose()
[—] ──────────────────────► [proposed]
                                 │
                   activate()    │  reject()
              ┌──────────────────┘──────────────► [rejected]
              ▼
           [active]
              │
              │ deprecate(successor, date, reason)
              ▼
          [deprecated] ─── (auto after deprecated date) ──► [archived]

Правила:
  deprecated кластер: принимает сигналы только с датой < deprecated_date
  archived кластер: не принимает новых сигналов; доступен только для чтения
```

---

## Раздел 22. Dependency Rules

### 22.1 Разрешённые зависимости

```
Слои (только вниз по стрелке):

UI (index.html)
  ↓ читает
synthesis_cache.json
  ↓ строится из
synthesis_store/
  ↓ создаётся
synthesizer.py
  ↓ читает
signals.json, relationships.json, ontology.json

validator.py ↓ читает ontology.json
contradiction_detector.py ↓ читает signals.json, relationships.json
```

### 22.2 Запрещённые зависимости

```
ЗАПРЕЩЕНО:
  signals.json → synthesis_store/ (данные не зависят от выводов)
  index.html → signals.json (только через synthesis_cache.json)
  validator.py → synthesis_store/ (валидация не зависит от синтеза)
  synthesizer.py → index.html (логика не зависит от UI)
  synthesis_cache.json → synthesis_store/ напрямую из JS
    (только через автоматический rebuild после approval)
```

### 22.3 Архитектурные границы

```
ГРАНИЦА 1: Data / Processing
  По границе: только через определённые функции (не прямой доступ к файлам)
  signals.json и relationships.json не изменяются Processing слоем напрямую
  Изменения только через validator.py + явную запись аналитиком

ГРАНИЦА 2: Processing / Narrative
  synthesizer.py получает данные через параметры функции
  Не читает файлы напрямую внутри функции synthesize()
  Загрузка данных — ответственность вызывающего кода (CLI скрипта)

ГРАНИЦА 3: Narrative / Delivery
  synthesis_cache.json — единственная точка передачи от Narrative к UI
  UI не знает о synthesizer.py, synthesis_store/, relationships.json
```

---

## Раздел 23. Структура проекта

```
bitcoin-intel/
│
├── data/                          # Хранилище данных (Source of Truth)
│   ├── signals.json               # База сигналов
│   ├── entities/
│   │   └── entities.json          # База сущностей
│   ├── relationships.json         # Граф связей
│   ├── ontology.json              # Онтология (кластеры, правила)
│   ├── synthesis_cache.json       # Актуальный синтез для UI (генерируется)
│   └── synthesis_store/           # История синтезов (append-only)
│       ├── 2026-06-28-strategy_model_stress-v001.json
│       └── ...
│
├── src/                           # Исходный код Python
│   ├── domain/                    # Бизнес-логика (чистая, без зависимостей)
│   │   ├── models.py              # Dataclass: Signal, Synthesis, Relationship, etc.
│   │   ├── ontology.py            # Загрузка и валидация онтологии
│   │   └── scoring.py             # Формулы скоринга (чистые функции)
│   │
│   ├── application/               # Прикладная логика (оркестрирует domain)
│   │   ├── synthesizer.py         # Synthesis Engine — единственная реализация
│   │   ├── validator.py           # Signal Validation
│   │   ├── contradiction_detector.py
│   │   └── cache_builder.py       # Сборка synthesis_cache.json
│   │
│   └── infrastructure/            # Взаимодействие с внешним миром
│       ├── signal_store.py        # Чтение/запись signals.json
│       ├── relationship_store.py  # Чтение/запись relationships.json
│       └── synthesis_store.py     # Чтение/запись synthesis_store/
│
├── scripts/                       # CLI скрипты для аналитика
│   ├── add_signal.py              # Добавить сигнал (валидация + запись)
│   ├── generate_synthesis.py      # Сгенерировать черновик синтеза
│   ├── approve_synthesis.py       # Утвердить синтез
│   ├── qa_report.py               # Отчёт о качестве базы
│   ├── migrate_relationships.py   # Миграция links.* → relationships.json
│   └── rebuild_cache.py           # Пересобрать synthesis_cache.json
│
├── tests/                         # Тесты
│   ├── unit/
│   │   ├── test_validator.py
│   │   ├── test_synthesizer.py
│   │   ├── test_contradiction_detector.py
│   │   └── test_scoring.py
│   ├── integration/
│   │   ├── test_signal_workflow.py
│   │   └── test_synthesis_workflow.py
│   ├── golden/                    # Golden Dataset
│   │   ├── fixtures/              # Эталонные сигналы
│   │   │   └── golden_signals.json
│   │   ├── expected/              # Ожидаемые синтезы
│   │   │   └── golden_synthesis.json
│   │   └── test_golden.py
│   └── regression/
│       └── test_regression.py
│
├── docs/                          # Документация
│   ├── BLUEPRINT.md
│   ├── BLUEPRINT_ADDENDUM.md      # Этот файл
│   ├── ALGORITHM.md
│   ├── SYNTHESIS_ARCHITECTURE.md
│   └── ADR/                       # Архитектурные решения
│       ├── ADR-001-synthesizer-python.md
│       └── ...
│
├── config/
│   └── settings.py                # Константы: WINDOW_DAYS, EXPIRE_DAYS, etc.
│
└── index.html                     # UI (без бизнес-логики синтеза)
```

---

## Раздел 24. Narrative Intelligence Engine Specification

### 24.1 Reasoning Pipeline

```
ВХОДНЫЕ ДАННЫЕ
  └── signals[] (отфильтрованные по кластеру и окну)
  └── relationships[] (граф связей)
  └── ontology (scoring rules, bridges)

ШАГ 1: NOISE FILTERING
  └── Удалить сигналы с age > window_days
  └── Удалить сигналы со status=archived
  └── Снизить вес сигналов с age > 30 дней (freshness decay)

ШАГ 2: SIGNAL IMPORTANCE RANKING
  └── Вычислить importance_score для каждого сигнала:
      importance = freshness_score + weight_score + role_score + contradiction_bonus
  └── Сортировка по importance DESC

ШАГ 3: PHASE DETECTION
  └── Подсчитать narrative_role distribution
  └── Определить phase: resolution | active | tension | structural

ШАГ 4: EVIDENCE RANKING
  └── triggers    = [s for s if role=trigger], sorted by importance DESC
  └── complications = [s for s if role=complication], sorted by importance DESC
  └── resolutions = [s for s if role=resolution], sorted by importance DESC

ШАГ 5: CONTRADICTION WEIGHTING
  └── Для каждого сигнала: contra_weight = len(contradicts) * 5
  └── Сигналы с высоким contra_weight приоритетны как источник tension
  └── При равном contra_weight: приоритет weight → date

ШАГ 6: TENSION SELECTION
  └── Кандидаты на tension: сигналы с непустым tension + contradicts > 0
  └── Победитель: MAX(contradicts) → MAX(weight) → MAX(date)
  └── Fallback: любой сигнал с непустым tension
  └── Last resort: построить tension из двух macro_implication через " — vs — "

ШАГ 7: CAUSAL CHAIN BUILDING
  └── chain[0] = anchor_trigger.macro_implication (первое предложение)
  └── chain[1] = anchor_complication.macro_implication (если не дублирует chain[0])
  └── chain[2] = anchor_resolution.macro_implication (если есть)
  └── Дедупликация: overlap > 4 слов длиннее 5 символов → пропустить

ШАГ 8: NARRATIVE SYNTHESIS
  └── partA = anchor_trigger.macro_implication.split(". ")[0]
  └── bridge = BRIDGES[phase][hash(len(signals)) % len(BRIDGES[phase])]
  └── partB = best_complication_with_contradicts.macro_implication.split(". ")[0]
  └── narrative = partA + " — " + bridge + " " + partB[0].lower() + partB[1:]

ШАГ 9: TAKEAWAY SELECTION
  └── Кандидаты: [anchor_complication, anchor_trigger, anchor_resolution, top_weight]
  └── Победитель: первый чей macro_implication не дублирует narrative и tension
  └── Обрезается до первого ". " (учитывает числа типа 0.83x)
  └── Fallback: btcImpl (свежий + весомый)

ШАГ 10: STRUCTURAL CHANGE DETECTION
  └── Сравнить фазу с предыдущим синтезом (из synthesis_store)
  └── Если phase изменилась (active → structural или structural → active) →
      добавить флаг phase_change: true в SynthesisResult
  └── Это сигнал аналитику что нарратив принципиально изменился

ШАГ 11: CONFIDENCE CALCULATION
  └── confidence = normalize(score.total / MAX_POSSIBLE_SCORE)
  └── Снижающие факторы:
      - Только один сигнал в кластере → confidence *= 0.5
      - Нет сигналов с contradicts → confidence *= 0.8
      - Все сигналы старше 30 дней → confidence *= 0.7
      - Нет tension у победителя (fallback построен) → confidence *= 0.6
  └── confidence = max(0.1, min(1.0, confidence))

ШАГ 12: EXPLANATION GENERATION
  └── rationale = f"""
        Tension взят из {tension_source_id} (contradicts: {n}, weight: {w})
        partA из {anchor_trigger.id} (trigger, {anchor_trigger.weight})
        partB из {comp_source.id} (complication, contradicts: {n})
        Bridge: '{bridge}' (phase: {phase})
        Проигнорированы: {ignored_ids} (вне окна / дубли / низкий score)
      """
```

### 24.2 Bridge Semantics

Мосты выбираются по фазе кластера — несут семантическую нагрузку:

```python
BRIDGES = {
    "active": [
        "при этом",           # нейтральное добавление
        "однако",             # мягкое противопоставление
        "в то время как",     # параллельные процессы
        "тогда как",          # контраст
    ],
    "tension": [
        "что усугубляется тем что",  # нарастание
        "несмотря на то что",        # парадокс
        "вопреки тому что",          # сопротивление
    ],
    "resolution": [
        "после чего",         # следствие
        "в результате чего",  # вывод
        "что означает что",   # импликация
    ],
    "structural": [
        "на фоне того что",   # контекст
        "в условиях",         # среда
        "в структуре которой",# анализ
    ]
}

# Детерминированный выбор: избегаем random()
def select_bridge(phase: str, seed: int) -> str:
    options = BRIDGES[phase]
    return options[abs(hash(seed)) % len(options)]

# seed = len(signals) — стабилен для одного набора данных
```

### 24.3 Conflict Resolution

При конфликте между сигналами одного кластера:

```
Приоритет разрешения конфликта (по убыванию):
1. resolution > trigger > complication > background
2. При равной роли: MAX(weight)
3. При равном weight: MAX(contradicts)
4. При равном contradicts: MAX(date) — свежее

Исключение для tension selection:
  contradicts → weight → date
  (tension берётся из наиболее противоречивого, не из наиболее свежего)
```

---

## Раздел 25. Deterministic AI

### 25.1 Что должно храниться в каждом Synthesis для воспроизводимости

```json
{
  "reproducibility": {
    "algorithm_version": "2.1.0",
    "ontology_version": "1.2.0",
    "scoring_version": "1.0.0",
    "schema_version": "1.0.0",
    "python_version": "3.12.0",
    "window_days": 90,
    "signals_snapshot": {
      "count": 42,
      "ids": ["STR-2026-0622-003", "STR-2026-0628-001", "..."],
      "hash": "sha256:a3f8d2..."
    },
    "relationships_snapshot": {
      "count": 15,
      "hash": "sha256:b4e9c1..."
    },
    "bridges_used": {
      "phase": "active",
      "bridge": "в то время как",
      "seed": 11
    },
    "computed_at": "2026-06-28T15:30:00Z"
  }
}
```

### 25.2 Процедура воспроизведения

```python
def reproduce_synthesis(synthesis_id: str) -> SynthesisResult:
    """
    Воспроизвести синтез по его ID.
    Должен дать идентичный результат при любых условиях.
    """
    # 1. Загрузить запись синтеза из synthesis_store
    record = synthesis_store.load(synthesis_id)
    r = record["reproducibility"]

    # 2. Проверить версию алгоритма
    if r["algorithm_version"] != ALGORITHM_VERSION:
        raise VersionMismatchError(
            f"Синтез создан алгоритмом v{r['algorithm_version']}, "
            f"текущий v{ALGORITHM_VERSION}"
        )

    # 3. Загрузить точно те же сигналы
    signals = signal_store.load_by_ids(r["signals_snapshot"]["ids"])

    # 4. Верифицировать хэш
    current_hash = compute_hash(signals)
    if current_hash != r["signals_snapshot"]["hash"]:
        raise DataIntegrityError("Сигналы изменились после создания синтеза")

    # 5. Запустить synthesize с теми же параметрами
    return synthesize(
        cluster=record["cluster"],
        signals=signals,
        window_days=r["window_days"]
    )
```

### 25.3 Версионирование алгоритма

```python
# synthesizer.py
ALGORITHM_VERSION = "2.1.0"

# Семантика версий:
# MAJOR (2.x.x) — изменение алгоритма выбора tension или causal chain
#                  → все существующие approved синтезы требуют ревью
# MINOR (x.1.x) — новые мосты, новые scoring modifiers
#                  → рекомендуется ревью для STRUCTURAL кластеров
# PATCH (x.x.1) — bugfix без изменения логики
#                  → ревью не требуется

# При MAJOR изменении:
def check_major_version_change(old_version: str, new_version: str) -> bool:
    return old_version.split(".")[0] != new_version.split(".")[0]

# Если MAJOR изменился → qa_report.py добавляет предупреждение:
# "11 синтезов созданы алгоритмом v1.x.x — рекомендуется перегенерация"
```

---

## Раздел 26. Golden Dataset

### 26.1 Назначение

Golden Dataset — эталонный набор сигналов с известными правильными синтезами. Используется для:
- Регрессионного тестирования при изменении алгоритма
- Верификации после миграции
- Обучения новых аналитиков

### 26.2 Структура

```
tests/golden/
├── fixtures/
│   └── golden_signals.json     # 20-30 эталонных сигналов
├── expected/
│   └── golden_synthesis.json   # Ожидаемые синтезы для каждого кластера
└── test_golden.py
```

### 26.3 Содержание golden_signals.json

Минимум по 4-5 сигналов на каждый кластер, покрывающих все сценарии:
- Кластер только с triggers (нет complication)
- Кластер с contradicts
- Кластер с resolution
- Кластер с сигналами вне окна (проверка filtering)
- Кластер с дублирующимися macro_implication (проверка dedupe)

```json
{
  "meta": {
    "version": "1.0",
    "description": "Эталонный набор для регрессионного тестирования",
    "created": "2026-06-28",
    "signals_count": 25
  },
  "signals": [
    {
      "id": "TEST-2026-0101-001",
      "cluster": "test_cluster_a",
      "narrative_role": "trigger",
      "weight": "primary",
      "tension": "Тест-сигнал A vs тест-сигнал B с известным outcome",
      "macro_implication": "Структурное изменение X происходит вследствие Y",
      "date": "2026-01-01",
      "_golden_note": "Должен быть выбран как anchor_trigger"
    }
  ]
}
```

### 26.4 Содержание golden_synthesis.json

```json
{
  "meta": {
    "algorithm_version": "2.1.0",
    "generated": "2026-06-28"
  },
  "expected": {
    "test_cluster_a": {
      "tension": "Тест-сигнал A vs тест-сигнал B с известным outcome",
      "narrative_starts_with": "Структурное изменение X происходит",
      "takeaway_not_duplicates_narrative": true,
      "strength": "strong",
      "signals_used_contains": ["TEST-2026-0101-001"],
      "phase": "active"
    }
  }
}
```

### 26.5 Автоматическое сравнение

```python
# tests/golden/test_golden.py

def test_golden_synthesis():
    signals = load_golden_signals()
    expected = load_golden_expected()

    for cluster, exp in expected["expected"].items():
        result = synthesize(
            cluster=cluster,
            signals=[s for s in signals if s.cluster == cluster],
            relationships=[],
            ontology=test_ontology()
        )

        # Проверки
        assert result.tension == exp["tension"], \
            f"Tension изменился для {cluster}"

        if "narrative_starts_with" in exp:
            assert result.narrative.startswith(exp["narrative_starts_with"]), \
                f"Narrative изменился для {cluster}"

        assert result.strength == exp["strength"], \
            f"Strength изменился для {cluster}"

        if "signals_used_contains" in exp:
            for sig_id in exp["signals_used_contains"]:
                assert sig_id in result.signals_used, \
                    f"Ожидался {sig_id} в signals_used для {cluster}"

# Запуск: pytest tests/golden/ -v
# Ожидание: все тесты зелёные; при изменении алгоритма — явный fail с diff
```

### 26.6 Правила принятия изменений алгоритма

```
Изменение алгоритма принимается если:
  1. Все golden тесты зелёные (не изменились)
  ИЛИ
  2. Golden тесты изменились + аналитик явно утвердил новые expected значения
     + в CHANGELOG.md добавлена запись с объяснением почему изменение правильное

Изменение НЕ принимается если:
  - Golden тесты красные без явного утверждения аналитиком
  - ALGORITHM_VERSION не обновлён при изменении логики
```

---

## Раздел 27. Testing Strategy

### 27.1 Полная матрица тестов

```
┌──────────────────────────────────────────────────────────────────────┐
│  Тип теста          │ Что проверяет              │ Когда запускать   │
├──────────────────────────────────────────────────────────────────────┤
│ Unit Tests          │ Каждая функция изолированно│ При каждом коммите│
│ Integration Tests   │ Цепочки компонентов        │ При каждом коммите│
│ Contract Tests      │ Схемы JSON                 │ При изменении схем│
│ Golden Tests        │ Эталонные синтезы          │ При изменении algo│
│ Regression Tests    │ Нет откатов качества       │ При каждом коммите│
│ Property-Based Tests│ Инварианты для любых данных│ Ежедневно         │
│ Performance Tests   │ Время на N сигналов        │ Еженедельно       │
│ Mutation Tests      │ Качество самих тестов      │ Ежемесячно        │
└──────────────────────────────────────────────────────────────────────┘
```

### 27.2 Unit Tests

```python
# tests/unit/test_validator.py

def test_tension_must_start_with_capital():
    result = validate_signal({"tension": "маленькая буква vs B"}, ontology)
    assert not result.is_valid
    assert any(e.code == "TENSION_NO_CAPITAL" for e in result.errors)

def test_tension_must_contain_formula():
    result = validate_signal({"tension": "Описание факта без формулы"}, ontology)
    assert not result.is_valid
    assert any(e.code == "TENSION_NO_FORMULA" for e in result.errors)

def test_unknown_cluster_rejected():
    result = validate_signal({"cluster": "nonexistent_cluster"}, ontology)
    assert not result.is_valid

def test_future_date_rejected():
    future = (date.today() + timedelta(days=1)).isoformat()
    result = validate_signal({"date": future}, ontology)
    assert not result.is_valid

# tests/unit/test_synthesizer.py

def test_empty_cluster_returns_weak():
    result = synthesize("empty_cluster", [], [], test_ontology())
    assert result.strength == "weak"
    assert result.narrative == ""

def test_single_trigger_no_bridge():
    """Без complication нет склейки — только partA"""
    result = synthesize("cluster", [make_trigger()], [], test_ontology())
    assert " — " not in result.narrative or result.narrative.count(" — ") == 1

def test_tension_starts_with_capital():
    result = synthesize("cluster", make_signals(), [], test_ontology())
    assert result.tension[0].isupper()

def test_split_preserves_decimals():
    """0.83x не должен обрезаться до 0"""
    signal = make_signal(macro_implication="При дисконте 0.83x модель меняется. Следствие.")
    result = synthesize("cluster", [signal], [], test_ontology())
    assert "0.83x" in result.narrative or "0.83x" in result.takeaway

def test_deterministic_same_input_same_output():
    signals = make_signals(seed=42)
    result1 = synthesize("cluster", signals, [], test_ontology())
    result2 = synthesize("cluster", signals, [], test_ontology())
    assert result1.narrative == result2.narrative
    assert result1.tension == result2.tension

# tests/unit/test_contradiction_detector.py

def test_no_self_contradiction():
    signal = make_signal(id="TEST-001")
    candidates = detect(signal, [signal], [])
    assert all(c.signal_id != "TEST-001" for c in candidates)

def test_max_three_candidates():
    signal = make_signal()
    existing = make_signals(count=10)
    candidates = detect(signal, existing, [])
    assert len(candidates) <= 3

def test_already_related_flagged():
    sig_a = make_signal(id="A")
    sig_b = make_signal(id="B")
    rel = make_relationship(from_id="A", to_id="B", type="contradicts")
    candidates = detect(sig_a, [sig_b], [rel])
    b_candidate = next((c for c in candidates if c.signal_id == "B"), None)
    if b_candidate:
        assert b_candidate.already_related == True
```

### 27.3 Integration Tests

```python
# tests/integration/test_signal_workflow.py

def test_full_signal_ingestion_workflow():
    """От raw сигнала до записи в store"""
    raw = load_fixture("valid_signal.json")

    # 1. Валидация
    result = validate_signal(raw, load_ontology())
    assert result.is_valid

    # 2. Запись
    signal_store.write(result.normalized)

    # 3. Детекция противоречий
    candidates = detect(result.normalized, signal_store.load_all(), load_relationships())
    assert isinstance(candidates, list)

    # 4. Сигнал читается обратно
    loaded = signal_store.load_by_id(raw["id"])
    assert loaded.id == raw["id"]

def test_synthesis_workflow():
    """От сигналов до утверждённого синтеза в cache"""
    # Подготовка
    populate_test_signals(count=5, cluster="test_cluster")

    # Генерация
    result = synthesize("test_cluster", signal_store.load_cluster("test_cluster"),
                        load_relationships(), load_ontology())
    assert result.tension
    assert result.narrative

    # Утверждение
    synthesis_store.write(result, status="approved", rationale="test")

    # Проверка cache
    rebuild_cache()
    cache = load_cache()
    assert "test_cluster" in cache["clusters"]
    assert cache["clusters"]["test_cluster"]["source"] == "approved"
```

### 27.4 Property-Based Tests

```python
# tests/test_properties.py
# Используем Hypothesis

from hypothesis import given, strategies as st

@given(st.lists(st.builds(make_random_signal), min_size=0, max_size=50))
def test_synthesizer_never_crashes(signals):
    """При любом наборе сигналов синтезатор не падает"""
    result = synthesize("cluster", signals, [], test_ontology())
    assert isinstance(result, SynthesisResult)

@given(st.lists(st.builds(make_random_signal), min_size=1, max_size=50))
def test_tension_always_starts_with_capital(signals):
    """Tension всегда начинается с заглавной буквы"""
    result = synthesize("cluster", signals, [], test_ontology())
    if result.tension:
        assert result.tension[0].isupper()

@given(st.lists(st.builds(make_random_signal), min_size=1, max_size=50))
def test_takeaway_does_not_duplicate_narrative(signals):
    """Takeaway не дублирует narrative"""
    result = synthesize("cluster", signals, [], test_ontology())
    if result.takeaway and result.narrative:
        common_words = set(result.takeaway.split()) & set(result.narrative.split())
        long_common = [w for w in common_words if len(w) > 5]
        # Не более 4 длинных общих слов
        assert len(long_common) <= 4
```

### 27.5 Критерии успешного прохождения

```
Обязательные (блокируют merge):
  ✓ Все Unit тесты зелёные
  ✓ Все Integration тесты зелёные
  ✓ Все Contract тесты зелёные (JSON Schema валидны)
  ✓ Все Property тесты зелёные (100 случайных прогонов)

Рекомендуемые (не блокируют, но мониторятся):
  ✓ Golden тесты зелёные (или явно утверждены изменения)
  ✓ Regression тесты зелёные
  ✓ Performance: synthesize(42 signals) < 100ms
```

---

## Раздел 28. Definition of Done (по компонентам)

### 28.1 validator.py

- [ ] Проверяет все обязательные поля из Signal Schema
- [ ] Возвращает код ошибки для каждого нарушения
- [ ] Проверяет формат ID (`PREFIX-YYYY-MMDD-NNN`)
- [ ] Проверяет наличие cluster в ontology
- [ ] Проверяет tension на заглавную букву
- [ ] Проверяет tension на наличие формулы («vs»/«несмотря на»/«при условии»)
- [ ] Проверяет что date не в будущем
- [ ] Проверяет уникальность ID
- [ ] Unit тесты: coverage > 90%
- [ ] Не имеет зависимостей кроме ontology
- [ ] Задокументирован в docs/components/validator.md

### 28.2 synthesizer.py

- [ ] Детерминирован: тест `test_deterministic_same_input_same_output` зелёный
- [ ] Не падает при пустом списке сигналов
- [ ] Не падает при сигналах вне окна (все отфильтрованы)
- [ ] tension всегда начинается с заглавной буквы
- [ ] 0.83x не обрезается (тест `test_split_preserves_decimals` зелёный)
- [ ] takeaway не дублирует narrative (property-based тест зелёный)
- [ ] SynthesisResult содержит signals_ignored (что было пропущено)
- [ ] SynthesisResult содержит rationale
- [ ] SynthesisResult содержит algorithm_version
- [ ] Golden тесты зелёные
- [ ] Unit тесты: coverage > 85%
- [ ] Идентичный результат с предыдущей JS реализацией (верификационный тест)

### 28.3 contradiction_detector.py

- [ ] Возвращает максимум 3 кандидата
- [ ] Кандидаты отсортированы по score DESC
- [ ] already_related флаг корректен
- [ ] Precision > 60% на тестовом датасете из 20 реальных пар
- [ ] НЕ добавляет связи автоматически
- [ ] Unit тесты зелёные

### 28.4 relationships.json (начальная миграция)

- [ ] Все связи из signals.json.links.* перенесены
- [ ] Каждая связь имеет rationale (хотя бы минимальный)
- [ ] Все from_id и to_id существуют в signals.json
- [ ] Нет дублирующих пар (from_id, to_id, type)
- [ ] Скрипт migrate_relationships.py задокументирован

### 28.5 synthesis_store/ (Фаза 1)

- [ ] Создан первый approved синтез для всех 5 активных кластеров
- [ ] Каждый синтез содержит rationale от аналитика
- [ ] synthesis_cache.json сгенерирован из store
- [ ] index.html читает synthesis_cache.json (не synthesis.json)
- [ ] UI показывает метку «✓ Аналитик · дата»
- [ ] rebuild_cache.py атомарен (temp file → rename)

### 28.6 Golden Dataset

- [ ] Минимум 20 сигналов покрывающих все кластеры
- [ ] Минимум 3 тестовых сценария на кластер
- [ ] Ожидаемые синтезы задокументированы и утверждены
- [ ] test_golden.py зелёный на текущем algorithm_version
- [ ] Процедура обновления при изменении алгоритма задокументирована

---

## Раздел 29. Readiness Assessment

### 29.1 Оценка после дополнений

| Критерий | До Addendum | После Addendum | Целевое |
|----------|-------------|----------------|---------|
| Архитектура данных | 4/10 | 8/10 | 9/10 |
| Архитектура синтеза | 5/10 | 8/10 | 9/10 |
| Масштабируемость | 3/10 | 7/10 | 8/10 |
| Поддерживаемость | 4/10 | 8/10 | 8/10 |
| Explainability | 3/10 | 7/10 | 8/10 |
| Надёжность | 5/10 | 7/10 | 8/10 |
| Тестируемость | 2/10 | 8/10 | 9/10 |
| Готовность к разработке | 3/10 | 8/10 | 9/10 |

### 29.2 Что готово к реализации

- ✅ Архитектура данных (Domain Model, ER, Data Contracts)
- ✅ Component Contracts (validator, synthesizer, contradiction_detector)
- ✅ Структура проекта (директории, назначение каждой)
- ✅ Testing Strategy (все типы тестов, критерии)
- ✅ Definition of Done (по каждому компоненту)
- ✅ Narrative Engine Specification (полный pipeline)
- ✅ Deterministic AI (воспроизводимость)
- ✅ Golden Dataset (структура и правила)
- ✅ State Machines (все сущности)
- ✅ API Contracts (для будущего backend)

### 29.3 Оставшиеся пробелы (не блокируют Фазу 0)

**Пробел 1: Мониторинг и алертинг**  
Не описан механизм уведомлений когда synthesis_cache.json устаревает. Рекомендация: добавить простой bash-скрипт `check_staleness.sh` запускаемый по cron или GitHub Actions.

**Пробел 2: Схема ontology.json не версионирована в git semver**  
Ontology меняется — нет автоматической проверки обратной совместимости. Рекомендация: добавить `ontology_validator.py` который проверяет что deprecated кластеры сохранены.

**Пробел 3: Multi-analyst workflow**  
При появлении второго аналитика нет механизма разрешения конфликтов в синтезе. Не блокирует — решается при масштабировании команды.

### 29.4 Финальный вердикт готовности

**Blueprint + Addendum готовы к старту Фазы 0.**

Каждый компонент Фазы 0 имеет:
- Чёткую зону ответственности
- Определённые контракты входа/выхода
- Критерии Definition of Done
- Тестовое покрытие
- Место в структуре проекта

Единственное условие перед стартом: создать `tests/golden/fixtures/golden_signals.json` с минимальным набором эталонных сигналов. Без этого изменения алгоритма будут невозможно верифицировать.

---

*BLUEPRINT_ADDENDUM.md · Версия 1.0 · 2026-06-28*  
*Читать совместно с BLUEPRINT.md*  
*Следующий ревью: после завершения Фазы 0*
