# Устранение гонки автомерджа — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Пересмотрено 2026-09-13:** исходный план (нативный GitHub Merge Queue) заблокирован на Task 2 — правило `merge_queue` недоступно на текущем тарифе GitHub (личный аккаунт, не Organization/Team), подтверждено прямым 422 от API. Task 1 уже выполнен и смержен, его результат безвреден и оставлен как есть. Task 2-4 ниже — план варианта B (свой auto-heal workflow), пришедшего на замену. См. `docs/superpowers/specs/2026-09-13-merge-queue-automation-design.md`, раздел «Обновление 2026-09-13».

**Goal:** Устранить гонку `behind`/`BLOCKED` между несколькими auto-merge PR на `main` — свой workflow, реагирующий на каждый push в `main` и подтягивающий отставшие auto-merge PR через `update-branch`.

**Architecture:** Новый workflow `.github/workflows/auto-update-behind-prs.yml`, триггер `push: branches: [main]`. На каждый push: найти открытые PR с одновременно включённым auto-merge и статусом `BEHIND`, вызвать `update-branch` для каждого через `SYNTHESIS_BOT_TOKEN` (не `GITHUB_TOKEN` — иначе последующий CI-прогон не запустится). Мердж одного PR порождает новый push → workflow срабатывает снова → каскадно подтягивает следующий.

**Tech Stack:** GitHub Actions (YAML), GitHub CLI (`gh`) внутри workflow, GitHub REST API.

**Ссылка на дизайн:** `docs/superpowers/specs/2026-09-13-merge-queue-automation-design.md`

---

## Task 1 (выполнен 2026-09-13, историческая запись — не переделывать)

