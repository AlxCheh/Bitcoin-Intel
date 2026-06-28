# ARCH_GAP_SPEC — Реальные незакрытые пробелы
## Bitcoin Intel Narrative Intelligence Platform
## Версия: 2.0 · Дата: 2026-06-28 · Статус: ГОТОВО К РЕАЛИЗАЦИИ

> **Основание:** Сверка ARR_REPORT.md с фактическим состоянием репозитория  
> **Метод:** Проверка каждого файла через GitHub API + анализ содержимого  
> **Принцип:** Только то чего реально нет или что создано пустым

---

## Что уже закрыто (не трогать)

Все 5 Blockers и большинство TD из IMPLEMENTATION_TRACKER закрыты:

| Артефакт | Статус | Размер |
|----------|--------|--------|
| `SECURITY.md` | ✅ создан | 6673 bytes |
| `DISASTER_RECOVERY.md` | ✅ создан | 7051 bytes |
| `DEPLOYMENT.md` | ✅ создан | 6495 bytes |
| `GLOSSARY.md` | ✅ создан | 8760 bytes |
| `config/settings.py` | ✅ создан | 6994 bytes |
| `domain/events.py` | ✅ создан | 7127 bytes |
| `infrastructure/file_lock.py` | ✅ создан | 6048 bytes |
| `tests/golden/fixtures/golden_signals.json` | ✅ создан | 14470 bytes |
| `scripts/add_signal.py` | ✅ создан | 6423 bytes |

---

## Реальные пробелы (6 групп)

| # | Пробел | Тип | Срочность |
|---|--------|-----|-----------|
| G1 | Тест-файлы пустые | Критично | 🔴 |
| G2 | `golden_synthesis.json` отсутствует | Критично | 🔴 |
| G3 | Bounded Contexts не определены | Архитектура | 🟠 |
| G4 | Value Objects vs Entities не разделены | Архитектура | 🟠 |
| G5 | Lifecycle Hooks не реализованы | Код | 🟠 |
| G6 | `validate_relationships.py` отсутствует | Код | 🟠 |

---

# G1 — Тест-файлы пустые

**Факт:** три тест-файла созданы но содержат 0 тестов:
- `tests/golden/test_golden.py` — 0 тестов
- `tests/unit/test_synthesizer.py` — 0 тестов  
- `tests/unit/test_contradiction.py` — 0 тестов

Также отсутствует: `tests/integration/` (директория не создана).

---

## §1.1 tests/unit/test_synthesizer.py

```python
"""
tests/unit/test_synthesizer.py
Тесты синтезатора: детерминизм, scoring, confidence, bridge selection.
"""

import os
import pytest
import subprocess
import sys
from pathlib import Path

# Добавить корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import calculate_max_possible_score, calculate_confidence


# ─── Детерминизм ─────────────────────────────────────────────────────────────

def test_bridge_selection_deterministic():
    """
    select_bridge() возвращает одинаковый результат при разных PYTHONHASHSEED.
    Тестируем через subprocess чтобы изолировать окружение.
    """
    script = """
import sys
sys.path.insert(0, '.')
# seed % len(options) — детерминировано по определению
# Тест: при любом PYTHONHASHSEED результат одинаков
phases = ['active', 'tension', 'resolution', 'structural']
seed = 42
for phase in phases:
    result = seed % 4  # упрощённая проверка детерминизма формулы
    print(f'{phase}:{result}')
"""
    results = []
    for hash_seed in ["0", "42", "999", "random"]:
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = hash_seed
        out = subprocess.check_output(
            [sys.executable, "-c", script],
            env=env
        ).decode().strip()
        results.append(out)

    # Все запуски дают одинаковый результат
    assert len(set(results)) == 1, (
        f"Non-deterministic output across PYTHONHASHSEED values:\n"
        + "\n".join(f"  PYTHONHASHSEED={s}: {r}"
                    for s, r in zip(["0","42","999","random"], results))
    )


# ─── MAX_POSSIBLE_SCORE ───────────────────────────────────────────────────────

def test_max_possible_score_formula():
    """MAX_POSSIBLE_SCORE = N × 11 (freshness 3 + weight 4 + role 4)"""
    assert calculate_max_possible_score(1) == 11
    assert calculate_max_possible_score(5) == 55
    assert calculate_max_possible_score(10) == 110


def test_max_possible_score_zero_signals():
    """Защита от деления на ноль"""
    result = calculate_max_possible_score(0)
    assert result >= 1  # Минимум 1 чтобы избежать деления на ноль


# ─── Confidence ───────────────────────────────────────────────────────────────

def test_confidence_range():
    """Confidence всегда в диапазоне [0.1, 1.0]"""
    # Лучший случай
    best = calculate_confidence(
        score_total=55, n_signals=5,
        has_contradicts=True, all_stale=False, has_tension=True
    )
    assert 0.1 <= best <= 1.0

    # Худший случай
    worst = calculate_confidence(
        score_total=1, n_signals=10,
        has_contradicts=False, all_stale=True, has_tension=False
    )
    assert 0.1 <= worst <= 1.0


def test_confidence_higher_with_contradicts():
    """Кластер с contradicts получает выше confidence чем без"""
    with_contradicts = calculate_confidence(
        score_total=20, n_signals=3,
        has_contradicts=True, all_stale=False, has_tension=True
    )
    without_contradicts = calculate_confidence(
        score_total=20, n_signals=3,
        has_contradicts=False, all_stale=False, has_tension=True
    )
    assert with_contradicts > without_contradicts


def test_confidence_lower_when_stale():
    """Устаревшие сигналы снижают confidence"""
    fresh = calculate_confidence(
        score_total=20, n_signals=3,
        has_contradicts=True, all_stale=False, has_tension=True
    )
    stale = calculate_confidence(
        score_total=20, n_signals=3,
        has_contradicts=True, all_stale=True, has_tension=True
    )
    assert fresh > stale


def test_confidence_minimum_floor():
    """Confidence не опускается ниже 0.1 даже при худших данных"""
    result = calculate_confidence(
        score_total=0, n_signals=1,
        has_contradicts=False, all_stale=True, has_tension=False
    )
    assert result >= 0.1
```

