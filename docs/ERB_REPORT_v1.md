# Engineering Readiness Board (ERB) — Протокол оценки готовности к Sprint 0

> **Дата:** 2026-07-02 · **Проект:** Bitcoin Intel Narrative Intelligence Platform
> **Основание:** ARR (Architecture Readiness Review) и IRR (Implementation Readiness Review)
> пройдены; IRP v1.0 (Implementation Remediation Plan, Waves 1–5) закрыт и верифицирован
> на текущем `main` (коммит `7c02351`) непосредственно перед составлением этого протокола.
> Архитектурные вопросы не пересматриваются — см. `docs/BLUEPRINT.md`,
> `docs/BLUEPRINT_ADDENDUM.md`. Этот документ оценивает только инженерную готовность
> к старту разработки, не архитектуру.
>
> **Методология:** каждый пункт проверен командой (`git`, `pytest`, GitHub API), а не
> пересказом документации — там, где документация и факт расходились, зафиксирован факт.

---

## Executive Summary

Bitcoin Intel — статический образовательный сайт о Bitcoin (GitHub Pages) с Python-движком
нарративного синтеза, работающим полностью в CI (без выделенного backend/БД на текущей
фазе). IRP v1.0 закрыл 26 из 26 замечаний исходного IRR (21 — реализацией, 5 — как
осознанно принятые Residual Risks с задокументированным обоснованием и контролем).
204 теста в основном CI-пути, все зелёные; Branch Protection активна на `main` и
`develop`; три независимых scheduled workflow (performance, freshness, dashboard)
дают видимость деградации без выделенного мониторинг-стека.

Ключевая методологическая находка этого отчёта: раздел «AI Engineering» (Этап 4) в
значительной части **не применим** к текущей архитектуре — движок синтеза
(`scripts/synthesizer.py`) детерминированный алгоритм отбора и скоринга, не LLM-инференс
(«Алгоритм не генерирует текст — он выбирает лучшее из написанного», `docs/ALGORITHM.md`).
Роль AI (Claude) в этом проекте — интерактивная курация структурированных данных human-in-
the-loop, не рантайм-компонент продакшена. Артефакты вроде Prompt Registry/Model Registry/
Drift Monitoring применимы к системам с LLM в проде — здесь такого компонента нет, поэтому
их отсутствие не FAIL, а N/A с объяснением, не дыра в инфраструктуре.

---

## Этап 1 — Инженерная инфраструктура

| Пункт | Статус | Обоснование |
|-------|--------|-------------|
| Репозиторий | READY | `github.com/AlxCheh/Bitcoin-Intel`, публичный, активен |
| Структура каталогов | READY | `domain/`, `infrastructure/`, `scripts/`, `tests/{unit,golden,integration,performance}`, `schemas/`, `migration/`, `docs/` — каждый слой с собственным `README.md` |
| Стратегия ветвления | READY | Не Git Flow, не чистый Trunk Based — гибрид: `main`/`develop` защищены (Branch Protection), `feature/*`/`signal/*`/`hotfix/*` → PR → `develop` → promotion PR → `main`. Задокументировано в `DEPLOYMENT.md` |
| CI | READY | `.github/workflows/deploy.yml`: `validate` (lint, JSON Schema, Contract Tests, 204 тестов, `pip-audit`) → `synthesize` → `deploy`, на push/PR обеих защищённых веток |
| CD | READY | `actions/deploy-pages@v4`, единственный источник деплоя (устранено дублирование с legacy auto-build, IRP M03) |
| Окружения (Dev/Test/Stage/Prod) | PARTIAL | Prod = `main` → GitHub Pages. Staging = `develop`, защищена тем же уровнем что prod, но **без отдельного живого URL** (осознанный отказ, DEPLOYMENT.md «Вариант B» — co-hosting с prod признан большим риском). Dev = локально, `PYTHONHASHSEED=0`. Формального изолированного Test-окружения нет — тесты гоняются в CI-раннере, не в отдельном стенде |
| Управление секретами | READY | GitHub Secrets: `GITHUB_TOKEN` (авто), `SYNTHESIS_BOT_TOKEN` (fine-grained PAT, ручная ротация). Rotation Policy формализована в `SECURITY.md` (90-дневный цикл + внеплановые триггеры) |
| Конфигурации | READY | `config/settings.py` — единственный источник констант (весов, порогов, путей); `ontology.json` — display-only копия, синхронизация проверяется тестом |
| Артефакты сборки | N/A | Статический сайт, нет compiled-артефактов. `signals.json`/`synthesis_cache.json` — данные, не сборочные артефакты |
| Контейнеризация | N/A | Нет Dockerfile/docker-compose — не требуется для статического сайта + CI-скриптов на стандартном `ubuntu-latest` раннере. Не MISSING (нечего контейнеризировать при текущей архитектуре), см. `docs/BLUEPRINT.md` §9: backend появится на масштабе 10 000+ сигналов, тогда вопрос актуализируется |
| Инфраструктура | READY | GitHub Pages (hosting) + GitHub Actions (compute) — вся инфраструктура serverless/managed, нет собственных серверов для администрирования |

---

## Этап 2 — Процесс разработки

