# ALGORITHM.md — Алгоритм нарративного синтеза
## Источник истины: `scripts/synthesizer.py`
## Версия: 2.0 · Обновлено: 2026-06-29

> Этот документ описывает **реально исполняемый код**, не архитектурный замысел.
> При любом расхождении между этим файлом и `scripts/synthesizer.py` — код прав, документ устарел.
> Каждый раздел ниже сверен построчно с актуальной версией синтезатора.

---

## Зачем нужен синтезатор

`signals.json` — плоский список фактов. Человек видит сигналы, но не видит **общую картину**: какое противоречие сейчас главное в кластере, насколько оно острое, к чему оно ведёт. Синтезатор превращает список сигналов в одну карточку нарратива на кластер — то что показывается в блоке «Главные нарративы» на сайте.

Запуск: `PYTHONHASHSEED=0 python3 scripts/synthesizer.py`. `PYTHONHASHSEED=0` обязателен — без него `select_bridge()` теряет воспроизводимость (хотя формула не зависит от хеша Python, переменная фиксируется для consistency со всей кодовой базой через `assert_deterministic_env()`).

---

## Общая схема

```
signals.json
     │
     ▼
группировка по cluster
     │
     ▼
для каждого кластера → synthesize_cluster(cluster_key, signals, previous_synthesis)
     │                                              │
     │                              previous_synthesis загружается
     │                              СНАРУЖИ функции (см. §17 ниже) —
     │                              синтезатор не читает файлы сам
     ▼
SynthesisResult
     │
     ▼
data/synthesis_cache.json  ──→  index.html (блок «Главные нарративы»)
     │
     └──→  synthesis_store/synthesis_{cluster}_{timestamp}.json (история)
```

---

## 12 шагов синтеза (`synthesize_cluster`)

Перед всеми 12 шагами выполняется **дедупликация** (не пронумерована, идёт первой):

### Шаг 0 — Дедупликация (`deduplicate_signals`)

Дубликатом считаются сигналы с одинаковым ключом `(date, actor, cluster, dir)`. Из дублирующей группы остаётся сигнал с наибольшим `weight_score`; остальные логируются как `ignored_ids` и не участвуют в синтезе. Это защита от шума — например, если два сигнала за один день про одного актора в одном направлении описывают по сути одно событие.

### Шаг 1 — Фильтрация по окну и статусу

Отбрасываются сигналы старше `WINDOW_DAYS_DEFAULT = 90` дней и сигналы со `status: archived`. Повреждённый сигнал (упавший на любой операции) пропускается с `WARNING`, не прерывая обработку остальных (DEGRADE GRACEFULLY). Если после фильтрации не осталось сигналов — `EmptyClusterError`.

### Шаг 2 — Ранжирование (`_rank_signals`)

4-уровневый tiebreaker, гарантирующий детерминизм:

1. `score.total` DESC (см. формулу score ниже)
2. `weight_score` DESC
3. `date` DESC
4. `id` ASC — последний уровень, если все остальные равны

### Шаг 3 — Определение фазы (`_detect_phase`)

```python
if есть resolution:                           → "resolution"
elif есть trigger И есть complication:        → "active"
elif complication > trigger:                  → "tension"
else:                                          → "structural"
```

Фаза влияет на выбор bridge-фразы (Шаг 7–8) и на приоритет в выборе tension (Шаг 6).

### Шаг 3.5 — Обработка неопределённости (`handle_uncertainty`)

Добавлен 2026-06-29 (B3, ARR v2). Три проверки, каждая может добавить запись в `uncertainty: dict`:

**1. Баланс pos/neg.** Если `pos/(pos+neg)` находится в диапазоне `[0.4, 0.6]` (порог `pos_neg_balance_threshold = 0.6`) — `uncertainty["direction"] = "contested"`, и `score_multiplier = 0.7` снижает freshness-часть итогового score кластера.

