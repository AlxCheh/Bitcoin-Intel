"""
tests/unit/test_js_python_equivalence.py
Bitcoin Intel — регрессионный тест эквивалентности JS/Python синтеза
(C1 ARR v3, Condition 5 ARR v2/v3, Этап 2.1 / 4.9 ARR v3).

КОНТЕКСТ
--------
Дашборд читает уже посчитанный data/synthesis_cache.json (производится
Python scripts/synthesizer.py). Если кэш недоступен или повреждён,
index.html переключается на client-side фоллбэк —
synthesizeNarrativeAdvanced() (Путь 3, ARR v3 §2.1). Это два РАЗНЫХ
исходных кода: Python — полный 12-шаговый Reasoning Pipeline с
дедупликацией, окном свежести WINDOW_DAYS_DEFAULT, uncertainty handling
и contradiction-бонусом; JS — упрощённый client-side алгоритм без
сетевого доступа к Python-зависимостям.

ЧТО ЭТОТ ТЕСТ ГАРАНТИРУЕТ (контракт эквивалентности — см. ADR-010)
-------------------------------------------------------------------
Полная байтовая эквивалентность вывода НЕ является целью и не была целью
ни в одной из архитектурных спецификаций проекта — это два независимых
алгоритма с разной формулировкой narrative/bridge-текста по дизайну.
Тест проверяет более узкий, но критичный для пользователя контракт:
при ОДИНАКОВОМ входном наборе сигналов оба пути обязаны прийти к
ОДИНАКОВОМУ выводу о:
  1. `phase`             — фаза кластера (active/tension/resolution/structural)
  2. `anchor_signal_id`  — какой сигнал выбран источником tension/якорем

Если эти два поля расходятся, читатель сайта увидит РАЗНЫЙ нарратив в
зависимости от того, успел ли загрузиться synthesis_cache.json — то есть
от факта, не относящегося к содержанию данных. Это и есть архитектурный
риск, описанный в ARR v3 §4.9.

ИЗВЕСТНЫЙ, ОСОЗНАННО НЕ ЗАКРЫТЫЙ ЭТИМ ТЕСТОМ GAP
--------------------------------------------------
JS-фоллбэк не реализует два Python-специфичных шага препроцессинга:
  - ШАГ 1 (window filtering): Python отбрасывает сигналы старше
    WINDOW_DAYS_DEFAULT (90 дней) или со status="archived" ДО синтеза.
  - §16 (deduplicate_signals): Python схлопывает дубликаты по
    (date, actor, cluster) ДО синтеза.
JS получает уже отфильтрованный `cl.signals` от рендер-пайплайна
дашборда (renderNarrativeItem строит cl из уже загруженного
signals.json), но синтезирующая функция сама эти шаги не повторяет.
Кластер `test_stale` в Golden Dataset существует специально, чтобы
сделать этот gap видимым, а не молчаливым: см.
test_known_gap_js_lacks_window_filtering ниже. Закрытие этого gap —
отдельная задача (см. docs/ADR-010-js-python-equivalence-contract.md,
раздел "Дальнейшая работа"), вне scope этого исправления: оно требует
переноса WINDOW_DAYS_DEFAULT/STALE_THRESHOLD и логики дедупликации в JS,
то есть дублирования бизнес-правил, а не просто исправления порядка
сортировки — более рискованное изменение, заслуживающее отдельного
ревью и тестирования.

Требует Node.js в PATH (доступен на GitHub Actions ubuntu-latest).
"""
import json
import re
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path

import pytest

REPO_ROOT  = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
GOLDEN     = REPO_ROOT / "tests" / "golden" / "fixtures" / "golden_signals.json"

NODE_AVAILABLE = shutil.which("node") is not None

# Кластер существует специально для теста на window-filtering gap (см. docstring).
KNOWN_GAP_CLUSTERS = {"test_stale"}


def _extract_function(html: str, name: str) -> str:
    """
    Извлекает тело функции по балансу фигурных скобок — устойчиво к
    любому отступу закрывающей скобки (см. test_uncertainty_indicator.py,
    где фиксированный-отступ regex однажды уже обрезал эту же функцию).
    """
    start = html.find(f"function {name}")
    assert start != -1, f"Function '{name}' not found in index.html — was it renamed?"
    brace_open = html.find("{", start)
    assert brace_open != -1, f"No opening brace found for '{name}'"
    depth = 0
    i = brace_open
    while i < len(html):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                return html[start:i + 1] + "\n"
        i += 1
    raise AssertionError(f"Unbalanced braces while extracting '{name}'")