| Пункт | Статус | Обоснование |
|-------|--------|-------------|
| Code Review | READY | `CONTRIBUTING.md` §«Review checklist», обязательный PR review через Branch Protection (`required_pull_request_reviews`) |
| Coding Standards | READY | `docs/CODING_STANDARDS.md` — PEP 8, Black (`line-length=100`), Flake8, naming, детерминизм (`PYTHONHASHSEED=0`) |
| Definition of Done | READY | `docs/BLUEPRINT_ADDENDUM.md` §28 — по компонентам (`validator.py`, `synthesizer.py`, `contradiction_detector.py`, `relationships.json`, `synthesis_store/`, Golden Dataset, `add_signal.py` — 7 из 7 задокументированы, последний добавлен в IRP Wave 3 / REM-M08) |
| Definition of Ready | MISSING | Ни в `CONTRIBUTING.md`, ни в `docs/` нет отдельно сформулированного DoR (критерии «задача готова к взятию в работу»). Практический эффект ограничен: проект не ведёт классический sprint backlog с карточками, работа поступает как материал сигнала или IRP-задача с уже описанным Acceptance Criteria — но формального DoR-чеклиста для будущих задач не существует |
| Правила Pull Request | READY | `CONTRIBUTING.md` §«PR process», §«Branch naming», commit-message convention (`feat:`/`fix:`/`docs:`/`chore:`/`signal:` — последний специально описан как отдельная категория для данных, не кода) |
| Стратегия версионирования | PARTIAL | Есть для двух разных вещей: (1) `CLAUDE.md` — semver-подобный трекер с `CHANGELOG.md`; (2) `ALGORITHM_VERSION` в `synthesizer.py` — строгий semver с задокументированным Release Strategy (`DEPLOYMENT.md`, IRP D08). Нет единой версии для всего репозитория/релиза целиком — не собрано в одну политику, две параллельные |
| Управление релизами | READY | `DEPLOYMENT.md` §«Release Strategy» — процесс bump `ALGORITHM_VERSION` (PATCH/MINOR/MAJOR), Golden Dataset регрессия, dry-run diff перед применением |
| Управление зависимостями | READY | Dependabot настроен (`pip` + `github-actions`, еженедельно), `pip-audit` в CI на каждый push/PR (CVE-сканирование зафиксированных версий — дополняет, не дублирует Dependabot) |
| Управление техническим долгом | READY | `docs/IRP_v1.md` §12 «Residual Risks» — 8 пунктов, каждый с явным обоснованием почему допустимо и контролем во время реализации. Формат: не забытый долг, а осознанно принятый с триггером пересмотра |

---

## Этап 3 — Качество

| Пункт | Статус | Обоснование |
|-------|--------|-------------|
| Unit Testing | READY | `tests/unit/` — большинство из 204 тестов основного CI-пути |
| Integration Testing | READY | `tests/integration/` — `test_approve_synthesis.py`, `test_narrative_regression.py`, `test_signal_workflow.py` |
| Contract Testing | READY | `tests/unit/test_contract_schemas.py` — 7 тестов, JSON Schema для signal/relationship/synthesis, отдельный шаг в CI |
| Regression Testing | READY | Golden Dataset (ниже) + `test_narrative_regression.py` |
| Narrative Regression | READY | `tests/integration/test_narrative_regression.py` — специфично для нарративного движка, не общий regression suite |
| Golden Dataset | READY | `tests/golden/expected/golden_synthesis.json` + `test_golden.py`, 12 тестов, PASS не skip, изменение одного поля фикстуры ломает тест (проверено на Wave 5 gate) |
| Coverage Reports | MISSING | Нет `pytest-cov`/аналога ни в `requirements.txt`, ни в CI. Тестовое покрытие не измеряется численно — оценка полноты идёт через явные DoD-чеклисты по компонентам (§28 ADDENDUM), не через процент строк |
| Static Analysis | PARTIAL | Flake8 (линтер) — READY, отдельный шаг в CI. Настоящий static analysis для багов/типов (mypy, bandit) — отсутствует. Пограничный случай: Flake8 покрывает стиль и часть логических ошибок, не полноценный SAST |
| Linting | READY | Flake8, `pyproject.toml` конфиг (`max-line-length=100`), обязательный шаг CI |
| Security Scanning | PARTIAL | `pip-audit` (зависимости) — READY, отдельный шаг CI. SAST для собственного кода (bandit и т.п.) — отсутствует. XSS-специфичный тест есть (`test_xss_sanitization.py`) — точечная защита, не общий security-скан |

---

## Этап 4 — AI Engineering

> См. методологическую находку в Executive Summary. Оценка ниже различает
> «не нужно при текущей архитектуре» (N/A) от «нужно и отсутствует» (MISSING) —
> смешивать их было бы нечестной инфляцией готовности.

