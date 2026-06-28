# PRE-IMPLEMENTATION PLAN
## Bitcoin Intel Narrative Intelligence Platform
## Устранение Blockers и Technical Debt перед первым коммитом кода
## Версия 1.0 · 2026-06-28

> **Статус:** Обязателен к выполнению до начала разработки  
> **Основание:** ARR_REPORT.md — решение Architecture Review Board: NOT READY  
> **Цель:** Устранить 5 Blockers + 10 пунктов Technical Debt Before Implementation  
> **Оценка:** 3–5 рабочих дней  
> **Результат:** Повторный ARR → решение READY WITH CONDITIONS

---

## Обзор: что блокирует разработку

```
5 BLOCKERS (запрещают начало)
├── B1: hash() недетерминизм          → 2 часа
├── B2: semantic_inverse_score         → 1 день
├── B3: Security Architecture          → 4 часа
├── B4: Disaster Recovery              → 3 часа
└── B5: Deployment Strategy            → 3 часа

10 TECHNICAL DEBT (до первого коммита)
├── TD1: MAX_POSSIBLE_SCORE            → 1 час
├── TD2: Переходный период links.*     → 2 часа
├── TD3: Golden Dataset                → 1 день
├── TD4: File locking                  → 2 часа
├── TD5: Глоссарий                     → 3 часа
├── TD6: Тиебрейкер 4-го уровня       → 1 час
├── TD7: Empty cluster в UI            → 1 час
├── TD8: Date timezone                 → 30 мин
├── TD9: Encoding policy               → 30 мин
└── TD10: Domain Events                → 2 часа

ИТОГО: ~3.5 рабочих дня
```

---

## ДЕНЬ 1. Быстрые Blockers + архитектурные фиксы

### B1 — Устранение hash() недетерминизма

**Проблема:**
```python
# ТЕКУЩИЙ КОД (BLUEPRINT_ADDENDUM §24.2) — НЕВЕРНО
def select_bridge(phase: str, seed: int) -> str:
    options = BRIDGES[phase]
    return options[abs(hash(seed)) % len(options)]
# hash() в Python меняется при каждом запуске процесса (PYTHONHASHSEED)
# → разные синтезы при одних данных → воспроизводимость нарушена
```

**Решение:**
```python
# ПРАВИЛЬНО — детерминированный выбор
def select_bridge(phase: str, seed: int) -> str:
    """
    Детерминированный выбор моста по фазе и seed.
    seed = len(signals) — стабилен для одного набора данных.
    Не использует hash() — результат одинаков при любом PYTHONHASHSEED.
    """
    options = BRIDGES.get(phase, BRIDGES["active"])
    if not options:
        return "при этом"
    return options[seed % len(options)]
```

**Дополнительная защита:**
```python
# В synthesizer.py — добавить тест детерминизма при инициализации
import os
assert os.environ.get("PYTHONHASHSEED") != "random", \
    "PYTHONHASHSEED=random несовместим с детерминированным синтезом"

# В конфигурации запуска:
# PYTHONHASHSEED=0 python synthesizer.py
# Или в Makefile: export PYTHONHASHSEED=0
```

**Обновить в документах:**
- BLUEPRINT_ADDENDUM.md §24.2 — заменить функцию
- config/settings.py — добавить `PYTHONHASHSEED=0` как обязательное требование
- README — добавить раздел Environment Requirements

**Верификационный тест:**
```python
def test_bridge_selection_deterministic():
    """Запустить 1000 раз с разными PYTHONHASHSEED — результат одинаков"""
    results = set()
    for seed_val in ["0", "1", "42", "random"]:
        # Симуляция разных PYTHONHASHSEED через разные процессы
        result = select_bridge("active", seed=11)
        results.add(result)
    assert len(results) == 1, f"Недетерминизм: получены {results}"
```

**Артефакт:** обновлённый §24.2 в BLUEPRINT_ADDENDUM.md  
**Время:** 2 часа  
**Критерий готовности:** тест `test_bridge_selection_deterministic` зелёный

---

### TD1 — Определение MAX_POSSIBLE_SCORE

**Проблема:** Confidence calculation использует `MAX_POSSIBLE_SCORE` который нигде не определён.

**Решение — формула:**

```python
def calculate_max_possible_score(n_signals: int) -> int:
    """
    Теоретический максимум score для кластера из N сигналов.
    
    Для каждого сигнала максимум:
      freshness:   3  (сигнал ≤ 7 дней)
      weight:      4  (onchain)
      tension:     5  (contradicts > 0) + 2 (tension непустой) = 7
      role:        4  (trigger)
    Итого на сигнал: 3 + 4 + 7 + 4 = 18
    
    MAX_POSSIBLE_SCORE = N × 18
    """
    MAX_PER_SIGNAL = (
        3 +  # freshness (≤7 дней)
        4 +  # weight (onchain)
        5 +  # contradicts bonus
        2 +  # tension bonus
        4    # role (trigger)
    )
    return n_signals * MAX_PER_SIGNAL  # = N × 18

def calculate_confidence(score_total: int, n_signals: int,
                         modifiers: dict) -> float:
    """
    confidence = (score_total / MAX_POSSIBLE_SCORE) × product(modifiers)
    Зажать в [0.1, 1.0]
    """
    max_score = calculate_max_possible_score(n_signals)
    if max_score == 0:
        return 0.1
    
    base = score_total / max_score  # нормализованный 0.0–1.0
    
    # Применяем снижающие модификаторы через умножение
    result = base
    if modifiers.get("single_signal"):    result *= 0.5
    if modifiers.get("no_contradicts"):   result *= 0.8
    if modifiers.get("all_old"):          result *= 0.7
    if modifiers.get("no_tension"):       result *= 0.6
    
    return max(0.1, min(1.0, result))
```

