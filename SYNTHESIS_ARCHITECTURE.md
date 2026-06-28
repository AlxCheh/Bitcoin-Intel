# SYNTHESIS_ARCHITECTURE.md — Архитектура нарративного синтеза

> **Статус:** Предложение к реализации  
> **Версия:** 1.0 · **Дата:** 2026-06-28  
> **Контекст:** Переход от полностью алгоритмического синтеза к гибридной схеме с утверждённым файлом

---

## Проблема которую решаем

### Текущая схема (алгоритм)

```
signals.json → synthesizeNarrativeAdvanced() → Главные нарративы
```

При 42 сигналах работает хорошо. При масштабировании возникают три проблемы:

| Проблема | Проявление при росте базы |
|----------|--------------------------|
| **Деградация качества** | Старые сигналы с большим `contradicts` перебивают новые острые |
| **Нет контроля** | Синтез меняется автоматически при каждом новом сигнале — иногда неожиданно |
| **Нет кэша** | Каждое открытие страницы пересчитывает весь кластер заново |

### Целевая схема (гибридная)

```
signals.json → [алгоритм] → я проверяю → synthesis.json → Главные нарративы
                                                    ↑
                              fallback если файл устарел или отсутствует
```

---

## Архитектура: три уровня

```
┌─────────────────────────────────────────────────────┐
│  УРОВЕНЬ 1: signals.json                            │
│  База данных сигналов — источник правды             │
│  Не меняется в рамках этой архитектуры              │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  УРОВЕНЬ 2: synthesis.json                          │
│  Утверждённый синтез — создаётся вручную            │
│  Обновляется после каждой сессии добавления         │
│  Срок жизни: 7 дней (потом fallback на алгоритм)   │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  УРОВЕНЬ 3: index.html                              │
│  Показывает synthesis.json если свежий              │
│  Fallback: synthesizeNarrativeAdvanced()            │
└─────────────────────────────────────────────────────┘
```

---

## Структура synthesis.json

```json
{
  "meta": {
    "generated": "2026-06-28",
    "signals_count": 42,
    "version": "1.0",
    "window_days": 90,
    "expires_days": 7
  },
  "clusters": {
    "strategy_model_stress": {
      "tension": "Сейлор публично подтверждает стратегию при $9.3 млрд убытка и STRC ниже номинала — vs рынок читает семантический сдвиг с «накопления» на «кредитное качество» как признание что модель вошла в режим выживания",
      "narrative": "STRC превращает привлечение капитала в автоматический спрос на BTC — тогда как крупнейшее корпоративное BTC-казначейство переходит от фазы накопления к фазе защиты: STRC не работает, ATM при mNAV < 1x разводняет",
      "takeaway": "Структурный спрос на BTC от Strategy временно заморожен — модель ждёт возврата STRC к номиналу или разворота цены",
      "strength": "structural",
      "signals_used": [
        "STR-2026-0622-003",
        "STR-2026-0628-001",
        "STR-2026-0625-001"
      ],
      "generated": "2026-06-28",
      "source": "approved"
    },
    "etf_institutional_flow": {
      "tension": "...",
      "narrative": "...",
      "takeaway": "...",
      "strength": "structural",
      "signals_used": [],
      "generated": "2026-06-28",
      "source": "approved"
    },
    "btc_infrastructure_growth": {
      "tension": "...",
      "narrative": "...",
      "takeaway": "...",
      "strength": "strong",
      "signals_used": [],
      "generated": "2026-06-28",
      "source": "approved"
    },
    "btc_treasury_competition": {
      "tension": "...",
      "narrative": "...",
      "takeaway": "...",
      "strength": "strong",
      "signals_used": [],
      "generated": "2026-06-28",
      "source": "approved"
    },
    "supply_scarcity": {
      "tension": "...",
      "narrative": "...",
      "takeaway": "...",
      "strength": "moderate",
      "signals_used": [],
      "generated": "2026-06-28",
      "source": "approved"
    }
  }
}
```

