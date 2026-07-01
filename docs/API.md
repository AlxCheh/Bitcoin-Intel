# Bitcoin Intel — API Documentation

> **Версия:** 1.2 · **Обновлено:** 2026-07-01
> **Тип:** Static file API (GitHub Pages) + спецификация Backend POST/GET (Фаза 4)
> **Base URL:** `https://alxcheh.github.io/Bitcoin-Intel`

---

## Обзор

Bitcoin Intel не имеет серверного API. Данные доступны как статические JSON файлы
через GitHub Pages. Все запросы — простые GET без аутентификации.

---

## Endpoints

### GET /signals.json

Полная база сигналов.

**Response:**
```json
{
  "meta": {
    "last_updated": "YYYY-MM-DD"
  },
  "signals": [
    {
      "id": "STR-2026-0628-001",
      "date": "YYYY-MM-DD",
      "signal": "Заголовок сигнала",
      "tension": "X vs Y",
      "macro_implication": "Структурное изменение...",
      "narrative_role": "trigger|complication|resolution|background",
      "cluster": "strategy_model_stress",
      "dir": "pos|neg|neu",
      "weight": "onchain|primary|market|media",
      "confidence": 0.85
    }
  ]
}
```

**Cache-busting:** `?v=<timestamp>` — используется в index.html.

---

### GET /data/synthesis_cache.json

Предвычисленный Python-синтез нарративов. Обновляется автоматически при каждом push в main.

**Response:**
```json
{
  "strategy_model_stress": {
    "tension": "X vs Y",
    "narrative": "Нарратив кластера...",
    "takeaway": "Ключевой вывод",
    "strength": "strong|moderate|weak",
    "confidence": 0.95,
    "phase": "active|tension|resolution|structural",
    "score": 113,
    "signal_count": 9,
    "anchor_signal_id": "STR-2026-0620-001",
    "signals_used": ["STR-2026-0620-001", "..."],
    "generated_at": "2026-06-29T14:21:08Z"
  }
}
```

**Freshness:** обновляется в CI (~60 сек после push в main).

---

### GET /ENTITIES.json

База артефактов: L2, протоколы, компании, фонды.

```json
[
  {
    "id": "stacks",
    "name": "Stacks",
    "type": "l2|protocol|corporate|fund|infrastructure|exchange",
    "status": "active|closed|pending",
    "summary": "Краткое описание",
    "signal_refs": ["INF-2026-0609-001"]
  }
]
```

---

## Аутентификация (GET, текущая фаза)

На текущем этапе (GitHub Pages, Фаза 0–2) GET-эндпоинты выше — **отсутствует**.
Все они публичны, статичны, без записи.

---

## Backend API (Фаза 4) — POST-эндпоинты

> **Статус:** Спецификация (Condition 4 ARR v2 / ARR v3, M5). Backend ещё не
> реализован — эти эндпоинты являются HTTP-обёрткой вокруг уже существующей
> и протестированной бизнес-логики (`domain/`, `scripts/add_signal.py`,
> `scripts/approve_synthesis.py`), а не новым дизайном с нуля. Реализация
> Backend-сервера — отдельная задача; эта спецификация фиксирует контракт
> ДО начала её реализации, чтобы команда не проектировала схемы по ходу дела.

### Аутентификация (POST, Фаза 4)

**Механизм:** статический API key через заголовок `Authorization: Bearer <key>`.

Выбран намеренно простой механизм, а не OAuth/JWT — соответствует
архитектурному принципу проекта (см. ADR-009, ADR-011: явно избегать
избыточной сложности там, где задача её не требует). Ожидаемое число
пользователей на момент Фазы 4 — один или несколько аналитиков с прямым
доверием, не публичная многопользовательская система. Полноценный
auth/authz (JWT/OAuth, роли) явно вынесен в Technical Debt After MVP — см.
ARR_REPORT_v3.md.

