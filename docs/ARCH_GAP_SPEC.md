# ARCH_GAP_SPEC — Спека для устранения архитектурных дыр
## Bitcoin Intel Narrative Intelligence Platform
## Версия: 1.0 · Дата: 2026-06-28 · Статус: ГОТОВО К РЕАЛИЗАЦИИ

> **Основание:** Architecture Readiness Review (ARR_REPORT.md, 2026-06-28)  
> **Охват:** 5 Blockers + 5 Critical + 7 Major  
> **Приоритет:** Blockers → Critical → Major  
> **Цель:** Закрыть все дыры и получить статус READY от ARB при повторном ARR

---

## Структура документа

| Приоритет | Блок | Что закрывает |
|-----------|------|--------------|
| 🔴 BLOCKER | §1–§5 | B1–B5 — запрещают старт разработки |
| 🟠 CRITICAL | §6–§10 | C1–C5 — высокий риск переработки |
| 🟡 MAJOR | §11–§17 | M1–M7 — до конца Фазы 0 |

---

# BLOCKERS

---

## §1. B1 — Детерминированный Bridge Selection

**Проблема из ARR:** `abs(hash(seed)) % len(options)` — Python hash() непредсказуем между запусками из-за PYTHONHASHSEED. Гарантия детерминизма нарушена.

**Файл:** `domain/synthesizer.py`, функция `select_bridge()`

### Решение

Заменить `hash(seed)` на детерминированный алгоритм на основе `hashlib`.

```python
# БЫЛО — НЕ ДЕТЕРМИНИРОВАНО
def select_bridge(phase: str, seed: int) -> str:
    options = BRIDGES[phase]
    return options[abs(hash(seed)) % len(options)]

# СТАЛО — ДЕТЕРМИНИРОВАНО
import hashlib

def select_bridge(phase: str, seed: int) -> str:
    """
    Детерминированный выбор bridge по фазе и seed.
    Гарантия: одни и те же аргументы → один и тот же результат
    при любом значении PYTHONHASHSEED на любой машине.
    """
    options = BRIDGES[phase]
    if not options:
        raise ValueError(f"No bridges defined for phase: {phase}")
    # SHA-256 детерминирован по стандарту — не зависит от PYTHONHASHSEED
    digest = hashlib.sha256(f"{phase}:{seed}".encode("utf-8")).digest()
    index = int.from_bytes(digest[:4], byteorder="big") % len(options)
    return options[index]
```

### Тест детерминизма

```python
# tests/unit/test_synthesizer_determinism.py
import subprocess, sys

def test_bridge_selection_is_deterministic():
    """Один и тот же seed → один и тот же bridge при разных PYTHONHASHSEED"""
    results = set()
    for seed_val in ["0", "42", "999"]:
        out = subprocess.check_output(
            [sys.executable, "-c",
             "from domain.synthesizer import select_bridge; print(select_bridge('active', 12345))"],
            env={"PYTHONHASHSEED": seed_val}
        )
        results.add(out.strip())
    assert len(results) == 1, f"Non-deterministic output: {results}"
```

### Acceptance критерий

- `select_bridge('active', 12345)` возвращает одно и то же значение при `PYTHONHASHSEED=0`, `PYTHONHASHSEED=42`, `PYTHONHASHSEED=random`
- Тест проходит в CI при трёх разных env запусках

---

## §2. B2 — Алгоритм semantic_inverse_score

**Проблема из ARR:** Contradiction Detector использует «keyword overlap» без спецификации. Precision > 60% заявлена, но недостижима без конкретного алгоритма.

**Файл:** `domain/contradiction_detector.py`, функция `semantic_inverse_score()`

### Алгоритм (полная спецификация)

`semantic_inverse_score(a: str, b: str) -> float` — число от 0.0 до 1.0.  
Возвращает насколько два `macro_implication` описывают несовместимые состояния.

#### Шаг 1 — Нормализация

```python
import re

def normalize(text: str) -> set[str]:
    """Токенизация с удалением стоп-слов и пунктуации."""
    STOP_WORDS = {
        # Русские
        "и", "в", "на", "не", "что", "с", "а", "но", "как", "это",
        "для", "по", "из", "при", "к", "от", "до", "о", "за", "же",
        "то", "или", "если", "то", "так", "уже", "он", "она", "они",
        "его", "её", "их", "все", "которые", "через", "между",
        # Английские (если попадут)
        "the", "a", "an", "and", "or", "but", "in", "on", "at",
        "to", "for", "of", "with", "by", "from", "as", "is", "are"
    }
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)  # убрать пунктуацию
    tokens = text.split()
    return {t for t in tokens if t not in STOP_WORDS and len(t) > 2}
```

#### Шаг 2 — Jaccard similarity

```python
def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Мера пересечения множеств слов."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union
```

#### Шаг 3 — Semantic polarity check

```python
# Пары антонимов которые сигнализируют о противоречии
ANTONYM_PAIRS = [
    ("рост", "падение"), ("рост", "снижение"), ("рост", "обвал"),
    ("приток", "отток"), ("покупка", "продажа"),
    ("позитив", "негатив"), ("усиление", "ослабление"),
    ("накопление", "ликвидация"), ("инфляция", "дефляция"),
    ("риск", "безопасность"), ("давление", "поддержка"),
    ("дефицит", "избыток"), ("рекорд", "минимум"),
    ("бычий", "медвежий"), ("рост", "сокращение"),
    ("укрепление", "ослабление"), ("эмиссия", "дефицит"),
]

def polarity_conflict(tokens_a: set, tokens_b: set) -> float:
    """
    Возвращает 1.0 если обнаружен антоним из одного утверждения в другом.
    Возвращает 0.0 если антонимов нет.
    """
    for word_a, word_b in ANTONYM_PAIRS:
        if (word_a in tokens_a and word_b in tokens_b) or \
           (word_b in tokens_a and word_a in tokens_b):
            return 1.0
    return 0.0
```

#### Шаг 4 — Итоговая формула