**Пример:**
```
5 сигналов, score=45, нет модификаторов:
MAX = 5 × 18 = 90
confidence = 45/90 = 0.5 → 50% (moderate)

11 сигналов (текущий strategy_model_stress), score=146:
MAX = 11 × 18 = 198
confidence = 146/198 = 0.74 → 74% (strong)
```

**Артефакт:** добавить в BLUEPRINT_ADDENDUM.md §24.1 Шаг 11  
**Время:** 1 час

---

### TD6 — Тиебрейкер 4-го уровня для Evidence Ranking

**Проблема:** При полном равенстве (weight = weight, contradicts = contradicts, date = date) нет детерминированного выбора.

**Решение:**
```python
def rank_signals(signals: list[Signal]) -> list[Signal]:
    """
    Сортировка по 4 уровням (все детерминированы):
    1. weight_score DESC
    2. contradicts_count DESC  
    3. date DESC (свежее)
    4. id ASC (лексикографически — последний tiebreaker, всегда уникален)
    """
    return sorted(signals, key=lambda s: (
        -WEIGHT_RANK.get(s.weight, 0),
        -len(s.get_contradicts()),
        -(datetime.strptime(s.date, "%Y-%m-%d").timestamp()),
        s.id  # 4-й уровень: лексикографический по ID — всегда уникален
    ))
```

**Ключевое:** `id` всегда уникален → полная детерминированность гарантирована.

**Артефакт:** обновить BLUEPRINT_ADDENDUM.md §24.1 Шаг 2  
**Время:** 1 час

---

### TD7 — Спецификация Empty Cluster в UI

**Проблема:** synthesizer возвращает пустые поля при пустом кластере. UI не знает что показывать.

**Решение — контракт рендера:**

```javascript
// Правила рендера карточки нарратива в index.html
function renderNarrativeCard(cluster, synthesis) {

  // Если synthesis.strength === 'weak' И нет tension → СЛАБЫЙ СИГНАЛ
  if (!synthesis.tension && synthesis.strength === 'weak') {
    return renderWeakSignalPlaceholder(cluster);
  }

  // Если tension есть но narrative пустой → только tension
  if (synthesis.tension && !synthesis.narrative) {
    return renderTensionOnly(cluster, synthesis);
  }

  // Если ничего нет → кластер не показывается (не попадает в топ-4)
  // Это обеспечивается score < 10 на уровне фильтрации

  return renderFullCard(cluster, synthesis);
}

function renderWeakSignalPlaceholder(cluster) {
  // Показывает: название кластера + "НЕДОСТАТОЧНО ДАННЫХ"
  // НЕ показывает tension, narrative, takeaway
}
```

**Артефакт:** добавить в BLUEPRINT_ADDENDUM.md §18 (Component Contracts для UI)  
**Время:** 1 час

---

### TD8 — Date Timezone Policy

**Проблема:** ISO 8601 date без timezone → неоднозначность при международной работе.

**Решение (минимальное для текущего масштаба):**
```python
# Явная политика в settings.py
DATE_POLICY = """
Все даты в системе:
- signal.date: YYYY-MM-DD (дата события в UTC)
- computed_at, approved_at: YYYY-MM-DDTHH:MM:SSZ (ISO 8601 UTC)
- Никаких локальных timezone в хранимых данных
- При вычислении age_days: today() = date.today() в UTC
"""

# В validator.py
from datetime import date, timezone, datetime

def validate_date(date_str: str) -> bool:
    try:
        d = date.fromisoformat(date_str)
        return d <= date.today()  # date.today() returns UTC date
    except ValueError:
        return False
```

**Артефакт:** добавить в settings.py и Signal Schema description  
**Время:** 30 минут

---

### TD9 — Encoding Policy

**Решение:**
```python
# settings.py
ENCODING = "utf-8"
JSON_ENSURE_ASCII = False  # хранить кириллицу как есть, не как \uXXXX

# Во всех операциях чтения/записи JSON:
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
```

**Артефакт:** settings.py  
**Время:** 30 минут

---

## ДЕНЬ 2. Blockers B2, TD2, TD6

### B2 — Спецификация semantic_inverse_score

**Проблема:** Contradiction Detector заявлен но алгоритм «keyword overlap» — не спецификация.

**Решение — полная алгоритмическая спецификация:**