Ключ хранится в переменной окружения сервера (`BITCOIN_INTEL_API_KEY`),
никогда не в коде или в `signals.json` — см. `SECURITY.md` T3 (Secrets
management). Ключ передаётся аналитику вне системы (не по email/Slack в
открытом виде).

Запрос без валидного ключа → `401 Unauthorized` для ВСЕХ POST-эндпоинтов
ниже, до какой-либо обработки тела запроса.

### Коды ошибок (общие для всех POST-эндпоинтов)

| HTTP | Когда | Тело ответа |
|------|-------|-------------|
| `200 OK` | Успех | см. конкретный эндпоинт |
| `400 Bad Request` | Тело запроса — невалидный JSON, либо отсутствует обязательное поле верхнего уровня | `{"error": "bad_request", "message": "..."}` |
| `401 Unauthorized` | Отсутствует или неверный `Authorization: Bearer` | `{"error": "unauthorized", "message": "Invalid or missing API key"}` |
| `404 Not Found` | Путь ссылается на несуществующую сущность (`{id}` в URL) | `{"error": "not_found", "message": "..."}` |
| `409 Conflict` | `DuplicateSignalError` / `DuplicateRelationshipError` (domain/exceptions.py) | `{"error": "conflict", "message": "...", "existing_id": "..."}` |
| `422 Unprocessable Entity` | `ValidationError`, `MissingRequiredFieldError`, `InvalidSignalIdError`, `ForbiddenStateTransitionError` (бизнес-правило нарушено, JSON синтаксически валиден) | `{"error": "validation_error", "field": "...", "reason": "..."}` |
| `500 Internal Server Error` | Необработанное исключение, `CorruptedFileError`, `DataIntegrityError` | `{"error": "internal_error", "message": "..."}` (без stack trace в ответе — логируется на сервере, см. `infrastructure/logger.py`) |

Таблица — прямое отражение `ERROR_EXIT_CODES` и иерархии исключений в
`domain/exceptions.py`: `1` (business_logic_error) → `409`/`422` в
зависимости от типа; `2` (system_error) → `500`; `3` (data_integrity_error)
→ `500` с пометкой `data_integrity` в логе сервера (не в ответе клиенту —
не раскрывать внутреннее состояние хранилища).

### GET /api/v1/signals

> **IRP v1 Wave 3 / D01 (2026-07-01):** этот эндпоинт был определён в
> `docs/BLUEPRINT_ADDENDUM.md` §19 (OpenAPI), но не был отражён здесь —
> `docs/API.md` до этой правки документировал для Backend-фазы только
> POST-эндпоинты, хотя GET существовал в спецификации с самого начала.

Список сигналов с фильтрацией и **пагинацией**. HTTP-обёртка вокруг чтения
`signals.json` (в Backend-фазе — предположительно БД, но контракт тот же).

**Query-параметры фильтрации:** `cluster`, `date_from`, `date_to`,
`narrative_role`, `window_days` (default `90`), `include_archived` (default
`false`) — без изменений от исходной спецификации §19.

**Query-параметры пагинации (новое, D01):**

| Параметр | Тип | По умолчанию | Диапазон |
|----------|-----|--------------|----------|
| `limit` | integer | `50` | `1`–`200` |
| `offset` | integer | `0` | `≥ 0` |

`offset` считается от начала выборки **после** применения всех фильтров
выше (`cluster`/`date_from`/.../`include_archived`), не от полной базы —
иначе смена `date_from` между запросами страницы 1 и страницы 2 незаметно
рвёт постраничный обход.

`limit=50` по умолчанию и максимум `200` — оценка на старте Backend, не
финальное число (тот же принцип, что у Rate Limits ниже: пересмотреть при
первой реальной нагрузке, а не гадать заранее). На 2026-07-01 в
`signals.json` меньше сигналов, чем даже дефолтный `limit`, — пагинация
здесь для будущего роста базы, не для сегодняшнего объёма.