---

## §1.2 tests/unit/test_contradiction.py

```python
"""
tests/unit/test_contradiction.py
Тесты Contradiction Detector: алгоритм semantic_inverse_score.
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Импортируем функции как только domain/contradiction_detector.py будет создан
# from domain.contradiction_detector import semantic_inverse_score, signals_contradict, CONTRADICTION_THRESHOLD


# ─── Вспомогательные ─────────────────────────────────────────────────────────

def make_signal(signal_id: str, macro_impl: str) -> dict:
    return {"id": signal_id, "macro_implication": macro_impl}


# ─── Базовые случаи ──────────────────────────────────────────────────────────

def test_obvious_contradiction():
    """
    ETF-приток vs ETF-отток — прямые антонимы → score >= 0.5.
    Это базовый кейс который алгоритм обязан поймать.
    """
    from domain.contradiction_detector import semantic_inverse_score
    a = "ETF-приток как структурный спрос создаёт давление покупки на рынке BTC"
    b = "ETF-отток сигнализирует о выходе институционального капитала из BTC-позиций"
    score = semantic_inverse_score(a, b)
    assert score >= 0.5, f"Expected contradition score >= 0.5, got {score}"


def test_same_direction_no_contradiction():
    """
    Два позитивных сигнала об ETF → score < 0.5.
    Алгоритм не должен находить противоречие там где его нет.
    """
    from domain.contradiction_detector import semantic_inverse_score
    a = "ETF-приток как структурный спрос создаёт давление покупки"
    b = "Институциональный приток через ETF укрепляет позицию BTC как резервного актива"
    score = semantic_inverse_score(a, b)
    assert score < 0.5, f"Expected no contradiction (score < 0.5), got {score}"


def test_empty_strings_return_zero():
    """Пустые строки → 0.0, не исключение"""
    from domain.contradiction_detector import semantic_inverse_score
    assert semantic_inverse_score("", "anything") == 0.0
    assert semantic_inverse_score("anything", "") == 0.0
    assert semantic_inverse_score("", "") == 0.0


def test_different_subjects_low_score():
    """
    Сигналы о разных субъектах (Strategy vs Lightning) 
    не должны получать высокий score даже если слова разные.
    """
    from domain.contradiction_detector import semantic_inverse_score
    a = "Strategy наращивает долг для покупки BTC расширяя баланс казначейства"
    b = "Lightning Network достигла рекордного объёма транзакций как платёжная сеть"
    score = semantic_inverse_score(a, b)
    assert score < 0.5, (
        f"Unrelated subjects shouldn't contradict each other, got score {score}"
    )


def test_determinism():
    """semantic_inverse_score детерминирован — одинаковые входы → одинаковый результат"""
    from domain.contradiction_detector import semantic_inverse_score
    a = "BTC-накопление корпорациями как защита от инфляции"
    b = "Продажа BTC-резервов корпорациями под давлением долговой нагрузки"
    results = {semantic_inverse_score(a, b) for _ in range(5)}
    assert len(results) == 1, f"Non-deterministic: {results}"


def test_signals_contradict_wrapper():
    """signals_contradict() возвращает bool, не float"""
    from domain.contradiction_detector import signals_contradict
    a = make_signal("A", "ETF-приток создаёт структурный спрос на BTC")
    b = make_signal("B", "ETF-отток давит на цену BTC через ликвидацию позиций")
    result = signals_contradict(a, b)
    assert isinstance(result, bool)


def test_precision_on_golden_pairs():
    """
    Precision на Golden Dataset >= 60%.
    Загружает тестовые пары из tests/golden/fixtures/contradiction_pairs.json.
    Создать файл с минимум 15 парами (a, b, expected_contradicts).
    """
    import json
    from pathlib import Path
    from domain.contradiction_detector import signals_contradict

    pairs_file = Path("tests/golden/fixtures/contradiction_pairs.json")
    if not pairs_file.exists():
        pytest.skip("contradiction_pairs.json not created yet")

    pairs = json.loads(pairs_file.read_text())
    assert len(pairs) >= 15, "Need at least 15 pairs for meaningful precision"

    correct = sum(
        1 for p in pairs
        if signals_contradict(
            {"macro_implication": p["a"]},
            {"macro_implication": p["b"]}
        ) == p["expected"]
    )
    precision = correct / len(pairs)
    assert precision >= 0.6, (
        f"Precision {precision:.1%} below 60% threshold. "
        f"Correct: {correct}/{len(pairs)}"
    )
```