```python
def semantic_inverse_score(impl_a: str, impl_b: str) -> float:
    """
    Оценка семантической несовместимости двух macro_implication.

    Диапазон: 0.0 (полностью совместимы) → 1.0 (прямое противоречие)

    Формула:
        score = (1 - jaccard) * 0.4 + polarity * 0.6

    Логика весов:
        - polarity_conflict (60%) — прямой антоним = сильный сигнал противоречия
        - (1 - jaccard) (40%) — малое пересечение слов усиливает оценку

    Threshold для вывода в contradicts: score >= 0.5
    """
    tokens_a = normalize(impl_a)
    tokens_b = normalize(impl_b)

    jaccard = jaccard_similarity(tokens_a, tokens_b)
    polarity = polarity_conflict(tokens_a, tokens_b)

    score = (1 - jaccard) * 0.4 + polarity * 0.6

    return round(min(1.0, max(0.0, score)), 3)


# Константа threshold — единое место для изменения
CONTRADICTION_THRESHOLD = 0.5

def signals_contradict(signal_a: dict, signal_b: dict) -> bool:
    """
    Возвращает True если macro_implication двух сигналов несовместимы.
    Используется в contradiction_detector.py.
    """
    impl_a = signal_a.get("macro_implication", "")
    impl_b = signal_b.get("macro_implication", "")
    if not impl_a or not impl_b:
        return False
    score = semantic_inverse_score(impl_a, impl_b)
    return score >= CONTRADICTION_THRESHOLD
```

### Тесты алгоритма

```python
# tests/unit/test_contradiction_detector.py

def test_obvious_contradiction():
    """Приток ETF vs отток ETF — должно быть contradicts"""
    a = "ETF-приток как структурный спрос — долгосрочные держатели получают новый класс покупателей"
    b = "ETF-отток сигнализирует о выходе институционального капитала из BTC-позиций"
    assert semantic_inverse_score(a, b) >= 0.5

def test_same_direction():
    """Оба positiv на ETF — не должно быть contradicts"""
    a = "ETF-приток как структурный спрос создаёт давление на предложение"
    b = "Институциональный приток через ETF укрепляет позицию BTC как резервного актива"
    assert semantic_inverse_score(a, b) < 0.5

def test_empty_strings():
    """Пустые строки — score 0.0"""
    assert semantic_inverse_score("", "anything") == 0.0
    assert semantic_inverse_score("anything", "") == 0.0

def test_precision_on_golden_pairs():
    """
    Golden Dataset противоречий — precision > 60%.
    Список пар (a, b, expected_contradicts) — минимум 15 пар.
    """
    # Пары загружаются из tests/golden/contradiction_pairs.json
    pairs = load_golden_contradiction_pairs()
    correct = sum(
        1 for a, b, expected in pairs
        if signals_contradict({"macro_implication": a}, {"macro_implication": b}) == expected
    )
    precision = correct / len(pairs)
    assert precision >= 0.6, f"Precision {precision:.2%} below threshold 60%"
```

### Файл Golden Dataset

`tests/golden/contradiction_pairs.json` — создать при реализации, минимум 15 пар:

```json
[
  {
    "a": "ETF-приток как структурный спрос — долгосрочные держатели получают новый класс покупателей",
    "b": "ETF-отток сигнализирует о выходе институционального капитала из BTC-позиций",
    "expected": true,
    "note": "приток vs отток — прямые антонимы"
  }
]
```

### Acceptance критерий

- Precision на Golden Dataset ≥ 60%
- `signals_contradict()` возвращает одинаковый результат при одинаковых входных данных (детерминизм)
- Пустые `macro_implication` → `False`, не exception

---

## §3. B3 — Security Architecture (MVP)

**Проблема из ARR:** Security полностью отсутствует. Нет аутентификации, авторизации, input sanitization.

> **Scope этой спеки:** MVP Security — минимально необходимое для production. Полноценный auth (OAuth, JWT) — Technical Debt After MVP.

### 3.1 Input Sanitization (критично — XSS в HTML)

**Проблема:** поля `tension`, `narrative`, `macro_implication` рендерятся в `index.html`. Если в них попадёт `<script>alert(1)</script>` — XSS.

```python
# infrastructure/sanitizer.py

import html
import re

# Максимальные длины полей (DoS protection)
MAX_LENGTHS = {
    "signal": 200,
    "tension": 300,
    "macro_implication": 500,
    "context": 2000,
    "caveat": 1000,
    "narrative": 3000,
}

# Разрешённые символы в ID
ID_PATTERN = re.compile(r'^[A-Z]{2,5}-\d{4}-\d{4}-\d{3}$')

def sanitize_text(value: str, field: str) -> str:
    """
    Очищает текстовое поле перед записью в JSON.
    1. HTML escape — предотвращает XSS при рендере
    2. Обрезка до MAX_LENGTHS
    3. Удаление управляющих символов
    """
    if not isinstance(value, str):
        raise TypeError(f"Field '{field}' must be string, got {type(value)}")

    # Удалить управляющие символы (кроме \n, \t)
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)

    # HTML escape
    value = html.escape(value, quote=True)

    # Обрезка
    max_len = MAX_LENGTHS.get(field, 5000)
    if len(value) > max_len:
        value = value[:max_len]

    return value.strip()


def sanitize_signal(signal: dict) -> dict:
    """
    Пропускает сигнал через sanitizer перед записью в signals.json.
    Возвращает очищенный dict или бросает ValueError при критических нарушениях.
    """
    sanitized = dict(signal)

    # Валидация ID формата
    signal_id = signal.get("id", "")
    if not ID_PATTERN.match(signal_id):
        raise ValueError(f"Invalid signal ID format: '{signal_id}'")

    # Текстовые поля
    text_fields = ["signal", "tension", "macro_implication", "context", "caveat"]
    for field in text_fields:
        if field in sanitized and sanitized[field]:
            sanitized[field] = sanitize_text(sanitized[field], field)

    # data: list of strings
    if "data" in sanitized:
        sanitized["data"] = [
            sanitize_text(item, "data") for item in sanitized["data"]
            if isinstance(item, str)
        ]

    return sanitized
```

### 3.2 File Permissions

```bash
# scripts/setup_permissions.sh
# Запускать один раз после клонирования репозитория

#!/bin/bash
set -e

# JSON данные — только для чтения для группы (аналитик пишет через скрипты)
chmod 644 signals.json
chmod 644 ENTITIES.json

# synthesis_store — только владелец читает/пишет
chmod 700 synthesis_store/ 2>/dev/null || mkdir -m 700 synthesis_store/

# scripts/ — исполняемые только для владельца
chmod 750 scripts/*.py

echo "✓ Permissions configured"
```

### 3.3 Secrets Management

