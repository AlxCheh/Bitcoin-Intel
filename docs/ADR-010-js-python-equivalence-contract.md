# ADR-010: Контракт эквивалентности JS/Python синтеза

**Статус:** Принято
**Дата:** 2026-06-30
**Авторы:** Команда Bitcoin Intel
**Контекст ревью:** C1 Architecture Review Board v3.0 (docs/ARR_REPORT_v3.md, Этап 2.1 / 4.9 / Technical Debt #4)

## Контекст

`index.html` рендерит блок «Главные нарративы» из `data/synthesis_cache.json`,
заранее посчитанного `scripts/synthesizer.py` (Python, полный 12-шаговый Reasoning
Pipeline). Если кэш недоступен или повреждён, дашборд переключается на client-side
фоллбэк — `synthesizeNarrativeAdvanced()` (inline JS). Это два независимых
исходных кода без общей библиотеки — JS не может импортировать Python и не имеет
доступа к серверным зависимостям на статическом GitHub Pages хостинге.

ARR v3.0 указала на отсутствие теста эквивалентности между ними (C1, перенесено из
C5 ARR v2 без изменений). Ручная проверка на Golden Dataset обнаружила два реальных
расхождения:

1. **Phase detection.** Python требует `trigger > 0 AND complication > 0` для
   `phase = "active"`. JS требовал только `trigger > 0`.
2. **Tension source priority.** Python отдаёт приоритет `resolution`-сигналу
   (самому свежему) перед обычным MAX(contradicts)→MAX(weight)→MAX(date) тай-брейком.
   JS не давал `resolution` приоритета вообще, а внутри обычного тай-брейка терял
   `weight` как критерий при равном числе `contradicts` (наиболее частый случай,
   так как `contradicts` заполняется редко) — порядок схлопывался к порядку массива.

Оба расхождения — не косметика: они определяют, какой сигнал станет «лицом»
нарратива, который видит читатель сайта, и расхождение проявлялось бы только в
деградированном режиме (когда кэш недоступен) — то есть именно тогда, когда
точность дашборда важнее всего, а отладка сложнее всего.

## Решение

### Что эквивалентность ГАРАНТИРУЕТ (закрыто, покрыто тестом)

`tests/unit/test_js_python_equivalence.py` извлекает реальный исходник
`synthesizeNarrativeAdvanced()` из `index.html` (тем же методом, что и
`test_xss_sanitization.py` для B2 — не копия логики, а сам production-код) и
прогоняет его через Node на Golden Dataset, сравнивая с выводом
`scripts/synthesizer.py::synthesize_cluster()` на том же входе:

- `phase` — должна совпадать дословно.
- `anchor_signal_id` — сигнал, выбранный источником tension (или anchor trigger,
  если tension нигде не задан), должен совпадать дословно.

Это исправлено в обоих местах JS (`index.html`, `synthesizeNarrativeAdvanced`):
phase-формула приведена к виду Python, добавлен `byTensionPriority` —
тай-брейк `(MAX contradicts → MAX weight → MAX date)`, идентичный
`_select_tension_source()`, и resolution получил явный приоритет.

### Что эквивалентность СОЗНАТЕЛЬНО НЕ ГАРАНТИРУЕТ (явный scope, не забытый gap)

1. **Точный текст narrative/tension.** Python собирает текст через
   `select_bridge()` с детерминированным `seed`; JS — через собственный набор
   связок `BRIDGES` и `Math.sin()`-псевдослучайность. Унификация текстогенерации
   потребовала бы либо переноса всего Python-пайплайна в JS, либо обратного —
   несоразмерный рефакторинг для риска, который проявляется только в
   деградированном режиме. Текст может отличаться; **смысл (phase, anchor) — нет**.

2. **Window filtering (ШАГ 1 Python).** Python отбрасывает сигналы старше
   `WINDOW_DAYS_DEFAULT` (90 дней) или со `status="archived"` до синтеза. JS
   такого шага не имеет — `synthesizeNarrativeAdvanced()` синтезирует любой
   переданный ей набор как актуальный. Зафиксировано тестом
   `test_known_gap_js_lacks_window_filtering` — он не закрывает gap, а
   документирует его так, чтобы он не мог снова стать невидимым.

3. **Deduplication (§16 Python, `deduplicate_signals`).** Аналогично — JS не
   повторяет дедупликацию по `(date, actor, cluster)`.

Сейчас (2) и (3) не создают видимого расхождения в production, потому что
`renderNarrativeItem()` в `index.html` уже получает отфильтрованный
`signals.json` от того же дашборда, который и формирует `cl.signals` — фильтрация
по окну происходит раньше, на уровне дашборда, а не внутри
`synthesizeNarrativeAdvanced()`. Однако это полагание не закреплено как
инвариант нигде в коде — `synthesizeNarrativeAdvanced()`, вызванная напрямую с
сырыми (неотфильтрованными) сигналами, даст другой результат, чем Python. Это
архитектурный долг, а не баг сегодняшнего поведения.

## Дальнейшая работа (не в scope этого ADR)

Перенос `WINDOW_DAYS_DEFAULT`/`STALE_THRESHOLD` и логики дедупликации в JS —
отдельная задача. Это дублирование бизнес-правил в двух местах (тот же класс
риска, что и M3 — freshness threshold drift), поэтому правильное решение —
не копировать константы, а либо: (а) сделать `ontology.json` единственным
источником этих порогов и для Python, и для JS через `fetch()`, либо
(б) убрать сам JS-фоллбэк и вместо него показывать явное сообщение об
устаревшем кэше (см. M4 — freshness-индикатор). Решение между (а) и (б) требует
отдельного ревью, так как (б) меняет UX деградации, а не просто код.

## Тесты

- `tests/unit/test_js_python_equivalence.py::test_phase_and_anchor_match_on_all_golden_clusters`
  — 7 из 8 кластеров Golden Dataset сравниваются напрямую (восьмой,
  `test_stale`, — явный gap, см. ниже), полное совпадение phase и anchor.
- `tests/unit/test_js_python_equivalence.py::test_known_gap_js_lacks_window_filtering`
  — фиксирует текущее (неполное) поведение `test_stale`, чтобы регресс или
  закрытие gap было видно в diff, а не молчало.

## Последствия

- `index.html`: `synthesizeNarrativeAdvanced()` — изменены формула `phase`,
  приоритет `tensionSig`, добавлен `byTensionPriority`, добавлены поля
  `anchor_signal_id` и `rationale` в возвращаемый объект (N02 — explainability
  anchor-сигнала на UI теперь работает на обоих путях: и кеш, и live-фоллбэк,
  с честной пометкой источника в тексте rationale).
- Новый тестовый файл, требует Node.js в CI (уже используется B2-тестом).
- Rollback: если регрессия будет найдена в production, откатить три
  `str_replace`-правки в `synthesizeNarrativeAdvanced()` до состояния перед
  этим ADR — старое поведение задокументировано в git history коммита,
  предшествующего этому ADR.