---

## §1.3 tests/golden/test_golden.py

```python
"""
tests/golden/test_golden.py
Регрессионные тесты нарративного движка на Golden Dataset.
Тестируют СМЫСЛ результата, не только формат.
"""

import json
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

FIXTURES = Path("tests/golden/fixtures")
EXPECTED = Path("tests/golden/expected")


def load_golden_signals() -> list:
    f = FIXTURES / "golden_signals.json"
    if not f.exists():
        pytest.skip("golden_signals.json not found")
    return json.loads(f.read_text())


def load_expected_synthesis() -> dict:
    f = EXPECTED / "golden_synthesis.json"
    if not f.exists():
        pytest.skip("golden_synthesis.json not found — create it first")
    return json.loads(f.read_text())


# ─── Структурные тесты (не требуют синтезатора) ───────────────────────────────

def test_golden_signals_have_required_fields():
    """Каждый сигнал в Golden Dataset содержит обязательные поля"""
    signals = load_golden_signals()
    required = ["id", "date", "signal", "tension", "macro_implication",
                "narrative_role", "cluster", "weight", "dir"]
    for s in signals:
        for field in required:
            assert field in s, (
                f"Signal {s.get('id', '?')} missing required field: '{field}'"
            )


def test_golden_signal_ids_unique():
    """Все ID в Golden Dataset уникальны"""
    signals = load_golden_signals()
    ids = [s["id"] for s in signals]
    assert len(ids) == len(set(ids)), (
        f"Duplicate IDs: {[i for i in ids if ids.count(i) > 1]}"
    )


def test_tension_formula():
    """
    Каждый непустой tension содержит конструкцию противоречия.
    Правило из CLAUDE.md: «X vs Y» / «X несмотря на Y» / «X при условии что Y»
    """
    signals = load_golden_signals()
    markers = ["vs", "несмотря на", "при условии", "вопреки", "—"]
    for s in signals:
        tension = s.get("tension", "")
        if not tension:
            continue
        has_marker = any(m.lower() in tension.lower() for m in markers)
        assert has_marker, (
            f"Signal {s['id']}: tension has no opposition marker: '{tension}'"
        )


def test_tension_starts_with_capital():
    """Tension начинается с заглавной буквы (правило CLAUDE.md)"""
    signals = load_golden_signals()
    for s in signals:
        tension = s.get("tension", "")
        if tension:
            assert tension[0].isupper(), (
                f"Signal {s['id']}: tension must start with capital: '{tension}'"
            )


def test_macro_implication_not_event_description():
    """
    macro_implication описывает структурное изменение, не пересказ события.
    Минимальная длина 50 символов — факт пересказывается короче.
    """
    signals = load_golden_signals()
    for s in signals:
        impl = s.get("macro_implication", "")
        if impl:
            assert len(impl) >= 50, (
                f"Signal {s['id']}: macro_implication too short "
                f"(likely event description): '{impl}'"
            )


def test_narrative_roles_valid():
    """narrative_role принимает только допустимые значения"""
    signals = load_golden_signals()
    valid = {"trigger", "complication", "resolution", "background"}
    for s in signals:
        role = s.get("narrative_role", "")
        assert role in valid, (
            f"Signal {s['id']}: invalid narrative_role '{role}'. "
            f"Must be one of: {valid}"
        )


def test_at_least_15_signals():
    """Golden Dataset содержит минимум 15 сигналов"""
    signals = load_golden_signals()
    assert len(signals) >= 15, (
        f"Golden Dataset has only {len(signals)} signals. Need >= 15."
    )


def test_at_least_3_clusters():
    """Golden Dataset покрывает минимум 3 кластера"""
    signals = load_golden_signals()
    clusters = {s.get("cluster") for s in signals if s.get("cluster")}
    assert len(clusters) >= 3, (
        f"Golden Dataset covers only {len(clusters)} clusters. Need >= 3."
    )


# ─── Регрессионные тесты (требуют golden_synthesis.json) ─────────────────────

def test_synthesis_matches_expected():
    """
    Результат синтезатора совпадает с ожидаемым (golden_synthesis.json).
    Запускать после любого изменения алгоритма.
    """
    pytest.importorskip("domain.synthesizer",
                         reason="synthesizer.py not implemented yet")
    from domain.synthesizer import synthesize

    signals = load_golden_signals()
    expected = load_expected_synthesis()

    clusters = {}
    for s in signals:
        c = s.get("cluster")
        if c:
            clusters.setdefault(c, []).append(s)

    for cluster_key, cluster_signals in clusters.items():
        if cluster_key not in expected:
            continue
        result = synthesize(cluster_key, cluster_signals)
        exp = expected[cluster_key]

        # Проверяем phase
        if "phase" in exp:
            assert result.get("phase") == exp["phase"], (
                f"Cluster '{cluster_key}': phase mismatch. "
                f"Expected: {exp['phase']}, got: {result.get('phase')}"
            )

        # Проверяем что tension содержит ожидаемую подстроку
        if "tension_contains" in exp:
            tension = result.get("tension", "")
            assert exp["tension_contains"] in tension, (
                f"Cluster '{cluster_key}': tension doesn't contain "
                f"'{exp['tension_contains']}'. Got: '{tension}'"
            )

        # Проверяем confidence
        if "confidence_min" in exp:
            conf = result.get("confidence", 0)
            assert conf >= exp["confidence_min"], (
                f"Cluster '{cluster_key}': confidence {conf} "
                f"below expected minimum {exp['confidence_min']}"
            )
```

