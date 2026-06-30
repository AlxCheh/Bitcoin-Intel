# IRR Implementation Plan
## Реализация Required Actions из IRR_REPORT.md
## Статус: 6/6 DONE · Создан: 2026-06-29 · Обновлён: 2026-06-30

> **Основание:** Implementation Review Board, IRR_REPORT.md  
> **Вердикт:** READY WITH CONDITIONS (6 условий)  
> **Цель:** Подготовить документацию для команды 10–20 разработчиков

---

## Чеклист выполнения

- [x] Шаг 1 — README.md (IRB-B1) · 2026-06-30
- [x] Шаг 2 — Coding Standards (IRB-B2) · 2026-06-30
- [x] Шаг 3 — requirements.txt (IRB-B3) · 2026-06-30
- [x] Шаг 4 — docs/ реструктуризация (IRB-B5) · 2026-06-30
- [x] Шаг 5 — Component README (Condition 5) · 2026-06-30
- [x] Шаг 6 — CONTRIBUTING.md (Condition 6) · 2026-06-30

Все 6 условий IRR_REPORT.md закрыты. План полностью выполнен.

---

## Шаг 1 — README.md (IRB-B1) · DONE

**Файл:** `README.md` (сейчас = одна строка `# Bitcoin-Intel`)  
**Приоритет:** ВЫСОКИЙ — первое что видит любой разработчик

**Содержимое:**
- Описание проекта (что это, для кого, какую задачу решает)
- Быстрый старт для аналитика (добавить сигнал)
- Быстрый старт для разработчика (клонировать, запустить тесты)
- Структура репозитория с пояснениями
- Ссылки на ключевые документы (CLAUDE.md, docs/ALGORITHM.md, docs/ONBOARDING.md)
- Статус CI badge
- Ссылка на сайт

---

## Шаг 2 — Coding Standards (IRB-B2) · DONE

**Файлы:**
- `docs/CODING_STANDARDS.md` — style guide
- `pyproject.toml` — конфигурация инструментов
- `.github/workflows/deploy.yml` — добавить шаг линтера

**Содержимое CODING_STANDARDS.md:**
- Python style: PEP 8 + Black форматтер
- Именование: файлы snake_case, классы PascalCase, константы UPPER_CASE
- Docstring формат: Google style
- Импорты: stdlib → domain → infrastructure → scripts (без circular)
- Куда добавлять новые компоненты:
  - Доменная логика → `domain/`
  - Инфраструктурный код → `infrastructure/`
  - CLI инструменты аналитика → `scripts/`
  - Тесты → `tests/unit/` или `tests/integration/`
- Правило именования тестов: `test_{component}_{scenario}.py`

**pyproject.toml:**
```toml
[tool.flake8]
max-line-length = 100
exclude = .git,__pycache__,archive/

[tool.black]
line-length = 100
target-version = ["py311"]
```

**deploy.yml — добавить после Set up Python в validate job:**
```yaml
- name: Lint
  run: |
    pip install flake8 --quiet
    flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```
(Только критические ошибки — E9xx, F63x, F7x, F82x — не стилевые)

---

## Шаг 3 — requirements.txt (IRB-B3) · DONE

**Файл:** `requirements.txt`

**Содержимое:**
```
# Core — нет внешних зависимостей (только stdlib)
# Python >= 3.11 required

# Development & Testing
pytest>=8.0.0,<9.0.0
hypothesis>=6.100.0,<7.0.0
flake8>=7.0.0,<8.0.0

# Optional: Backend Phase 4
# fastapi>=0.111.0,<1.0.0
# uvicorn>=0.29.0,<1.0.0
# sqlalchemy>=2.0.0,<3.0.0
```

---

## Шаг 4 — docs/ реструктуризация (IRB-B5) · DONE

**Действие:** скопировать активные документы из `archive/` в `docs/`

| Откуда | Куда |
|--------|------|
| `archive/ALGORITHM.md` | `docs/ALGORITHM.md` |
| `archive/BLUEPRINT.md` | `docs/BLUEPRINT.md` |
| `archive/BLUEPRINT_ADDENDUM.md` | `docs/BLUEPRINT_ADDENDUM.md` |
| `archive/SYNTHESIS_ARCHITECTURE.md` | `docs/SYNTHESIS_ARCHITECTURE.md` |

Оригиналы в archive/ — не удалять (git history).
Добавить в начало каждого файла в archive/ шапку:
```
> ⚠️ Этот файл перемещён. Актуальная версия: docs/FILENAME.md
```

---

## Шаг 5 — Component README (Condition 5) · DONE

**Файлы:**
- `domain/README.md`
- `scripts/README.md`
- `infrastructure/README.md`

**Содержимое каждого:**
- Назначение директории
- Список файлов с однострочным описанием
- Правило: что добавлять сюда, что — нет
- Правило именования новых файлов

---

## Шаг 6 — CONTRIBUTING.md (Condition 6) · DONE

**Файл:** `CONTRIBUTING.md`

**Содержимое:**
- Commit message convention (Conventional Commits):
  - `feat:` — новый компонент или функциональность
  - `fix:` — исправление бага
  - `docs:` — изменение документации
  - `test:` — добавление тестов
  - `chore:` — CI, зависимости, конфигурация
  - `refactor:` — рефакторинг без изменения функциональности
- Branch naming: `feat/`, `fix/`, `docs/`
- PR process: ветка → PR в develop → CI зелёный → review → merge
- Review checklist: тесты написаны, docstring добавлен, CLAUDE.md обновлён если нужно

---

## Порядок выполнения

```
Шаг 1 (README)  →  Шаг 3 (requirements)  →  Шаг 2 (Coding Standards)
     ↓
Шаг 4 (docs/)   →  Шаг 5 (Component README)  →  Шаг 6 (CONTRIBUTING)
```

Шаги 1–3 и 4–6 можно выполнять параллельно.  
Шаг 2 зависит от Шага 3 (ссылается на requirements.txt).  
Шаг 5 зависит от Шага 2 (ссылается на Coding Standards).

---

## Definition of Done для этого плана

- [ ] `README.md` — открыть на GitHub, убедиться что новый человек понимает проект за 2 минуты
- [ ] `pyproject.toml` — `flake8 .` не выдаёт критических ошибок на текущем коде
- [ ] CI validate job — шаг Lint зелёный
- [ ] `requirements.txt` — `pip install -r requirements.txt && pytest` работает с нуля
- [ ] `docs/ALGORITHM.md` существует и открывается
- [ ] `domain/README.md` — новый разработчик понимает куда добавить новый exception
- [ ] `CONTRIBUTING.md` — первый коммит нового разработчика соответствует convention

---

*Создан: 2026-06-29 · Следующая сессия: реализация всех 6 шагов*