@pytest.fixture(scope="module")
def js_synthesize_source() -> str:
    """
    Реальный исходник synthesizeNarrativeAdvanced() из index.html, плюс
    глобальные FRESHNESS_FRESH_DAYS/FRESHNESS_RECENT_DAYS (M3 ARR v3) —
    функция читает их как глобалы, в изолированном Node-сниппете их нужно
    объявить явно, иначе ReferenceError при вызове.
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    fresh_match = re.search(r"let FRESHNESS_FRESH_DAYS\s*=\s*(\d+);", html)
    recent_match = re.search(r"let FRESHNESS_RECENT_DAYS\s*=\s*(\d+);", html)
    assert fresh_match and recent_match, (
        "FRESHNESS_FRESH_DAYS/FRESHNESS_RECENT_DAYS not found in index.html "
        "— were they renamed? (M3 ARR v3)"
    )
    globals_src = (
        f"const FRESHNESS_FRESH_DAYS = {fresh_match.group(1)};\n"
        f"const FRESHNESS_RECENT_DAYS = {recent_match.group(1)};\n"
    )
    return globals_src + _extract_function(html, "synthesizeNarrativeAdvanced")


@pytest.fixture(scope="module")
def golden_clusters() -> dict:
    """Golden Dataset, сгруппированный по cluster — {cluster_key: [signals]}."""
    if not GOLDEN.exists():
        pytest.skip("golden_signals.json not found")
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    signals = data.get("signals", data) if isinstance(data, dict) else data
    by_cluster: dict = defaultdict(list)
    for s in signals:
        by_cluster[s["cluster"]].append(s)
    return dict(by_cluster)


def _run_js_synthesis(js_source: str, cluster_key: str, signals: list) -> dict:
    """Запускает реальный JS-фоллбэк через node и возвращает результат."""
    payload = json.dumps({"key": cluster_key, "signals": signals}, ensure_ascii=False)
    script = (
        js_source
        + "\nconst input = " + payload + ";"
        + "\nconst result = synthesizeNarrativeAdvanced(input.key, {signals: input.signals});"
        + "\nprocess.stdout.write(JSON.stringify(result));"
    )
    result = subprocess.run(
        ["node", "-e", script],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, f"Node execution failed:\n{result.stderr}"
    return json.loads(result.stdout)


def _run_python_synthesis(cluster_key: str, signals: list):
    """Запускает реальный scripts/synthesizer.py::synthesize_cluster()."""
    from scripts.synthesizer import synthesize_cluster
    return synthesize_cluster(cluster_key, signals)


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestJSPythonEquivalence:
    """
    C1 ARR v3 / Condition 5 ARR v2+v3: JS-фоллбэк и Python-синтезатор
    должны соглашаться по phase и anchor_signal_id на одинаковом входе.
    """

    def test_phase_and_anchor_match_on_all_golden_clusters(
        self, js_synthesize_source, golden_clusters
    ):
        from domain.exceptions import EmptyClusterError

        mismatches = []
        skipped_known_gap = []
        checked = 0

        for cluster_key, signals in sorted(golden_clusters.items()):
            if cluster_key in KNOWN_GAP_CLUSTERS:
                skipped_known_gap.append(cluster_key)
                continue

            try:
                py_result = _run_python_synthesis(cluster_key, signals)
            except EmptyClusterError:
                # Кластер пуст после Python-препроцессинга (окно/архив) —
                # не входит в контракт эквивалентности, не тестируем здесь.
                skipped_known_gap.append(cluster_key)
                continue

            js_result = _run_js_synthesis(js_synthesize_source, cluster_key, signals)
            checked += 1

            if js_result.get("phase") != py_result.phase:
                mismatches.append(
                    f"{cluster_key}: phase mismatch — "
                    f"python={py_result.phase!r} js={js_result.get('phase')!r}"
                )
            if js_result.get("anchor_signal_id") != py_result.anchor_signal_id:
                mismatches.append(
                    f"{cluster_key}: anchor_signal_id mismatch — "
                    f"python={py_result.anchor_signal_id!r} "
                    f"js={js_result.get('anchor_signal_id')!r}"
                )

        assert checked >= 5, (
            f"Only {checked} clusters were actually compared — "
            f"Golden Dataset too small or too many skipped: {skipped_known_gap}"
        )
        assert not mismatches, (
            "JS/Python synthesis disagree on phase or anchor for golden clusters "
            "(see ADR-010 for the equivalence contract):\n" + "\n".join(mismatches)
        )

    def test_known_gap_js_lacks_window_filtering(
        self, js_synthesize_source, golden_clusters
    ):
        """
        Документирует (не скрывает) известный gap: test_stale содержит только
        сигналы старше WINDOW_DAYS_DEFAULT. Python корректно отбрасывает их
        (EmptyClusterError). JS фоллбэк синтезирует их как актуальные —
        неверно, если бы JS получал сырые сигналы напрямую. На практике риск
        ниже заявленного: renderNarrativeItem в index.html не вызывает
        synthesizeNarrativeAdvanced для кластеров, отфильтрованных дашбордом
        ещё на этапе chartData/filteredSignals — однако synthesizeNarrativeAdvanced
        сама по себе не несёт этой гарантии, и это либо должно быть
        зафиксировано как инвариант вызывающей стороны, либо перенесено внутрь
        функции. Если этот тест начнёт падать (т.е. JS вдруг начнёт сам
        фильтровать устаревшие сигналы) — gap закрылся, обнови ADR-010 и
        удали этот тест.
        """
        signals = golden_clusters.get("test_stale")
        if not signals:
            pytest.skip("test_stale cluster not in golden dataset")

        from domain.exceptions import EmptyClusterError
        with pytest.raises(EmptyClusterError):
            _run_python_synthesis("test_stale", signals)

        # JS, в отличие от Python, не выбрасывает исключение и не возвращает
        # пустой результат — он синтезирует устаревшие сигналы как валидные.
        js_result = _run_js_synthesis(js_synthesize_source, "test_stale", signals)
        assert js_result.get("phase"), (
            "Если JS начал возвращать пустой/falsy phase для устаревшего "
            "кластера — возможно, window filtering уже добавлен в JS. "
            "Обнови ADR-010 и замени этот тест на позитивную проверку."
        )