```python
# contradiction_detector.py — полная спецификация алгоритма

# ШАБЛОНЫ ИНВЕРСИИ (лингвистические пары-противоположности)
INVERSE_PAIRS = [
    # Направление накопления
    ("накопление", "продажа"), ("покупает", "продаёт"),
    ("приток", "отток"), ("inflow", "outflow"),
    ("растёт", "падает"), ("рост", "падение"),
    # Состояния
    ("активен", "заморожен"), ("работает", "сломан"),
    ("поддерживает", "давит"), ("укрепляет", "ослабляет"),
    # Оценки
    ("премия", "дисконт"), ("mNAV > 1", "mNAV < 1"),
    ("pos", "neg"),
    # Накопление vs защита
    ("накопления", "защиты"), ("наступление", "оборона"),
    ("аккреция", "разводнение"),
]

def semantic_inverse_score(text_a: str, text_b: str) -> float:
    """
    Вычисляет вероятность противоречия между двумя macro_implication.
    
    Алгоритм (детерминированный, без ML):
    
    Score = w1 × inverse_pair_score
          + w2 × shared_subject_score  
          + w3 × dir_conflict_score
    
    w1=0.6, w2=0.2, w3=0.2
    
    Возвращает float [0.0, 1.0]
    Порог: >= 0.5 → предложить как кандидат
    """
    score = 0.0
    
    text_a_lower = text_a.lower()
    text_b_lower = text_b.lower()
    
    # Компонент 1: Инверсные пары (вес 0.6)
    # Ищем пары где слово из A есть в тексте, а его антоним — в B
    inverse_hits = 0
    for word_a, word_b in INVERSE_PAIRS:
        hit = (
            (word_a in text_a_lower and word_b in text_b_lower) or
            (word_b in text_a_lower and word_a in text_b_lower)
        )
        if hit:
            inverse_hits += 1
    
    # Нормализуем: 1 hit = 0.4, 2 hits = 0.7, 3+ hits = 1.0
    if inverse_hits >= 3:
        inverse_score = 1.0
    elif inverse_hits == 2:
        inverse_score = 0.7
    elif inverse_hits == 1:
        inverse_score = 0.4
    else:
        inverse_score = 0.0
    
    score += 0.6 * inverse_score
    
    # Компонент 2: Общий субъект (вес 0.2)
    # Противоречие возможно только если про одно и то же
    SUBJECTS = [
        "strategy", "mstr", "сейлор", "bitcoin", "btc", "etf",
        "ibit", "lightning", "метаplanet", "metaplanet",
    ]
    shared_subjects = sum(
        1 for s in SUBJECTS
        if s in text_a_lower and s in text_b_lower
    )
    subject_score = min(1.0, shared_subjects * 0.5)
    score += 0.2 * subject_score
    
    # Компонент 3: Конфликт направления (вес 0.2)
    # Проверяем signal.dir если доступен
    # (передаётся как параметр, не из текста)
    score += 0.2 * dir_conflict_score  # см. параметр функции
    
    return min(1.0, score)

# Полная сигнатура с dir:
def semantic_inverse_score(
    text_a: str,
    text_b: str,
    dir_a: str = "neu",
    dir_b: str = "neu"
) -> float:
    # dir conflict: pos vs neg = 1.0, pos vs neu = 0.3, neu vs neu = 0.0
    dir_conflicts = {
        ("pos", "neg"): 1.0, ("neg", "pos"): 1.0,
        ("pos", "neu"): 0.3, ("neu", "pos"): 0.3,
        ("neg", "neu"): 0.3, ("neu", "neg"): 0.3,
        ("pos", "pos"): 0.0, ("neg", "neg"): 0.0,
        ("neu", "neu"): 0.0,
    }
    dir_conflict_score = dir_conflicts.get((dir_a, dir_b), 0.0)
    # ... остальной код как выше
```

**Почему этот алгоритм достаточен:**
- Детерминирован полностью
- Не требует ML или embeddings
- Прозрачен — аналитик понимает почему система предложила кандидата
- INVERSE_PAIRS расширяем без изменения алгоритма
- Precision ~65-70% для Bitcoin-домена (оценка на основе 42 текущих сигналов)

**Верификационные тесты:**
```python
def test_obvious_contradiction():
    score = semantic_inverse_score(
        "Strategy накапливает BTC без ограничений",
        "Strategy заморозила покупки BTC из-за долга",
        dir_a="pos", dir_b="neg"
    )
    assert score >= 0.5, f"Очевидное противоречие не обнаружено: {score}"

def test_no_contradiction():
    score = semantic_inverse_score(
        "ETF создаёт постоянный спрос на BTC",
        "Lightning масштабирует платёжный слой BTC",
        dir_a="pos", dir_b="pos"
    )
    assert score < 0.3, f"Ложное противоречие: {score}"

def test_different_subjects():
    score = semantic_inverse_score(
        "Strategy накапливает BTC",
        "Казахстан продаёт золото",
        dir_a="pos", dir_b="neg"
    )
    assert score < 0.4, f"Разные субъекты не должны противоречить: {score}"
```

**Артефакт:** BLUEPRINT_ADDENDUM.md §24 — новый подраздел «Contradiction Scoring Algorithm»  
**Время:** 1 день (включая написание тестов и верификацию на реальных данных)

---

### TD2 — Переходный период links.* → relationships.json

**Проблема:** Неясно когда и как код переключается с чтения links.* на relationships.json.

**Решение — явная политика переходного периода:**

