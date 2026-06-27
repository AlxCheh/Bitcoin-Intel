# ALGORITHM.md — Алгоритм нарративного синтеза

> Как из `signals.json` формируется блок **Главные нарративы** на вкладке Обзор.
> Версия: 2026-06-27 · Источник: `index.html` → `synthesizeNarrativeAdvanced()`

---

## Общая схема

```
signals.json (40 сигналов)
        ↓
[1] ГРУППИРОВКА по полю cluster
        ↓
[2] СКОРИНГ каждого кластера (4 оси)
        ↓
[3] ФИЛЬТРАЦИЯ — score ≥ 10, топ-4 кластера
        ↓
[4] СИНТЕЗ — 7 этапов аналитика
        ↓
[5] РЕНДЕР — tension → narrative → takeaway → счётчики
```

---

## Шаг 1 — Группировка

Каждый сигнал попадает в кластер через поле `cluster` (fallback: `theme`).

| cluster | Отображается как |
|---------|-----------------|
| `strategy_model_stress` | 🏦 STRATEGY: МОДЕЛЬ ПОД ДАВЛЕНИЕМ |
| `etf_institutional_flow` | 📊 ETF: ИНСТИТУЦИОНАЛЬНЫЙ ПОТОК |
| `btc_treasury_competition` | 🏛️ КАЗНАЧЕЙСТВА: КОНКУРЕНЦИЯ |
| `btc_infrastructure_growth` | 🔗 ИНФРАСТРУКТУРА |
| `supply_scarcity` | ⬛ ПРЕДЛОЖЕНИЕ |

---

## Шаг 2 — Скоринг кластера

```
score = freshness + weight + tension + roles
```

### Freshness (свежесть сигналов)
```
date ≤ 7 дней   → +3
date ≤ 30 дней  → +1
date > 30 дней  → 0
```

### Weight (достоверность источника)
```
onchain  → +4
primary  → +3
market   → +2
media    → +1
```

### Tension (острота противоречий)
```
links.contradicts непустой → +5 за каждый сигнал
поле tension непустое      → +2 за каждый сигнал
```
> ⚠️ Это самый важный множитель. Сигналы с `contradicts` дают +5 баллов кластеру.

### Roles (нарративная роль)
```
trigger       → +4
complication  → +3
resolution    → +2
background    → 0
```

### Пороги
```
score ≥ 35 → STRUCTURAL
score ≥ 20 → STRONG
score ≥ 10 → MODERATE
score < 10 → WEAK (показывается только если нет других)
```

---

## Шаг 3 — Фильтрация

- Кластеры с score ≥ 10 идут в показ
- Максимум 4 кластера
- Если ни один не набрал 10 — показывается 1 лучший с пометкой СЛАБЫЙ СИГНАЛ

---

## Шаг 4 — Синтез нарратива (7 этапов)

Функция `synthesizeNarrativeAdvanced(key, cl)` реализует логику Bitcoin Macro Analyst.

### Этап 1 — Главный процесс (phase)

Определяется по количеству ролей в кластере:

```
resolution > 0             → phase: 'resolution'  (противоречие закрыто)
trigger > 0                → phase: 'active'       (новое событие)
complication > background  → phase: 'tension'      (нарастает конфликт)
иначе                      → phase: 'structural'   (фоновый контекст)
```

### Этап 2 — Разделение сигналов

```
triggers      = сигналы с narrative_role === 'trigger'
complications = сигналы с narrative_role === 'complication'
resolutions   = сигналы с narrative_role === 'resolution'
```

Из каждой группы выбирается **лучший** по весу + свежести.

### Этап 3 — core_tension (главное противоречие)

Алгоритм поиска по приоритету:

```
1. Сигнал с max links.contradicts И непустым tension → берём tension
2. Любой сигнал с непустым tension → берём tension
3. Fallback: строим из двух противоречащих macro_implication:
   "<macro_impl_A> — vs — <macro_impl_B>"
```

