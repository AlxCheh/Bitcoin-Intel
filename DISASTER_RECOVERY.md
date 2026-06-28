# DISASTER_RECOVERY.md
## Bitcoin Intel — Процедуры восстановления

> **Версия:** 1.0 · **Дата:** 2026-06-28  
> **Статус:** BLOCKER B4 — закрыт

---

## RTO / RPO по сценариям

| Сценарий | RTO (цель восстановления) | RPO (допустимая потеря данных) | Приоритет |
|----------|--------------------------|-------------------------------|-----------|
| S1: повреждён `signals.json` | < 15 минут | 0 (git-история) | Критический |
| S2: ошибочно добавлен сигнал | < 10 минут | последний сигнал | Высокий |
| S3: повреждён `synthesis_cache` | < 30 минут | кеш пересчитывается | Средний |
| S4: полная потеря репозитория | < 2 часов | последний push | Низкий |

---

## S1 — Восстановление повреждённого signals.json

**Симптом:** сайт показывает пустой экран или ошибку загрузки данных.

```bash
# 1. Найти последний рабочий коммит
git log --oneline signals.json | head -10

# 2. Проверить файл в том коммите
git show <COMMIT_SHA>:signals.json | python3 -m json.tool > /dev/null
# Если выходит без ошибок — JSON валиден

# 3. Восстановить
git checkout <COMMIT_SHA> -- signals.json

# 4. Проверить локально
python3 -m json.tool signals.json > /dev/null && echo "OK"

# 5. Закоммитить восстановление
git add signals.json
git commit -m "fix: restore signals.json from <COMMIT_SHA>"
git push origin main
```

**Время:** ~10 минут  
**Верификация:** открыть https://alxcheh.github.io/Bitcoin-Intel — карточки сигналов отображаются.

---

## S2 — Удаление ошибочно добавленного сигнала

**Симптом:** в базе появился некорректный или случайный сигнал.

```bash
# 1. Определить id сигнала для удаления, например STR-2026-0628-002

# 2. Удалить из signals.json (Python)
python3 << 'EOF'
import json

with open('signals.json', 'r', encoding='utf-8') as f:
    signals = json.load(f)

target_id = 'STR-2026-0628-002'
before = len(signals)
signals = [s for s in signals if s.get('id') != target_id]
after = len(signals)

with open('signals.json', 'w', encoding='utf-8') as f:
    json.dump(signals, f, ensure_ascii=False, indent=2)

print(f"Удалено: {before - after} сигналов. Осталось: {after}")
EOF

# 3. Удалить из SIGNALS.md вручную — найти блок с id и удалить
# grep -n "STR-2026-0628-002" SIGNALS.md

# 4. Проверить JSON
python3 -m json.tool signals.json > /dev/null && echo "JSON валиден"

# 5. Закоммитить
git add signals.json SIGNALS.md
git commit -m "fix: remove erroneous signal STR-2026-0628-002"
git push origin main
```

**Время:** ~10 минут

---

## S3 — Восстановление synthesis_cache

**Симптом:** блок «Главные нарративы» не отображается или показывает устаревшие данные.

```bash
# Вариант А: пересчитать кеш (когда скрипт создан в Фазе 0)
python3 scripts/rebuild_cache.py

# Вариант Б: удалить кеш — сайт пересчитает при следующем открытии
# (если кеш хранится в data/synthesis_cache.json)
rm data/synthesis_cache.json
git add data/synthesis_cache.json
git commit -m "fix: reset synthesis cache for rebuild"
git push origin main
```

**Время:** ~30 минут (включая время деплоя GitHub Pages)  
**Примечание:** synthesis_cache.json — производный артефакт. Первичные данные — `signals.json`. Потеря кеша не означает потерю данных.

---

## S4 — Полная потеря репозитория

**Симптом:** репозиторий AlxCheh/Bitcoin-Intel удалён или недоступен.

```bash
# 1. Создать новый репозиторий на GitHub: AlxCheh/Bitcoin-Intel

# 2. Восстановить из локальной копии (если есть)
git remote set-url origin https://github.com/AlxCheh/Bitcoin-Intel.git
git push --mirror origin

# 3. Если локальной копии нет — восстановить из резервной копии
tar -xzf bitcoin-intel-backup-YYYY-MM-DD.tar.gz
cd Bitcoin-Intel
git init
git remote add origin https://github.com/AlxCheh/Bitcoin-Intel.git
git add .
git commit -m "restore: full repository from backup"
git push -u origin main

# 4. Включить GitHub Pages в настройках репозитория:
# Settings → Pages → Source: Deploy from branch → main → / (root)
```

**Время:** ~2 часа  
**Профилактика:** еженедельный backup (см. ниже).

---

## Скрипт резервного копирования

Сохранить как `scripts/backup.sh`:

```bash
#!/bin/bash
# backup.sh — еженедельный архив репозитория Bitcoin Intel
# Запускать: bash scripts/backup.sh

set -e

REPO_DIR="$(git rev-parse --show-toplevel)"
BACKUP_DIR="${HOME}/bitcoin-intel-backups"
DATE=$(date +%Y-%m-%d)
ARCHIVE="${BACKUP_DIR}/bitcoin-intel-backup-${DATE}.tar.gz"

mkdir -p "${BACKUP_DIR}"

tar -czf "${ARCHIVE}" \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='__pycache__' \
  -C "$(dirname ${REPO_DIR})" \
  "$(basename ${REPO_DIR})"

echo "✓ Backup создан: ${ARCHIVE}"
echo "  Размер: $(du -sh ${ARCHIVE} | cut -f1)"

# Удалить архивы старше 30 дней
find "${BACKUP_DIR}" -name "*.tar.gz" -mtime +30 -delete
echo "✓ Старые архивы очищены"
```

**Запуск:** `bash scripts/backup.sh`  
**Рекомендуемая частота:** еженедельно (добавить в cron или запускать вручную).

---

## DR Тест — результат

**Дата теста:** 2026-06-28  
**Сценарий:** S2 (удаление тестового сигнала)

```
Шаг 1: добавлен тестовый сигнал TEST-2026-0628-000 в signals.json
Шаг 2: выполнена процедура S2
Шаг 3: проверка — python3 -m json.tool signals.json → OK
Шаг 4: сигнал TEST-2026-0628-000 отсутствует в файле
Результат: ✅ PASSED — процедура работает, время выполнения ~5 минут
```

---

*DISASTER_RECOVERY.md · v1.0 · 2026-06-28 · Закрывает BLOCKER B4*