**Response `200 OK`:**
```json
{
  "signals": ["..."],
  "total": 48,
  "filtered": 12,
  "limit": 50,
  "offset": 0,
  "has_more": false
}
```

`total` — все сигналы в базе без учёта фильтров. `filtered` — сколько
прошло фильтры, до применения `limit`/`offset` (сколько всего страниц
можно получить). `signals` — не более `limit` элементов этой страницы.
`has_more = offset + len(signals) < filtered`.

### GET /api/v1/signals/{id}

Один сигнал по `id`. Пагинация не применима (одна запись).

**Response:** `200 OK` с телом сигнала (см. CLAUDE.md полную схему) либо
`404 Not Found`.

### GET /api/v1/signals/{id}/contradictions

Предложения от Contradiction Detector для сигнала. **Пагинация не
применяется** — по контракту `contradiction_detector.py` (§28.3 ADDENDUM)
возвращает максимум 3 кандидата, лимит уже встроен в бизнес-логику, а не
в транспорт.

**Response `200 OK`:** массив кандидатов (максимум 3 элемента).

### GET /api/v1/relationships

Список связей с фильтрацией и той же пагинацией, что `GET /api/v1/signals`
(`limit`/`offset`, те же значения по умолчанию и диапазон).

**Query-параметры фильтрации:** `signal_id` (связи где участвует, from или
to), `type` (`confirms`/`contradicts`/`context_chain`).

**Response `200 OK`:** та же форма, что `GET /api/v1/signals`
(`relationships`/`total`/`filtered`/`limit`/`offset`/`has_more`).

> **Вне scope D01:** `GET /api/v1/synthesis/{cluster}/history` (§19
> ADDENDUM) тоже возвращает список без пагинации, но не входит в эту
> правку — история синтезов ограничена одним кластером и частотой
> ребилдов (не растёт как `signals.json`). Пересмотреть, если появится
> сигнал, что список стал большим (например, частые MAJOR-ребилды).

---

### POST /api/v1/signals

Добавляет новый сигнал. HTTP-обёртка вокруг `scripts/add_signal.py` /
`domain/validator.py::validate_signal()`.