### Поля объекта кластера

| Поле | Тип | Описание |
|------|-----|----------|
| `tension` | string | Утверждённое противоречие — главный крючок карточки |
| `narrative` | string | Утверждённый синтез — склейка trigger + complication |
| `takeaway` | string | Одна мысль — первое предложение из resolution или свежего сигнала |
| `strength` | enum | structural / strong / moderate / weak |
| `signals_used` | array | id сигналов которые вошли в синтез |
| `generated` | date | Дата создания этой записи |
| `source` | enum | approved / algo (algo = сгенерирован алгоритмом как fallback) |

---

## Логика загрузки в index.html

### loadSynthesis() — новая функция

```javascript
let SYNTHESIS = null;

async function loadSynthesis() {
  try {
    const resp = await fetch('synthesis.json?v=' + Date.now());
    const data = await resp.json();

    // Проверяем срок жизни
    const ageDays = (Date.now() - new Date(data.meta.generated)) / 86400000;
    const expiresDays = data.meta.expires_days || 7;

    if (ageDays <= expiresDays) {
      SYNTHESIS = data.clusters;
      window.SYNTHESIS_META = data.meta;
    } else {
      console.warn('synthesis.json устарел (' + Math.round(ageDays) + ' дней) — используем алгоритм');
      SYNTHESIS = null;
    }
  } catch(e) {
    // Файла нет или ошибка — тихо падаем на алгоритм
    SYNTHESIS = null;
  }
}
```

### Интеграция в renderNarrative()

```javascript
// Вместо:
const synthesis = synthesizeNarrativeAdvanced(key, cl);

// Становится:
const synthesis = (SYNTHESIS && SYNTHESIS[key] && SYNTHESIS[key].source === 'approved')
  ? {
      narrative: SYNTHESIS[key].narrative,
      tension:   SYNTHESIS[key].tension,
      macro:     SYNTHESIS[key].narrative,
      takeaway:  SYNTHESIS[key].takeaway,
      strength:  SYNTHESIS[key].strength,
      source:    'approved'
    }
  : synthesizeNarrativeAdvanced(key, cl);
```

### Индикатор в карточке

```javascript
// Показываем дату утверждения если source === 'approved'
const dateLabel = synthesis.source === 'approved'
  ? '<span class="synth-date">✎ ' + SYNTHESIS[key].generated + '</span>'
  : '';
```

```css
.synth-date {
  font-family: var(--mono);
  font-size: 8px;
  color: var(--dim);
  letter-spacing: 0.06em;
  margin-left: 8px;
  opacity: 0.7;
}
.synth-date.stale { color: var(--amber); } /* старше 5 дней */
```

### Загрузка параллельно с signals.json

```javascript
// В loadSignals() — Promise.all расширяем:
const [sigResp, entResp] = await Promise.all([
  fetch('signals.json?v=' + Date.now()),
  fetch('ENTITIES.json?v=' + Date.now())
]);
// synthesis.json грузим отдельно — не блокирует рендер
loadSynthesis().then(() => {
  if (SIGNALS && SIGNALS.length) renderDashboard();
});
```

---

## Workflow: как обновлять synthesis.json

### Триггеры для обновления

| Событие | Нужно обновлять? |
|---------|-----------------|
| Добавлен новый сигнал (trigger/complication) | **Да** |
| Добавлен фоновый сигнал (background) | Не обязательно |
| Исправлен tension у существующего сигнала | **Да** |
| Изменены links.contradicts | **Да** |
| Прошло 7+ дней | **Да** (автоматически fallback) |

### Пошаговый процесс