```python
# config/secrets.py

import os
from pathlib import Path

def get_secret(name: str, required: bool = True) -> str | None:
    """
    Читает секрет из переменной окружения.
    НЕ читает из файлов, НЕ хардкодит значения.

    Порядок поиска:
    1. Переменная окружения (production, CI)
    2. .env файл (только локальная разработка, в .gitignore)
    """
    # Из env
    value = os.environ.get(name)
    if value:
        return value

    # Из .env (локально)
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()

    if required:
        raise EnvironmentError(
            f"Secret '{name}' not found. "
            f"Set environment variable or add to .env file."
        )
    return None
```

```
# .env.example (коммитить)
# .env (в .gitignore — НИКОГДА не коммитить)
GITHUB_TOKEN=ghp_...
```

```
# .gitignore — добавить
.env
*.secret
secrets/
```

### 3.4 Dependency Vulnerability Scanning

```yaml
# .github/workflows/security.yml
name: Security Scan

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 9 * * 1'  # Каждый понедельник

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install pip-audit
        run: pip install pip-audit
      - name: Run audit
        run: pip-audit --requirement requirements.txt --format json > audit.json
      - name: Fail on high severity
        run: |
          VULNS=$(python -c "
          import json
          data = json.load(open('audit.json'))
          highs = [v for v in data.get('vulnerabilities', [])
                   if v.get('fix_versions')]
          print(len(highs))
          ")
          if [ "$VULNS" -gt 0 ]; then
            echo "⛔ Found $VULNS fixable vulnerabilities"
            cat audit.json
            exit 1
          fi
          echo "✓ No fixable vulnerabilities"
```

### Acceptance критерий

- `sanitize_signal()` вызывается в `add_signal.py` перед каждой записью
- `.env` добавлен в `.gitignore`
- `.env.example` закоммичен
- CI запускает `pip-audit` при каждом push в main
- Тест: сигнал с `<script>` в tension → поле сохраняется как `&lt;script&gt;` (не исполняется)

---

## §4. B4 — Disaster Recovery

**Проблема из ARR:** Нет RTO/RPO, backup strategy, corruption recovery procedure.

### 4.1 RTO / RPO

| Метрика | Значение | Обоснование |
|---------|----------|-------------|
| RTO (Recovery Time Objective) | 30 минут | Время восстановления из git backup |
| RPO (Recovery Point Objective) | 24 часа | Частота push в main (при соблюдении workflow) |

### 4.2 Backup Strategy

**Первичный backup: Git репозиторий**

Git — это de facto append-only append история изменений. Каждый коммит в main — это точка восстановления.

```
Backup chain:
  signals.json (main) → git history → GitHub remote
  synthesis_store/     → git history → GitHub remote
  ENTITIES.json        → git history → GitHub remote
```

**Правило:** `signals.json`, `ENTITIES.json`, `synthesis_store/` — всегда в git. Никогда не в `.gitignore`.

**Вторичный backup: автоматический снапшот**

```python
# scripts/backup.py

import json, shutil, hashlib
from datetime import datetime, UTC
from pathlib import Path

BACKUP_TARGETS = [
    "signals.json",
    "ENTITIES.json",
    "synthesis_store/",
]

BACKUP_DIR = Path("backups/")
MAX_BACKUPS = 7  # Хранить 7 последних снапшотов

def create_snapshot() -> Path:
    """
    Создаёт снапшот критических файлов.
    Возвращает путь к директории снапшота.
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    snapshot_dir = BACKUP_DIR / timestamp
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    manifest = {}
    for target in BACKUP_TARGETS:
        src = Path(target)
        if not src.exists():
            continue
        dst = snapshot_dir / src.name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
            # Контрольная сумма
            checksum = hashlib.sha256(src.read_bytes()).hexdigest()
            manifest[str(src)] = checksum

    (snapshot_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )
    print(f"✓ Snapshot created: {snapshot_dir}")

    # Удалить старые снапшоты
    snapshots = sorted(BACKUP_DIR.iterdir())
    for old in snapshots[:-MAX_BACKUPS]:
        shutil.rmtree(old)
        print(f"  Removed old snapshot: {old}")

    return snapshot_dir


if __name__ == "__main__":
    create_snapshot()
```

### 4.3 Corruption Recovery Procedure (Runbook)

#### Сценарий A: signals.json повреждён (невалидный JSON)

```bash
# Шаг 1 — Диагностика
python -m json.tool signals.json
# Если ошибка → файл повреждён

# Шаг 2 — Восстановление из git
git log --oneline signals.json | head -5
# Выбрать последний рабочий коммит
git show COMMIT_SHA:signals.json > signals_recovered.json

# Шаг 3 — Проверка восстановленного файла
python -m json.tool signals_recovered.json > /dev/null && echo "✓ Valid JSON"

# Шаг 4 — Применить
mv signals.json signals_backup_$(date +%Y%m%d).json
mv signals_recovered.json signals.json

# Шаг 5 — Зафиксировать восстановление
git add signals.json
git commit -m "fix: restore signals.json from COMMIT_SHA after corruption"
```

#### Сценарий B: synthesis_store файл повреждён

```bash
# Синтез — пересчитываемые данные. Восстановление = пересчёт.
python scripts/rebuild_synthesis.py --cluster CLUSTER_KEY

# Если весь synthesis_store повреждён
python scripts/rebuild_synthesis.py --all
```

#### Сценарий C: ENTITIES.json повреждён

```bash
# Аналогично сценарию A — восстановить из git
git show HEAD~1:ENTITIES.json > ENTITIES_recovered.json
python -m json.tool ENTITIES_recovered.json > /dev/null && echo "✓ Valid"
mv ENTITIES_recovered.json ENTITIES.json
git add ENTITIES.json && git commit -m "fix: restore ENTITIES.json"
```

### 4.4 Validation Script (запускать после восстановления)

```python
# scripts/validate_integrity.py

import json
from pathlib import Path

def validate():
    errors = []

    # signals.json
    try:
        signals = json.loads(Path("signals.json").read_text())
        if not isinstance(signals, list):
            errors.append("signals.json: root must be array")
        else:
            ids = [s.get("id") for s in signals]
            duplicates = [i for i in ids if ids.count(i) > 1]
            if duplicates:
                errors.append(f"signals.json: duplicate IDs: {set(duplicates)}")
            print(f"✓ signals.json: {len(signals)} signals, {len(set(ids))} unique IDs")
    except Exception as e:
        errors.append(f"signals.json: {e}")

    # ENTITIES.json
    try:
        entities = json.loads(Path("ENTITIES.json").read_text())
        print(f"✓ ENTITIES.json: {len(entities)} entities")
    except Exception as e:
        errors.append(f"ENTITIES.json: {e}")

    # synthesis_store
    store = Path("synthesis_store")
    if store.exists():
        files = list(store.glob("*.json"))
        valid = 0
        for f in files:
            try:
                json.loads(f.read_text())
                valid += 1
            except Exception as e:
                errors.append(f"synthesis_store/{f.name}: {e}")
        print(f"✓ synthesis_store: {valid}/{len(files)} valid files")

    if errors:
        print(f"\n⛔ {len(errors)} integrity errors:")
        for e in errors:
            print(f"  - {e}")
        return False

    print("\n✓ All integrity checks passed")
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if validate() else 1)
```