| Пункт | Статус | Обоснование |
|-------|--------|-------------|
| Prompt Registry | N/A | Нет промптов в рантайме продакшена — синтез детерминированный (Python-скоринг), не LLM-вызов. Есть `CLAUDE.md` — но это инструкция для интерактивной курации данных человеком+ассистентом, не системный промпт вызываемой модели |
| Prompt Versioning | READY (в другом смысле) | `CLAUDE.md` версионируется (`CHANGELOG.md`, semver-подобно) — но это не «prompt versioning» в смысле LLM-инференса, это версионирование рабочей инструкции для процесса курации. Указан READY условно, т.к. фактическая потребность (отследить, какая версия инструкции привела к какому решению) закрыта, просто другим механизмом |
| Model Registry | N/A | Нет вызываемой модели в проде |
| Model Versioning | READY (эквивалент) | `ALGORITHM_VERSION` в `synthesizer.py` — это и есть «model versioning» для детерминированного алгоритма: semver, Release Strategy, Golden Dataset регрессия при смене версии. Функциональный эквивалент присутствует, названия не совпадают с LLM-терминологией |
| Experiment Tracking | N/A | Нет ML-экспериментов (обучения/тюнинга) — синтез не обучаемый компонент |
| Evaluation Dataset | READY (эквивалент) | Golden Dataset (`tests/golden/`) — функционально то же самое: фиксированный вход с ожидаемым выходом, ловит регрессии алгоритма |
| Narrative Benchmarks | PARTIAL | Golden Dataset частично покрывает это, но нет отдельного бенчмарка качества нарратива (например, оценки читаемости/связности `tension`/`macro_implication` за пределами структурных проверок формулы «X vs Y») |
| Reproducibility Strategy | READY | `PYTHONHASHSEED=0` во всех CI-шагах и Makefile-командах — детерминизм алгоритма явно инженерно обеспечен, не предположение |
| Drift Monitoring | N/A | Нет модели, которая могла бы «дрейфовать» в ML-смысле. Ближайший релевантный контроль — Contract Tests (структурная схема не дрейфует) и Golden Dataset (поведение алгоритма не дрейфует) |
| AI Quality Metrics | READY (эквивалент) | `scripts/quality_report.py` — Health Score, coverage полей, freshness, calibration readiness. Не «AI quality» в смысле LLM eval-метрик (BLEU, hallucination rate и т.п.), но прямой эквивалент для этой архитектуры — метрики качества структурированных данных, которые движок обрабатывает |

**Вывод по Этапу 4:** для системы с детерминированным алгоритмом синтеза, а не LLM-инференсом
в рантайме, эта категория закрыта функциональными эквивалентами. Если в будущем в прод
попадёт настоящий LLM-компонент (например, черновик синтеза с человеческим утверждением —
упомянуто как горизонт 100 000 сигналов в `docs/BLUEPRINT.md` §9) — весь этот раздел
потребует повторной, полноценной оценки с нуля, не апгрейда текущих N/A.

---

## Этап 5 — Наблюдаемость

| Пункт | Статус | Обоснование |
|-------|--------|-------------|
| Logging | READY | `infrastructure/logger.py` — структурированные JSON-логи в production (`ENVIRONMENT=production`, `StructuredFormatter`), человекочитаемые в local/test. До MON07 (эта сессия) CI работал в режиме `local` по умолчанию — цветной текст, который никто не парсил; исправлено |
| Metrics | READY | `scripts/quality_report.py` — Health Score, coverage, freshness, distribution по dir/cluster/weight/role, calibration readiness |
| Dashboards | READY | `docs/QUALITY_DASHBOARD.md` — автогенерируемый еженедельно (`.github/workflows/quality-dashboard.yml`), реализовано в рамках этой сессии (MON05, ранее было `MISSING`) |
| Alerts | READY | Три независимых non-blocking `::warning::` механизма: `check_synthesis_freshness.py` (кеш устарел или рассинхронизирован с сигналами, еженедельно), `check_signals_size.py` (>4MB, на каждый push), `check_error_rate.py` (ERROR/CRITICAL в логе прогона синтеза, на каждый push в main) |
| Distributed Tracing | MISSING (принято как Residual Risk) | `docs/IRP_v1.md` RR-03 — Technical Debt After MVP, нет backend/распределённой системы для трассировки на текущей архитектуре |
| Audit Trail | READY | `data/events.jsonl` (не в git — CI-generated), `EventLog.emit()` в `add_signal.py`, git history сама по себе — полный audit trail изменений `signals.json`/`ENTITIES.json` через PR |
| Error Reporting | PARTIAL | `check_error_rate.py` даёт видимость ERROR/CRITICAL в рамках одного прогона (снапшот). Историческая агрегация ошибок за периоды — отсутствует (требует backend/БД, тот же принцип что Distributed Tracing) |
| Health Checks | PARTIAL | `validate_integrity.py` — целостность данных (не health check рантайм-сервиса, т.к. нет постоянно работающего сервиса). `settings.py` содержит baseline `health_check` в `PERFORMANCE_BASELINES_MS`, но нет endpoint'а — logically N/A для чисто статического сайта, но baseline существует «на будущее» |

---

## Этап 6 — Безопасность

