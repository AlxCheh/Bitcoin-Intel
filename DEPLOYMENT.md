# DEPLOYMENT.md
## Bitcoin Intel — Стратегия деплоя

> **Версия:** 1.1 · **Дата:** 2026-07-02
> **Статус:** BLOCKER B5 — закрыт · IRP v1 Wave 4 / D08 — Release Strategy добавлена, Branch Strategy и Pipeline актуализированы

---

## Архитектура деплоя

```
GitHub Repository (AlxCheh/Bitcoin-Intel)
    │
    ├── main branch ──────────────→ GitHub Pages (Production)
    │    ▲                          https://alxcheh.github.io/Bitcoin-Intel
    │    │ PR (validate + review)
    │
    ├── develop branch ───────────→ Staging (интеграционная ветка,
    │    ▲                          БЕЗ отдельного живого URL — см. ниже)
    │    │ PR (validate)
    │
    └── feature/* / hotfix/* ─────→ PR в develop (не напрямую в main)
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

### Staging (develop)

> ✅ **IRP v1 Wave 2 / M04 (2026-07-01, Вариант B):** ветка `develop`
> реализована как защищённая интеграционная ветка, без отдельного живого
> URL превью.

| Параметр | Значение |
|----------|---------|
| Живой URL | Нет — GitHub Pages даёт один URL на репозиторий; co-hosting
    staging на том же сайте (subpath) рассматривался и отклонён как
    Вариант A: он бы связал деплой prod с состоянием `develop` — если
    сборка develop падает, это блокирует деплой main, хотя main мог быть
    в порядке. Риск сочли неоправданным ради живого превью. |
| Ветка | `develop` |
| Branch Protection | Require PR + required status check `Validate and Test`, `enforce_admins: true` — тот же уровень защиты, что на `main` (M05) |
| CI | `validate` job запускается (Contract Tests, тесты, линтер). `synthesize` и `deploy` — НЕ запускаются: оба жёстко привязаны к `if: github.ref == 'refs/heads/main'` в `deploy.yml`, независимо от того что триггеры `push`/`pull_request` теперь включают `develop` |
| Как смотреть изменения | Локально: `open index.html` после checkout ветки/PR, либо смотреть diff в самом PR — без хостинга |

**Поток разработки:**
```
feature/* ──PR──→ develop ──PR──→ main ──auto──→ Production
           (validate)      (validate)   (deploy)
```
Фичи мерджатся в `develop` первыми. Когда `develop` накопил проверенные
изменения — отдельный PR `develop → main` разворачивает их в prod.

---

## Branch Strategy

> **IRP v1 Wave 4 / D08 (2026-07-02):** этот раздел противоречил уже
> актуализированному разделу «Environments → Staging (develop)» выше
> (M04, Wave 2) — там описана модель `feature/* → develop → main` с
> Branch Protection на обеих ветках, а здесь раньше утверждалось
> «прямой push в main» для `signals.json`/`ENTITIES.json`. Это не
> отражало реальность с момента внедрения M04/M05: `develop` защищена
> тем же уровнем правил, что и `main` (required status check,
> `enforce_admins: true`), прямой push куда-либо кроме hotfix
> невозможен. Раздел переписан под фактическую модель.

```
main          — production. Прямой push запрещён Branch Protection
                (кроме экстренного hotfix с явным обходом правил
                администратором — не штатный путь, см. Rollback ниже).
develop       — staging/интеграционная ветка. Тот же уровень защиты,
                что на main (M05). Все PR идут сюда первыми.
signal/*      — одна ветка на один добавляемый сигнал. PR → develop.
feature/*     — новые функции, правки документации. PR → develop.
hotfix/*      — срочные исправления. PR → main напрямую, в обход
                develop, когда ждать обычный цикл promotion недопустимо.
```

**Правила:**
- `main` и `develop` всегда в рабочем состоянии (оба защищены required status check `Validate and Test`)
- Изменения `signals.json` и `ENTITIES.json` — **через PR** в `develop`, как любой другой код, не прямой push. Это данные, но версионируемые и с CI-валидацией (Contract Tests, `validate_integrity.py`, `check_signals_size.py`) — не исключение из общего потока
- Изменения `index.html` — через ветку `feature/...` + PR
- Из `develop` в `main` — отдельный promotion PR, не автоматический merge (см. «Поток разработки» выше)

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

## GitHub Actions Pipeline

> **IRP v1 Wave 4 / D08 (2026-07-02):** этот раздел был помечен «к
> созданию в Фазе 0» и содержал устаревший YAML-снимок ранней стадии
> планирования. Реальный `.github/workflows/deploy.yml` существует и
> вырос далеко за пределы этого снимка — раздел переписан как указатель
> на файл + краткая карта того, что реально выполняется, вместо
> дублирования YAML, который неизбежно снова разойдётся с кодом.

Файл: [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) —
триггеры `push`/`pull_request` на `main` и `develop`.

| Job | Когда запускается | Что делает |
|-----|-------------------|-----------|
| `validate` | Всегда (push и PR, обе ветки) | Lint, валидация `signals.json`/`ENTITIES.json`, уникальность `id`, `validate_integrity.py`, size monitoring (OP06), Contract Tests, `pytest tests/unit/ tests/golden/ tests/integration/`, `pip-audit` |
| `synthesize` | Только `push` на `main` (`if: github.ref == 'refs/heads/main'`) | Перестраивает `synthesis_cache.json`, нормализованный diff-check (`cache_diff_check.py`) против волатильных полей, коммитит только если diff содержательный (защита от auto-merge loop, M05) |
| `deploy` | После `synthesize`, только `main` | `actions/deploy-pages@v4` — единственный источник продакшен-деплоя (M03) |

Отдельные scheduled workflows (не в `deploy.yml`, не блокируют push/PR):

| Файл | Расписание | Что проверяет |
|------|-----------|---------------|
| [`performance.yml`](.github/workflows/performance.yml) | Пн 06:00 UTC | `pytest -m perf` — `synthesize_cluster() < 100ms` (REM-M09) |
| [`synthesis-freshness.yml`](.github/workflows/synthesis-freshness.yml) | Пн 07:00 UTC | `check_synthesis_freshness.py` — кеш не устарел, нет рассинхронизации с сигналами (OP05) |

Плюс [`dependabot.yml`](.github/dependabot.yml) — еженедельные PR на обновление pip/github-actions зависимостей (OP04), с тем же `Validate and Test` required check.

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

## Release Strategy

> **IRP v1 Wave 4 / D08 (2026-07-02):** отсутствовал полностью (REL:
> «Нет описания процесса релиза новых версий алгоритма» — Этап 12
> оригинального аудита). Раздел описывает конкретно то, чего не было:
> процесс релиза новой версии `ALGORITHM_VERSION` в `synthesizer.py`
> (§25.3/§25.3bis ADDENDUM, REM-M07 Wave 3) — не общий деплой сайта
> (тот описан выше) и не добавление сигналов (это данные, не релиз кода).

Релиз новой версии алгоритма синтеза — это MAJOR/MINOR/PATCH bump
`ALGORITHM_VERSION` в `scripts/synthesizer.py`. Семантика версий
зафиксирована в ADDENDUM §25.3:

| Тип изменения | Что это | Пример |
|----------------|---------|--------|
| **PATCH** | Bugfix без изменения логики | Опечатка в формулировке `narrative` |
| **MINOR** | Новые мосты, новые scoring modifiers | Новый источник `weight`, доп. штраф за возраст сигнала |
| **MAJOR** | Изменение алгоритма выбора tension/causal chain | Смена формулы ранжирования кластера |

### Процесс релиза

1. **Изменить `ALGORITHM_VERSION`** в `scripts/synthesizer.py` согласно
   типу изменения выше. Semver — тест
   `test_algorithm_version_is_semver` (REM-M07) держит формат явно.
2. **Прогнать Golden Dataset** (`tests/golden/test_golden.py`, §26
   ADDENDUM) — регрессия на зафиксированном наборе кластеров с
   известными ожидаемыми результатами. Красный Golden Dataset при MAJOR
   — ожидаемо, если изменение алгоритма намеренно меняет вывод;
   тогда `tests/golden/expected/golden_synthesis.json` обновляется
   осознанно, не автоматически.
3. **Dry-run diff перед применением к продакшен-кешу** —
   `python3 scripts/rebuild_synthesis.py` (без `--apply`) на текущем
   `synthesis_cache.json`: печатает diff по каждому кластеру
   (tension/phase/narrative) между старым и новым алгоритмом, ничего не
   пишет. Это единственный способ увидеть эффект MAJOR/MINOR-изменения
   на реальных данных до того, как он попадёт в прод — см. §18.4
   ADDENDUM (REM-M01, Wave 3) про разницу между этим инструментом и
   обычной пересборкой `synthesizer.py::main()`.
4. **Смотреть предупреждение quality_report.py** при MAJOR-изменении —
   §25.3 ADDENDUM описывает, что старые синтезы (созданные предыдущим
   MAJOR) должны быть помечены как рекомендуемые к перегенерации.
   *Ограничение на 2026-07-02: сам механизм предупреждения
   (`check_major_version_change()` в `quality_report.py`) не
   реализован — см. §25.3bis. Пока MAJOR-релиз требует ручной проверки:
   какие кластеры используют старые синтезы, стоит ли применять
   `--apply` сразу ко всем.*
5. **PR по обычному потоку** (`feature/algorithm-vX.Y.Z` → `develop` →
   `main`, см. Branch Strategy выше) — Contract Tests и основной
   pytest-набор в `deploy.yml` покрывают структурную валидность,
   Golden Dataset запускается в этом же наборе
   (`tests/unit/ tests/golden/ tests/integration/`).
6. **После merge в `main`** — `synthesize` job в `deploy.yml`
   автоматически перестраивает `synthesis_cache.json` новым алгоритмом
   для всех кластеров (полный, не dry-run прогон) при следующем push.
   Если шаг 3 уже показал приемлемый diff — это ожидаемо и безопасно.

### Что осознанно не входит в этот процесс

- **Формальный CHANGELOG для кода** (не для `CLAUDE.md`, у которого
  свой `CHANGELOG.md`) — не создаётся отдельно. История версий
  алгоритма прослеживается через commit messages (`feat:`/`fix:` с
  ссылкой на `ALGORITHM_VERSION`) и `git log -- scripts/synthesizer.py`
  — заводить отдельный файл-дубликат этой истории вне scope D08 (1 час,
  Technical Writer); если станет реальной болью — отдельный тикет.
- **Автоматическое версионирование** (semantic-release и подобное) —
  `ALGORITHM_VERSION` меняется вручную, осознанно, при каждом релизе;
  инструмент, которые делает это автоматически по commit message
  convention, не нужен на текущем масштабе (5 кластеров, редкие
  изменения алгоритма).

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