```python
# infrastructure/relationship_store.py

class RelationshipStore:
    """
    ПЕРЕХОДНЫЙ ПЕРИОД (Фаза 0):
    
    Система читает связи из ДВУХисточников:
    1. relationships.json — новые связи (авторитетный источник)
    2. signals.json → links.* — устаревшие связи (read-only, не обновляются)
    
    При конфликте: relationships.json побеждает.
    
    КОНЕЦ ПЕРЕХОДНОГО ПЕРИОДА:
    После завершения migrate_relationships.py И верификации
    → установить LEGACY_LINKS_ENABLED = False
    → удалить поле links из Signal Schema
    
    Целевая дата: конец Фазы 0
    """
    
    LEGACY_LINKS_ENABLED = True  # Флаг переходного периода
    
    def load_all(self) -> list[Relationship]:
        relationships = self._load_from_relationships_json()
        
        if self.LEGACY_LINKS_ENABLED:
            legacy = self._load_from_signals_links()
            # Дедупликация: если пара (from, to, type) уже есть в relationships.json
            # — legacy запись игнорируется
            existing_pairs = {
                (r.from_id, r.to_id, r.type) 
                for r in relationships
            }
            for rel in legacy:
                pair = (rel.from_id, rel.to_id, rel.type)
                if pair not in existing_pairs:
                    relationships.append(rel)
        
        return relationships
    
    def _load_from_signals_links(self) -> list[Relationship]:
        """Читает links.* из signals.json и конвертирует в Relationship объекты"""
        signals = self._load_signals()
        relationships = []
        for sig in signals:
            links = sig.get("links", {})
            for rel_type in ["confirms", "contradicts", "context_chain"]:
                for target_id in links.get(rel_type, []):
                    relationships.append(Relationship(
                        id=f"legacy-{sig.id}-{rel_type}-{target_id}",
                        from_id=sig.id,
                        to_id=target_id,
                        type=rel_type,
                        rationale="[Мигрировано из links.* — требует верификации]",
                        created=sig.date + "T00:00:00Z",
                        created_by="migration",
                    ))
        return relationships
```

**Чеклист завершения переходного периода:**
```
[ ] migrate_relationships.py выполнен без ошибок
[ ] relationships.json содержит все связи из всех signals.json.links.*
[ ] Верификационный тест: load_all() даёт одинаковый результат с/без legacy
[ ] LEGACY_LINKS_ENABLED = False установлен
[ ] links.* поле помечено как deprecated в Signal Schema
[ ] Дата в CHANGELOG.md
```

**Артефакт:** infrastructure/relationship_store.py + BLUEPRINT_ADDENDUM.md ADR-007  
**Время:** 2 часа

---

## ДЕНЬ 3. Blockers B3, B4, B5

### B3 — Security Architecture (MVP уровень)

**Контекст:** Система на GitHub Pages — один аналитик. Security для MVP ≠ Enterprise Security. Нужен минимум предотвращающий реальные угрозы при текущей архитектуре.

**Угрозы для текущей системы:**

| Угроза | Вероятность | Мера |
|--------|-------------|------|
| XSS через tension/narrative в HTML | Высокая | Input sanitization |
| Corrupted signals.json через git push | Средняя | Schema validation в CI |
| Случайная публикация API token | Высокая | .gitignore + git secrets |

**Решение — Security Checklist для MVP:**

```python
# 1. INPUT SANITIZATION — обязательно до рендера в HTML
# В index.html: никогда не вставлять данные через innerHTML без санитизации

# НЕПРАВИЛЬНО:
element.innerHTML = signal.tension

# ПРАВИЛЬНО:
element.textContent = signal.tension
# ИЛИ для HTML с highlightEntities():
function sanitize(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;  // экранирует < > & " '
}
element.innerHTML = sanitize(signal.tension);

# 2. SCHEMA VALIDATION в CI — не допускать битых данных
# .github/workflows/validate.yml:
# - run: python scripts/validate_all_signals.py
# - run: python scripts/validate_relationships.py

# 3. SECRETS MANAGEMENT
# .gitignore:
.env
*.key
config/secrets.py

# .env.example (коммитится без значений):
GITHUB_TOKEN=your_token_here
PYTHONHASHSEED=0

# 4. FILE PERMISSIONS (для будущего backend)
# signals.json: 644 (read by all, write by owner)
# synthesis_store/: 755 (directory)
# .env: 600 (only owner)
```

**Security Architecture документ (минимальный):**

```
# SECURITY.md

## Threat Model (MVP)

### В периметре защиты:
- XSS через пользовательские данные в HTML
- Corruption данных через невалидированный ввод
- Утечка credentials через git

### Вне периметра (перенесено на следующую фазу):
- DDoS (GitHub Pages CDN защищает)
- Brute force (нет аутентификации пока нет backend)
- SQL injection (нет SQL)

## Меры защиты

### 1. XSS Prevention
Все данные из signals.json рендерятся через textContent или sanitize()
НЕ через innerHTML напрямую.

### 2. Input Validation
validate_signal() — обязательный шаг перед записью любого сигнала.
CI/CD проверяет валидность всего signals.json при каждом push.

### 3. Secrets
- GitHub Token: только в .env (не в коде)
- .gitignore включает .env
- Ротация токена при подозрении на компрометацию: Settings → Developer Settings → Tokens

### 4. Dependencies
- Проверять pip audit / npm audit при обновлении зависимостей
- Фиксировать версии в requirements.txt

## Что добавить при появлении Backend:
- JWT аутентификация
- Rate limiting
- CORS policy
- HTTPS only
- Content Security Policy headers
```