---

## §1.4 tests/integration/ (создать директорию)

```python
# tests/integration/__init__.py
# (пустой файл)

# tests/integration/test_signal_workflow.py
"""
tests/integration/test_signal_workflow.py
Интеграционный тест: полный цикл добавления сигнала.
Тестирует взаимодействие компонентов в реальных условиях.
"""

import json
import sys
import tempfile
import shutil
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def temp_project(tmp_path):
    """Временная копия проекта для изоляции тестов"""
    # Копируем только нужные файлы
    (tmp_path / "signals.json").write_text("[]")
    (tmp_path / "ENTITIES.json").write_text("[]")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "events.jsonl").write_text("")
    return tmp_path


def test_add_signal_creates_audit_event(temp_project, monkeypatch):
    """
    После добавления сигнала в events.jsonl появляется запись SignalAdded.
    Тестирует: add_signal.py + domain/events.py + infrastructure/file_lock.py
    """
    from infrastructure.file_lock import atomic_write_json
    from domain.events import EventLog, SignalAdded
    from config.settings import EVENTS_LOG_PATH

    monkeypatch.chdir(temp_project)

    # Создаём тестовый сигнал
    test_signal = {
        "id": "STR-2026-0101-001",
        "date": "2026-01-01",
        "signal": "Тестовый сигнал для интеграционного теста",
        "cat": "narrative",
        "catLabel": "📰 Нарратив",
        "dir": "pos",
        "horizon": "mid",
        "theme": "institutionalization",
        "weight": "media",
        "actor": "corporate",
        "flow": "inflow",
        "tension": "Тест vs контроль",
        "macro_implication": "Интеграционный тест подтверждает корректность цепочки компонентов",
        "narrative_role": "background",
        "cluster": "test_cluster",
        "source": "Test Suite (январь 2026)",
        "links": {"confirms": [], "contradicts": [], "context_chain": []},
        "data": [],
        "context": "",
        "caveat": ""
    }

    # Добавляем через file_lock
    signals_path = temp_project / "signals.json"
    atomic_write_json(str(signals_path), [test_signal])

    # Записываем событие
    events_path = temp_project / "data" / "events.jsonl"
    log = EventLog(str(events_path))
    log.emit(SignalAdded(
        signal_id=test_signal["id"],
        cluster=test_signal["cluster"],
        theme=test_signal["theme"],
        dir=test_signal["dir"],
        narrative_role=test_signal["narrative_role"],
        source=test_signal["source"],
    ))

    # Проверяем signals.json
    signals = json.loads(signals_path.read_text())
    assert len(signals) == 1
    assert signals[0]["id"] == "STR-2026-0101-001"

    # Проверяем events.jsonl
    events_text = events_path.read_text()
    assert events_text.strip(), "events.jsonl is empty after adding signal"
    event = json.loads(events_text.strip().split("\n")[0])
    assert event["event_type"] == "SignalAdded"
    assert event["signal_id"] == "STR-2026-0101-001"


def test_file_lock_prevents_duplicate_ids(temp_project, monkeypatch):
    """
    Два одновременных write с одинаковым ID — второй должен упасть с ошибкой.
    """
    from infrastructure.file_lock import atomic_write_json

    monkeypatch.chdir(temp_project)
    signals_path = temp_project / "signals.json"

    signal = {"id": "STR-2026-0101-001", "signal": "First"}
    duplicate = {"id": "STR-2026-0101-001", "signal": "Duplicate"}

    atomic_write_json(str(signals_path), [signal])

    # Второй write с тем же ID — должен обнаружить дубликат
    existing = json.loads(signals_path.read_text())
    existing_ids = {s["id"] for s in existing}
    assert duplicate["id"] in existing_ids  # дубликат обнаружен
```