**2. Несколько trigger.** Если в кластере больше одного `trigger` — выбирается самый свежий по дате, остальные попадают в `ignored_triggers`.

**3. Устаревший tension.** Если у текущего anchor-победителя (по числу contradicts) дата старше `tension_staleness_days = 90` дней — добавляется `tension_stale: True` и `tension_stale_label` с предупреждающим текстом.

Все три правила читаются из `UNCERTAINTY_RULES` в `config/settings.py`.

### Шаг 4 — Разбивка по ролям

Сигналы разбираются на `triggers`, `complications`, `resolutions` (списки, отсортированные по итогам Шага 2). `anchor_trigger` — первый trigger или, если их нет, первый сигнал по рангу вообще. `anchor_complication` и `anchor_resolution` — первые в своих списках или `None`.

### Шаг 5 — Contradiction weighting

Не отдельный шаг по факту — бонус за `contradicts` уже учтён в `_score_signal()` при вычислении `score.total` на Шаге 2 (см. формулу score).

### Шаг 6 — Выбор tension (`_select_tension_source`)

**Обновлено 2026-06-29.** Приоритет:

```
0. Если есть сигнал с narrative_role = "resolution"
   → он побеждает безусловно (самый свежий, если их несколько),
     независимо от числа contradicts.

1. Иначе: MAX(contradicts) → MAX(weight) → MAX(date)
```

Resolution получил приоритет 0 потому что фаза кластера уже объявляет "вопрос закрыт" (Шаг 3) — продолжать показывать старый tension от complication создавало внутреннее противоречие карточки: phase говорит "разрешено", tension говорит "ещё открыто". Реальный кейс который выявил проблему: `STR-2026-0629-001` (Strategy Digital Credit Capital Framework) не мог стать anchor с 0 contradicts против complication с 4 contradicts, хотя именно он закрывал главный вопрос кластера.

Текст tension берётся **как есть**, без модификации, только с приведением первой буквы к заглавной (`_capitalize`).

### Шаг 7–8 — Narrative (partA + bridge + partB)

```python
partA  = anchor_trigger.macro_implication, первое предложение (до ". ")
bridge = select_bridge(phase, seed=len(active_signals))
partB  = (anchor_complication или второй сигнал по рангу).macro_implication,
         первое предложение, первая буква в нижнем регистре
narrative = f"{partA} — {bridge} {partB}"
```

Bridge-фразы детерминированы: `seed % len(options)`, где `seed = len(active_signals)`. Набор фраз зависит от фазы:

| Фаза | Bridges |
|------|---------|
| `active` | при этом / однако / в то время как / тогда как |
| `tension` | что усугубляется тем что / несмотря на то что / вопреки тому что |
| `resolution` | после чего / в результате чего / что означает что |
| `structural` | на фоне того что / в условиях / в структуре которой |

### Шаг 9 — Takeaway

Перебираются кандидаты в порядке: `anchor_complication → anchor_trigger → anchor_resolution → top_weight_signal`. Берётся первое предложение `macro_implication` кандидата, которое ещё не встречается ни в `narrative`, ни в `tension` (чтобы не дублировать текст в карточке).

### Шаг 10 — Phase changed

```python
phase_changed = previous_synthesis is not None and previous_synthesis["phase"] != phase
```

### Structural Change Detection (между Шагом 10 и 11, не пронумерован)

Если `phase_changed = True`, записывается:
```json
{"detected": true, "from_phase": "...", "to_phase": "...", "detected_at": "ISO8601"}
```

### Шаг 11 — Confidence

```python
max_score = n_signals * MAX_PER_SIGNAL   # MAX_PER_SIGNAL = 3+4+4 = 11
raw = score_total / max_score

if n_signals == 1:        raw *= 0.5
if not has_contradicts:   raw *= 0.8
if all_stale:              raw *= 0.7
if not has_tension:        raw *= 0.6

confidence = clamp(raw, 0.1, 1.0)
```

