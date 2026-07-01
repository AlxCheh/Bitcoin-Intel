# SECURITY.md
## Bitcoin Intel — Модель угроз и меры защиты

> **Версия:** 1.1 · **Дата:** 2026-07-01
> **Область:** MVP — статический сайт на GitHub Pages + signals.json
> **Статус:** BLOCKER B3 — закрыт · IRP v1 Wave 3 / OP03 — Secrets Rotation Policy добавлена

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

### Secrets Rotation Policy (IRP v1 Wave 3 / OP03, 2026-07-01)

**Реальные секреты в проекте на 2026-07-01:**

| Секрет | Где хранится | Где используется | Ротация |
|--------|--------------|-------------------|---------|
| `GITHUB_TOKEN` | Авто-генерируется GitHub Actions на каждый run | `.github/workflows/deploy.yml` (checkout) | Авто — живёт только время выполнения run, ручная ротация не требуется |
| `SYNTHESIS_BOT_TOKEN` | GitHub Secrets (repo settings → Secrets and variables → Actions) | `.github/workflows/deploy.yml` — push синтезированного кеша от имени бота, в обход `GITHUB_TOKEN`, чтобы не порождать рекурсивный workflow run | **Ручная, по правилам ниже** |

**Плановая ротация:** раз в 90 дней. Fine-grained PAT (не classic) с минимальным
scope — `contents: write` только на этот репозиторий, без доступа к остальным
репозиториям аккаунта и без прав на Actions/Settings.

**Внеплановая ротация — обязательна немедленно, если:**
- Токен был вставлен в текстовое сообщение (issue, PR, commit message, чат
  с ассистентом) в открытом виде — даже если сообщение потом отредактировано
  или удалено. Токен, once написанный текстом в чужом интерфейсе (включая
  AI-ассистентов), должен считаться скомпрометированным независимо от того,
  утёк ли он в git history репозитория — то, что он не попал в сам код или
  коммит, не значит, что он не был виден третьей стороне (провайдеру
  чат-интерфейса, логам, кэшу).
- Есть подозрение на компрометацию по любой другой причине (утечка секрета
  CI-провайдера, случайный `echo`/`print` в логах workflow run и т.п.)

**Процедура ротации:**
1. GitHub → Settings → Developer settings → Fine-grained tokens →
   Regenerate (или создать новый и отозвать старый явно — не полагаться
   на истечение по таймауту)
2. Обновить значение в repo Settings → Secrets and variables → Actions →
   `SYNTHESIS_BOT_TOKEN`
3. Прогнать `deploy.yml` вручную (workflow_dispatch либо тривиальный PR) —
   убедиться, что push от имени бота проходит новым токеном
4. Убедиться, что старый токен возвращает `401` при запросе к GitHub API —
   подтверждение, что отзыв применился, а не просто перезаписан в Secrets

**Уточнение к IRP/IRR (RR-07):** формулировка «PAT в git history» в
`docs/IRP_v1.md` (раздел Residual Risks) неточна — поиск по всей истории
коммитов (`git rev-list --all` + `git grep`) не находит реального PAT ни
в одном блобе репозитория, только текстовые упоминания шаблона `ghp_...`
в этом файле как примера. Риск был не в git history репозитория, а в
истории переписки с AI-ассистентом (несколько токенов были вставлены
открытым текстом в чат в разных сессиях реализации Wave 1–3) — отсюда и
формулировка выше про «once написанный текстом... должен считаться
скомпрометированным». Это тот же класс риска, просто другой канал утечки.

**Статус:** ✅ Политика описана. Плановая ротация по календарю — вне
scope OP03 (нет автоматизации/напоминания в CI, ручной процесс).

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