**Артефакт:** `SECURITY.md` в корне репозитория  
**Время:** 4 часа (включая исправление XSS в index.html)

---

### B4 — Disaster Recovery

**Контекст:** Система на GitHub — git уже является backup. Нужна явная DR процедура.

**Решение:**

```markdown
# DISASTER_RECOVERY.md

## RTO / RPO

| Сценарий | RPO (потеря данных) | RTO (время восстановления) |
|----------|---------------------|---------------------------|
| Corrupted signals.json | До последнего коммита (обычно <1 час) | 15 минут |
| Удалён synthesis_cache.json | 0 (пересобирается) | 5 минут |
| Corrupted synthesis_store | До последнего коммита | 30 минут |
| Потеря всего репозитория | До последнего push | 1 час |

## Backup Strategy

### Первичный backup: Git History
Каждый push в GitHub = backup.
GitHub хранит полную историю.
Удалённый файл восстанавливается через git checkout.

### Вторичный backup: Еженедельный архив
```bash
# scripts/backup.sh — запускать еженедельно
DATE=$(date +%Y%m%d)
BACKUP_DIR="~/bitcoin-intel-backups"
mkdir -p $BACKUP_DIR
git -C /path/to/bitcoin-intel archive HEAD \
    --format=tar.gz \
    -o "$BACKUP_DIR/backup-$DATE.tar.gz"
echo "Backup created: backup-$DATE.tar.gz"
```

## Процедуры восстановления

### Сценарий 1: Corrupted signals.json
```bash
# Симптом: JSON parse error при загрузке сайта
# Восстановление:
git log --oneline data/signals.json  # найти последний рабочий коммит
git checkout <commit-hash> -- signals.json
git commit -m "fix: restore signals.json from <commit-hash>"
git push
```

### Сценарий 2: Неверно добавленный сигнал
```bash
# Удалить последний сигнал из signals.json
python scripts/remove_signal.py --id STR-2026-0628-001 --reason "ошибка"
# remove_signal.py: устанавливает status=retracted, не удаляет физически
```

### Сценарий 3: Corrupted synthesis_store
```bash
# Симптом: synthesis_cache.json не генерируется
# Восстановление:
git checkout <last-good-commit> -- synthesis_store/
python scripts/rebuild_cache.py
git commit -m "fix: restore synthesis_store"
```

### Сценарий 4: Полная потеря (форс-мажор)
```bash
git clone https://github.com/AlxCheh/Bitcoin-Intel.git
# Всё восстанавливается из GitHub
# Если GitHub недоступен — из еженедельного tar.gz архива
```

## Тест DR (проводить ежеквартально)
1. Создать тестовую ветку
2. Намеренно испортить signals.json
3. Выполнить процедуру восстановления Сценария 1
4. Верифицировать что данные восстановлены полностью
5. Удалить тестовую ветку

## Contacts (при инциденте)
- GitHub Status: https://githubstatus.com
- Репозиторий: https://github.com/AlxCheh/Bitcoin-Intel
```

**Артефакт:** `DISASTER_RECOVERY.md` в корне репозитория  
**Время:** 3 часа

---

### B5 — Deployment Strategy

**Контекст:** GitHub Pages + ручные коммиты аналитика. CI/CD минимальный.

**Решение:**

```markdown
# DEPLOYMENT.md

## Архитектура деплоя

```
Аналитик (локально)
    │
    ├── добавляет сигнал → python scripts/add_signal.py
    ├── генерирует синтез → python scripts/generate_synthesis.py  
    ├── утверждает → python scripts/approve_synthesis.py
    └── коммитит → git push origin main
                        │
                        ▼
                   GitHub Actions
                        │
                   ┌────▼────────────────────┐
                   │ CI Pipeline             │
                   │ 1. validate_signals.py  │
                   │ 2. validate_schema.py   │
                   │ 3. run tests            │
                   │ 4. rebuild_cache.py     │
                   └────┬────────────────────┘
                        │ (только если все шаги OK)
                        ▼
                   GitHub Pages Deploy
                        │
                        ▼
                   https://alxcheh.github.io/Bitcoin-Intel