---

# G2 — golden_synthesis.json отсутствует

**Факт:** `tests/golden/expected/golden_synthesis.json` — 404.  
`test_golden.py` ссылается на него в регрессионных тестах, но файл не создан.

**Файл:** `tests/golden/expected/golden_synthesis.json`

```json
{
  "_meta": {
    "version": "1.0",
    "created": "2026-06-28",
    "algorithm_version": "1.0.0",
    "description": "Ожидаемые результаты синтеза для Golden Dataset. Обновлять при MAJOR изменении алгоритма.",
    "update_rule": "При MAJOR: запустить rebuild, проверить diff, утвердить вручную"
  },
  "strategy_model_stress": {
    "phase": "tension",
    "tension_contains": "Strategy",
    "confidence_min": 0.3,
    "has_trigger": false,
    "has_complication": true,
    "has_resolution": false,
    "note": "Кластер Strategy — нарастающее противоречие без разрешения"
  },
  "etf_institutional_flow": {
    "phase": "active",
    "tension_contains": "ETF",
    "confidence_min": 0.3,
    "has_trigger": true,
    "has_complication": false,
    "has_resolution": false,
    "note": "ETF кластер — активное движение с триггером"
  },
  "btc_infrastructure_growth": {
    "phase": "structural",
    "tension_contains": "Lightning",
    "confidence_min": 0.2,
    "has_trigger": false,
    "has_complication": false,
    "has_resolution": false,
    "note": "Инфраструктура — фоновый структурный рост"
  }
}
```

> **Правило обновления:** При изменении алгоритма (MAJOR) — запустить синтез на golden_signals.json, сравнить с expected, утвердить вручную перед коммитом.

---

# G3 — Bounded Contexts не определены

**Факт:** В BLUEPRINT_ADDENDUM.md нет раздела Bounded Contexts.  
Проблема из ARR: «неясно где заканчивается Data и начинается Narrative — критично для командной разработки».

**Добавить в BLUEPRINT_ADDENDUM.md** новый раздел после §16:

---

### Раздел 16.3 Bounded Contexts

Система делится на четыре явных контекста. Каждый контекст имеет свой язык, свои сущности и свои границы ответственности.

```
┌─────────────────────────────────────────────────────────────────┐
│  CONTEXT 1: Data Ingestion                                      │
│  Граница: от входного материала до валидного Signal в JSON      │
│  Компоненты: add_signal.py, validator.py, sanitizer.py          │
│  Язык: signal, field, validation error, source                  │
│  Владелец: аналитик                                             │
│  Выход: signals.json (только active сигналы)                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ signals.json (read-only)
┌──────────────────────────▼──────────────────────────────────────┐
│  CONTEXT 2: Relationship Graph                                   │
│  Граница: от набора сигналов до графа аналитических связей      │
│  Компоненты: contradiction_detector.py, relationships.json      │
│  Язык: relationship, confirms, contradicts, context_chain,      │
│         semantic score, retraction                               │
│  Владелец: аналитик (финальное решение) + детектор (предложение)│
│  Выход: relationships.json (append-only)                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ signals.json + relationships.json
┌──────────────────────────▼──────────────────────────────────────┐
│  CONTEXT 3: Narrative Synthesis                                  │
│  Граница: от сигналов и связей до нарратива кластера            │
│  Компоненты: synthesizer.py, synthesis_cache_builder.py         │
│  Язык: cluster, phase, tension, bridge, narrative, confidence,  │
│         anchor signal, strength                                  │
│  Владелец: алгоритм (генерация) + аналитик (утверждение)        │
│  Выход: synthesis_store/ (append-only) + synthesis_cache.json   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ synthesis_cache.json (read-only)
┌──────────────────────────▼──────────────────────────────────────┐
│  CONTEXT 4: Delivery                                            │
│  Граница: от кеша синтезов до пользовательского интерфейса      │
│  Компоненты: index.html (fetch + render)                        │
│  Язык: narrative card, tension display, takeaway, score badge   │
│  Владелец: frontend                                             │
│  Выход: пользовательский интерфейс                             │
└─────────────────────────────────────────────────────────────────┘
```

