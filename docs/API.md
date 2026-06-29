# Bitcoin Intel — API Documentation

> **Версия:** 1.0 · **Обновлено:** 2026-06-29  
> **Тип:** Static file API (GitHub Pages)  
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

## Аутентификация

На текущем этапе (GitHub Pages, Фаза 0–2) — **отсутствует**.  
Все endpoints публичны. После перехода на Backend (Фаза 4+):
- `POST /api/signals` — добавить сигнал (требует API key)
- `POST /api/syntheses/{id}/approve` — утвердить синтез (требует аналитик-роль)
- `GET /api/history/{cluster}` — история синтезов

---

## Rate Limits

GitHub Pages: стандартные лимиты CDN. Рекомендуется кешировать ответы на стороне клиента.

---

## Версионирование

Схема сигналов: `SIGNAL_SCHEMA_VERSION = "1.0"` (в `config/settings.py`).  
При MINOR изменении схемы — поддерживается backward compatibility через паттерн
`signal.get("new_field") || signal.get("old_field")`.
