# Bitcoin Intel

[![Validate, Synthesize and Deploy](https://github.com/AlxCheh/Bitcoin-Intel/actions/workflows/deploy.yml/badge.svg)](https://github.com/AlxCheh/Bitcoin-Intel/actions/workflows/deploy.yml)

> Образовательный ресурс о Bitcoin. **Только Bitcoin — никаких других тем.**

🌐 Сайт: **https://alxcheh.github.io/Bitcoin-Intel**

---

## Что это

Bitcoin Intel собирает значимые рыночные, on-chain и нарративные события вокруг Bitcoin,
структурирует их в **сигналы** и автоматически синтезирует из них **нарративы** — карточки
«Главные нарративы» на сайте, которые показывают не разрозненные факты, а противоречия и
структурные сдвиги в системе.

Каждый сигнал — это не новость, а интерпретированный факт со связями: что он подтверждает,
чему противоречит, из какого контекста вырастает. Детерминированный синтезатор (`scripts/synthesizer.py`)
собирает из этих связей нарративную карту без участия LLM на этапе генерации текста сайта —
весь текст пишется аналитиком на этапе создания сигнала, алгоритм только **выбирает лучшее**.

---

## Быстрый старт для аналитика

Задача аналитика — превращать события в сигналы. Полный алгоритм (8 шагов) описан в [`CLAUDE.md`](CLAUDE.md).

1. Прочитать [`CLAUDE.md`](CLAUDE.md) — главный документ с алгоритмом, схемой сигнала, метаметками.
2. Посмотреть текущее качество базы:
   ```bash
   python3 scripts/quality_report.py
   ```
3. Полный гид для первого сигнала → [`docs/ONBOARDING.md`](docs/ONBOARDING.md).

Сигнал добавляется в `signals.json` и `SIGNALS.md` одновременно — `index.html` руками не трогаем,
сайт читает данные через `fetch`.

---

## Быстрый старт для разработчика

```bash
git clone https://github.com/AlxCheh/Bitcoin-Intel.git
cd Bitcoin-Intel
python3 -m pip install -r requirements.txt

# Запустить тесты (детерминированно — обязателен фиксированный hash seed)
PYTHONHASHSEED=0 python3 -m pytest tests/unit/ tests/golden/ tests/integration/ -v

# Проверить целостность данных
python3 scripts/validate_integrity.py

# Пересобрать нарративы локально
PYTHONHASHSEED=0 python3 scripts/synthesizer.py
```

Перед изменением структуры или визуала `index.html` — обязательно прочитать
[`docs/spec-pilot.md`](docs/spec-pilot.md). Это требование, а не рекомендация: алгоритм сборки
сайта специфичен и не очевиден из самого HTML.

Стиль кода, naming conventions и куда класть новые файлы → [`docs/CODING_STANDARDS.md`](docs/CODING_STANDARDS.md).
Правила коммитов и процесс PR → [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## Структура репозитория

```
Bitcoin-Intel/
├── index.html              # Единственный файл сайта (статика, fetch из signals.json)
├── signals.json            # База сигналов — единственный источник правды для данных
├── SIGNALS.md              # Читаемый текстовый архив сигналов (дублирует signals.json)
├── ENTITIES.json           # База артефактов: L2, протоколы, компании, фонды
├── ontology.json           # Онтология сущностей для синтезатора
│
├── domain/                 # Доменная логика: события, исключения, state machine, валидация
├── infrastructure/         # Инфраструктура: file locking, логирование, хранилище связей
├── scripts/                # CLI-инструменты: add_signal, synthesizer, quality_report и др.
├── config/                 # Централизованные настройки и константы
├── data/                   # Производные данные: synthesis_cache.json, events.jsonl
│
├── tests/
│   ├── unit/                # Юнит-тесты компонентов
│   ├── integration/         # Сквозные сценарии (workflow сигнала, регрессия нарратива)
│   └── golden/              # Golden dataset — фиксированные сигналы → ожидаемый синтез
│
├── docs/                   # Архитектурная и процессная документация (актуальная)
├── archive/                # Устаревшие версии документов (история, не редактировать)
│
├── CLAUDE.md                # Алгоритм обработки сигнала — главный рабочий документ
├── CHANGELOG.md             # История версий CLAUDE.md
└── .github/workflows/       # CI: валидация → синтез → деплой на GitHub Pages
```

---

## Ключевые документы

| Документ | Назначение |
|----------|-----------|
| [`CLAUDE.md`](CLAUDE.md) | Алгоритм обработки сигнала, схема объекта, метаметки, кластеры |
| [`docs/ONBOARDING.md`](docs/ONBOARDING.md) | Гид для нового аналитика — первый сигнал за 5 шагов |
| [`docs/ALGORITHM.md`](docs/ALGORITHM.md) | Алгоритм нарративного синтеза — как работает блок «Обзор» |
| [`docs/spec-pilot.md`](docs/spec-pilot.md) | Алгоритм сборки `index.html` — обязателен перед правкой сайта |
| [`docs/CODING_STANDARDS.md`](docs/CODING_STANDARDS.md) | Style guide, naming, куда класть новые компоненты |
| [`docs/API.md`](docs/API.md) | Спецификация backend API |
| [`docs/ARR_EXECUTION_STATUS.md`](docs/ARR_EXECUTION_STATUS.md) | Статус выполнения ARR v3 — что закрыто, что осталось осознанно открытым |
| [`SECURITY.md`](SECURITY.md) | Threat model, политика секретов |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | CI/CD pipeline, branch strategy, rollback |
| [`DISASTER_RECOVERY.md`](DISASTER_RECOVERY.md) | RTO/RPO, backup, runbook |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Commit convention, branch naming, PR process |
| [`archive/STRUCTURE.md`](archive/STRUCTURE.md) | Архитектура и дизайн-система сайта (исторический, до перехода на Narrative Intelligence Platform) |

---

## CI/CD

Каждый push в `main` проходит три стадии (`.github/workflows/deploy.yml`):

1. **Validate** — целостность `signals.json` / `ENTITIES.json`, уникальность ID, тесты, security audit
2. **Synthesize** — пересборка `data/synthesis_cache.json` детерминированным синтезатором
3. **Deploy** — публикация на GitHub Pages

---

## Лицензия и статус

Проект в активной разработке. Образовательный, некоммерческий ресурс о Bitcoin.

<!-- IRP v1 M05: Branch Protection verification 2026-07-01T11:44:42Z -->

<!-- M04 flow test 1782926397 -->