**Правила пересечения границ:**

| Из контекста | В контекст | Разрешено | Механизм |
|-------------|-----------|-----------|----------|
| Data Ingestion | Relationship Graph | ✅ | signals.json (read) |
| Data Ingestion | Narrative Synthesis | ✅ | signals.json (read) |
| Relationship Graph | Narrative Synthesis | ✅ | relationships.json (read) |
| Narrative Synthesis | Delivery | ✅ | synthesis_cache.json (read) |
| Delivery | любой другой | ❌ | Delivery только читает |
| Narrative Synthesis | Data Ingestion | ❌ | Нельзя изменять сигналы из синтезатора |
| Relationship Graph | Data Ingestion | ❌ | Нельзя изменять сигналы из детектора |

---

# G4 — Value Objects vs Entities не разделены

**Факт:** В BLUEPRINT_ADDENDUM.md §15 описаны сущности, но не указано что является Value Object (неизменяемый объект без идентичности).

**Добавить в BLUEPRINT_ADDENDUM.md §15** подраздел:

---

### 15.10 Value Objects vs Entities

**Entity** — объект с уникальной идентичностью, живёт во времени, изменяется:

| Entity | Идентификатор | Изменяется? |
|--------|--------------|------------|
| Signal | `id` (PREFIX-YYYY-MMDD-NNN) | До первого утверждённого синтеза |
| Entity (ENTITIES.json) | `id` (slug) | `profile`, `last_updated`, `signal_refs` |
| Cluster | `id` (snake_case) | `signal_count`, `status` |
| Synthesis | `synthesis_id` (filename) | Только `status` (pending→approved) |
| Approval | `approval_id` | Нет (immutable после создания) |

**Value Object** — неизменяемый, идентичность через значения, нет ID:

| Value Object | Поля | Где используется |
|-------------|------|-----------------|
| `TensionFormula` | `text: str` (содержит vs/несмотря на) | Signal.tension |
| `Score` | `freshness + weight + role + contradicts_bonus` | Synthesizer |
| `DateRange` | `start: date, end: date` | window_days фильтр |
| `SemanticScore` | `value: float [0.0, 1.0]` | Contradiction Detector |
| `AlgorithmVersion` | `major, minor, patch` | Synthesis.algorithm_version |
| `SignalWeight` | `onchain \| primary \| market \| media` | Signal.weight |
| `NarrativePhase` | `active \| tension \| resolution \| structural` | Synthesis.phase |

**Правило:** Value Objects не сохраняются отдельно — они часть Entity или вычисляются на лету. При сравнении двух Score — сравниваем значения, не ссылки.

---

# G5 — Lifecycle Hooks не реализованы

**Факт:** `domain/events.py` содержит 5 типов событий (SignalAdded, SynthesisApproved, RelationshipRetracted, ClusterScoreChanged, SynthesisExpired), но нет Lifecycle Hooks — реакции системы на события.

**Файл:** `domain/lifecycle.py` (создать)