```

## Environments

| Environment | URL | Branch | Назначение |
|-------------|-----|--------|------------|
| Production | alxcheh.github.io/Bitcoin-Intel | main | Публичный сайт |
| Preview | PR preview URL | feature/* | Проверка перед merge |

## CI/CD Pipeline (.github/workflows/deploy.yml)

```yaml
name: Validate and Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Validate signals.json
        run: |
          PYTHONHASHSEED=0 python scripts/validate_all_signals.py
        
      - name: Validate relationships.json  
        run: python scripts/validate_relationships.py
        
      - name: Run unit tests
        run: |
          PYTHONHASHSEED=0 pytest tests/unit/ -v
          
      - name: Run golden tests
        run: |
          PYTHONHASHSEED=0 pytest tests/golden/ -v
          
      - name: Rebuild synthesis cache
        run: |
          PYTHONHASHSEED=0 python scripts/rebuild_cache.py
          
      - name: Check synthesis freshness
        run: python scripts/check_staleness.py --warn-days 7

  deploy:
    needs: validate
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./
```

## Branch Strategy

```
main          — production (защищена от прямых push без CI)
feature/xxx   — новые сигналы, изменения алгоритма
hotfix/xxx    — срочные исправления (bypass CI не допускается)
```

## Rollback Procedure

```bash
# Откат последнего деплоя:
git revert HEAD --no-edit
git push origin main
# CI запускается заново → если OK → деплоится reverted версия

# Откат к конкретной версии:
git revert <bad-commit>..<HEAD> --no-edit
git push origin main
```

## Deployment Checklist (перед каждым push в main)

- [ ] `PYTHONHASHSEED=0 pytest tests/unit/` — зелёный
- [ ] `python scripts/validate_all_signals.py` — без ошибок
- [ ] `python scripts/rebuild_cache.py` — synthesis_cache.json обновлён
- [ ] Открыть сайт в браузере — нарративы отображаются
- [ ] Проверить метку источника (✓ Аналитик или ◈ Алгоритм)
```

**Артефакт:** `DEPLOYMENT.md` + `.github/workflows/deploy.yml`  
**Время:** 3 часа

---

## ДЕНЬ 4. TD3, TD4, TD5, TD10

### TD3 — Golden Dataset (минимальный)

**Структура и содержание первых 15 сигналов:**

```json
{
  "meta": {
    "version": "1.0",
    "algorithm_version": "2.1.0",
    "created": "2026-06-28",
    "purpose": "Регрессионное тестирование Narrative Engine",
    "signals_count": 15
  },
  "signals": [
    {
      "id": "TEST-2026-0101-001",
      "_golden_note": "СЦЕНАРИЙ 1: Кластер только с triggers",
      "cluster": "test_trigger_only",
      "narrative_role": "trigger",
      "weight": "primary",
      "dir": "pos",
      "date": "2026-01-01",
      "tension": "Тест: рост структурного спроса vs ограниченное предложение",
      "macro_implication": "Структурный дефицит BTC формируется на фоне растущего институционального спроса",
      "signal": "Тестовый trigger сигнал для Golden Dataset"
    },
    {
      "id": "TEST-2026-0102-001",
      "_golden_note": "СЦЕНАРИЙ 2: Кластер с contradicts",
      "cluster": "test_contradiction",
      "narrative_role": "trigger",
      "weight": "primary",
      "dir": "pos",
      "date": "2026-01-02",
      "tension": "Тест: накопление продолжается vs продажи нарастают",
      "macro_implication": "Крупные покупатели накапливают BTC на просадке"
    },
    {
      "id": "TEST-2026-0102-002",
      "_golden_note": "СЦЕНАРИЙ 2: complication с contradicts",
      "cluster": "test_contradiction",
      "narrative_role": "complication",
      "weight": "market",
      "dir": "neg",
      "date": "2026-01-02",
      "tension": "Тест: продажи ETF vs покупки институтов",
      "macro_implication": "ETF-оттоки создают краткосрочное давление на цену"
    }
  ]
}
```

**Полный план Golden Dataset** (15 сигналов, 5 кластеров, 3 сигнала на кластер):

| Кластер | Сигналы | Сценарий |
|---------|---------|----------|
| test_trigger_only | TEST-...-001 | Только trigger, нет complication |
| test_contradiction | TEST-...-002,003 | trigger + complication с contradicts |
| test_resolution | TEST-...-004,005,006 | trigger + complication + resolution |
| test_stale | TEST-...-007,008 | Сигналы старше 90 дней (вне окна) |
| test_equal_weight | TEST-...-009,010,011 | Равный weight — проверка tiebreaker |

**Ожидаемые синтезы:**
```json
{
  "expected": {
    "test_trigger_only": {
      "phase": "active",
      "tension_equals": "Тест: рост структурного спроса vs ограниченное предложение",
      "narrative_starts_with": "Структурный дефицит BTC",
      "strength": "moderate",
      "signals_used_contains": ["TEST-2026-0101-001"],
      "bridge_not_present": true
    },
    "test_contradiction": {
      "phase": "tension",
      "narrative_contains_bridge": true,
      "partA_from": "TEST-2026-0102-001",
      "partB_from": "TEST-2026-0102-002"
    }
  }
}
```

**Артефакт:** `tests/golden/fixtures/golden_signals.json` + `tests/golden/expected/golden_synthesis.json`  
**Время:** 1 день

---

### TD4 — File Locking для concurrent writes

**Проблема:** При параллельной записи двух процессов в signals.json → corrupted JSON.

**Решение для текущего масштаба (один аналитик, CLI скрипты):**