### Acceptance критерий

- `scripts/backup.py` создаёт снапшот с manifest.json и контрольными суммами
- Runbook для 3 сценариев задокументирован и проверен вручную
- `scripts/validate_integrity.py` проходит на текущих данных
- `backups/` добавлен в `.gitignore` (локальные снапшоты не идут в git)

---

## §5. B5 — Deployment Strategy

**Проблема из ARR:** Команда не знает как, куда и в каком порядке деплоить.

### 5.1 Окружения

| Environment | Назначение | Ветка | URL |
|-------------|-----------|-------|-----|
| `local` | Разработка | любая | `localhost` / file:// |
| `staging` | Проверка перед релизом | `develop` | GitHub Pages preview |
| `production` | Пользователи | `main` | alxcheh.github.io/Bitcoin-Intel |

### 5.2 Branch Strategy

```
main        ← production. Только через PR. Прямой push запрещён.
develop     ← staging. Все фичи мержатся сюда сначала.
feat/*      ← feature branches. Живут до PR в develop.
fix/*       ← hotfix branches. PR напрямую в main при критическом баге.
```

**Правила:**

- Коммит в `main` → автоматический деплой на production (GitHub Actions)
- PR в `main` требует: CI зелёный + ручная проверка на staging
- `feat/*` удаляется после merge

### 5.3 CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  # ── Шаг 1: Валидация данных ─────────────────────────────────
  validate:
    name: Validate data files
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Validate signals.json
        run: |
          python -m json.tool signals.json > /dev/null
          echo "✓ signals.json is valid JSON"

      - name: Validate ENTITIES.json
        run: |
          python -m json.tool ENTITIES.json > /dev/null
          echo "✓ ENTITIES.json is valid JSON"

      - name: Check signal IDs unique
        run: |
          python3 -c "
          import json
          signals = json.load(open('signals.json'))
          ids = [s['id'] for s in signals]
          dupes = [i for i in ids if ids.count(i) > 1]
          if dupes:
              print(f'⛔ Duplicate IDs: {set(dupes)}')
              exit(1)
          print(f'✓ {len(ids)} unique signal IDs')
          "

  # ── Шаг 2: Тесты (когда появятся) ──────────────────────────
  test:
    name: Run tests
    runs-on: ubuntu-latest
    needs: validate
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: python -m pytest tests/ -v --tb=short
        continue-on-error: false

  # ── Шаг 3: Security scan ────────────────────────────────────
  security:
    name: Security audit
    runs-on: ubuntu-latest
    needs: validate
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install pip-audit
      - run: pip-audit --requirement requirements.txt || true
        # || true — не блокировать деплой на первом этапе;
        # убрать || true когда базовые зависимости проверены

  # ── Шаг 4: Деплой (только main) ─────────────────────────────
  deploy:
    name: Deploy to GitHub Pages
    runs-on: ubuntu-latest
    needs: [validate, test]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    permissions:
      contents: read
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/configure-pages@v4
      - uses: actions/upload-pages-artifact@v3
        with:
          path: '.'
      - id: deployment
        uses: actions/deploy-pages@v4
```

### 5.4 Деплой Runbook (пошагово)

```
# ДЕПЛОЙ НОВЫХ СИГНАЛОВ (стандартный workflow)

1. Локально:
   git checkout -b feat/add-signal-STR-2026-XXXX
   # Добавить сигнал в signals.json + SIGNALS.md
   python scripts/validate_integrity.py  # проверить локально
   git add signals.json SIGNALS.md
   git commit -m "feat: add signal STR-2026-XXXX — <короткое описание>"
   git push origin feat/add-signal-STR-2026-XXXX

2. GitHub:
   Создать PR: feat/... → develop
   Дождаться: CI зелёный (validate + test)
   Merge в develop (staging деплой)

3. Проверить на staging:
   Открыть staging URL
   Убедиться что сигнал отображается корректно

4. Merge в main:
   Создать PR: develop → main
   Дождаться: CI зелёный
   Merge — автоматически деплоится на production

# HOTFIX (критический баг в production)

1. git checkout main
   git checkout -b fix/critical-bug-description
   # Исправить
   git push origin fix/critical-bug-description

2. PR: fix/... → main (минуя develop)
   Review → Merge → автодеплой
```

### 5.5 Rollback Procedure

```bash
# Откатить production на предыдущий коммит

# Найти последний рабочий коммит
git log --oneline -10

# Создать revert коммит (НЕ force push)
git revert COMMIT_SHA --no-edit
git push origin main
# GitHub Actions автоматически задеплоит откат
```

### Acceptance критерий

- `.github/workflows/deploy.yml` присутствует в репозитории
- Push в main → автодеплой на GitHub Pages (проверить вручную)
- PR в main не проходит если `signals.json` невалиден
- Rollback протестирован: revert коммит деплоится корректно

---

# CRITICAL

---

## §6. C1 — MAX_POSSIBLE_SCORE

**Проблема из ARR:** Формула confidence несостоятельна без определённого MAX_POSSIBLE_SCORE.

### Решение

```python
# domain/synthesizer.py

def calculate_max_possible_score(signals: list[dict]) -> float:
    """
    MAX_POSSIBLE_SCORE — теоретический максимум для данного набора сигналов.

    Каждый сигнал может принести максимум:
        contradicts score: +5 (если у сигнала есть хотя бы 1 contradicts)
        tension score:     +2 (если tension непустой)
        weight score:      +4 (onchain = максимальный вес)
        freshness score:   +3 (сигнал ≤ 7 дней)
        role score:        +4 (trigger = максимальная роль)
    
    Итого на сигнал: 5 + 2 + 4 + 3 + 4 = 18
    MAX_POSSIBLE_SCORE = 18 * len(signals)
    """
    PER_SIGNAL_MAX = 18.0
    return PER_SIGNAL_MAX * max(len(signals), 1)