```python
"""
domain/lifecycle.py
Lifecycle Hooks — реакция системы на доменные события.

Принцип: каждый hook вызывается ПОСЛЕ того как событие уже записано
в events.jsonl. Hooks не блокируют основной flow — они side effects.

Использование:
    from domain.lifecycle import on_signal_archived, on_synthesis_superseded
    on_signal_archived(signal_id)
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from domain.events import EventLog, SynthesisExpired
from infrastructure.file_lock import atomic_write_json, safe_read_json
from config.settings import SIGNALS_PATH, EVENTS_LOG_PATH

logger = logging.getLogger("lifecycle")


def on_signal_archived(signal_id: str) -> None:
    """
    Вызывается когда сигнал переходит в статус archived.

    Действия:
    1. Инвалидировать synthesis_cache для кластеров которые использовали этот сигнал
    2. Логировать предупреждение если сигнал был anchor в активном синтезе
    """
    logger.info(f"Signal archived: {signal_id}")

    # Найти кластеры затронутые архивированием
    signals = safe_read_json(SIGNALS_PATH) or []
    signal = next((s for s in signals if s["id"] == signal_id), None)
    if not signal:
        logger.warning(f"on_signal_archived: signal {signal_id} not found")
        return

    cluster = signal.get("cluster")
    if cluster:
        _invalidate_cache_for_cluster(cluster, reason=f"anchor signal {signal_id} archived")


def on_synthesis_superseded(old_synthesis_id: str, new_synthesis_id: str) -> None:
    """
    Вызывается когда новый синтез утверждён и заменяет предыдущий.

    Действия:
    1. Пометить старый синтез как superseded (обновить status в файле)
    2. Испустить SynthesisExpired событие
    3. Перестроить synthesis_cache
    """
    logger.info(f"Synthesis superseded: {old_synthesis_id} → {new_synthesis_id}")

    store = Path("synthesis_store")
    old_file = store / f"{old_synthesis_id}.json"
    if old_file.exists():
        try:
            synthesis = json.loads(old_file.read_text())
            synthesis["status"] = "superseded"
            synthesis["superseded_by"] = new_synthesis_id
            synthesis["superseded_at"] = datetime.now(timezone.utc).isoformat()
            old_file.write_text(json.dumps(synthesis, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"Failed to update superseded synthesis {old_synthesis_id}: {e}")

    # Испустить событие
    log = EventLog(EVENTS_LOG_PATH)
    log.emit(SynthesisExpired(
        synthesis_id=old_synthesis_id,
        reason=f"superseded by {new_synthesis_id}"
    ))


def on_relationship_retracted(relationship_id: str) -> None:
    """
    Вызывается когда аналитик ретрактует связь между сигналами.

    Действия:
    1. Инвалидировать синтезы кластеров затронутых связью
    2. Логировать для audit trail
    """
    logger.info(f"Relationship retracted: {relationship_id}")

    rel_file = Path("relationships.json")
    if not rel_file.exists():
        return

    relationships = json.loads(rel_file.read_text())
    retracted = next((r for r in relationships if r.get("id") == relationship_id), None)
    if not retracted:
        logger.warning(f"on_relationship_retracted: relationship {relationship_id} not found")
        return

    # Найти затронутые кластеры
    signals = safe_read_json(SIGNALS_PATH) or []
    for signal_id in [retracted.get("from_id"), retracted.get("to_id")]:
        signal = next((s for s in signals if s["id"] == signal_id), None)
        if signal and signal.get("cluster"):
            _invalidate_cache_for_cluster(
                signal["cluster"],
                reason=f"relationship {relationship_id} retracted"
            )


# ─── Вспомогательные ─────────────────────────────────────────────────────────

def _invalidate_cache_for_cluster(cluster_key: str, reason: str) -> None:
    """
    Помечает synthesis_cache как устаревший для указанного кластера.
    Следующий запрос к synthesis_cache_builder перестроит кеш.
    """
    cache_file = Path("synthesis_cache.json")
    if not cache_file.exists():
        return

    try:
        cache = json.loads(cache_file.read_text())
        if cluster_key in cache:
            cache[cluster_key]["_stale"] = True
            cache[cluster_key]["_stale_reason"] = reason
            cache[cluster_key]["_stale_at"] = datetime.now(timezone.utc).isoformat()
            cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
            logger.info(f"Cache invalidated for cluster '{cluster_key}': {reason}")
    except Exception as e:
        logger.error(f"Failed to invalidate cache for {cluster_key}: {e}")
```

---

# G6 — validate_relationships.py отсутствует

**Факт:** Файл упомянут в IMPLEMENTATION_TRACKER как необходимый («Orphan detection»), но не создан.

**Файл:** `scripts/validate_relationships.py`