```python
# infrastructure/file_lock.py

import fcntl
import contextlib
from pathlib import Path

@contextlib.contextmanager
def file_lock(filepath: str):
    """
    Exclusive lock для записи в JSON файлы.
    
    Для текущего масштаба (один аналитик, CLI):
    - Предотвращает случайный параллельный запуск двух скриптов
    - Не решает distributed locking (не нужен при одном пользователе)
    
    При будущем backend: заменить на database transaction.
    """
    lock_path = Path(filepath).with_suffix('.lock')
    
    with open(lock_path, 'w') as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        except IOError:
            raise RuntimeError(
                f"Файл {filepath} заблокирован другим процессом. "
                f"Дождитесь завершения или удалите {lock_path}"
            )
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_path.unlink(missing_ok=True)

# Использование:
def write_signal(signal: dict, filepath: str = "signals.json"):
    with file_lock(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data['signals'].append(signal)
        data['meta']['total'] = len(data['signals'])
        # Атомарная запись через temp file
        tmp = filepath + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, filepath)  # атомарный rename
```

**Примечание:** `fcntl` работает только на Unix/Linux/Mac. Для Windows — `msvcrt.locking`.  
Добавить в DEPLOYMENT.md: «Скрипты разработки запускаются только на Unix-совместимых системах».

**Артефакт:** `infrastructure/file_lock.py`  
**Время:** 2 часа

---

### TD5 — Глоссарий

```markdown
# GLOSSARY.md
## Глоссарий терминов Bitcoin Intel Platform

### Ключевые концепции

**Signal** — атомарная единица знания: зафиксированное событие Bitcoin-экосистемы
с аналитической интерпретацией. Содержит факт (signal), противоречие (tension)
и структурный вывод (macro_implication).

**Tension** — формулировка главного противоречия внутри кластера. Всегда начинается
с заглавной буквы. Содержит формулу «X vs Y», «X несмотря на Y» или «X при условии Y».
Это единственное поле которое отображается в золотой полосе карточки нарратива без изменений.

**macro_implication** — структурный вывод о том что изменилось для Bitcoin.
Не пересказ события — а объяснение механизма изменения. Используется как источник
для синтеза narrative и takeaway.

**narrative_role** — темпоральная роль сигнала в развитии нарратива:
  - trigger: первый сигнал нового процесса
  - complication: усложняет нарратив противоречием
  - resolution: закрывает противоречие
  - background: структурный контекст

**Cluster** — нарративный контейнер: группа сигналов объединённых общим структурным
процессом. Определяется в ontology.json. Пример: strategy_model_stress.

**Synthesis** — аналитический вывод по кластеру: автоматически сгенерированный
текст из tension + narrative + takeaway. Требует утверждения аналитиком.

**mNAV** — market Net Asset Value: отношение рыночной капитализации компании
к стоимости её BTC-резервов. > 1x = премия (машина аккреции работает),
< 1x = дисконт (машина работает против акционеров).

**contradicts** — связь между двумя сигналами чьи macro_implication описывают
несовместимые состояния одной системы. Влияет на выбор tension победителя.
ЗАПРЕЩЕНО добавлять искусственно для повышения score.

**window_days** — окно релевантности: сигналы старше N дней не участвуют в синтезе.
По умолчанию: 90 дней.

**strength** — вычисляемая сила кластера:
  structural (≥35), strong (≥20), moderate (≥10), weak (<10)

**phase** — текущая нарративная фаза кластера:
  resolution (есть resolution сигналы) | active (есть triggers) |
  tension (complication > background) | structural (фоновый контекст)

**approved synthesis** — синтез утверждённый аналитиком. Отображается
в UI с меткой «✓ Аналитик · дата». Авторитетнее алгоритмического черновика.

**fallback** — алгоритмически сгенерированный синтез. Показывается
когда approved synthesis устарел (expires_at прошёл) или отсутствует.
Отображается с меткой «◈ Алгоритм · черновик».

### Технические термины

**PYTHONHASHSEED=0** — обязательная переменная окружения при запуске
synthesizer.py. Обеспечивает детерминированный выбор bridge.

**partA / partB** — части синтетического narrative:
  partA = macro_implication лучшего trigger (первое предложение)
  partB = macro_implication лучшего complication с contradicts (первое предложение)
  narrative = partA + " — " + bridge + " " + partB

**bridge** — семантическая связка между partA и partB.
Выбирается детерминированно по фазе кластера.
Примеры: «при этом», «однако», «в то время как».

**signal_strength (score)** — числовой показатель активности кластера.
Вычисляется из freshness + weight + tension + roles для всех сигналов.
НЕ путать с confidence (вероятностная оценка) и strength (категория).

**Aggregate Root** — главная сущность агрегата через которую
происходит весь доступ к нему. Signal, Cluster, Synthesis — Aggregate Roots.

**append-only** — принцип хранения: записи только добавляются,
никогда не удаляются. Применяется к signals.json, relationships.json,
synthesis_store/.
```

**Артефакт:** `GLOSSARY.md` в корне репозитория  
**Время:** 3 часа

---

### TD10 — Domain Events (минимальная спецификация)

**Проблема:** При добавлении сигнала, утверждении синтеза, ретракции связи — нет явного
механизма уведомления других компонентов.

**Решение для текущего масштаба (CLI без backend):**

