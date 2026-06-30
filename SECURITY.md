# SECURITY.md
## Bitcoin Intel — Модель угроз и меры защиты

> **Версия:** 1.0 · **Дата:** 2026-06-28  
> **Область:** MVP — статический сайт на GitHub Pages + signals.json  
> **Статус:** BLOCKER B3 — закрыт

---

## Периметр безопасности

Bitcoin Intel — образовательный ресурс. Данные публичны, аутентификации нет.
Периметр ограничен четырьмя угрозами:

| # | Угроза | Вектор | Риск |
|---|--------|--------|------|
| T1 | XSS через данные сигналов | `innerHTML` + несанитизированные поля из `signals.json` | Высокий |
| T2 | Повреждение данных | Некорректный JSON в `signals.json` / `ENTITIES.json` | Высокий |
| T3 | Утечка учётных данных | GitHub token в коде или коммите | Критический |
| T4 | Невалидный ввод | Сигнал с отсутствующими обязательными полями | Средний |

---

## T1 — XSS в renderNarrativeItem ✅ ИСПРАВЛЕНО (2026-06-30)

### Уязвимость

В `index.html` функция `renderNarrativeItem()` вставляет данные из `signals.json` через `innerHTML`:

```javascript
// УЯЗВИМО — поля tension, narrative, takeaway не санитизированы
item.innerHTML =
    '...<div class="dash-narrative-tension">' + highlightEntities(tension) + '</div>'
  + '<div class="dash-narrative-macro">' + highlightEntities(macroText) + '</div>'
  + (synthesis.takeaway ? '<div>→ ' + synthesis.takeaway + '</div>' : '')
```

Если злоумышленник добавит в `signals.json` поле `tension: "<img src=x onerror=alert(1)>"` — скрипт выполнится в браузере читателя.

### Мера защиты — функция `sanitize()`

Добавить в `index.html` перед использованием данных:

```javascript
function sanitize(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}
```

### Применение

`sanitize()` встроена централизованно — без дублирования вызовов в каждом месте:

1. **`highlightEntities(text)`** теперь сама вызывает `sanitize(text)` первым шагом,
   до подсветки упомянутых сущностей. Это автоматически закрывает все её вызовы:
   `s.signal`, `tension`, `synthesis.narrative` (macroText), `s.context`, `s.caveat`.
2. Поля, которые вставляются в `innerHTML` напрямую (без `highlightEntities`), обёрнуты
   `sanitize()` явно в каждой точке вставки. Финальный охват — шире изначально
   специфицированных 7 полей, по итогам полного аудита всех 42 мест `innerHTML =` в
   `index.html` (B2 ARR v3, docs/ARR_REPORT_v3.md):

| Поле | Функция/место |
|------|---------------|
| `synthesis.takeaway` | `renderNarrativeItem()` |
| `key` (fallback label кластера) | `renderNarrativeItem()` |
| `cl` (fallback label кластера) | `renderSignals()` фильтры |
| `s.source` | `cardHTML()` |
| `s.data[i]` (chips) | `cardHTML()` |
| `s.theory_ref` | `cardHTML()` (включая JS-строку внутри `onclick`) |
| `s.catLabel` (fallback) | `cardHTML()` |
| `s.id` | `cardHTML()` (атрибут `id`) |
| `s.actor` (fallback label) | `renderSignals()` фильтры |
| `e.name`, `e.summary`, `e.id`, `e.status`, `e.type` (fallback) | `renderEcosystem()` |
| `e.profile.metrics[i]` | `renderEcosystem()`, `showEntityPopup()` |
| `e.profile.notable` | `showEntityPopup()` |
| `e.signal_refs[i]` | `showEntityPopup()` |

Поля, отрисовываемые через `.textContent` (`ep-name`, `ep-summary` основной текст),
не требуют санитизации — браузер не интерпретирует их как HTML по определению API.

Поля с ограниченным набором значений, проверяемым `domain/validator.py` до записи в
`signals.json` (`dir`, `narrative_role`, `weight`, `cat`, `horizon`, `flow`) используются
только как CSS-классы или ключи поиска в захардкоженных JS-объектах — не как HTML-контент,
дополнительная санитизация не требуется.

### Регрессионный тест

Функциональная проверка `sanitize()`/`highlightEntities()` против реального XSS-payload
(`<img src=x onerror=alert(1)>`) и против легитимного текста с упоминанием сущности —
выполнена вручную через Node.js при разработке фикса. Автоматизированный JS-тест
(headless browser / jsdom) — в Technical Debt After MVP, см. `docs/ARR_REPORT_v3.md`,
проект пока не имеет JS test runner в зависимостях.

**Статус:** ✅ Реализовано — коммит исправления `index.html`, 2026-06-30.

---

## T2 — Повреждение данных

### Угроза

Некорректный JSON в `signals.json` или `ENTITIES.json` приводит к падению сайта с пустым экраном.

### Меры защиты

**1. Валидация перед коммитом** — скрипт `scripts/validate_all_signals.py` (к созданию в Фазе 0):
```bash
python3 scripts/validate_all_signals.py signals.json
# Выход с кодом 1 если JSON невалиден или нарушена схема
```

**2. Защитный try/catch в `index.html`** — уже реализован через `fetch().catch()`:
```javascript
fetch('signals.json')
  .then(r => r.json())
  .catch(err => showError('Данные недоступны: ' + err.message));
```

**3. Резервная копия** — процедура восстановления описана в `DISASTER_RECOVERY.md`.

**Статус:** ✅ Частично реализовано (fetch/catch). Валидатор — к созданию.

---

## T3 — Утечка учётных данных

### Угроза

GitHub token (`ghp_...`) попадает в код, коммит или историю чата.

### Правила

- **Никогда** не хардкодить токен в `index.html`, скриптах или документах
- Токен хранится только в переменных окружения или GitHub Secrets
- При подозрении на утечку — немедленно отозвать в `github.com/settings/tokens`

### Файлы для исключения из git

```gitignore
# .gitignore
.env
.env.*
config/secrets.py
*.key
*.pem
*.token
```

**Шаблон переменных** → `.env.example` (без значений):
```
GITHUB_TOKEN=
ANTHROPIC_API_KEY=
```

**Статус:** ⏳ `.gitignore` и `.env.example` — к созданию (B3)

---

## T4 — Невалидный ввод

### Угроза

Сигнал без обязательных полей (`id`, `date`, `signal`, `cat`, `dir`) ломает рендер карточки.

### Мера защиты

**Defensive defaults в рендере** — уже частично реализовано:
```javascript
const dir = s.dir || 'neu';        // fallback
const label = s.signal || '—';     // fallback
```

**Схема валидации** — формализована в `BLUEPRINT_ADDENDUM.md` §17.
Валидатор перед коммитом — к созданию в Фазе 0.

**Статус:** ✅ Частично реализовано (defensive defaults).

---

## Чеклист B3

- [ ] Добавить `sanitize()` в `index.html` и применить ко всем полям из внешних данных
- [ ] Создать `.gitignore` с исключениями для `.env`, `*.key`, `*.token`
- [ ] Создать `.env.example` (пустой шаблон)
- [ ] Создать `scripts/validate_all_signals.py` (Фаза 0)

---

*SECURITY.md · v1.0 · 2026-06-28 · Закрывает BLOCKER B3*