`has_contradicts` — есть ли хотя бы один сигнал в кластере с непустым `links.contradicts`. `all_stale` — все сигналы старше `STALE_THRESHOLD = 30` дней. `has_tension` — у anchor-победителя (Шаг 6) есть непустой `tension` (не fallback-конкатенация).

После расчёта confidence к `cluster_score.freshness` применяется `uncertainty["score_multiplier"]` из Шага 3.5, если он был установлен.

### Шаг 12 — Rationale

Строка-объяснение синтеза, машиночитаемый формат:
```
Tension from {anchor_id} (contradicts: N, weight: W); partA from {trigger_id};
phase: P; bridge: '...'; confidence: C; signals_used: N; ignored_duplicates: [...]
```

---

## Формула Score сигнала (`_score_signal`)

```
score.total = freshness + weight + role + contradiction
```

| Компонент | Формула | Значения |
|-----------|---------|----------|
| `freshness` | по возрасту сигнала | `fresh` (≤7д) = **3**, `recent` (≤30д) = **1**, `stale` (>30д) = **0** |
| `weight` | по полю `weight` сигнала | `onchain`=**4**, `primary`=**3**, `market`=**2**, `media`=**1** |
| `role` | по полю `narrative_role` | `trigger`=**4**, `complication`=**3**, `resolution`=**2**, `background`=**0** |
| `contradiction` | `len(links.contradicts) × CONTRADICTION_BONUS` | `CONTRADICTION_BONUS = 5` за каждый ID |

**MAX_PER_SIGNAL = 3 + 4 + 4 = 11** (freshness_max + weight_max + role_max; contradiction не ограничен сверху и не входит в максимум — поэтому реальный score может превышать 11 на сигнал).

---

## Пороги силы нарратива кластера (`get_strength`)

| score_total кластера | strength |
|----------------------|----------|
| ≥ 20 (`SCORE_HOT`) | 🔥 horizontal в UI как "горячий" |
| ≥ 12 (`SCORE_STRONG`) | `strong` |
| ≥ 6 (`SCORE_MODERATE`) | `moderate` |
| < 6 | `weak` |

---

## Временные окна

| Константа | Значение | Назначение |
|-----------|----------|-----------|
| `WINDOW_DAYS_DEFAULT` | 90 дней | старше — не участвует в синтезе (Шаг 1) |
| `STALE_THRESHOLD` | 30 дней | старше — `freshness=0`, и считается "stale" для confidence |
| `ARCHIVE_THRESHOLD` | 180 дней | старше — кандидат на авто-архивацию (вне синтезатора) |
| `tension_staleness_days` (UNCERTAINTY_RULES) | 90 дней | anchor старше — помечается STALE на Шаге 3.5 |

---

## Поля результата (`SynthesisResult`)

Реальная структура dataclass — единственный источник правды для имён полей карточки:

```python
@dataclass
class SynthesisResult:
    cluster:           str
    tension:           str      # золотая полоса карточки, текст as-is
    narrative:         str      # partA — bridge partB
    takeaway:          str      # ключевая мысль, не дублирует tension/narrative
    strength:          str      # strong | moderate | weak
    confidence:        float    # [0.1, 1.0]
    phase:             str      # active | tension | resolution | structural
    score:             SignalScore
    anchor_signal_id:  str      # ID сигнала-источника tension
    signal_count:      int
    phase_changed:     bool = False
    structural_change: dict = {}
    rationale:         str  = ""
    uncertainty:       dict = {}   # {direction, score_multiplier, tension_stale, ...}
    signals_used:      list = []
    signals_ignored:   list = []   # дубликаты, выброшенные на Шаге 0
    generated_at:      str
```

Имён `core_tension`, `market_structure`, `btc_implication` в коде **не существует** — если встретишь их в старой документации, это устаревшие названия из ранней архитектурной версии (до реализации).

---

## §17 — Архитектурный контракт: synthesizer не читает файлы

