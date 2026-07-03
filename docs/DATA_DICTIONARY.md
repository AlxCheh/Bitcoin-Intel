# Data Dictionary — мост «Знание ↔ Реализация»

**Версия:** 1.0
**Назначение:** каноническое соответствие между уровнем знания (BDKS) и уровнем реализации (схема `signals.json`, enum'ы CLAUDE.md, `ENTITIES.json`). Закрывает CR-20 / G-07 / Q-08 из KE-аудита.
**Привязки версий:** BDKS v1.2 ([docs/BDKS.md](BDKS.md)) · BAMS v1.1 ([docs/BAMS.md](BAMS.md)) · CLAUDE.md v6.1

---

## 1. Правило авторитета

Смысл каждого поля и значения канонически определяется на своём уровне:

| Уровень | Владеет | Документ |
|---|---|---|
| Знание | Что означают классы, категории, горизонты, агенты, потоки | BDKS |
| Метод | Интерпретационные поля: как аналитик приходит к значению | BAMS, ALGORITHM.md |
| Реализация | Формат полей, enum-строки, схема JSON, префиксы id | CLAUDE.md |

Изменение enum'а реализации сверяется с этим словарём до внесения. Расхождение между уровнями — либо дефект реализации (чинится здесь и в CLAUDE.md), либо заявка на изменение BDKS (проходит его процедуру эволюции знаний). Молчаливое расхождение недопустимо.

## 2. Поля сигнала по уровням

| Поле | Уровень | Канонический источник смысла |
|---|---|---|
| `id`, `catLabel`, `signal`, `data` | Реализация | CLAUDE.md (формат, префиксы, display) |
| `date` | Знание (дата события) + Метод (правило фиксации из первоисточника, Шаг 3) | BDKS Р4 · CLAUDE.md |
| `cat`, `theme`, `weight`, `actor`, `flow`, `horizon` | Знание | BDKS (маппинги — раздел 3 ниже) |
| `dir` | Метод — интерпретационная оценка влияния на позицию BTC | BAMS (гипотезы/доказательства) |
| `context`, `caveat` | Метод, с опорой на знание | `context` ↔ прецеденты BDKS Р13; `caveat` ↔ неопределённость BDKS Р11, правила R-09/R-11 |
| `source` | Знание | BDKS Р10 (категории источников, шкала надёжности) |
| `links`, `narrative_role`, `cluster`, `tension`, `macro_implication` | Метод / Реализация | BAMS + ALGORITHM.md; в BDKS не определяются (граница уровней, BDKS Р2) |

## 3. Маппинг enum'ов

### 3.1. `cat` → классы BDKS (Р3)

| cat | Классы BDKS |
|---|---|
| `onchain` | UTXO, Wallets, LTH/STH; метрики Р9 (MVRV, SOPR, Realized Cap, Exchange Reserve) |
| `macro` | Macroeconomic Environment, Central Banks, Liquidity (макроконтур) |
| `mining` | Mining, Hashrate, Difficulty, Fee Market |
| `narrative` | Narrative, информационные и регуляторные события (Р4) |
| `layer2` | Layer 2, Infrastructure |
| `ownership` | Institutions, Governments, ETFs, Custodians, Treasury-владение |
| ~~`ta`~~ | Депрецирована (v6.0): технический анализ вне предметной области — BDKS Р1 |

### 3.2. `theme` ↔ префикс `id` ↔ область BDKS

| theme | Префикс | Область BDKS |
|---|---|---|
| `supply` | SUP | Эмиссия, halving, потерянные монеты, ликвидный float (Р7) |
| `institutionalization` | STR | Институциональный контур: Уровень 3 карты знаний (Р14) |
| `infrastructure` | INF | Layer 2, Infrastructure, Fee Market |
| `macro` | MAC | Macroeconomic Environment, Central Banks — внешний канал (Р1) |
| `narrative` | NAR | Narrative (Уровень 4 карты знаний) |

### 3.3. `weight` ↔ таксономия сигналов BDKS (Р5)

| weight | Категория BDKS |
|---|---|
| `onchain` | On-chain |
| `market` | Market |
| `media` | Media / Analyst |
| `primary` | Primary |
| — | **Infrastructure metrics: значения нет** → конвенция DD-01 |

### 3.4. `actor` ↔ агенты BDKS (Р6/Р3)

| actor | Агент BDKS |
|---|---|
| `etf` | ETF-провайдеры и потоки их продуктов |
| `corporate` | Публичные корпорации-держатели |
| `government` | Государства |
| `miner` | Майнеры |
| `retail` | Розничные инвесторы |
| `defi` | DeFi/BTCFi-протоколы |
| — | **Exchanges, Custodians, Central Banks: значения нет** → пробел DD-02 |

### 3.5. `flow` ↔ CapitalFlow (BDKS Р3/Р7)

`inflow` / `outflow` / `internal` — канонические направления CapitalFlow. `neutral` — расширение уровня реализации: движения капитала нет или оно неизвестно (в BDKS отсутствие потока не является состоянием потока). Расширение согласовано: DD-03.

### 3.6. `horizon` ↔ горизонты BDKS

`short` = краткосрочный (недели–месяцы) · `mid` = среднесрочный (месяцы–год) · `long` = долгосрочный/структурный (годы). Совпадает с горизонтами Р3/Р4/Р8 BDKS.

## 4. ENTITIES.json ↔ онтология BDKS

| type | Класс BDKS |
|---|---|
| `l2` | Layer 2 |
| `protocol` | Infrastructure / Layer 2 (протокольные системы поверх базового слоя) |
| `corporate` | Institutions |
| `fund` | ETFs (продукты) / Institutions (управляющие) |
| `infrastructure` | Infrastructure |
| `exchange` | Exchanges |
| — | **Governments, Custodians, Central Banks: типа нет** → пробел DD-04 |

## 5. Реестр конвенций и пробелов

| ID | Суть | Статус |
|---|---|---|
| DD-01 | Infrastructure metrics (BDKS Р5) не имеет значения `weight`. Конвенция: верифицируемые сетевые метрики (hashrate, Lightning capacity, node count) кодируются `weight: onchain`; отраслевые отчёты о инфраструктуре — `media` | Конвенция принята; расширение enum (`infra`) — только при накоплении сигналов, где конвенция искажает достоверность |
| DD-02 | Классы-агенты Exchanges / Custodians / Central Banks невыразимы в `actor`. До первого реального сигнала с таким субъектом enum не расширяется (YAGNI); при появлении — заявка на `exchange` / `custodian` / `centralbank` | Пробел зафиксирован, ожидает триггера |
| DD-03 | `flow: neutral` — расширение реализации без доменного аналога | Согласовано, доменного изменения не требует |
| DD-04 | `ENTITIES.json` не имеет типов для government / custodian / central bank | Пробел зафиксирован, триггер — первая сущность |
| DD-05 | `dir` — методологическая оценка, не доменный факт: два аналитика могут расходиться в `dir` при одинаковых фактах. Валидируется через BAMS (доказательства), не через BDKS | Разграничение зафиксировано |
| DD-06 | `cluster` и таблица кластеров — уровень метода/реализации, живут в CLAUDE.md; в BDKS осознанно отсутствуют | Разграничение зафиксировано |

## 6. Governance

1. Новое значение любого enum'а → проверка по разделам 3–4: есть ли доменный смысл в BDKS. Нет — сначала расширение BDKS (его процедурой), потом enum.
2. Изменение классов BDKS → проход по этому словарю: не осиротели ли маппинги.
3. Версия словаря пиннится к версиям BDKS и CLAUDE.md (шапка); рассинхронизация пинов — сигнал незавершённой синхронизации.
4. Изменения словаря версионируются по схеме проекта: +0.1 минор / +1.0 мажор.