```
1. Добавил новые сигналы в signals.json (как сейчас)

2. Говорю Claude: «Обнови synthesis.json»

3. Claude запускает Python-скрипт:
   - читает signals.json
   - запускает synthesizeNarrativeAdvanced() на Python
   - применяет окно релевантности (последние 90 дней)
   - показывает результат по каждому кластеру

4. Проверяю текст:
   - tension — острое противоречие? С заглавной буквы?
   - narrative — склейка двух частей? Не дублирует tension?
   - takeaway — одно предложение, новый угол?

5. При необходимости правлю вручную

6. Claude записывает synthesis.json в репозиторий

7. Сайт автоматически показывает утверждённый синтез
```

---

## Масштабирование при росте базы

### Окно релевантности (90 дней)

При 100+ сигналах не все участвуют в синтезе:

```python
SYNTHESIS_WINDOW = 90  # дней

def get_relevant_signals(cluster_signals):
    today = date.today()
    relevant = [
        s for s in cluster_signals
        if days_ago(s['date']) <= SYNTHESIS_WINDOW
    ]
    # Если релевантных мало (< 3) — берём последние 5 из всей базы
    if len(relevant) < 3:
        relevant = sorted(cluster_signals,
            key=lambda s: s['date'], reverse=True)[:5]
    return relevant
```

### Freshness decay (при 200+ сигналах)

Старые сигналы получают сниженный вес в скоринге:

```python
def freshness_weight(days):
    if days <= 7:   return 3.0   # полный вес
    if days <= 30:  return 1.5   # средний
    if days <= 90:  return 0.75  # половина
    return 0.0                   # не участвует в синтезе
```

### Архивирование (при 500+ сигналах)

Сигналы старше 180 дней переносятся в `signals_archive.json`:
- Из основной базы удаляются
- Доступны для исторического поиска
- Не влияют на синтез и скоринг

```
signals.json         — активные (последние 180 дней)
signals_archive.json — архив (старше 180 дней)
synthesis.json       — утверждённый синтез (обновляется вручную)
```

---

## Состояния synthesis.json на сайте

| Состояние | Условие | Что показывается |
|-----------|---------|-----------------|
| **Актуальный** | Файл есть, возраст ≤ 7 дней | Утверждённый синтез + `✎ дата` |
| **Устаревший** | Файл есть, возраст > 7 дней | Алгоритм + `⚠ синтез устарел` |
| **Отсутствует** | Файл не найден (404) | Алгоритм (тихо, без предупреждения) |
| **Ошибка** | JSON битый | Алгоритм (тихо) |

---

## Что НЕ меняется

- `signals.json` — структура и процесс добавления сигналов
- `CLAUDE.md` — алгоритм обработки сигналов
- `ALGORITHM.md` — правила tension и contradicts
- `synthesizeNarrativeAdvanced()` — остаётся как fallback
- Все остальные вкладки сайта

---

## План реализации

### Фаза 1 — Файл и загрузка (1 сессия)
- [ ] Создать `synthesis.json` с текущим утверждённым синтезом
- [ ] Добавить `loadSynthesis()` в `index.html`
- [ ] Интегрировать в `renderNarrative()`
- [ ] Добавить индикатор даты в карточку

### Фаза 2 — Workflow (следующая сессия)
- [ ] Python-скрипт для генерации черновика синтеза
- [ ] Процесс проверки и утверждения
- [ ] Обновить CLAUDE.md — добавить шаг «обновить synthesis.json»

### Фаза 3 — Масштабирование (при 100+ сигналах)
- [ ] Окно релевантности 90 дней
- [ ] Freshness decay в скоринге
- [ ] Архивирование при 500+ сигналах

---

## Связанные файлы

| Файл | Роль |
|------|------|
| `signals.json` | База данных — источник данных для синтеза |
| `synthesis.json` | Утверждённый синтез — новый файл |
| `ENTITIES.json` | База сущностей — не меняется |
| `ALGORITHM.md` | Правила алгоритма — описывает synthesizeNarrativeAdvanced() |
| `CLAUDE.md` | Инструкции — добавить шаг обновления synthesis.json |
| `index.html` | Сайт — читает synthesis.json, fallback на алгоритм |

---

*Документ создан: 2026-06-28*  
*Статус: готов к реализации*
