"""
tests/unit/test_cluster_label_tables_sync.py
Bitcoin Intel — тест-страж на синхронность трёх JS-таблиц подписей кластеров
(DIGEST_CLUSTER_LABELS, CLUSTER_LABELS, CLUSTER_LABELS_AI в js/app-main.js)
с ontology.json (источник истины по кластерам, см. CLAUDE.md → «Кластеры»).

КОНТЕКСТ (найдено при стратегическом аудите системы на масштабирование,
2026-07-31): создание нового кластера требует точечных правок в пяти местах
(CLAUDE.md сам документирует это как «пять мест одновременно», история
находок 2→4 в 2026-07-07, 4→5 в 2026-07-27). У остальных single-source-
of-truth механизмов проекта есть тест-стражи в обе стороны — SIGNALS.md
(байт-в-байт, test_signals_md_sync.py), facts.json (test_facts.py),
site_map.json (test_site_map_sync.py), CLAUDE.md-таблица кластеров
(test_claude_md_schema_sync.py::test_claude_md_cluster_table_matches_ontology_json).
Только у трёх JS-таблиц подписей не было ни одного — единственная защита
была пункт в ручном чеклисте CLAUDE.md, и класс дрейфа уже материализовался
дважды на практике. Этот файл закрывает пробел тем же паттерном, что уже
работает для остальных: JS — не источник истины, ontology.json — источник,
таблицы сверяются с ним в обе стороны (missing / stale).

ПОЧЕМУ ЧЕРЕЗ NODE, НЕ REGEX-ПАРСИНГ ЗНАЧЕНИЙ: значения — строки с emoji и
двоеточиями, ключи выравниваются пробелами по-разному в каждой таблице.
Тот же приём, что test_js_python_equivalence.py уже использует для функций
(баланс фигурных скобок для извлечения литерала + реальный Node для
интерпретации JS-синтаксиса) — надёжнее самодельного regex для объектных
литералов произвольной внутренней структуры.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT     = Path(__file__).parent.parent.parent
APP_MAIN_JS   = REPO_ROOT / "js" / "app-main.js"
ONTOLOGY_PATH = REPO_ROOT / "ontology.json"
SIGNALS_PATH  = REPO_ROOT / "signals.json"

NODE_AVAILABLE = shutil.which("node") is not None

TABLE_NAMES = ["DIGEST_CLUSTER_LABELS", "CLUSTER_LABELS", "CLUSTER_LABELS_AI"]


def _extract_top_level_const_object(js_source: str, name: str) -> str:
    """
    Извлекает `const NAME = { ... };` по балансу фигурных скобок. Ищет
    'const NAME<пробелы>=' через regex (не .find(name)) — иначе поиск
    "CLUSTER_LABELS" ложно матчится на префикс "CLUSTER_LABELS_AI", если
    она встречается раньше в файле (реальная ловушка при трёх похоже
    названных константах в одном файле).
    """
    match = re.search(rf"const {re.escape(name)}\s*=", js_source)
    assert match, (
        f"'const {name} = ...' не найдено в js/app-main.js — "
        f"переименовали или удалили?"
    )
    start = match.start()
    brace_open = js_source.find("{", match.end())
    assert brace_open != -1, f"Не найдена открывающая скобка для '{name}'"
    depth = 0
    i = brace_open
    while i < len(js_source):
        if js_source[i] == "{":
            depth += 1
        elif js_source[i] == "}":
            depth -= 1
            if depth == 0:
                return js_source[start:i + 1] + ";"
        i += 1
    raise AssertionError(f"Несбалансированные скобки при извлечении '{name}'")


def _load_js_object(js_source: str, name: str) -> dict:
    literal = _extract_top_level_const_object(js_source, name)
    script = literal + f"\nprocess.stdout.write(JSON.stringify({name}));"
    result = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"Node execution failed extracting '{name}':\n{result.stderr}"
    )
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def js_source() -> str:
    return APP_MAIN_JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def label_tables(js_source) -> dict:
    """{table_name: {cluster_key: label}} для всех трёх таблиц."""
    return {name: _load_js_object(js_source, name) for name in TABLE_NAMES}


@pytest.fixture(scope="module")
def ontology_clusters() -> set:
    ontology = json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))
    return set(ontology["clusters"].keys())


@pytest.fixture(scope="module")
def signals_clusters() -> set:
    data = json.loads(SIGNALS_PATH.read_text(encoding="utf-8"))
    signals = data.get("signals", data) if isinstance(data, dict) else data
    return {s["cluster"] for s in signals if s.get("cluster")}


def _assert_matches_ontology(table_name: str, table_keys: set, ontology_keys: set) -> None:
    missing = ontology_keys - table_keys
    assert not missing, (
        f"Кластеры есть в ontology.json, но не в {table_name} "
        f"(js/app-main.js) — на сайте покажется сырой SNAKE_CASE вместо "
        f"человеческой подписи: {sorted(missing)}"
    )
    stale = table_keys - ontology_keys
    assert not stale, (
        f"{table_name} ссылается на кластеры, которых нет в ontology.json "
        f"— удалён кластер без чистки таблицы, либо опечатка: {sorted(stale)}"
    )


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestClusterLabelTablesSyncWithOntology:
    """
    Источник истины — ontology.json (см. CLAUDE.md → «Кластеры»). Каждая
    из трёх JS-таблиц проверяется независимо и с явным сообщением о том,
    В КАКОЙ ИМЕННО таблице обнаружено расхождение — три отдельных теста,
    не один общий, чтобы падение сразу указывало место правки, а не только
    факт «где-то разошлось».
    """

    def test_digest_cluster_labels_matches_ontology(self, label_tables, ontology_clusters):
        _assert_matches_ontology(
            "DIGEST_CLUSTER_LABELS", set(label_tables["DIGEST_CLUSTER_LABELS"]), ontology_clusters
        )

    def test_cluster_labels_matches_ontology(self, label_tables, ontology_clusters):
        _assert_matches_ontology(
            "CLUSTER_LABELS", set(label_tables["CLUSTER_LABELS"]), ontology_clusters
        )

    def test_cluster_labels_ai_matches_ontology(self, label_tables, ontology_clusters):
        _assert_matches_ontology(
            "CLUSTER_LABELS_AI", set(label_tables["CLUSTER_LABELS_AI"]), ontology_clusters
        )


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestSignalsUseOnlyKnownClusters:
    """
    Более глубокая проверка того же класса риска: сигнал может ссылаться на
    cluster, которого нет ни в ontology.json, ни в одной из JS-таблиц —
    сама первопричина того, почему на сайте показывается SNAKE_CASE.
    """

    def test_all_signal_clusters_exist_in_ontology(self, signals_clusters, ontology_clusters):
        unknown = signals_clusters - ontology_clusters
        assert not unknown, (
            f"signals.json содержит сигналы с cluster, которого нет в "
            f"ontology.json — Шаг 4 CLAUDE.md («Кластеризация») пропущен "
            f"или опечатка в значении cluster: {sorted(unknown)}"
        )

    def test_all_signal_clusters_have_labels_in_every_js_table(self, signals_clusters, label_tables):
        for table_name in TABLE_NAMES:
            missing = signals_clusters - set(label_tables[table_name])
            assert not missing, (
                f"signals.json использует кластеры, для которых нет подписи "
                f"в {table_name}: {sorted(missing)}"
            )


class TestGuardCatchesInjectedDrift:
    """
    Страж должен быть проверен на подставленном разрыве, не только проходить
    молча на чистом репозитории (тот же принцип, что уже применён для
    scripts/check_stale_facts.py::test_check_stale_facts_catches_injected_stale_copy).
    Не зависит от Node — тестирует саму функцию сравнения на синтетических
    множествах, не парсинг реального JS.
    """

    def test_detects_missing_cluster_in_one_table(self):
        ontology_keys = {"a", "b", "c"}
        table_missing_c = {"a", "b"}
        with pytest.raises(AssertionError) as excinfo:
            _assert_matches_ontology("MOCK_TABLE", table_missing_c, ontology_keys)
        assert "MOCK_TABLE" in str(excinfo.value)
        assert "'c'" in str(excinfo.value)

    def test_detects_stale_cluster_removed_from_ontology(self):
        ontology_keys = {"a", "b"}
        table_with_stale_c = {"a", "b", "c"}
        with pytest.raises(AssertionError) as excinfo:
            _assert_matches_ontology("MOCK_TABLE", table_with_stale_c, ontology_keys)
        assert "MOCK_TABLE ссылается" in str(excinfo.value)
        assert "'c'" in str(excinfo.value)

    def test_passes_when_keys_match_exactly(self):
        keys = {"a", "b", "c"}
        _assert_matches_ontology("MOCK_TABLE", set(keys), set(keys))  # не должно бросить


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
def test_end_to_end_guard_catches_real_missing_key_injected_into_js_source(js_source):
    """
    Полный путь, не только сравнение множеств: берёт реальный js/app-main.js,
    вырезает одну строку из настоящей CLUSTER_LABELS_AI (симулируя ровно тот
    инцидент 2026-07-27, когда третья таблица не была синхронизирована при
    создании quantum_security), прогоняет через реальный Node-экстрактор и
    убеждается, что тест обнаруживает пропажу — не проходит молча.
    """
    broken_source = js_source.replace(
        "quantum_security:            '🔐 Q-Day: квантовая угроза',\n", ""
    )
    assert broken_source != js_source, (
        "Строка для инъекции не найдена — CLUSTER_LABELS_AI переформатирован, "
        "обнови сниппет в этом тесте"
    )
    broken_tables = {name: _load_js_object(broken_source, name) for name in TABLE_NAMES}
    ontology = json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))
    ontology_keys = set(ontology["clusters"].keys())

    with pytest.raises(AssertionError):
        _assert_matches_ontology(
            "CLUSTER_LABELS_AI", set(broken_tables["CLUSTER_LABELS_AI"]), ontology_keys
        )