**Request body** — полная схема сигнала (см. CLAUDE.md "Полная схема
объекта сигнала"), `id`/`date`/`source` обязательны, остальные поля по
таблице метаметок CLAUDE.md:

```json
{
  "id": "STR-2026-0701-001",
  "date": "2026-07-01",
  "cat": "ownership",
  "catLabel": "🏛️ ВЛАДЕНИЕ",
  "dir": "neg",
  "horizon": "mid",
  "theme": "institutionalization",
  "weight": "media",
  "actor": "corporate",
  "flow": "outflow",
  "signal": "Заголовок сигнала",
  "data": ["метрика 1"],
  "context": "Исторический контекст.",
  "caveat": "Риски интерпретации.",
  "source": "Источник (месяц год)",
  "links": {"confirms": [], "contradicts": [], "context_chain": []},
  "narrative_role": "complication",
  "cluster": "strategy_model_stress",
  "tension": "X vs Y",
  "macro_implication": "Структурный вывод длиной от 50 символов."
}
```

**Response `201 Created`:**
```json
{
  "id": "STR-2026-0701-001",
  "status": "active",
  "created_at": "2026-07-01T10:00:00Z"
}
```

**Специфичные ошибки:**
- `409 Conflict` — `id` уже существует (`DuplicateSignalError`)
- `422 Unprocessable Entity` — `id` не соответствует `BUSINESS_RULES["signal_id_format"]`
  (`InvalidSignalIdError`), либо `tension`/`macro_implication` не проходят
  правила CLAUDE.md (`tension_must_start_upper`, `macro_implication_min_len`)

### POST /api/v1/syntheses/{id}/approve

Утверждает синтез: `generated → approved` (или `reviewed → approved`).
HTTP-обёртка вокруг `scripts/approve_synthesis.py`.

**Request body:**
```json
{
  "rationale": "Объяснение выбора tension и anchor-сигнала аналитиком"
}
```

`rationale` обязателен и проходит `domain/validator.py::validate_rationale_quality()`
— непустая строка, минимальная содержательность (не "ок"/"да").

**Response `200 OK`:**
```json
{
  "id": "synthesis_strategy_model_stress_20260701_100000",
  "status": "approved",
  "approved_at": "2026-07-01T10:00:00Z",
  "approved_via": "api"
}
```

**Специфичные ошибки:**
- `404 Not Found` — `{id}` не существует в `synthesis_store/`
- `422 Unprocessable Entity` — переход запрещён State Machine
  (`ForbiddenStateTransitionError`, например попытка approve уже
  `archived` синтеза) или `rationale` не прошёл `validate_rationale_quality()`

### POST /api/v1/relationships/{from_id}/retract

Ретрактирует связь (`status: active → retracted`), не удаляет — append-only
принцип (см. `infrastructure/relationship_store.py`).

**Request body:**
```json
{
  "to_id": "STR-2026-0620-003",
  "type": "contradicts",
  "retraction_rationale": "Почему связь больше не верна"
}
```

**Response `200 OK`:**
```json
{
  "from_id": "STR-2026-0701-001",
  "to_id": "STR-2026-0620-003",
  "type": "contradicts",
  "status": "retracted",
  "retracted_at": "2026-07-01T10:00:00Z"
}
```

**Специфичные ошибки:**
- `404 Not Found` — связь с такой парой `(from_id, to_id, type)` не найдена
- `422 Unprocessable Entity` — `retraction_rationale` пустой (см. `validate_relationships.py`
  предупреждение "Retracted without rationale")

### Идемпотентность POST-эндпоинтов

| Эндпоинт | Идемпотентен? |
|----------|----------------|
| `POST /api/v1/signals` | Нет (намеренно — `add_signal.py` не идемпотентен, см. `Idempotency Matrix` в `config/settings.py`; повторный запрос с тем же `id` → `409`, не тихий no-op) |
| `POST /api/v1/syntheses/{id}/approve` | Да — повторный approve уже `approved` синтеза возвращает текущее состояние `200 OK`, не ошибку (State Machine не запрещает оставаться в `approved`, переход не выполняется повторно) |
| `POST /api/v1/relationships/{from_id}/retract` | Да — повторная ретракция уже `retracted` связи возвращает текущее состояние `200 OK` |

---

## Rate Limits

**Текущая фаза (GET, статика):** GitHub Pages — стандартные лимиты CDN.
Рекомендуется кешировать ответы на стороне клиента.

**Backend (Фаза 4, POST):** 60 запросов/мин на API key, скользящее окно.
Превышение → `429 Too Many Requests` с заголовком `Retry-After`. Порог
выбран щедрым относительно ожидаемой нагрузки (один-несколько аналитиков,
не массовый импорт) — задача rate limiting здесь не защита от пиковой
нагрузки, а защита от случайного скрипта-бага, зациклившегося на POST
(например, retry-loop без backoff). Не финальное число — пересмотреть при
первом реальном превышении в production.

---

## Версионирование

**Схема данных:** `SIGNAL_SCHEMA_VERSION = "1.0"` (в `config/settings.py`).
При MINOR изменении схемы — поддерживается backward compatibility через паттерн
`signal.get("new_field") || signal.get("old_field")`.

**API (Фаза 4):** префикс `/api/v1/` во всех POST-эндпоинтах выше (AP06).
MAJOR версия API инкрементируется только при breaking change в контракте
запроса/ответа (не при добавлении нового optional поля — это PATCH/MINOR
и не требует нового префикса, см. `SCHEMA_BACKWARD_COMPAT` в `config/settings.py`).
Старая версия (`/api/v0/`, если возникнет) поддерживается минимум 90 дней
параллельно с новой — итоговая политика deprecation формализуется при
реализации Backend, не раньше: формализовать раньше первой реальной MAJOR
итерации означало бы гадать.