Добавлен триггер `merge_group:` в `.github/workflows/deploy.yml` (PR #1291, коммит `86481a22485cc2a9d932e739c3329c5bca624522`) как подготовка к варианту A. Прошёл spec-review и code-quality review без критичных замечаний. Сейчас неактивен (не срабатывает без включённой очереди), решено не откатывать — см. дизайн, раздел «Наследие варианта A». **Не включать эту задачу в новый прогон subagent-driven-development — она уже закрыта.**

---

## Предварительно проверено (не гадать на месте)

- Все существующие bot-workflow'ы (`update-bip110-signaling.yml` и аналогичные) уже используют секрет `SYNTHESIS_BOT_TOKEN` (не `GITHUB_TOKEN`) именно для этого класса проблемы — push/API-изменение от штатного `GITHUB_TOKEN` не порождает новый workflow run на затронутом PR, обязательный чек не перезапустится. Секрет уже существует в репозитории (`secrets.SYNTHESIS_BOT_TOKEN`), создавать не нужно.
- `gh pr list --json autoMergeRequest,mergeStateStatus` — поле `autoMergeRequest` равно `null`, если auto-merge не включён, и объекту с деталями, если включён. `mergeStateStatus` принимает значения `BEHIND`/`BLOCKED`/`CLEAN`/`DIRTY`/`UNKNOWN` и другие — интересует конкретно `"BEHIND"`.
- `gh api --method PUT repos/{owner}/{repo}/pulls/{n}/update-branch` — тот же вызов, что уже трижды использовался вручную сегодня для #1287/#1288 (задокументировано в текущей сессии) — рабочий, проверенный вызов, не гипотеза.
- Репозиторий: `AlxCheh/Bitcoin-Intel`.

---

### Task 2: Создать workflow автолечения отставших PR

**Files:**
- Create: `.github/workflows/auto-update-behind-prs.yml`

- [ ] **Step 1: Создать ветку**

```bash
cd "D:\Claude\Bitcoin-Intel"
git checkout main
git pull --ff-only
git checkout -b ci/auto-update-behind-prs
```

- [ ] **Step 2: Написать workflow**

Создать `.github/workflows/auto-update-behind-prs.yml`:

```yaml
name: Auto-update behind PRs

# Реагирует на каждый push в main — это событие, которое делает другие
# открытые auto-merge PR отставшими (mergeStateStatus: BEHIND), потому
# что required_status_checks.strict=true требует актуальности ветки
# перед мерджем, а ничего не обновляет её автоматически. Без этого
# workflow каждый такой случай требует ручного update-branch (см.
# docs/superpowers/specs/2026-09-13-merge-queue-automation-design.md).
#
# SYNTHESIS_BOT_TOKEN, не GITHUB_TOKEN — тот же паттерн, что и в
# update-bip110-signaling.yml и аналогичных: update-branch от штатного
# GITHUB_TOKEN не порождает новый workflow run на PR, обязательный чек
# "Validate and Test" не перезапустится, PR зависнет по другой причине.

on:
  push:
    branches: [main]

jobs:
  update-behind:
    name: Update branch for behind auto-merge PRs
    runs-on: ubuntu-latest
    steps:
      - name: Update branches of behind auto-merge PRs
        env:
          GH_TOKEN: ${{ secrets.SYNTHESIS_BOT_TOKEN }}
          REPO: ${{ github.repository }}
        run: |
          # Небольшая пауза — GitHub пересчитывает mergeStateStatus не
          # синхронно с push, сразу после события список может быть
          # ещё не актуален.
          sleep 10

          BEHIND_PRS=$(gh pr list --repo "$REPO" --state open \
            --json number,autoMergeRequest,mergeStateStatus \
            -q '.[] | select(.autoMergeRequest != null and .mergeStateStatus == "BEHIND") | .number')

          if [ -z "$BEHIND_PRS" ]; then
            echo "Нет отставших auto-merge PR."
            exit 0
          fi

          echo "$BEHIND_PRS" | while read -r pr; do
            echo "Обновляю ветку PR #$pr (behind + auto-merge включён)"
            gh api --method PUT "repos/$REPO/pulls/$pr/update-branch" \
              || echo "⚠ update-branch для #$pr не удался — не блокирует обработку остальных PR"
          done
```

- [ ] **Step 3: Валидировать YAML**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/auto-update-behind-prs.yml', encoding='utf-8')); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Полный прогон тестов (регрессия)**

Run: `PYTHONHASHSEED=0 python -m pytest tests/ --ignore=tests/performance -q`
Expected: `750 passed, 1 skipped` (новый workflow-файл не затрагивает Python-код, но подтвердить явно)

- [ ] **Step 5: Коммит и PR**

```bash
git add .github/workflows/auto-update-behind-prs.yml
git commit -m "$(cat <<'EOF'
ci: workflow автолечения отставших auto-merge PR

Заменяет план на нативный GitHub Merge Queue — тот план заблокирован
(правило merge_queue недоступно на текущем тарифе GitHub, подтверждено
422 от Rulesets API, см. docs/superpowers/specs/2026-09-13-merge-queue-automation-design.md,
раздел "Обновление 2026-09-13").

Реагирует на push в main (событие, которое делает другие auto-merge PR
отставшими из-за required_status_checks.strict=true) и вызывает
update-branch для каждого открытого PR с включённым auto-merge и
статусом BEHIND — автоматизирует ручное действие, трижды выполненное
сегодня вручную для #1287/#1288/#1234.

Часть внедрения docs/superpowers/plans/2026-09-13-merge-queue-automation.md
(Task 2 из 4, после отменённого Task 2 варианта A).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LVCircfCLoxLUATE461juo
EOF
)"
git push -u origin ci/auto-update-behind-prs
PR_URL=$(gh pr create --title "ci: workflow автолечения отставших auto-merge PR" --body "$(cat <<'EOF'
Task 2 (пересмотренный) из docs/superpowers/plans/2026-09-13-merge-queue-automation.md — вариант B взамен заблокированного нативного Merge Queue (правило merge_queue недоступно на текущем тарифе, см. дизайн-документ).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01LVCircfCLoxLUATE461juo
EOF
)")
PR_NUMBER=$(basename "$PR_URL")
echo "PR: $PR_NUMBER"
```

- [ ] **Step 6: Дождаться зелёного CI и смержить**

Run: `gh pr checks "$PR_NUMBER"` до `Validate and Test: pass`, затем:

```bash
gh pr merge "$PR_NUMBER" --squash --delete-branch
git checkout main
git pull --ff-only
```

Expected: PR в состоянии `MERGED`, локальный `main` содержит новый workflow-файл. Этот самый push в main — первый реальный триггер нового workflow (он ещё ничего не найдёт, т.к. других PR сейчас нет, но должен отработать без ошибок — проверить `gh run list --workflow "Auto-update behind PRs" --limit 1`).

---

### Task 3: Сквозная проверка на реальном сценарии гонки

**Files:** нет изменений кода — только наблюдение за реальным поведением GitHub.

- [ ] **Step 1: Воспроизвести вчерашний сценарий — два bot-workflow почти одновременно**

```bash
gh workflow run update-bip110-signaling.yml
gh workflow run update-volume.yml
```

- [ ] **Step 2: Дождаться создания обоих PR и первого мерджа**

```bash
for i in 1 2 3 4 5 6 7 8; do sleep 20; gh pr list --state open --json number,title,mergeStateStatus,autoMergeRequest; done
```

Наблюдать: оба PR появляются с `autoMergeRequest` не null; после того как первый смержится (его чек стал зелёным раньше), второй должен на короткое время показать `mergeStateStatus: BEHIND`.

- [ ] **Step 3: Убедиться, что auto-heal workflow сам подтянул второй PR**

```bash
gh run list --workflow "Auto-update behind PRs" --limit 5
```

Expected: как минимум один прогон, случившийся сразу после мерджа первого PR (по времени), с успешным завершением.

- [ ] **Step 4: Дождаться мерджа второго PR без ручного вмешательства**

```bash
for i in 1 2 3 4 5 6; do sleep 20; gh pr list --state open --json number,title; done
```

Expected: список открытых PR пустеет сам, без единого ручного `update-branch` за это Task — именно то, что вчера потребовало три раунда вручную.

- [ ] **Step 5: Убедиться, что PR без auto-merge не трогается**

```bash
git checkout main
git pull --ff-only
git checkout -b docs/auto-heal-noop-check
echo "" >> docs/BACKLOG.md
git add docs/BACKLOG.md
git commit -m "test: пустая правка для проверки auto-heal workflow (будет отменена)"
git push -u origin docs/auto-heal-noop-check
NOOP_PR_URL=$(gh pr create --title "test: noop PR без auto-merge (для проверки Task 3)" --body "Временный PR без auto-merge — проверяет, что auto-update-behind-prs.yml его не трогает. Будет закрыт без мерджа.")
NOOP_PR_NUMBER=$(basename "$NOOP_PR_URL")
echo "Noop PR: $NOOP_PR_NUMBER"
```

Не включать auto-merge на этом PR. Затем спровоцировать ещё один push в main (например, запустить любой `workflow_dispatch` из уже использованных выше — `update-top-addresses.yml` ещё не запускался в рамках этой проверки) и убедиться, что `mergeStateStatus` этого noop-PR не менялся под действием auto-heal workflow:

```bash
gh workflow run update-top-addresses.yml
sleep 60
gh run list --workflow "Auto-update behind PRs" --limit 3
gh pr view "$NOOP_PR_NUMBER" --json mergeStateStatus
```

Expected: последний прогон `Auto-update behind PRs` в логах не содержит номер `$NOOP_PR_NUMBER` (проверить через `gh run view <id> --log`), т.к. `autoMergeRequest` для него `null` и он не проходит фильтр `select()`. Затем закрыть PR без мерджа:

```bash
gh pr close "$NOOP_PR_NUMBER" --delete-branch
git checkout main
```

---

### Task 4: Задокументировать поведение auto-heal workflow

**Files:**
- Modify: `docs/CI_RUNBOOK.md`

- [ ] **Step 1: Добавить раздел в конец файла**

Текущее последнее предложение файла (`docs/CI_RUNBOOK.md`, последняя строка):

```markdown
Проверить фактический статус смерженного sync-PR нужно через **отдельный GET на сам PR** (`/pulls/{number}`), не через список (`/pulls?state=closed`) — список не всегда отдаёт поле `merged` надёжно.
```

Добавить после неё:

```markdown

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
  auto-merge).
- Если PR завис дольше нескольких минут — проверить `gh run list
  --workflow "Auto-update behind PRs"`, не упал ли сам вызов
  `update-branch` (лог печатает `⚠` при неудаче на конкретном PR, не
  прерывая обработку остальных).

```
✗ Увидеть mergeStateStatus: BEHIND у auto-merge PR и вручную гонять
  update-branch — auto-heal workflow сделает это сам на следующем push
✓ Подождать один цикл push→workflow→update-branch→CI
```
```

- [ ] **Step 2: Коммит и PR**

```bash
cd "D:\Claude\Bitcoin-Intel"
git checkout main
git pull --ff-only
git checkout -b docs/ci-runbook-auto-heal
git add docs/CI_RUNBOOK.md
git commit -m "$(cat <<'EOF'
docs: задокументировать auto-heal workflow в CI_RUNBOOK.md

Без этого будущая сессия увидит mergeStateStatus: BEHIND у auto-merge
PR и по привычке начнёт вручную гонять update-branch — то самое
ручное вмешательство, которое auto-update-behind-prs.yml устраняет
(Task 4 из docs/superpowers/plans/2026-09-13-merge-queue-automation.md).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LVCircfCLoxLUATE461juo
EOF
)"
git push -u origin docs/ci-runbook-auto-heal
PR_URL=$(gh pr create --title "docs: задокументировать auto-heal workflow в CI_RUNBOOK.md" --body "$(cat <<'EOF'
Task 4 (последний) из docs/superpowers/plans/2026-09-13-merge-queue-automation.md.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01LVCircfCLoxLUATE461juo
EOF
)")
PR_NUMBER=$(basename "$PR_URL")
echo "PR: $PR_NUMBER"
```

- [ ] **Step 3: Дождаться зелёного CI и смержить**

```bash
gh pr checks "$PR_NUMBER"
gh pr merge "$PR_NUMBER" --squash --delete-branch
git checkout main
git pull --ff-only
```

---

## Откат (если что-то пошло не так)

Удалить файл (обычным PR, как любую другую правку):

```bash
git checkout main && git pull --ff-only
git checkout -b revert/auto-update-behind-prs
git rm .github/workflows/auto-update-behind-prs.yml
git commit -m "revert: убрать auto-update-behind-prs.yml"
git push -u origin revert/auto-update-behind-prs
gh pr create --title "revert: убрать auto-update-behind-prs.yml" --body "Откат Task 2/docs/superpowers/plans/2026-09-13-merge-queue-automation.md"
```

Workflow ни на что не влияет кроме собственных вызовов `update-branch` — ничего в branch protection не менялось, откат чист.