def calculate_confidence(score: float, signals: list[dict]) -> float:
    """
    Нормализованный confidence в диапазоне [0.1, 1.0].
    
    Формула: score / MAX_POSSIBLE_SCORE * penalty_multipliers
    
    Penalty multipliers (последовательное умножение):
        × 0.5  если нет сигналов с contradicts
        × 0.8  если нет tension у победителя кластера
        × 0.7  если все сигналы старше 30 дней
        × 0.6  если нет resolution в кластере
    """
    max_score = calculate_max_possible_score(signals)
    base = score / max_score  # нормализованный [0, 1]

    # Penalty multipliers
    has_contradicts = any(s.get("links", {}).get("contradicts") for s in signals)
    has_tension_winner = any(s.get("tension") for s in signals
                             if s.get("links", {}).get("contradicts"))
    all_old = all(is_older_than_days(s.get("date", ""), 30) for s in signals)
    has_resolution = any(s.get("narrative_role") == "resolution" for s in signals)

    multiplier = 1.0
    if not has_contradicts:
        multiplier *= 0.5
    if not has_tension_winner:
        multiplier *= 0.8
    if all_old:
        multiplier *= 0.7
    if not has_resolution:
        multiplier *= 0.6

    confidence = base * multiplier
    return round(max(0.1, min(1.0, confidence)), 3)
```

---

## §7. C2 — Переходный период links.* → relationships.json

**Проблема из ARR:** Неясно в переходный период откуда читать связи.

### Правило переходного периода

**Фаза A (текущая — до реализации `relationships.json`):**
- Все связи хранятся в `signals.json` в поле `links`
- `relationships.json` не существует
- Читать: только из `signals[*].links`

**Фаза B (после реализации `relationships.json`, Roadmap Фаза 1):**
- `relationships.json` создан
- `signals.json` поле `links` помечено DEPRECATED но не удалено
- Читать: из `relationships.json` (primary) + `signals[*].links` (fallback для старых сигналов без записи в relationships)

**Фаза C (после migration script):**
- `migrate_relationships.py` выполнен — все `links.*` перенесены в `relationships.json`
- `signals.json` поле `links` удалено из схемы
- Читать: только из `relationships.json`

### Функция-адаптер

```python
# infrastructure/relationship_reader.py

from pathlib import Path
import json

def get_relationships(signal_id: str, signals: list[dict]) -> dict:
    """
    Читает связи для сигнала в зависимости от текущей фазы миграции.
    Возвращает dict с ключами: confirms, contradicts, context_chain
    """
    relationships_file = Path("relationships.json")

    # Фаза B/C — relationships.json существует
    if relationships_file.exists():
        relationships = json.loads(relationships_file.read_text())
        # Ищем запись для данного сигнала
        for rel in relationships:
            if rel.get("signal_id") == signal_id:
                return {
                    "confirms": rel.get("confirms", []),
                    "contradicts": rel.get("contradicts", []),
                    "context_chain": rel.get("context_chain", []),
                }

    # Фаза A / Fallback — читаем из links в signals.json
    signal = next((s for s in signals if s.get("id") == signal_id), None)
    if signal:
        return signal.get("links", {
            "confirms": [], "contradicts": [], "context_chain": []
        })

    return {"confirms": [], "contradicts": [], "context_chain": []}
```

### migrate_relationships.py (спека)

```python
# scripts/migrate_relationships.py
"""
Миграция: переносит links.* из signals.json в relationships.json.
Запускать ОДИН РАЗ при переходе в Фазу C.

Для старых links без rationale — устанавливает rationale = "" (пустая строка).
Это допустимо: contradiction_detector использует macro_implication, не rationale.
"""
# Реализовать в Roadmap Фаза 1
```

---

## §8. C3 — File Locking при параллельной записи

**Проблема из ARR:** Race condition при одновременной записи в `signals.json`.

```python
# infrastructure/file_lock.py

import fcntl
import json
from pathlib import Path
from contextlib import contextmanager

@contextmanager
def locked_json_write(filepath: str | Path):
    """
    Context manager для атомарной записи JSON файла с file locking.
    
    Использование:
        with locked_json_write("signals.json") as data:
            data.append(new_signal)
        # После выхода из блока — файл записан атомарно
    
    Гарантии:
        - Только один процесс записывает одновременно
        - При сбое записи оригинал не повреждён (temp → rename)
        - Возвращает список (mutable) для модификации
    """
    path = Path(filepath)
    lock_path = path.with_suffix(".lock")

    with open(lock_path, "w") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)  # Exclusive lock

            # Читаем текущее содержимое
            data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

            yield data  # Передаём caller для модификации

            # Атомарная запись: temp → rename
            temp_path = path.with_suffix(".tmp")
            temp_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            temp_path.replace(path)  # Атомарная операция на POSIX

        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)  # Release lock
```

```python
# Использование в scripts/add_signal.py

from infrastructure.file_lock import locked_json_write

def add_signal(new_signal: dict) -> None:
    with locked_json_write("signals.json") as signals:
        # Проверить дубликат ID
        existing_ids = {s["id"] for s in signals}
        if new_signal["id"] in existing_ids:
            raise ValueError(f"Signal ID {new_signal['id']} already exists")
        signals.append(new_signal)
    print(f"✓ Signal {new_signal['id']} added")
```

> **Примечание:** `fcntl` работает на Linux/macOS. Для Windows — использовать `msvcrt.locking()`. Текущий deployment target (GitHub Pages + Linux CI) — `fcntl` достаточен.

---

## §9. C4 — Signal Edit Lock (O(N×M) → O(1))

**Проблема из ARR:** Проверка «использует ли синтез сигнал» = O(N×M) — неприемлемо при масштабировании.

### Решение: обратный индекс

```python
# infrastructure/synthesis_index.py

import json
from pathlib import Path

INDEX_FILE = Path("synthesis_store/_signal_usage_index.json")

def build_signal_usage_index() -> dict[str, list[str]]:
    """
    Строит обратный индекс: signal_id → [synthesis_id, ...]
    
    Запускать:
        - После каждого нового синтеза (инкрементально)
        - Или rebuild при corruption
    
    Структура индекса:
    {
        "STR-2026-0625-001": ["synthesis_2026-06-25_strategy_v001"],
        "ETF-2026-0620-001": ["synthesis_2026-06-20_etf_v001", "synthesis_2026-06-25_etf_v002"]
    }
    """
    index = {}
    store = Path("synthesis_store")
    if not store.exists():
        return index

    for synthesis_file in store.glob("synthesis_*.json"):
        try:
            synthesis = json.loads(synthesis_file.read_text())
            synthesis_id = synthesis_file.stem
            for signal_id in synthesis.get("signals_used", []):
                index.setdefault(signal_id, []).append(synthesis_id)
        except (json.JSONDecodeError, KeyError):
            continue

    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=2))
    return index