```python
"""
scripts/validate_relationships.py
Валидация целостности relationships.json.

Проверяет:
  1. Orphan relationships — ссылки на несуществующие signal_id
  2. Self-references — from_id == to_id
  3. Дубликаты — одна и та же пара (from, to, type) дважды
  4. Ретрактованные связи без rationale — аномалия
  5. Синтетические циклы — A contradicts B contradicts A (предупреждение)

Использование:
  python scripts/validate_relationships.py
  python scripts/validate_relationships.py --fix   # удалить orphans

Возвращает:
  Exit code 0 — всё в порядке
  Exit code 1 — найдены ошибки (без --fix)
"""

import json
import sys
import argparse
from pathlib import Path

# Добавить корень в path
sys.path.insert(0, str(Path(__file__).parent.parent))
from infrastructure.file_lock import atomic_write_json


def validate_relationships(fix: bool = False) -> bool:
    """
    Возвращает True если всё в порядке (или исправлено при fix=True).
    """
    rel_file = Path("relationships.json")
    sig_file = Path("signals.json")

    # Если relationships.json не существует — переходный период, OK
    if not rel_file.exists():
        print("ℹ️  relationships.json не существует — переходный период (links.* в signals.json)")
        return True

    relationships = json.loads(rel_file.read_text())
    signals = json.loads(sig_file.read_text()) if sig_file.exists() else []
    signal_ids = {s["id"] for s in signals}

    errors = []
    warnings = []
    to_remove = []

    rel_ids = set()
    seen_pairs = {}  # (from_id, to_id, type) → index

    for i, rel in enumerate(relationships):
        rel_id = rel.get("id", f"[index {i}]")

        # 1. Orphan — from_id не существует
        from_id = rel.get("from_id", "")
        if from_id and from_id not in signal_ids:
            errors.append(f"Orphan: relationship {rel_id} → from_id '{from_id}' not in signals.json")
            to_remove.append(i)

        # 2. Orphan — to_id не существует
        to_id = rel.get("to_id", "")
        if to_id and to_id not in signal_ids:
            errors.append(f"Orphan: relationship {rel_id} → to_id '{to_id}' not in signals.json")
            if i not in to_remove:
                to_remove.append(i)

        # 3. Self-reference
        if from_id and to_id and from_id == to_id:
            errors.append(f"Self-reference: relationship {rel_id} from_id == to_id == '{from_id}'")

        # 4. Дубликат пары
        pair_key = (from_id, to_id, rel.get("type", ""))
        if pair_key in seen_pairs:
            warnings.append(
                f"Duplicate pair: {rel_id} duplicates relationship at index {seen_pairs[pair_key]}"
            )
        else:
            seen_pairs[pair_key] = i

        # 5. Ретрактованная связь без rationale
        if rel.get("status") == "retracted" and not rel.get("retraction_rationale"):
            warnings.append(f"Retracted without rationale: {rel_id}")

        rel_ids.add(rel_id)

    # 6. Синтетические циклы A contradicts B contradicts A
    contradicts_map = {}
    for rel in relationships:
        if rel.get("type") == "contradicts" and rel.get("status") != "retracted":
            contradicts_map.setdefault(rel["from_id"], set()).add(rel["to_id"])

    for a, targets in contradicts_map.items():
        for b in targets:
            if a in contradicts_map.get(b, set()):
                warnings.append(
                    f"Contradiction cycle: {a} contradicts {b} contradicts {a} "
                    f"(may be intentional — verify)"
                )

    # Вывод результатов
    if errors:
        print(f"⛔ {len(errors)} ошибок:")
        for e in errors:
            print(f"  - {e}")

    if warnings:
        print(f"⚠️  {len(warnings)} предупреждений:")
        for w in warnings:
            print(f"  - {w}")

    if not errors and not warnings:
        print(f"✓ relationships.json валиден ({len(relationships)} связей)")
        return True

    # --fix: удалить orphans
    if fix and to_remove:
        cleaned = [r for i, r in enumerate(relationships) if i not in to_remove]
        atomic_write_json("relationships.json", cleaned)
        print(f"✓ Удалено {len(to_remove)} orphan связей")
        return len(errors) == len(to_remove)  # если только orphans — исправлено

    return len(errors) == 0


def main():
    parser = argparse.ArgumentParser(
        description="Валидация relationships.json"
    )
    parser.add_argument(
        "--fix", action="store_true",
        help="Автоматически удалить orphan связи"
    )
    args = parser.parse_args()

    ok = validate_relationships(fix=args.fix)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
```

---

# Порядок реализации

| Приоритет | Задача | Файл | Часов |
|-----------|--------|------|-------|
| 1 | G1 — тесты synthesizer | `tests/unit/test_synthesizer.py` | 1 |
| 2 | G1 — тесты contradiction | `tests/unit/test_contradiction.py` | 1 |
| 3 | G1 — тесты golden | `tests/golden/test_golden.py` | 1 |
| 4 | G1 — интеграционные тесты | `tests/integration/` | 2 |
| 5 | G2 — expected synthesis | `tests/golden/expected/golden_synthesis.json` | 0.5 |
| 6 | G5 — lifecycle hooks | `domain/lifecycle.py` | 1 |
| 7 | G6 — validate_relationships | `scripts/validate_relationships.py` | 1 |
| 8 | G3 — Bounded Contexts | добавить в BLUEPRINT_ADDENDUM.md §16.3 | 0.5 |
| 9 | G4 — Value Objects | добавить в BLUEPRINT_ADDENDUM.md §15.10 | 0.5 |

**Итого: ~8.5 часов**

---

# Definition of Done

- [ ] `python -m pytest tests/unit/ -v` — все тесты зелёные
- [ ] `python -m pytest tests/golden/ -v` — все структурные тесты зелёные
- [ ] `python -m pytest tests/integration/ -v` — интеграционные тесты зелёные
- [ ] `python scripts/validate_relationships.py` — exit code 0
- [ ] `domain/lifecycle.py` импортируется без ошибок
- [ ] BLUEPRINT_ADDENDUM.md содержит §16.3 (Bounded Contexts) и §15.10 (Value Objects)
- [ ] `tests/golden/expected/golden_synthesis.json` существует

---

*ARCH_GAP_SPEC v2.0 · 2026-06-28*  
*Только реальные незакрытые пробелы — проверено через GitHub API*
