# CI Runbook — механика автосинка после мержа сигнала

> Часть проекта Bitcoin-Intel. Основной файл: [CLAUDE.md](../CLAUDE.md)

**Автосинк после мержа сигнала — ждать, не мержить вручную.** После мержа PR с сигналом CI сам создаёт `bot/sync-synthesis-*` PR с пересчитанным `data/synthesis_cache.json` и сам ставит его в очередь на автомерж (`gh pr merge --auto`, `allow_auto_merge: true` на уровне репозитория). Обычно завершается в течение ~1–2 минут после того, как на самом sync-PR позеленеет `Validate and Test`.

```
✗ Искать sync-PR вручную и мержить его самому — не нужно, это уже
  автоматизировано; ручное вмешательство в это окно может создать
  гонку состояний с логикой закрытия устаревших sync-PR (см. комментарии
  в .github/workflows/deploy.yml)
✓ Подождать ~1-2 минуты, затем проверить data/synthesis_cache.json
  напрямую (raw.githubusercontent.com или git pull) — если он уже
  отражает новый сигнал, синк завершился сам
```

Проверить фактический статус смерженного sync-PR нужно через **отдельный GET на сам PR** (`/pulls/{number}`), не через список (`/pulls?state=closed`) — список не всегда отдаёт поле `merged` надёжно.

## Auto-update behind PRs (с 2026-09-13)

`.github/workflows/auto-update-behind-prs.yml` реагирует на каждый push
в `main` и сам вызывает `update-branch` для открытых PR, у которых
одновременно включён auto-merge и `mergeStateStatus == "BEHIND"` — см.
`docs/superpowers/specs/2026-09-13-merge-queue-automation-design.md`.
Это замена изначально планировавшегося нативного GitHub Merge Queue —
он недоступен на текущем тарифе аккаунта (личный, не Organization).

**Что это значит на практике:**
- Увидеть `mergeStateStatus: BEHIND` на PR с зелёным чеком — не повод
  вручную вызывать `update-branch`: следующий push в `main` (обычно
  очень скоро — сами sync-workflow'ы делают это часто) сам подтянет
  ветку через этот workflow.
- PR **без** включённого auto-merge этим workflow не трогается — там
  ожидается участие человека (ревью, ручной мердж или включение
  auto-merge). Подтверждено вживую 2026-09-13: PR без auto-merge
  оставался `BEHIND` сколько угодно, пока workflow обрабатывал соседние
  auto-merge PR — это ожидаемое поведение, не баг.
- **Возможен «тихий период».** Реакция привязана к push в `main` — если
  после того как PR стал `BEHIND`, долго не происходит следующий push
  (вне активных часов bot-синков), PR может провисеть дольше обычного.
  Это не баг workflow — просто нет триггера. Запустить вручную:
  `gh workflow run auto-update-behind-prs.yml` (есть `workflow_dispatch`).
- Если PR завис дольше нескольких минут — проверить `gh run list
  --workflow "Auto-update behind PRs"`, не упал ли сам вызов
  `update-branch` (лог печатает аннотацию `::warning::` при неудаче на
  конкретном PR, видимую в сводке прогона, не прерывая обработку
  остальных).

```
✗ Увидеть mergeStateStatus: BEHIND у auto-merge PR и вручную гонять
  update-branch — auto-heal workflow сделает это сам на следующем push
  (или запустить его вручную через workflow_dispatch, если push не
  предвидится)
✓ Подождать один цикл push→workflow→update-branch→CI
```