def signal_is_used_in_synthesis(signal_id: str) -> bool:
    """
    O(1) проверка: использован ли сигнал в хотя бы одном утверждённом синтезе.
    Использует кешированный индекс.
    """
    if not INDEX_FILE.exists():
        build_signal_usage_index()

    index = json.loads(INDEX_FILE.read_text())
    return bool(index.get(signal_id))


def can_edit_signal(signal_id: str) -> tuple[bool, str]:
    """
    Возвращает (can_edit: bool, reason: str).
    Сигнал нельзя редактировать если он использован в утверждённом синтезе.
    """
    if signal_is_used_in_synthesis(signal_id):
        index = json.loads(INDEX_FILE.read_text())
        syntheses = index.get(signal_id, [])
        return False, f"Signal used in approved syntheses: {syntheses}"
    return True, "Signal can be edited"
```

---

## §10. C5 — Acceptance Tests

**Проблема из ARR:** Нет определения «что значит хороший нарратив». Команда не знает когда система готова.

### Acceptance Criteria (от пользователя)

```python
# tests/acceptance/test_narrative_quality.py
"""
Acceptance тесты для нарративного движка.
Тестируют СМЫСЛ результата, не только формат.
"""

def test_tension_has_two_opposing_forces():
    """
    Tension должен содержать конструкцию 'vs', 'несмотря на' или 'при условии'.
    Нельзя: простое описание факта.
    """
    for cluster_key, synthesis in get_all_syntheses():
        tension = synthesis.get("tension", "")
        if not tension:
            continue  # Пустой tension — отдельная проверка
        has_opposition = any(
            marker in tension.lower()
            for marker in ["vs", "несмотря на", "при условии", "вопреки", "против"]
        )
        assert has_opposition, (
            f"Cluster '{cluster_key}': tension has no opposing forces: '{tension}'"
        )


def test_macro_implication_describes_structural_change():
    """
    macro_implication не должен быть пересказом события.
    Минимальная длина: 50 символов (факт пересказывается короче, вывод длиннее).
    """
    signals = load_signals()
    for signal in signals:
        impl = signal.get("macro_implication", "")
        if impl:
            assert len(impl) >= 50, (
                f"Signal {signal['id']}: macro_implication too short "
                f"(likely event description, not structural change): '{impl}'"
            )


def test_cluster_has_at_least_one_signal():
    """Пустой кластер не должен появляться в нарративах."""
    clusters = group_signals_by_cluster(load_signals())
    for cluster_key, signals in clusters.items():
        assert len(signals) >= 1, f"Empty cluster: {cluster_key}"


def test_top_narrative_clusters_have_contradicts():
    """
    Топ-2 кластера по score должны иметь хотя бы 1 сигнал с contradicts.
    Если contradicts нет — нарратив слабый, score завышен.
    """
    synthesis = run_synthesis(load_signals())
    top_clusters = sorted(synthesis, key=lambda c: c["score"], reverse=True)[:2]
    for cluster in top_clusters:
        has_contradicts = any(
            s.get("links", {}).get("contradicts")
            for s in cluster["signals"]
        )
        assert has_contradicts, (
            f"Top cluster '{cluster['key']}' has no contradicts signals — "
            f"narrative quality is low"
        )


def test_confidence_is_between_0_and_1():
    """Confidence всегда в диапазоне [0.1, 1.0]."""
    synthesis = run_synthesis(load_signals())
    for cluster in synthesis:
        conf = cluster.get("confidence", 0)
        assert 0.1 <= conf <= 1.0, (
            f"Cluster '{cluster['key']}': confidence {conf} out of range [0.1, 1.0]"
        )
```

---

# MAJOR

---

## §11. M1 — Tiebreaker четвёртого уровня

**Проблема:** При равном importance_score нет детерминированного выбора anchor-сигнала.

```python
# domain/synthesizer.py

def rank_signals(signals: list[dict]) -> list[dict]:
    """
    Сортировка сигналов по importance_score.
    4 уровня tiebreaker — детерминированный порядок гарантирован.
    """
    def sort_key(s: dict) -> tuple:
        # Уровень 1: weight score
        weight_score = {"onchain": 4, "primary": 3, "market": 2, "media": 1}.get(
            s.get("weight", ""), 0
        )
        # Уровень 2: количество contradicts
        contradicts_count = len(s.get("links", {}).get("contradicts", []))
        # Уровень 3: свежесть (дата сигнала)
        date_str = s.get("date", "1970-01-01")
        # Уровень 4: ID (лексикографически) — последний детерминированный tiebreaker
        signal_id = s.get("id", "")

        return (weight_score, contradicts_count, date_str, signal_id)

    return sorted(signals, key=sort_key, reverse=True)
    # Для ID — reverse=False (старший ID = более ранний → ниже приоритет)
    # Поэтому ID сортируем отдельно:

def rank_signals(signals: list[dict]) -> list[dict]:
    """Корректная версия с 4-уровневым tiebreaker."""
    def sort_key(s: dict) -> tuple:
        weight_score = {"onchain": 4, "primary": 3, "market": 2, "media": 1}.get(
            s.get("weight", ""), 0
        )
        contradicts_count = len(s.get("links", {}).get("contradicts", []))
        date_str = s.get("date", "1970-01-01")
        # Инвертируем ID для сортировки: более поздний ID (больший NNN) = выше
        signal_id = s.get("id", "ZZZ-0000-0000-000")

        return (weight_score, contradicts_count, date_str, signal_id)

    return sorted(signals, key=sort_key, reverse=True)
```

---

## §12. M2 — Empty Cluster UI Contract

**Проблема:** UI (index.html) не специфицирован для пустого кластера.

### Контракт renderCluster()

```javascript
// В index.html — renderCluster() должен обрабатывать все 3 состояния:

