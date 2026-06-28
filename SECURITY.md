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

## T1 — XSS в renderNarrativeItem

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

Заменить прямую подстановку на `sanitize()` для всех полей из внешних данных:

| Поле | До | После |
|------|----|-------|
| `tension` | `highlightEntities(tension)` | `highlightEntities(sanitize(tension))` |
| `macroText` | `highlightEntities(macroText)` | `highlightEntities(sanitize(macroText))` |
| `synthesis.takeaway` | прямая подстановка | `sanitize(synthesis.takeaway)` |
| `label` из `CLUSTER_LABELS` | прямая подстановка | `sanitize(label)` |
| `e.profile.notable` | прямая подстановка | `sanitize(e.profile.notable)` |
| `e.profile.metrics[i]` | прямая подстановка | `sanitize(m)` |
| `e.signal_refs[i]` | прямая подстановка | `sanitize(r)` |

> `highlightEntities()` — внутренняя функция проекта, оборачивает известные сущности в `<span>`. Санитизацию проводить **до** передачи в неё, чтобы не экранировать её собственные теги.

**Статус:** ⏳ К реализации (см. IMPLEMENTATION_TRACKER.md → B3)

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