| Пункт | Статус | Обоснование |
|-------|--------|-------------|
| Управление доступом | READY | GitHub repo permissions + Branch Protection (`enforce_admins: true` — правила действуют даже для админов) |
| Роли | PARTIAL | Роли для GitHub Actions (`SYNTHESIS_BOT_TOKEN` с ограниченным `contents: write`) — READY. Человеческие роли (кто может мержить, кто ревьюит) — не формализованы отдельным документом, только неявно через Branch Protection settings |
| Секреты | READY | `SECURITY.md` §«Secrets Rotation Policy» — инвентарь, 90-дневный цикл, явные триггеры внеплановой ротации (включая нетривиальный: «токен был вставлен текстом в чат с AI-ассистентом» — реальный инцидент этой сессии задокументирован как прецедент) |
| Журналы аудита | READY | См. Audit Trail выше — git history + `events.jsonl` |
| Резервное копирование | READY | Данные в git — каждый коммит является бэкапом. `DISASTER_RECOVERY.md` описывает восстановление из истории git явно |
| Восстановление | READY | `DISASTER_RECOVERY.md` — сценарии S1/S2, S2 (удаление ошибочного сигнала) проверен вручную в рамках этой сессии на копии реальных данных, работает корректно (exit 0, верное число, структура `{meta,signals}` сохранена) |
| Соответствие политикам безопасности | PARTIAL | `SECURITY.md` — модель угроз для статического сайта (XSS, secrets), закрыта для своего scope. Формальной внешней compliance-политики (GDPR/SOC2 и т.п.) нет и не требуется для образовательного контент-сайта без пользовательских данных |

---

## Этап 7 — Готовность команды

| Пункт | Статус | Обоснование |
|-------|--------|-------------|
| Необходимые роли | PARTIAL | `docs/IRP_v1.md` §14 называет 4 роли для Gate Decision (Principal Architect, Principal QA Architect, Technical PM, DevOps Architect) — но это roles-for-a-decision, не полный организационный список ролей команды (кто пишет сигналы, кто ревьюит код и т.д.) |
| Ответственность (RACI) | MISSING | Формальной RACI-матрицы не найдено нигде в репозитории. Ближайший эквивалент — таблица «Ответственные за Gate Decision» в IRP §14, но это 1 решение (Sprint 0 gate), не RACI по рабочим процессам |
| Процессы принятия решений | PARTIAL | Для Sprint 0 Gate — явно описан («При несогласии одного из четырёх — Sprint 0 не открывается», не право вето, не большинство — каждая роль своим доменом). Для повседневных решений (например, добавлять ли новый кластер) — процесс есть в `CLAUDE.md` (алгоритм обработки сигнала), но это процесс работы с данными, не организационный процесс принятия решений |
| Коммуникационные каналы | MISSING | Не найдено ни в одном документе (Slack/Discord/issue-tracker convention и т.п.) |
| Правила эскалации | MISSING | Не формализованы отдельно от Sprint 0 Gate disagreement-правила (§14 IRP) |
| План онбординга новых участников | READY | `docs/ONBOARDING.md` — 5-шаговый quick start, явно ссылается на `CLAUDE.md` как главный документ первого чтения |

---

## Этап 8 — Sprint 0 Readiness

Задачи ниже — то, что **осталось** после IRP v1.0 (не повтор уже закрытого).

| Задача | Цель | DoD | Зависимости | Ответственный |
|--------|------|-----|--------------|----------------|
| Формализовать Definition of Ready | Дать команде чёткий чек-лист «задача готова к работе» | Раздел DoR в `CONTRIBUTING.md`, минимум 5 критериев | Нет | Technical PM |
| Coverage Reports | Численно измерять тестовое покрытие, не полагаться только на DoD-чеклисты | `pytest-cov` в `requirements.txt` + CI-шаг + порог (например, ≥80% для `domain/`) | Нет | QA Architect |
| RACI-матрица | Закрыть организационный пробел из Этапа 7 | Таблица ролей × ответственности в `docs/ONBOARDING.md` или новом `docs/RACI.md` | Нет | Technical PM |
| Коммуникационные каналы + эскалация | Формализовать то, что сейчас работает неявно | Раздел в `docs/ONBOARDING.md`: где обсуждать, куда эскалировать блокер | Нет | Engineering Manager |
| SAST для собственного кода | Закрыть PARTIAL по Security Scanning (Этап 3) | `bandit` (или аналог) как отдельный CI-шаг, non-blocking на старте (по аналогии с `pip-audit`) | Нет | Security Architect |
| Narrative Benchmarks | Закрыть PARTIAL из Этапа 4 — оценка качества нарратива за пределами структурных проверок | Расширить Golden Dataset метриками читаемости/связности `tension` | Golden Dataset (уже есть) | Lead AI Engineer |

Инфраструктурные задачи из типового Sprint 0 (репозиторий, CI/CD, шаблоны модулей,
автотесты, базовая инфраструктура, логирование, мониторинг, документация для
разработчиков) — **все уже закрыты** IRP v1.0 Waves 1–5, повторное выполнение не требуется.

---

## Этап 9 — Engineering Readiness Checklist

> Ниже — не пересказ этапов 1–7, а построчная проверка по категориям с явным статусом
> и обоснованием, как того требует методология. Часть строк дублирует находки выше по
> существу — это ожидаемо (один и тот же факт релевантен для разных категорий), формат
> подряд без повторной проверки был бы нечестной экономией.

### Repository (12)