function renderCluster(cluster) {
    // Состояние 1: нет сигналов
    if (!cluster.signals || cluster.signals.length === 0) {
        return `
            <div class="cluster-card cluster-empty">
                <div class="cluster-label">${cluster.label}</div>
                <div class="cluster-empty-msg">Нет сигналов в этом кластере</div>
            </div>
        `;
    }

    // Состояние 2: сигналы есть, tension пустой (слабый нарратив)
    if (!cluster.tension) {
        return `
            <div class="cluster-card cluster-weak">
                <div class="cluster-label">${cluster.label}</div>
                <div class="cluster-score-badge">СЛАБЫЙ СИГНАЛ</div>
                <div class="cluster-narrative">${cluster.narrative || '—'}</div>
            </div>
        `;
    }

    // Состояние 3: полный кластер (нормальный рендер)
    return `
        <div class="cluster-card">
            <div class="cluster-tension">${cluster.tension}</div>
            <div class="cluster-narrative">${cluster.narrative}</div>
            <div class="cluster-takeaway">${cluster.key_takeaway}</div>
        </div>
    `;
}
```

---

## §13. M3 — Audit Trail для signals.json

**Проблема:** Нет audit trail для изменений сигналов и связей (только для синтеза).

### Решение: append-only audit log

```python
# infrastructure/audit_log.py

import json
from datetime import datetime, UTC
from pathlib import Path

AUDIT_LOG = Path("audit_log.jsonl")  # JSON Lines format

def log_event(event_type: str, payload: dict) -> None:
    """
    Записывает событие в append-only audit log.
    Формат: JSON Lines (одна запись = одна строка).
    
    event_type: signal_added | signal_edited | signal_archived |
                relationship_added | relationship_retracted |
                synthesis_created | synthesis_approved
    """
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event_type,
        **payload
    }
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
```

```python
# Использование в scripts/add_signal.py

from infrastructure.audit_log import log_event

def add_signal(signal: dict) -> None:
    with locked_json_write("signals.json") as signals:
        signals.append(signal)
    log_event("signal_added", {
        "signal_id": signal["id"],
        "cluster": signal.get("cluster"),
        "dir": signal.get("dir"),
    })
```

---

## §14. M4 — Онтологическая миграция (ретроспективная переклассификация)

**Проблема:** При создании нового кластера старые сигналы остаются в старом — историческая аналитика искажается.

### Решение: reclassify script + правило

```python
# scripts/reclassify_signals.py
"""
Инструмент ретроспективной переклассификации сигналов.
Запускать при создании нового кластера если старые сигналы принадлежат ему.

Пример: создали кластер 'btc_reserve_policy' →
пересмотреть все сигналы с theme='institutionalization' и actor='government'
"""

import json
from pathlib import Path
from infrastructure.file_lock import locked_json_write
from infrastructure.audit_log import log_event

def reclassify(
    old_cluster: str,
    new_cluster: str,
    filter_fn,  # callable(signal) -> bool — какие сигналы переклассифицировать
    dry_run: bool = True
) -> list[str]:
    """
    Переносит сигналы из old_cluster в new_cluster.
    dry_run=True — только показать что изменится, не писать.
    Возвращает список ID затронутых сигналов.
    """
    signals = json.loads(Path("signals.json").read_text())
    affected = [s["id"] for s in signals
                if s.get("cluster") == old_cluster and filter_fn(s)]

    if dry_run:
        print(f"DRY RUN: Would reclassify {len(affected)} signals:")
        for sid in affected:
            print(f"  {sid}: {old_cluster} → {new_cluster}")
        return affected

    with locked_json_write("signals.json") as signals:
        for signal in signals:
            if signal["id"] in affected:
                signal["cluster"] = new_cluster
                log_event("signal_reclassified", {
                    "signal_id": signal["id"],
                    "old_cluster": old_cluster,
                    "new_cluster": new_cluster,
                })

    print(f"✓ Reclassified {len(affected)} signals")
    return affected
```

**Правило в CLAUDE.md:** При создании нового кластера — обязательно запустить `reclassify_signals.py --dry-run` и решить нужна ли ретроклассификация.

---

## §15. M5 — Batch перегенерация при MAJOR Algorithm Change

**Проблема:** При MAJOR изменении алгоритма 500+ синтезов требуют ревью — нереалистично вручную.

```python
# scripts/rebuild_synthesis.py
"""
Пересчитывает синтезы при MAJOR изменении алгоритма.
Создаёт diff между старым и новым синтезом для ревью аналитиком.
"""

import json
from pathlib import Path
from domain.synthesizer import synthesize  # новая версия алгоритма

def rebuild_with_diff(cluster_key: str = None) -> None:
    """
    Пересчитывает синтезы и создаёт diff файлы для ревью.
    
    Для каждого кластера создаёт:
        synthesis_store/CLUSTER_KEY_diff_TIMESTAMP.json
    Содержащий: old_tension, new_tension, old_narrative, new_narrative, changed: bool
    """
    signals = json.loads(Path("signals.json").read_text())
    store = Path("synthesis_store")

    clusters_to_process = (
        [cluster_key] if cluster_key
        else list({s.get("cluster") for s in signals if s.get("cluster")})
    )

    for cluster in clusters_to_process:
        cluster_signals = [s for s in signals if s.get("cluster") == cluster]
        if not cluster_signals:
            continue

        # Старый синтез
        old_files = sorted(store.glob(f"synthesis_{cluster}_*.json"))
        old_synthesis = json.loads(old_files[-1].read_text()) if old_files else {}

        # Новый синтез (новый алгоритм)
        new_synthesis = synthesize(cluster, cluster_signals)

        # Diff
        changed = (
            old_synthesis.get("tension") != new_synthesis.get("tension") or
            old_synthesis.get("narrative") != new_synthesis.get("narrative")
        )

        diff = {
            "cluster": cluster,
            "changed": changed,
            "old_tension": old_synthesis.get("tension", ""),
            "new_tension": new_synthesis.get("tension", ""),
            "old_narrative": old_synthesis.get("narrative", ""),
            "new_narrative": new_synthesis.get("narrative", ""),
            "recommendation": "REVIEW" if changed else "AUTO_APPROVE",
        }

        from datetime import datetime, UTC
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        diff_path = store / f"{cluster}_diff_{ts}.json"
        diff_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2))

        status = "⚠️  CHANGED — needs review" if changed else "✓  unchanged"
        print(f"{cluster}: {status}")

    print("\n✓ Diff files created in synthesis_store/")
    print("Review CHANGED clusters before approving new algorithm version")
