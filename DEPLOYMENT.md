# DEPLOYMENT.md
## Bitcoin Intel — Стратегия деплоя

> **Версия:** 1.0 · **Дата:** 2026-06-28  
> **Статус:** BLOCKER B5 — закрыт

---

## Архитектура деплоя

```
GitHub Repository (AlxCheh/Bitcoin-Intel)
    │
    ├── main branch ──────────────→ GitHub Pages (Production)
    │                                https://alxcheh.github.io/Bitcoin-Intel
    │
    └── feature/* / hotfix/* ─────→ Preview (Pull Request preview)
                                     https://alxcheh.github.io/Bitcoin-Intel (PR preview)
```

**Текущий стек:** 100% статика. Нет серверной части, нет базы данных.
**CI/CD:** есть, `.github/workflows/deploy.yml` — `validate` → `synthesize` → `deploy`
(это описание было устаревшим на момент написания раздела; актуализировано
IRP v1 Wave 2 / M03).
**Деплой:** автоматически при push в `main`, через GitHub Actions
(`actions/deploy-pages@v4`), не через встроенный GitHub Pages auto-build.
**Время деплоя:** ~1–3 минуты после push.

> ✅ **IRP v1 Wave 2 / M03 (2026-07-01):** GitHub Pages Source переключён с
> `build_type: legacy` на `build_type: workflow` (Settings → Pages → Source
> → «GitHub Actions»). До этого работали два параллельных механизма деплоя
> одновременно — встроенный legacy auto-build («pages build and deployment»
> job) и кастомный `deploy` job в `deploy.yml` — избыточно и было источником
> «deploy-job стабильно красный» (alarm fatigue) в отдельные периоды.
> Теперь единственный источник деплоя — `deploy.yml`.

---

## Environments

### Production

| Параметр | Значение |
|----------|---------|
| URL | https://alxcheh.github.io/Bitcoin-Intel |
| Ветка | `main` |
| Триггер | push в `main` |
| Данные | `signals.json`, `ENTITIES.json` (публичные, в репозитории) |
| Кеш браузера | CDN GitHub Pages, TTL ~10 минут |

### Preview (Pull Request)

На текущем этапе (MVP) preview отсутствует — все изменения идут напрямую в `main`.  
При появлении нескольких контрибьюторов — создать ветку `develop` и настроить PR preview.

---

## Branch Strategy

```
main          — production. Прямой push только для hotfix.
feature/*     — новые функции и сигналы. Мерж через PR.
hotfix/*      — срочные исправления. Мерж напрямую в main с тегом.
```

**Правила:**
- `main` всегда в рабочем состоянии
- Изменения `signals.json` и `ENTITIES.json` — прямой push в `main` (это данные, не код)
- Изменения `index.html` — через ветку `feature/...` + PR

---

## Deployment Checklist

Перед каждым push в `main` c изменениями `index.html`:

- [ ] `python3 -m json.tool signals.json > /dev/null` — JSON валиден
- [ ] `python3 -m json.tool ENTITIES.json > /dev/null` — JSON валиден
- [ ] Открыть сайт локально (открыть `index.html` в браузере) — нет JS-ошибок в консоли
- [ ] Проверить вкладки: Обзор, Дайджест, Экосистема — данные отображаются
- [ ] После push: подождать 2 минуты, открыть https://alxcheh.github.io/Bitcoin-Intel
- [ ] Жёсткое обновление (Ctrl+Shift+R / закрыть и открыть вкладку) — изменения видны

---

## GitHub Actions Pipeline (к созданию в Фазе 0)

Файл: `.github/workflows/deploy.yml`

```yaml
name: Validate and Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  PYTHONHASHSEED: "0"

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Validate signals.json
        run: python3 -m json.tool signals.json > /dev/null

      - name: Validate ENTITIES.json
        run: python3 -m json.tool ENTITIES.json > /dev/null

      - name: Run signal schema validation
        run: |
          if [ -f scripts/validate_all_signals.py ]; then
            python3 scripts/validate_all_signals.py signals.json
          else
            echo "⚠ validate_all_signals.py не создан — пропуск"
          fi

      - name: Run unit tests
        run: |
          if [ -d tests/unit ]; then
            pip install pytest --quiet
            python3 -m pytest tests/unit/ -v
          else
            echo "⚠ tests/unit/ не создана — пропуск"
          fi

  # GitHub Pages деплоится автоматически при merge в main
  # Никакого дополнительного шага деплоя не нужно
```

**Статус:** ⏳ К созданию в Фазе 0  
**Немедленный эффект:** после создания — валидация JSON будет автоматической при каждом push.

---

## Rollback Procedure

### Откат изменений `index.html`

```bash
# 1. Найти последний рабочий коммит
git log --oneline index.html | head -5

# 2. Откатить файл
git checkout <COMMIT_SHA> -- index.html

# 3. Закоммитить откат
git add index.html
git commit -m "revert: rollback index.html to <COMMIT_SHA>"
git push origin main
```

**Время до восстановления:** ~5 минут (2 минуты деплоя GitHub Pages).

### Откат данных

Описан в `DISASTER_RECOVERY.md` → S1, S2.

---

## Переменные окружения

| Переменная | Где нужна | Хранить в |
|-----------|-----------|----------|
| `GITHUB_TOKEN` | Скрипты push в API | Локально в `.env` (не в git) |
| `ANTHROPIC_API_KEY` | Если появится AI-функциональность | GitHub Secrets |
| `PYTHONHASHSEED` | Скрипты синтеза | Makefile: `PYTHONHASHSEED=0 python3 ...` |

Шаблон → `.env.example` (без значений, в git).

---

## Мониторинг (текущий уровень MVP)

| Метод | Что проверяет | Частота |
|-------|--------------|---------|
| Открыть сайт руками | Сайт доступен, данные загружаются | После каждого push |
| Консоль браузера (F12) | JS-ошибки, ошибки fetch | После изменений `index.html` |
| GitHub → Actions | CI прошёл/упал | Автоматически (после создания pipeline) |

Полноценный мониторинг (Uptime Robot, Sentry, алерты) — после появления серверной части.

---

*DEPLOYMENT.md · v1.0 · 2026-06-28 · Закрывает BLOCKER B5*