`synthesize_cluster()` принимает `previous_synthesis: Optional[dict]` как параметр — функция никогда не открывает файлы сама. Загрузка происходит в `main()` через `_load_previous_synthesis(cluster_key)`, которая ищет последний файл `synthesis_store/synthesis_{cluster_key}_*.json` по сортировке имени (timestamp в имени файла).

Это разделяет ответственность: Narrative Synthesis Context вычисляет, Delivery/Orchestration Context (main()) занимается I/O. Нарушение этого контракта было найдено и исправлено в ARR v2 (ранее функция читала файл сама).

---

## Lifecycle после синтеза (`main()`)

```
для каждого кластера:
    1. previous = _load_previous_synthesis(cluster_key)
    2. result   = synthesize_cluster(cluster_key, signals, previous)
    3. _save_synthesis() → synthesis_store/synthesis_{cluster}_{timestamp}.json
    4. если previous существовал → on_synthesis_superseded(old_id, new_id)
       (lifecycle hook, сбой здесь не останавливает синтез — DEGRADE GRACEFULLY)
    5. результат добавляется в общий dict results[cluster_key]

после всех кластеров:
    atomic_write_json_safe(SYNTHESIS_CACHE_PATH, results)
    → data/synthesis_cache.json — читается index.html напрямую
```

Ошибка одного кластера (`EmptyClusterError` или любое исключение) не прерывает обработку остальных — каждый кластер изолирован в своём `try/except` внутри `main()`.

---

## Чувствительные места — где легко ошибиться при изменении кода

**Дедупликация перед фильтрацией по окну.** Если добавить сигнал который по ключу `(date, actor, cluster, dir)` совпадает с существующим — один из двух тихо исчезнет из синтеза (с WARNING в логах, но не в UI). Это было причиной путаницы 2026-06-29 при тестировании resolution-приоритета.

**`_get_contradicts()` читает только `links.contradicts`**, и только если `LEGACY_LINKS_ENABLED = True` (сейчас так). После миграции на `relationships.json` (Фаза C, см. `ADR-008`) эта функция должна быть переписана — иначе contradiction-bonus в score перестанет работать молча.

**`previous_synthesis` ищется по сортировке имени файла**, не по дате внутри JSON. Если запустить синтез дважды в одну секунду — `_load_previous_synthesis` может выбрать не тот файл (коллизия timestamp в имени). На практике не встречалось, но это слабое место.

**Capitalize применяется только к tension**, не к narrative и takeaway. Если `macro_implication` сигнала начинается со строчной буквы — narrative/takeaway унаследуют это.

---

## Связанные документы

- `config/settings.py` — все константы (`FRESHNESS_SCORE`, `WEIGHT_SCORE`, `ROLE_SCORE`, `UNCERTAINTY_RULES`, пороги)
- `scripts/contradiction_detector.py` — как заполняется `links.contradicts` (не входит в синтезатор, отдельный компонент)
- `tests/integration/test_narrative_regression.py` — E2E тесты конкретно этого алгоритма, включая resolution-priority
- `CLAUDE.md` — как аналитик формулирует `tension` и `macro_implication` при создании сигнала, до того как они попадут в этот алгоритм
- `docs/ARCH_GAP_SPEC.md` §17 — обоснование архитектурного контракта previous_synthesis как параметра

---

## Как проверить что документ ещё актуален

```bash
PYTHONHASHSEED=0 python3 -m pytest tests/integration/test_narrative_regression.py -v
```

Если все тесты зелёные — поведение синтезатора соответствует тому что описано выше. Если документ снова разойдётся с кодом (новый ШАГ добавлен, формула изменена) — обновлять этот файл тем же коммитом что меняет `synthesizer.py`, не отдельно.

---

*ALGORITHM.md v2.0 · Полностью переписан 2026-06-29 на основе построчной сверки с scripts/synthesizer.py*
*Предыдущая версия (v1.x) описывала более раннюю архитектуру с другими именами полей (core_tension, market_structure, btc_implication) — она устарела и не отражала реализованный код*