```

---

## §16. M6 — Golden Dataset

**Проблема:** Структура определена, данные отсутствуют.

### Создать файл: `tests/golden/golden_signals.json`

Минимальный состав: 15 сигналов, 3 кластера, с известным ожидаемым синтезом.

```json
{
  "_meta": {
    "version": "1.0",
    "created": "2026-06-28",
    "description": "Golden dataset для регрессионного тестирования нарративного движка",
    "clusters": ["strategy_model_stress", "etf_institutional_flow", "btc_infrastructure_growth"],
    "signals_count": 15,
    "expected_syntheses": 3
  },
  "signals": [
    // Минимум 5 сигналов на кластер
    // Взять из реальных signals.json (те что уже проверены аналитиком)
  ],
  "expected_syntheses": {
    "strategy_model_stress": {
      "phase": "tension",
      "tension_contains": "Strategy",
      "confidence_min": 0.4,
      "has_trigger": false,
      "has_complication": true
    }
  }
}
```

**Правило:** Golden Dataset создаётся из реальных сигналов которые уже прошли проверку аналитика. Не синтетические данные.

---

## §17. M7 — Monitoring и Observability (MVP)

**Проблема из ARR:** Monitoring и Observability полностью отсутствуют.

> **Scope:** MVP мониторинг без Prometheus/Grafana. Простые решения совместимые с GitHub Pages deployment.

### 17.1 Structured Logging

```python
# infrastructure/logger.py

import json, logging
from datetime import datetime, UTC

class JSONFormatter(logging.Formatter):
    """Структурированные логи в JSON формате."""
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
            **(record.__dict__.get("extra", {}))
        }, ensure_ascii=False)

def get_logger(component: str) -> logging.Logger:
    logger = logging.getLogger(component)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
```

### 17.2 Health Check

```python
# scripts/health_check.py
"""
Проверяет здоровье системы. Запускать вручную или в CI.
Выводит JSON с результатами.
"""

import json, sys
from pathlib import Path
from datetime import datetime, UTC

def health_check() -> dict:
    checks = {}

    # signals.json
    try:
        signals = json.loads(Path("signals.json").read_text())
        checks["signals_json"] = {
            "status": "ok",
            "count": len(signals),
            "latest": max((s.get("date", "") for s in signals), default="unknown")
        }
    except Exception as e:
        checks["signals_json"] = {"status": "error", "error": str(e)}

    # ENTITIES.json
    try:
        entities = json.loads(Path("ENTITIES.json").read_text())
        checks["entities_json"] = {"status": "ok", "count": len(entities)}
    except Exception as e:
        checks["entities_json"] = {"status": "error", "error": str(e)}

    # synthesis_store
    store = Path("synthesis_store")
    if store.exists():
        files = list(store.glob("synthesis_*.json"))
        checks["synthesis_store"] = {
            "status": "ok",
            "count": len(files),
            "latest": max((f.stat().st_mtime for f in files), default=0)
        }
    else:
        checks["synthesis_store"] = {"status": "missing"}

    # Свежесть данных (алерт если нет новых сигналов > 14 дней)
    if checks.get("signals_json", {}).get("status") == "ok":
        latest = checks["signals_json"]["latest"]
        if latest != "unknown":
            from datetime import date
            days_old = (date.today() - date.fromisoformat(latest)).days
            checks["data_freshness"] = {
                "status": "warning" if days_old > 14 else "ok",
                "days_since_last_signal": days_old
            }

    overall = "ok" if all(
        v.get("status") in ("ok", "warning") for v in checks.values()
    ) else "error"

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "overall": overall,
        "checks": checks
    }


if __name__ == "__main__":
    result = health_check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["overall"] in ("ok", "warning") else 1)
```

### 17.3 CI Health Check

```yaml
# Добавить в .github/workflows/deploy.yml

  health-check:
    name: Health Check
    runs-on: ubuntu-latest
    needs: deploy
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Run health check
        run: python scripts/health_check.py
```

---

# Зависимости между задачами

```
B1 (hash детерминизм)   → независимо
B2 (semantic_inverse)   → нужен для C5 (Acceptance Tests)
B3 (Security)           → нужен для B5 (Deployment) — .env должен быть в .gitignore до CI
B4 (DR)                 → нужен для B5 (Deployment) — rollback procedure часть deploy runbook
B5 (Deployment)         → зависит от B3, B4

C1 (MAX_POSSIBLE_SCORE) → зависит от B2 (semantic_inverse используется в confidence)
C2 (links переход)      → независимо
C3 (file locking)       → нужен для C4 (signal edit lock)
C4 (edit lock index)    → зависит от C3
C5 (Acceptance Tests)   → зависит от B2

M1 (tiebreaker)         → зависит от B1 (детерминизм)
M2 (empty cluster UI)   → независимо
M3 (audit trail)        → зависит от C3 (file lock — пишем через locked context)
M4 (reclassify)         → зависит от C3
M5 (batch rebuild)      → зависит от B1, B2
M6 (golden dataset)     → зависит от B2 (contradiction pairs нужны для precision test)
M7 (monitoring)         → зависит от B5 (CI pipeline должен существовать)
```

---

# Порядок реализации

| День | Задачи | Цель |
|------|--------|------|
| День 1 | B1, C1 | Детерминизм полностью закрыт |
| День 2 | B2, M6 | Contradiction Detector + Golden Dataset |
| День 3 | B3, C2 | Security + Transition period |
| День 4 | B4, B5 | DR + Deployment (CI/CD запущен) |
| День 5 | C3, C4, M3 | File locking + Audit Trail |
| День 6 | C5, M1, M2 | Acceptance Tests + UI contract + Tiebreaker |
| День 7 | M4, M5, M7 | Reclassify + Batch rebuild + Monitoring |

**Итого: 7 дней → повторный ARR → ожидаемый статус READY**

---

# Definition of Done

Спека считается реализованной когда:

- [ ] `python -m pytest tests/ -v` проходит без ошибок
- [ ] `python scripts/health_check.py` возвращает `"overall": "ok"`
- [ ] `python scripts/validate_integrity.py` проходит
- [ ] CI в GitHub Actions зелёный на main
- [ ] `select_bridge()` проходит тест детерминизма при разных PYTHONHASHSEED
- [ ] `semantic_inverse_score()` precision ≥ 60% на Golden Dataset
- [ ] Push в main автоматически деплоится на GitHub Pages
- [ ] `.env` не попадает в git (проверить `git log --all -- .env`)
- [ ] `audit_log.jsonl` создаётся при добавлении сигнала
- [ ] Runbook для DR сценариев A, B, C протестирован вручную

---

*ARCH_GAP_SPEC v1.0 · 2026-06-28*  
*Основание: ARR_REPORT.md Blockers B1–B5, Critical C1–C5, Major M1–M7*  
*Следующий шаг: реализация → повторный ARR*