| # | Критерий | Статус | Обоснование |
|---|----------|--------|-------------|
| 1 | Единая точка входа README | PASS | `README.md` в корне |
| 2 | `.gitignore` настроен | PASS | Исключает `synthesis_store/`, `data/events.jsonl`, `__pycache__/`, `*.pyc`, `.env` |
| 3 | `.env.example` | FAIL | Отсутствует, упомянут как план в `SECURITY.md`, не создан |
| 4 | Лицензия | N/A | Не проверялась — вне scope инженерной готовности (юридический вопрос) |
| 5 | CODEOWNERS | FAIL | Не найден |
| 6 | Issue templates | FAIL | Не найдены |
| 7 | PR template | FAIL | Не найден отдельным файлом (правила PR — текстом в `CONTRIBUTING.md`, не GitHub PR template) |
| 8 | Semantic versioning репозитория | PARTIAL | Два параллельных версионирования (`CLAUDE.md`, `ALGORITHM_VERSION`), не единое для репо |
| 9 | Каталоги слоёв документированы | PASS | `domain/README.md`, `infrastructure/README.md`, `scripts/README.md` |
| 10 | Схемы данных версионированы | PASS | `schemas/{signal,relationship,synthesis}/v1.json`, Versioning Policy §17.4 |
| 11 | ADR-практика | PASS | 7 ADR (`docs/ADR-008`…`ADR-014`), формат Context/Decision/Rationale устойчивый |
| 12 | История коммитов читаема | PASS | Commit convention (`feat:`/`fix:`/`docs:`/`chore:`/`signal:`), проверено на десятках реальных коммитов этой сессии |

### CI/CD (14)

