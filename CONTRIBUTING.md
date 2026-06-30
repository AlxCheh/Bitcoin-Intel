# Contributing to Bitcoin Intel

> Перед первым PR прочитать [`docs/CODING_STANDARDS.md`](docs/CODING_STANDARDS.md).
> Для изменений `index.html` — обязательно [`docs/spec-pilot.md`](docs/spec-pilot.md).
> Для добавления сигнала — алгоритм в [`CLAUDE.md`](CLAUDE.md), не код.

---

## Commit message convention

Проект использует [Conventional Commits](https://www.conventionalcommits.org/).

| Префикс | Когда использовать |
|---------|---------------------|
| `feat:` | Новый компонент или функциональность |
| `fix:` | Исправление бага |
| `docs:` | Изменение документации |
| `test:` | Добавление или изменение тестов |
| `chore:` | CI, зависимости, конфигурация |
| `refactor:` | Рефакторинг без изменения поведения |

Формат: `тип: краткое описание в повелительном наклонении`.

```
feat: add contradiction cycle detection to validate_relationships.py
fix: handle empty signals.json in quality_report.py
docs: update CODING_STANDARDS.md with import order rule
test: add golden case for tension formula validation
chore: pin flake8 version in requirements.txt
```

Коммиты с новым сигналом — отдельная категория, не код:

```
signal: STR-2026-0630-001 — Strategy NAV discount widens to 0.79x
```

## Branch naming

`{тип}/{краткое-описание-через-дефис}`:

```
feat/contradiction-cycle-detection
fix/synthesizer-hash-determinism
docs/coding-standards
```

## PR process

1. Создать ветку от `main` по правилу naming выше.
2. Внести изменения, закоммитить по convention.
3. Открыть PR в `main` (репозиторий использует single-branch flow — `develop` не используется).
4. Дождаться зелёного CI (`validate` job: lint → integrity check → tests → security audit).
5. Пройти review.
6. Merge — после merge автоматически запускается `synthesize` и `deploy` (см. [`DEPLOYMENT.md`](DEPLOYMENT.md)).

## Review checklist

Перед запросом review убедиться:

- [ ] Тесты написаны для нового кода (`tests/unit/` или `tests/integration/`)
- [ ] Docstring добавлен в формате Google style (см. `docs/CODING_STANDARDS.md`)
- [ ] `flake8 .` и `black --check .` проходят без ошибок
- [ ] Если менялся `signals.json` или `SIGNALS.md` — оба файла обновлены вместе
- [ ] Если менялась структура/визуал `index.html` — `docs/spec-pilot.md` прочитан и применён
- [ ] `CLAUDE.md` обновлён, если изменение затрагивает алгоритм обработки сигнала или схему
- [ ] При изменении `CLAUDE.md` — версия в шапке и `CHANGELOG.md` обновлены

## Вопросы

Если что-то не описано здесь — сначала проверить [`docs/ONBOARDING.md`](docs/ONBOARDING.md)
и [`docs/API.md`](docs/API.md). Если ответа всё ещё нет — завести issue с тегом `question`.
