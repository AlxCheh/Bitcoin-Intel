# Onboarding Guide — Bitcoin Intel

> Для нового аналитика. Читать перед первым сигналом.

---

## Что это

Образовательный ресурс о Bitcoin. Сайт: https://alxcheh.github.io/Bitcoin-Intel  
Задача аналитика — находить значимые события, превращать их в структурированные сигналы,
которые питают нарративный движок и блок «Обзор» на сайте.

---

## Быстрый старт (5 шагов)

### 1. Прочитать CLAUDE.md

Главный документ. Содержит алгоритм обработки сигнала (шаги 1–8), схему объекта,
все метаметки и правила. Начинать здесь.

### 2. Посмотреть существующие сигналы

```bash
# Последние 5 сигналов
python3 -c "
import json
data = json.load(open('signals.json'))
signals = data.get('signals', data)
for s in sorted(signals, key=lambda x: x['date'], reverse=True)[:5]:
    print(s['id'], s['date'], s['signal'][:60])
"
```

### 3. Посмотреть качество базы

```bash
python3 scripts/quality_report.py
```

### 4. Добавить первый сигнал

```bash
# Создать файл signal.json со структурой из CLAUDE.md
# Проверить без записи
python3 scripts/add_signal.py --file signal.json --dry-run

# Добавить
python3 scripts/add_signal.py --file signal.json
```

### 5. CI сделает остальное

После `git push` — автоматически: тесты → синтез → деплой → сайт обновлён.

---

## Алгоритм добавления сигнала

Полный алгоритм в CLAUDE.md. Коротко:

```
Материал → Исследование (fetch + web_search) → Разбор (4 пункта)
→ Кластеризация → Связывание → Синтез (tension + macro_implication)
→ Проверка → Оформление (ID) → Запись в signals.json + SIGNALS.md
```

**Ключевые правила:**
- `tension` — формула «X vs Y» / «X несмотря на Y», начинается с заглавной буквы
- `macro_implication` — структурное изменение, не пересказ события, минимум 50 символов
- `id` — формат `PREFIX-YYYY-MMDD-NNN`, проверить уникальность перед записью
- Всегда два файла одновременно: `signals.json` + `SIGNALS.md`

---

## Инструменты аналитика

| Скрипт | Что делает |
|--------|-----------|
| `scripts/add_signal.py --file X --dry-run` | Валидация без записи |
| `scripts/quality_report.py` | Здоровье базы сигналов |
| `scripts/history_query.py --tension-history CLUSTER` | История нарративов |
| `scripts/validate_relationships.py` | Проверка связей |
| `scripts/approve_synthesis.py --list` | Синтезы ожидающие утверждения |
| `scripts/validate_integrity.py` | Целостность всех файлов |

---

## Структура репозитория

```
signals.json          ← база сигналов (редактировать только через add_signal.py)
SIGNALS.md            ← читаемый архив сигналов
ENTITIES.json         ← база артефактов (L2, протоколы, компании)
CLAUDE.md             ← главный документ аналитика
data/
  synthesis_cache.json ← предвычисленные нарративы (генерируется CI)
scripts/              ← инструменты аналитика
domain/               ← бизнес-логика
docs/                 ← документация (ARR, спеки, ADR)
tests/                ← тесты (запускает CI)
```

---

## Частые вопросы

**Почему сигнал не появился на сайте?**  
CI занимает ~2 минуты. Если через 5 минут нет — проверить GitHub Actions.

**Как изменить tension существующего сигнала?**  
Напрямую в `signals.json`. Но если сигнал уже использован в утверждённом синтезе — нельзя.

**Как посмотреть что сейчас в Обзоре?**  
`data/synthesis_cache.json` — это именно то что видит сайт.

**Что такое кластер и как выбрать?**  
Таблица кластеров в CLAUDE.md. Кластер = группа сигналов с общим `tension`. Новый кластер — при 2+ сигналах с общим противоречием которого нет в существующих.

---

## Контакты и помощь

При вопросах по алгоритму → CLAUDE.md  
При вопросах по архитектуре → docs/BLUEPRINT.md и docs/BLUEPRINT_ADDENDUM.md  
При ошибках CI → GitHub Actions → View workflow run
