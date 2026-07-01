# ADR-014: Единственный источник истины для весов scoring — config/settings.py

**Статус:** Принято
**Дата:** 2026-07-01
**Авторы:** Команда Bitcoin Intel
**Контекст ревью:** IRP v1.0 Wave 3 / REM-M06 (docs/IRP_v1.md)

## Контекст

IRR v1.0 (M06) зафиксировал: веса scoring существуют в двух местах —
`config/settings.py` (`WEIGHT_SCORE`, `ROLE_SCORE`, `FRESHNESS_SCORE`,
`CONTRADICTION_BONUS`) и `ontology.json` (`weight_scores`). Два источника
истины для одних и тех же чисел — риск дрейфа: значение меняется в одном
месте, второе тихо расходится, и никто не замечает до следующего аудита
(тот же класс проблемы, что M3 из ARR v3 для `freshness_windows`, уже
закрытый структурно через `test_ontology_settings_consistency.py`).

При проверке на 2026-07-01 обнаружено:

- `ontology.json.weight_scores` дублирует `config/settings.py.WEIGHT_SCORE`
  (`onchain: 4, primary: 3, market: 2, media: 1`) — оба места **синхронны**
  на момент ревью, но ничего не мешает им разойтись.
- Ни один Python-файл, ни `index.html`/JS не читают `ontology.json.weight_scores`
  — grep по всему репозиторию не находит ни одного обращения к этому ключу
  вне самого `ontology.json`. Это уже мёртвые/display-only данные де-факто,
  просто не помеченные как таковые.
- `ROLE_SCORE` (`config/settings.py`) вообще не имеет числового аналога в
  `ontology.json` — там есть только `narrative_roles` с текстовыми
  описаниями ролей (не весами). Исходная формулировка M06 в IRR
  («WEIGHT_SCORE, ROLE_SCORE в обоих местах») неточна для `ROLE_SCORE`:
  дублирования там нет и не было. Дублирование реально касается только
  `weight_scores`.

## Решение

`config/settings.py` — единственный runtime-источник весов scoring для
Python (`FRESHNESS_SCORE`, `WEIGHT_SCORE`, `ROLE_SCORE`,
`CONTRADICTION_BONUS`). `ontology.json.weight_scores` остаётся в файле как
человекочитаемая документация (структура MVP-онтологии), но помечен полем
`"_note"` внутри объекта как `display only, не используется в вычислениях`.

`tests/unit/test_ontology_settings_consistency.py` расширен тестом
`test_ontology_weight_scores_matches_settings()`, который сравнивает
`ontology.json.weight_scores` (кроме `_note`) с `config/settings.py.WEIGHT_SCORE`
поэлементно. Пока оба значения умышленно синхронны — тест держит это
явно, а не полагается на то, что никто не забудет проверить руками; при
осознанном изменении `WEIGHT_SCORE` тест упадёт и потребует либо обновить
`ontology.json` вместе с кодом, либо (лучше) удалить дублирующее поле из
`ontology.json` вовсе, когда MVP перейдёт на Backend (см. `note` в
`ontology.json._meta`).

`ROLE_SCORE` дублирования не имеет — правка не требуется, только
уточнение формулировки замечания M06 (см. ниже).

## Обоснование

Тот же паттерн, что в ADR-011/012/013: не удалять данные и не тратить время
на «синхронизацию руками разово», а сделать расхождение видимым и
проверяемым автоматически. `ontology.json` в MVP — не runtime-контракт (его
не читает ни бэкенд, ни фронтенд для scoring), поэтому удалять секцию
целиком — избыточная правка вне scope M06; пометка `_note` + guard-тест
дешевле и достаточна.

## Уточнение к IRR/IRP

`docs/IRP_v1.md` REM-M06 ссылается на «ADR-013» как решение для этой
задачи — на момент написания IRP этот номер ещё не был занят. К моменту
реализации M06 (Wave 3) `ADR-013` уже был создан для несвязанного вопроса
(`docs/ADR-013-synthesis-schema-reflects-implementation.md`, REM-B3, Wave 2).
Правильная ссылка для M06 — этот документ, ADR-014. `docs/IRP_v1.md`
обновлён соответствующим образом.

## Связанные документы

- `docs/IRP_v1.md` REM-M06
- `tests/unit/test_ontology_settings_consistency.py` — расширен этим ADR
- ADR-011, ADR-012, ADR-013 — тот же паттерн (документировать расхождение
  явно, вместо тихой синхронизации)