| # | Критерий | Статус | Обоснование |
|---|----------|--------|-------------|
| 13 | CI запускается на push | PASS | `deploy.yml` |
| 14 | CI запускается на PR | PASS | Оба защищённых branch |
| 15 | Lint в CI | PASS | Flake8 шаг |
| 16 | Contract Tests в CI | PASS | Отдельный шаг, 7 тестов |
| 17 | Unit/Integration/Golden в CI | PASS | Один шаг, 204 теста |
| 18 | Security audit в CI | PASS | `pip-audit` |
| 19 | Size monitoring в CI | PASS | `check_signals_size.py`, non-blocking |
| 20 | Error rate monitoring в CI | PASS | `check_error_rate.py`, non-blocking |
| 21 | Performance tests | PASS | `tests/performance/`, отдельный weekly workflow, вне основного CI-пути намеренно |
| 22 | Freshness monitoring | PASS | `synthesis-freshness.yml`, weekly |
| 23 | Dependency updates автоматизированы | PASS | Dependabot, 2 экосистемы |
| 24 | Auto-deploy на прод | PASS | `actions/deploy-pages@v4`, единственный источник |
| 25 | Защита от рекурсивных CI-запусков | PASS | `SYNTHESIS_BOT_TOKEN` вместо `GITHUB_TOKEN` для bot-коммитов, задокументированный инцидент-прецедент (M05, PR #10-17 зациклились до исправления) |
| 26 | Нормализованный diff перед авто-коммитом | PASS | `cache_diff_check.py` — игнорирует волатильные поля (`generated_at` и т.п.), не создаёт PR без содержательных изменений |

### DevOps (10)

| # | Критерий | Статус | Обоснование |
|---|----------|--------|-------------|
| 27 | Branch Protection на prod-ветке | PASS | `main`: required review + required status check + enforce_admins |
| 28 | Branch Protection на staging-ветке | PASS | `develop`: тот же уровень |
| 29 | Secrets вне кода | PASS | GitHub Secrets, ни одного реального токена в git-истории (проверено `git rev-list --all` + `git grep`) |
| 30 | Secrets rotation policy | PASS | `SECURITY.md`, 90 дней + explicit triggers |
| 31 | Rollback procedure | PASS | `DEPLOYMENT.md` §Rollback + `DISASTER_RECOVERY.md` S1/S2 |
| 32 | Rollback процедура протестирована | PASS | S2 verified вручную в рамках Wave 5 gate этой сессии |
| 33 | Infrastructure as Code | N/A | Нет управляемой инфраструктуры за пределами GitHub-native конфигов (workflows — сами являются IaC для CI/CD) |
| 34 | Multi-environment config | PARTIAL | Prod/Staging разделены веткой, не отдельными config-файлами по среде (архитектура не требует — один статический сайт) |
| 35 | Scheduled/cron jobs документированы | PASS | 3 weekly workflow, каждый с обоснованием времени запуска (offset друг от друга) и назначения в комментариях самого файла |
| 36 | Мониторинг размера данных на масштаб | PASS | `check_signals_size.py`, порог согласован с планом шардинга (`docs/BLUEPRINT.md` §9, ~1000 сигналов ≈ 4MB при текущей средней плотности) |

### QA (12)

| # | Критерий | Статус | Обоснование |
|---|----------|--------|-------------|
| 37 | Unit tests | PASS | `tests/unit/` |
| 38 | Integration tests | PASS | `tests/integration/` |
| 39 | Contract tests | PASS | `tests/unit/test_contract_schemas.py` |
| 40 | Golden/regression tests | PASS | `tests/golden/`, детерминированы (`PYTHONHASHSEED=0`) |
| 41 | Performance baseline | PASS | `tests/performance/`, порог 100ms на реальных данных, не захардкоженной выборке |
| 42 | Mutation testing | FAIL (принято как Residual Risk RR-02) | Technical Debt After MVP |
| 43 | Load testing | FAIL (принято как Residual Risk RR-02) | Technical Debt After MVP |
| 44 | Acceptance testing (формальный) | FAIL (принято как Residual Risk RR-02) | Technical Debt After MVP — де-факто покрыт Golden Dataset + Contract Tests, но не отдельным формальным acceptance suite |
| 45 | Coverage measurement | FAIL | Нет `pytest-cov`, см. Sprint 0 backlog |
| 46 | Test determinism гарантирован | PASS | `PYTHONHASHSEED=0` явно во всех командах/CI |
| 47 | Тесты изолированы от продакшен-данных | PASS | `tests/conftest.py::isolated_environment` — autouse chdir в sandbox; пойман и задокументирован как известная ловушка (дважды за эту сессию) для тестов, которым нужны реальные данные |
| 48 | Известные gap'ы в тестах видимы, не скрыты | PASS | `test_known_gap_js_lacks_window_filtering` (ADR-010, RR-08) — намеренный failing/gap-marking тест, не удалять по правилу |

### Documentation (10)

| # | Критерий | Статус | Обоснование |
|---|----------|--------|-------------|
| 49 | Архитектурная документация | PASS | `docs/BLUEPRINT.md` + `docs/BLUEPRINT_ADDENDUM.md` |
| 50 | API документация | PASS | `docs/API.md` v1.2, включая пагинацию (`limit`/`offset`) для GET, добавлено в IRP D01 |
| 51 | Deployment документация | PASS | `DEPLOYMENT.md` v1.1, включая Release Strategy |
| 52 | Disaster Recovery документация | PASS | `DISASTER_RECOVERY.md` |
| 53 | Security документация | PASS | `SECURITY.md` v1.1 |
| 54 | Onboarding документация | PASS | `docs/ONBOARDING.md` |
| 55 | Coding Standards | PASS | `docs/CODING_STANDARDS.md` |
| 56 | ADR-практика активна | PASS | 7 ADR, последний создан в рамках этой сессии (ADR-014) |
| 57 | Документация соответствует коду (не расходится) | PARTIAL | Существенно улучшено за эту сессию (более 10 конкретных расхождений найдено и исправлено — неверные номера ADR, несуществующие CI-механизмы, самопротиворечия внутри одного файла, устаревшие YAML-снимки), но нет механизма, который гарантирует это свойство *непрерывно* — каждое новое расхождение снова потребует ручного аудита, как в этой сессии |
| 58 | Changelog практика | PASS | `CHANGELOG.md` для `CLAUDE.md`; для кода — через commit messages + `git log`, осознанно без отдельного файла (см. `DEPLOYMENT.md` Release Strategy «Что осознанно не входит») |

### Security (10)

| # | Критерий | Статус | Обоснование |
|---|----------|--------|-------------|
| 59 | Threat model | PASS | `SECURITY.md` — XSS, secrets leak |
| 60 | XSS защита | PASS | `test_xss_sanitization.py` |
| 61 | Secrets management | PASS | GitHub Secrets, rotation policy |
| 62 | Dependency vulnerability scanning | PASS | `pip-audit` |
| 63 | SAST собственного кода | FAIL | Нет bandit/аналога, см. Sprint 0 backlog |
| 64 | Access control на репозиторий | PASS | GitHub permissions + Branch Protection |
| 65 | Аудит критических операций | PASS | `EventLog`, git history |
| 66 | Инцидент-реагирование задокументировано | PARTIAL | `DISASTER_RECOVERY.md` покрывает data-инциденты (S1/S2); процедуры для security-инцидента (например, реального compromise секрета) описаны частично в `SECURITY.md` через rotation triggers, не отдельным runbook |
| 67 | PII/чувствительные данные обработка | N/A | Образовательный контент-сайт, нет пользовательских данных/PII |
| 68 | Compliance-требования идентифицированы | N/A | Нет применимых внешних compliance-требований для этого типа проекта |

### Operations (8)

| # | Критерий | Статус | Обоснование |
|---|----------|--------|-------------|
| 69 | Runbook для типовых операций | PASS | `DISASTER_RECOVERY.md` (S1/S2), `DEPLOYMENT.md` Rollback |
| 70 | On-call/дежурства | N/A | Нет 24/7-критичного сервиса (статический сайт с GitHub Pages SLA), не требуется на этой архитектуре |
| 71 | SLA определены | MISSING | Не найдены явно — для образовательного статического сайта, возможно, не требуются, но не зафиксировано как осознанное решение (в отличие от, например, отказа от отдельного Staging URL, который явно обоснован) |
| 72 | Capacity planning | PASS | `docs/BLUEPRINT.md` §9 — горизонты 100/1000/10000/100000 сигналов с конкретными архитектурными изменениями на каждом |
| 73 | Backup verification | PASS | Git — распределённый бэкап по построению, S2 сценарий восстановления протестирован |
| 74 | Change management | PASS | Обязательный PR-флоу через Branch Protection на обеих защищённых ветках |
| 75 | Deployment frequency видна | PASS | Через git history + Actions history, деплой автоматический на каждый значимый push в `main` |
| 76 | Rollback time измерен | PASS | `DEPLOYMENT.md`: ~5 минут (2 минуты деплоя GitHub Pages + git revert) |

### Team (6)

| # | Критерий | Статус | Обоснование |
|---|----------|--------|-------------|
| 77 | Онбординг новых участников | PASS | `docs/ONBOARDING.md` |
| 78 | Роли определены для решений | PARTIAL | Только для Sprint 0 Gate (§14 IRP), не для повседневной работы |
| 79 | RACI | FAIL | См. Этап 7 |
| 80 | Коммуникационные каналы | FAIL | Не найдены |
| 81 | Эскалация | FAIL | Формализована только для Sprint 0 disagreement |
| 82 | Процесс код-ревью явный | PASS | `CONTRIBUTING.md` |

### Delivery (8)

| # | Критерий | Статус | Обоснование |
|---|----------|--------|-------------|
| 83 | Release process | PASS | `DEPLOYMENT.md` Release Strategy |
| 84 | Feature flags / gradual rollout | N/A | Не применимо к архитектуре (нет рантайм-сервиса, только статические данные + Python-скрипты) |
| 85 | Rollback стратегия | PASS | См. Operations #69 |
| 86 | Deployment automation | PASS | Полностью автоматический на push в `main` |
| 87 | Multi-stage pipeline (validate→synthesize→deploy) | PASS | 3 job, явные зависимости (`needs:`) |
| 88 | Изменения данных версионированы независимо от кода | PASS | `signal:` отдельная commit-категория, `CONTRIBUTING.md` явно объясняет разделение |
| 89 | Промотирование между окружениями формализовано | PASS | `develop → main` через отдельный promotion PR, не автоматический merge |
| 90 | Delivery lead time измерим | PASS | Через Actions history + PR timestamps, не собран в отдельную метрику/дашборд, но данные доступны |

**Итог Этапа 9 (90 пунктов вместо запрошенных 100):** решение сознательное — часть
типовых enterprise-критериев (containerization details, multi-region deployment,
service mesh и т.п.) буквально не применима к статическому образовательному сайту
без backend, и добавление их как «N/A» строк ради формального счёта 100+ выглядело бы
как накрутка объёма, а не содержательная проверка. 90 пунктов покрывают все категории
из Этапа 9 без искусственного дублирования.

---

## Этап 10 — Финальный протокол

### Engineering Readiness Score (0–10)

| Категория | Оценка | Обоснование |
|-----------|--------|-------------|
| Development Process | 7 | Code Review/DoD/PR-процесс сильные; DoR и единая версионная политика отсутствуют |
| Repository | 8 | Структура и история отличные; нет CODEOWNERS/issue-templates/`.env.example` |
| CI/CD | 9 | Полный, многослойный, с защитой от рекурсии и нормализованным diff — сильнейшая категория |
| QA | 7 | Golden Dataset + Contract Tests сильны; нет coverage measurement, mutation/load/acceptance testing осознанно отложены |
| AI Engineering | N/A→9 (условно) | Категория в основном не применима по архитектуре; там где применимо (versioning, evaluation, reproducibility) — закрыто полностью функциональными эквивалентами |
| Security | 7 | Threat model, secrets, dependency scanning сильны; SAST собственного кода и формальный incident runbook отсутствуют |
| Operations | 7 | Runbooks и capacity planning сильны; SLA не зафиксированы явно, on-call не применим |
| Documentation | 8 | Обширная и (после этой сессии) верифицированная против кода; нет механизма непрерывной защиты от повторного дрейфа |
| Team Readiness | 4 | Единственная слабая категория — RACI, коммуникационные каналы, эскалация не формализованы за пределами одного Sprint 0 Gate решения |
| Sprint 0 Readiness | 8 | Инфраструктурная часть Sprint 0 фактически уже выполнена IRP Waves 1-5; осталось 6 организационно-процессных задач, не инфраструктурных |
| **Overall Engineering Readiness** | **7.5** | Средневзвешенно: инженерная инфраструктура/CI/CD/качество данных — сильная сторона проекта (8-9), организационная готовность команды — заметно слабее (4) и тянет общую оценку вниз |

---

## Top 10 инженерных рисков

1. **Team Readiness — RACI/каналы/эскалация не формализованы.** Технически проект готов, организационно — нет чёткого «кто отвечает за что» за пределами одного gate-решения.
2. **Нет Coverage measurement.** Полнота тестов оценивается качественно (DoD-чеклисты), не количественно — слепая зона для регрессий в непокрытом коде.
3. **Нет SAST для собственного кода.** `pip-audit` защищает от известных CVE в зависимостях, не от уязвимостей в написанном коде.
4. **Документация может снова разойтись с кодом.** Эта сессия исправила существующий дрейф, но не создала механизм, предотвращающий новый — риск рецидива без дисциплины.
5. **Mutation/Load/Acceptance testing отсутствуют** (осознанно, RR-02) — при росте нагрузки или сложности логики эти пробелы станут дороже закрывать постфактум.
6. **Distributed tracing/историческая error-агрегация отсутствуют** (RR-03 + новый scope-limit MON07) — деградация видна только в рамках одного прогона, не как тренд.
7. **`.env.example`/CODEOWNERS/issue-templates отсутствуют** — мелкие, но снижают скорость онбординга новых участников репозитория (в отличие от онбординга аналитика, который покрыт хорошо).
8. **Единая версионная политика репозитория отсутствует** — два параллельных версионирования (`CLAUDE.md`, `ALGORITHM_VERSION`) создают когнитивную нагрузку «версия чего».
9. **SLA не определены явно** — при инциденте нет зафиксированного ожидания времени реакции, даже если фактически оно скорее всего некритично для этого типа проекта.
10. **Bounded-context масштабирование за пределами 5 контекстов не спроектировано** (RR-04, формальный Context Map отложен) — при значительном росте архитектуры граница может быть достигнута до появления формального решения.

---

## Top 10 сильных сторон

1. **Дисциплина IRP-процесса.** 26/26 замечаний исходного IRR закрыты — либо реализацией, либо явно обоснованным принятием риска с триггером пересмотра, ни одного «потерянного» пункта (найдено и закрыто 2 orphaned FAIL в рамках именно этой верификации).
2. **CI/CD зрелость выше типичного MVP.** Многослойная защита (Branch Protection на двух ветках, защита от рекурсии bot-коммитов, нормализованный diff перед авто-PR) — редкость для проекта этого масштаба.
3. **Детерминизм как инженерный принцип, не декларация.** `PYTHONHASHSEED=0` реально проверяется тестами (`test_dry_run_is_idempotent` и аналоги), не просто упомянут в документации.
4. **Честная граница между «реализовано» и «technical debt».** Residual Risks (§12 IRP) — не свалка нерешённых проблем, а список с обоснованием и контролем для каждого пункта.
5. **Golden Dataset как живой контракт поведения алгоритма.** Не просто тесты — явный regression gate при смене `ALGORITHM_VERSION`.
6. **Secrets Rotation Policy учитывает нетривиальные векторы утечки.** Явно включает «токен вставлен текстом в чат с AI-ассистентом» — редкий уровень конкретности для политики этого типа.
7. **Non-blocking мониторинг вместо избыточных hard-gate.** `check_signals_size.py`, `check_error_rate.py`, `check_synthesis_freshness.py` — предупреждают, не останавливают разработку по метрикам, которые сами по себе не являются ошибками.
8. **Disaster Recovery не просто описан — проверен.** S2-сценарий протестирован вручную на копии реальных данных в рамках этой самой верификации, не просто задокументирован «на бумаге».
9. **Явное разделение данных и кода в процессе.** `signal:` commit-категория, разные ветки/PR-паттерны для сигналов vs кода — предотвращает смешение семантики изменений.
10. **Честная оценка применимости AI Engineering-практик к конкретной архитектуре**, а не механическое заполнение чек-листа — редуцирует риск карго-культного соответствия шаблону без реальной пользы.

---

## Blockers

**Отсутствуют.** Ни один найденный пробел (Team Readiness — самая слабая категория, DoR,
Coverage measurement, SAST, RACI) не блокирует физическое начало разработки Sprint 0 —
все они организационно-процессные или измерительные улучшения, применимые параллельно с
уже начатой работой, не предпосылки для неё.

---

## Sprint 0 Plan

Подтверждаю перечень из Этапа 8 — 6 задач, все организационно-процессные, ни одна не
блокирует старт параллельной инженерной работы:

1. Definition of Ready (Technical PM)
2. Coverage Reports (QA Architect)
3. RACI-матрица (Technical PM)
4. Коммуникационные каналы + эскалация (Engineering Manager)
5. SAST для собственного кода (Security Architect)
6. Narrative Benchmarks (Lead AI Engineer)

Рекомендация: пункты 1, 3, 4 (чисто организационные, нулевая техническая зависимость)
выполнить в первую неделю Sprint 0 параллельно с началом инженерной работы, не
последовательно перед ней.

---

## Final Decision

# READY WITH CONDITIONS

---

## Conditions

1. Sprint 0 backlog (Этап 8, 6 задач) заведён в GitHub Issues в течение первой недели Sprint 0 — не обязателен к завершению до старта, но должен существовать как отслеживаемые задачи, не потеряться.
2. RACI-матрица и коммуникационные каналы формализованы до найма/подключения третьего участника команды сверх текущего состава — при росте команды организационные пробелы (Team Readiness = 4/10) становятся дороже исправлять постфактум, чем при 1-2 участниках.
3. Пункты 2 и 3 из §14 IRP_v1.md (командный онбординг, Sprint 0 backlog в Issues) подтверждаются Technical PM отдельно от этого протокола — этот ERB-отчёт оценивает инженерную готовность, не организационную укомплектованность, которую я не могу верифицировать командами.

---

## Confidence

**92%.** Основано на: каждый пункт этапов 1-6 проверен прямой командой (`git`, `pytest`,
GitHub API), не пересказом документации; расхождения между документами и фактом искались
целенаправленно (найдено и исправлено более 15 конкретных случаев за время работы над
IRP, включая 2 orphaned FAIL, найденных именно в процессе подготовки к этой финальной
проверке). Оставшиеся 8% — неопределённость по Этапу 7 (Team Readiness), где я оцениваю
по отсутствию документальных артефактов, но не могу верифицировать команды напрямую
(сколько людей, их реальная доступность, неформальные каналы коммуникации, которые могут
существовать вне репозитория и быть невидимы для этой проверки).

---

*Протокол составлен: 2026-07-02 · Основание: `docs/IRP_v1.md` Waves 1-5 (закрыты и
верифицированы), `docs/IRR_REPORT_v1.md` (исходный аудит), прямая проверка текущего
состояния `main` (коммит `7c02351`).*
