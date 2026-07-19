"""
tests/unit/test_workflow_sync_pr_safety.py
Bitcoin Intel — страж против зависших bot-sync-PR (обнаружено 2026-07-19).

КОНТЕКСТ: main защищён branch protection с required_status_checks.strict=true
("ветка должна быть up to date с main перед мерджем"). Три автоматизации
(synthesize в deploy.yml, build-facts.yml, update-volume.yml) коммитят через
паттерн "своя ветка → PR → gh pr merge --auto" — ветка создаётся ОДИН РАЗ и
никогда не обновляется. Если main уходит вперёд (любой другой мердж) ДО того
как auto-merge успеет сработать — PR виснет НАВСЕГДА в mergeable_state=unknown,
ожидая состояние, которое никто не актуализирует. В активном репозитории это
не редкий случай: за 2026-07-14..17 накопилось 4 зависших sync-synthesis PR
подряд (#276, #299, #313, #327), обнаружено и устранено 2026-07-19.

ФИКС: перед созданием нового PR каждая автоматизация закрывает все ещё
открытые старые PR той же категории (bot/sync-<kind>-*) — гарантирует
максимум один открытый sync-PR любой категории в любой момент, и он всегда
создаётся от актуального main. Этот тест — структурная проверка, что паттерн
"закрыть старые перед созданием нового" присутствует в каждом workflow,
который создаёт bot/sync-* ветку — если кто-то добавит четвёртую такую
автоматизацию без этой защиты (или случайно уберёт её при правке), тест упадёт
на PR, а не после нескольких дней тихого накопления зависших PR в проде.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Каждый workflow, создающий ветку по этому паттерну, обязан ТАКЖЕ закрывать
# старые PR той же категории тем же шагом. Явный список — не автоскан всех
# *.yml — чтобы добавление НОВОЙ bot/sync-автоматизации без этой защиты было
# заметной сознательной правкой теста, а не тихим пропуском.
KNOWN_SYNC_PR_WORKFLOWS = {
    "deploy.yml": "bot/sync-synthesis-",
    "build-facts.yml": "bot/sync-facts-",
    "update-volume.yml": "bot/sync-volume-",
}


def _read(workflow_file: str) -> str:
    path = WORKFLOWS_DIR / workflow_file
    assert path.exists(), f"Workflow {workflow_file} не найден — {path}"
    return path.read_text(encoding="utf-8")


def test_known_workflows_still_create_expected_branch_prefix():
    """
    Если кто-то переименует префикс ветки (BRANCH="bot/sync-XXX-...") не
    обновив KNOWN_SYNC_PR_WORKFLOWS — этот тест должен заметить расхождение,
    а не тихо перестать проверять нужный файл.
    """
    for workflow_file, prefix in KNOWN_SYNC_PR_WORKFLOWS.items():
        text = _read(workflow_file)
        assert f'BRANCH="{prefix}' in text, (
            f"{workflow_file}: ожидаемый префикс ветки '{prefix}' не найден — "
            "переименовали BRANCH и забыли обновить KNOWN_SYNC_PR_WORKFLOWS "
            "в этом тесте, или защита была случайно удалена"
        )


def test_every_sync_pr_workflow_closes_stale_prs_before_creating_new():
    """
    Каждый workflow из KNOWN_SYNC_PR_WORKFLOWS обязан содержать блок
    'gh pr close' с поиском по префиксу СВОЕЙ же категории ветки,
    расположенный РАНЬШЕ (по тексту файла) команды создания новой ветки
    (git checkout -b "$BRANCH") — порядок важен: закрыть старые НУЖНО ДО
    создания новой, не после.
    """
    for workflow_file, prefix in KNOWN_SYNC_PR_WORKFLOWS.items():
        text = _read(workflow_file)

        close_match = re.search(
            r'gh pr close .*\n', text
        )
        search_pattern_present = f'head:{prefix}' in text
        checkout_idx = text.find('git checkout -b "$BRANCH"')

        assert search_pattern_present, (
            f"{workflow_file}: не найден поиск открытых PR по префиксу "
            f"'{prefix}' (ожидался 'head:{prefix}' в gh pr list --search) — "
            "защита от накопления зависших PR отсутствует или сломана"
        )
        assert close_match, (
            f"{workflow_file}: не найдена команда 'gh pr close' — "
            "автоматизация создаёт новые sync-PR, но не закрывает старые"
        )
        assert checkout_idx != -1, (
            f"{workflow_file}: не найдена команда создания ветки "
            '(git checkout -b "$BRANCH") — структура шага изменилась, '
            "тест нужно обновить"
        )
        assert close_match.start() < checkout_idx, (
            f"{workflow_file}: 'gh pr close' находится ПОСЛЕ создания новой "
            "ветки — старые PR должны закрываться ДО создания новой, иначе "
            "порядок операций не защищает от накопления зависших PR"
        )


def test_all_workflow_files_are_valid_yaml():
    """Базовая проверка синтаксиса — правки этой сессии не сломали YAML."""
    import yaml

    for path in WORKFLOWS_DIR.glob("*.yml"):
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise AssertionError(f"{path.name}: невалидный YAML — {e}")