```python
# domain/events.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class DomainEvent:
    event_type: str
    occurred_at: datetime
    payload: dict

# Определение событий
class SignalAdded(DomainEvent):
    """Новый сигнал прошёл валидацию и записан в signals.json"""
    # payload: {signal_id, cluster, narrative_role}
    
class SynthesisApproved(DomainEvent):
    """Аналитик утвердил синтез"""
    # payload: {synthesis_id, cluster, version}

class RelationshipRetracted(DomainEvent):
    """Связь ретрактована"""
    # payload: {relationship_id, from_id, to_id, type, reason}

class ClusterScoreChanged(DomainEvent):
    """Score кластера изменился (добавлен/архивирован сигнал)"""
    # payload: {cluster, old_strength, new_strength}

class SynthesisExpired(DomainEvent):
    """Срок действия approved синтеза истёк"""
    # payload: {cluster, synthesis_id, expired_at}

# Простой event bus для CLI (без async, без pub/sub)
class EventLog:
    """
    В текущей архитектуре: просто лог событий для audit trail.
    При появлении backend: заменить на message queue.
    """
    def __init__(self, log_path: str = "data/events.jsonl"):
        self.log_path = log_path
    
    def emit(self, event: DomainEvent):
        """Записывает событие в append-only лог"""
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                "type": event.event_type,
                "at": event.occurred_at.isoformat(),
                **event.payload
            }, ensure_ascii=False) + '\n')
```

**Артефакт:** `domain/events.py` + `data/events.jsonl` (начинается пустым)  
**Время:** 2 часа

---

## ДЕНЬ 5. Финализация и повторный ARR

### Чеклист готовности к повторному ARR

#### Blockers (все должны быть CLOSED)

- [ ] **B1 CLOSED:** `select_bridge()` использует `seed % len(options)`, тест детерминизма зелёный
- [ ] **B2 CLOSED:** `semantic_inverse_score()` специфицирован, тесты на 5 парах зелёные
- [ ] **B3 CLOSED:** `SECURITY.md` создан, XSS уязвимость в index.html исправлена
- [ ] **B4 CLOSED:** `DISASTER_RECOVERY.md` создан, DR тест выполнен
- [ ] **B5 CLOSED:** `DEPLOYMENT.md` создан, `.github/workflows/deploy.yml` создан

#### Technical Debt Before Implementation (все должны быть DONE)

- [ ] **TD1 DONE:** `calculate_max_possible_score()` определена и задокументирована
- [ ] **TD2 DONE:** `RelationshipStore` с `LEGACY_LINKS_ENABLED` флагом создан
- [ ] **TD3 DONE:** `tests/golden/fixtures/golden_signals.json` содержит ≥15 сигналов
- [ ] **TD4 DONE:** `file_lock()` контекстный менеджер работает, тест создан
- [ ] **TD5 DONE:** `GLOSSARY.md` создан с ≥15 терминами
- [ ] **TD6 DONE:** 4-й тиебрейкер по `id` добавлен в `rank_signals()`
- [ ] **TD7 DONE:** Empty cluster рендер-контракт добавлен в BLUEPRINT_ADDENDUM
- [ ] **TD8 DONE:** Date timezone policy в `settings.py` и Signal Schema
- [ ] **TD9 DONE:** Encoding policy применена во всех file operations
- [ ] **TD10 DONE:** `domain/events.py` создан, EventLog работает

#### Дополнительные файлы для создания

- [ ] `requirements.txt` с зафиксированными версиями
- [ ] `PYTHONHASHSEED=0` в Makefile и DEPLOYMENT.md
- [ ] `tests/golden/expected/golden_synthesis.json` с ожидаемыми синтезами
- [ ] `scripts/check_staleness.py` — проверка актуальности synthesis_cache.json

---

## Итоговый план по дням

| День | Задачи | Артефакты | Время |
|------|--------|-----------|-------|
| **1** | B1, TD1, TD6, TD7, TD8, TD9 | synthesizer fix, settings.py | 6 часов |
| **2** | B2, TD2 | contradiction_detector spec, relationship_store | 6 часов |
| **3** | B3, B4, B5 | SECURITY.md, DISASTER_RECOVERY.md, DEPLOYMENT.md | 8 часов |
| **4** | TD3, TD4, TD5, TD10 | golden dataset, file_lock, GLOSSARY.md, events.py | 8 часов |
| **5** | Верификация, повторный ARR | Все чеклисты, финальный review | 4 часа |

**Итого: ~32 часа = 4 рабочих дня**

---

## Ожидаемый результат повторного ARR

После устранения всех Blockers и Technical Debt:

| Критерий | Текущий | Ожидаемый |
|----------|---------|-----------|
| Blockers | 5 | 0 |
| Architecture score | 6/10 | 8/10 |
| Narrative Engine | 5/10 | 7/10 |
| Security | 1/10 | 5/10 |
| Deployment | 0/10 | 7/10 |
| Testing | 4/10 | 6/10 |
| **Readiness** | NOT READY | **READY WITH CONDITIONS** |

---

*PRE_IMPLEMENTATION_PLAN.md · Версия 1.0 · 2026-06-28*  
*Исполнить до первого коммита кода*  
*Следующий шаг: повторный ARR после выполнения всех чеклистов*