> **Вывод:** чем точнее написан `tension` в сигнале — тем сильнее карточка.

### Этап 4 — Причинно-следственная цепочка

```
chain[0] = macro_implication лучшего trigger
chain[1] = macro_implication лучшего complication (если не дублирует chain[0])
chain[2] = macro_implication resolution (если есть)
```

### Этап 5 — market_structure (основной текст карточки)

```
Приоритет:
1. resolution.macro_implication
2. trigger.macro_implication
3. топ по weight → macro_implication
```

### Этап 6 — btc_implication

```
Из сигналов за последние 30 дней, отсортированных по weight DESC
→ первый непустой macro_implication
```

### Этап 7 — key_takeaway (одна мысль)

```
Приоритет:
1. resolution.macro_implication → первое предложение
2. trigger.macro_implication → первое предложение
3. top_weight.macro_implication → первое предложение
```

Обрезается до первого `.!?` — одно чёткое утверждение.

---

## Шаг 5 — Рендер карточки

```
[НАЗВАНИЕ КЛАСТЕРА]  [N сигналов]

▌ core_tension
  (золотая левая полоса, белый текст — главный крючок)

  market_structure / btc_implication
  (серый текст — структурный вывод)

→ key_takeaway
  (оранжевый моно — одна мысль)

🟢 N  🔴 N  ⚪ N        [STRUCTURAL] score: N ▾
```

---

## Что определяет качество нарратива

Алгоритм **выбирает и компонует** из того что написано в сигналах.
Генерация не происходит — только отбор и сборка.

| Поле сигнала | Роль в нарративе | Влияние на score |
|-------------|-----------------|-----------------|
| `tension` | Главный крючок карточки | +2 к кластеру |
| `macro_implication` | Структурный вывод (narrative + takeaway) | — |
| `narrative_role` | Приоритет в синтезе | +0..+4 |
| `links.contradicts` | Активирует tension-логику | +5 к кластеру |
| `weight` | Приоритет при выборе anchor-сигнала | +1..+4 |
| `date` | Freshness — сигналы > 30 дней теряют вес | +0..+3 |

---

## Правила написания полей для сильного нарратива

### tension — формула противоречия
```
✗ «Strategy продолжает покупать BTC»
✓ «Strategy наращивает долг для покупки BTC vs рынок ставит NAV-дисконт 0.83x»

✗ «ETF показал отток»
✓ «ETF-оттоки $6.4 млрд как поверхностное давление vs LTH покупают в 10x больше»
```

### macro_implication — структурный сдвиг, не пересказ
```
✗ «Franklin подала заявку на ETF»
✓ «Пассивный дивидендный поток как источник BTC-спроса — новая категория
    не зависящая от настроений рынка»

✗ «Metaplanet купила Siiibo»
✓ «BTC-казначейство эволюционирует от пассивного баланса к операционному движку:
    коллатерал → лицензия → продукты → комиссионный доход»
```

### narrative_role — выбирай осознанно
```
trigger      → первый сигнал нового процесса (редко, ≤1 на кластер)
complication → усложняет нарратив противоречием (основная роль)
resolution   → закрывает противоречие (редко, только при реальном разрешении)
background   → структурный контекст без острого события
```

### links.contradicts — заполняй всегда когда есть
```
Если сигнал A противоречит сигналу B — оба получают по +5 к score кластера.
Это самый быстрый способ поднять кластер в нарративах.
```

---

## Текущие кластеры и score (ориентировочно)

| Кластер | Сигналов | Примерный score | Статус |
|---------|----------|----------------|--------|
| `strategy_model_stress` | 10 | ~45 | STRUCTURAL 🔥 |
| `etf_institutional_flow` | 10 | ~38 | STRUCTURAL 🔥 |
| `btc_treasury_competition` | 8 | ~32 | STRONG |
| `btc_infrastructure_growth` | 9 | ~28 | STRONG |
| `supply_scarcity` | 2 | ~12 | MODERATE |

---

*Файл обновляется при изменении алгоритма в `index.html`*
