"""
tests/unit/test_detect_pipeline_events.py
Bitcoin Intel — тесты общего детектора порогов в live-пайплайнах
(scripts/detect_pipeline_events.py, см. docs/ADR-019).

Три группы:
1. Логика условий — в первую очередь РАЗНИЦА между «пересекло» и «уже было
   верно на первом наблюдении». Это не косметика: детектор без состояния
   сигналил бы об одном и том же пороге при каждом прогоне (каждые 3 часа
   для BIP-110), и лог событий превратился бы в шум.
2. Валидность самого конфига правил — пути должны разрешаться на РЕАЛЬНЫХ
   файлах пайплайнов, иначе правило молча не сработает никогда.
3. Устойчивость: битый/отсутствующий файл пайплайна не должен ронять прогон.
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from detect_pipeline_events import (  # noqa: E402
    VALID_CONDITIONS,
    evaluate,
    resolve_path,
    run,
)

RULES_PATH = REPO_ROOT / "data" / "pipeline_watch_rules.json"


# ─────────────────────────── 1. Логика условий ───────────────────────────

def test_crosses_above_fires_only_on_transition():
    """Порог пересечён — событие; остался выше — НЕ событие повторно."""
    _, is_event, kind = evaluate("crosses_above", 60.0, 55.0, previous=50.0)
    assert is_event and kind == "crossed"

    _, is_event, kind = evaluate("crosses_above", 61.0, 55.0, previous=60.0)
    assert not is_event, "уже был выше порога — повторного события быть не должно"


def test_crosses_above_without_previous_is_baseline_not_crossing():
    """
    Ключевое различие: на первом наблюдении мы не видели перехода, только
    застали результат. Реальный случай — BIP-110 прошёл deadline_block ДО
    появления детектора.
    """
    _, is_event, kind = evaluate("crosses_above", 964581, 961632, previous=None)
    assert is_event, "факт всё равно стоит зафиксировать"
    assert kind == "true_at_baseline", "но НЕ как пересечение — перехода мы не наблюдали"


def test_crosses_above_baseline_false_produces_no_event():
    _, is_event, kind = evaluate("crosses_above", 0.89, 55.0, previous=None)
    assert not is_event and kind is None


def test_crosses_below_symmetric():
    _, is_event, kind = evaluate("crosses_below", -70.0, -60.0, previous=-10.0)
    assert is_event and kind == "crossed"
    _, is_event, _ = evaluate("crosses_below", -71.0, -60.0, previous=-70.0)
    assert not is_event


def test_delta_conditions_need_previous_value():
    """
    У дельта-условий нет понятия «выполнено сейчас» без предыдущего значения —
    на первом наблюдении событий быть не может по построению.
    """
    for cond in ("changes_by_at_least", "pct_change_exceeds"):
        _, is_event, kind = evaluate(cond, 100.0, 10.0, previous=None)
        assert not is_event and kind is None, f"{cond} не должно срабатывать без базовой линии"


def test_changes_by_at_least_is_absolute_in_both_directions():
    _, up, _ = evaluate("changes_by_at_least", 260000.0, 10000.0, previous=248000.0)
    _, down, _ = evaluate("changes_by_at_least", 236000.0, 10000.0, previous=248000.0)
    _, small, _ = evaluate("changes_by_at_least", 249000.0, 10000.0, previous=248000.0)
    assert up and down and not small


def test_pct_change_handles_zero_previous_without_dividing_by_zero():
    _, is_event, _ = evaluate("pct_change_exceeds", 5.0, 50.0, previous=0.0)
    assert not is_event, "деление на ноль должно быть обработано, а не брошено"


def test_unknown_condition_raises():
    with pytest.raises(ValueError):
        evaluate("nonsense", 1.0, 1.0, previous=None)


# ─────────────────────────── resolve_path ───────────────────────────

@pytest.mark.parametrize("path,expected", [
    ("a.b", 5),
    ("items.1.v", 20),
    ("missing", None),
    ("a.missing", None),
    ("items.9.v", None),
    ("a", None),          # dict, не число
    ("flag", None),       # bool не считается числом
    ("text", None),       # строка не считается числом
])
def test_resolve_path(path, expected):
    data = {"a": {"b": 5}, "items": [{"v": 10}, {"v": 20}], "flag": True, "text": "12"}
    assert resolve_path(data, path) == expected


# ─────────────────── 2. Валидность реального конфига ───────────────────

def _rules():
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))["rules"]


def test_rule_ids_unique():
    ids = [r["id"] for r in _rules()]
    assert len(ids) == len(set(ids))


def test_every_rule_has_required_fields_and_valid_condition():
    for r in _rules():
        assert r["condition"] in VALID_CONDITIONS, f"{r['id']}: неизвестное condition"
        assert ("threshold" in r) ^ ("threshold_path" in r), \
            f"{r['id']}: нужен ровно один из threshold / threshold_path"
        for f in ("description", "why_it_matters", "source_file", "value_path"):
            assert r.get(f), f"{r['id']}: пустое обязательное поле {f}"


def test_every_rule_path_resolves_against_real_pipeline_data():
    """
    Главный страж этого конфига: правило с неразрешимым путём молча не
    сработает НИКОГДА. Проверяем на живых файлах пайплайнов в репозитории.
    """
    for r in _rules():
        src = REPO_ROOT / r["source_file"]
        assert src.exists(), f"{r['id']}: нет файла {r['source_file']}"
        data = json.loads(src.read_text(encoding="utf-8"))
        assert resolve_path(data, r["value_path"]) is not None, \
            f"{r['id']}: value_path '{r['value_path']}' не разрешается в число"
        if "threshold_path" in r:
            assert resolve_path(data, r["threshold_path"]) is not None, \
                f"{r['id']}: threshold_path '{r['threshold_path']}' не разрешается в число"


def test_suggested_clusters_exist_in_ontology():
    """suggested_cluster — подсказка, но подсказывать несуществующий кластер нельзя."""
    ontology = json.loads((REPO_ROOT / "ontology.json").read_text(encoding="utf-8"))
    known = set(ontology["clusters"].keys()) if isinstance(ontology.get("clusters"), dict) \
        else {c["id"] if isinstance(c, dict) else c for c in ontology.get("clusters", [])}
    for r in _rules():
        sc = r.get("suggested_cluster")
        if sc:
            assert sc in known, f"{r['id']}: suggested_cluster '{sc}' нет в ontology.json"


# ─────────────────── 3. Устойчивость прогона ───────────────────

def test_run_survives_missing_and_malformed_sources(tmp_path):
    """Битый или отсутствующий файл пайплайна → правило пропущено, прогон жив."""
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "broken.json").write_text("{ not json", encoding="utf-8")
    (tmp_path / "data" / "good.json").write_text(json.dumps({"current": {"v": 10}}), encoding="utf-8")

    rules = {"rules": [
        {"id": "missing_file", "source_file": "data/nope.json", "value_path": "a",
         "condition": "crosses_above", "threshold": 1, "description": "d", "why_it_matters": "w"},
        {"id": "broken_file", "source_file": "data/broken.json", "value_path": "a",
         "condition": "crosses_above", "threshold": 1, "description": "d", "why_it_matters": "w"},
        {"id": "bad_path", "source_file": "data/good.json", "value_path": "current.nope",
         "condition": "crosses_above", "threshold": 1, "description": "d", "why_it_matters": "w"},
        {"id": "works", "source_file": "data/good.json", "value_path": "current.v",
         "condition": "crosses_above", "threshold": 1, "description": "d", "why_it_matters": "w"},
    ]}
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps(rules), encoding="utf-8")
    out = tmp_path / "events.json"

    n = run(rules_file, out, tmp_path)
    assert n == 1, "должно сработать только исправное правило"
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert len(doc["rules_skipped"]) == 3
    assert doc["events"][0]["rule_id"] == "works"


def test_state_persists_so_second_run_does_not_refire(tmp_path):
    """
    Регрессия на главную идею состояния: тот же порог при повторном прогоне
    не должен давать второе событие (иначе лог засорится за сутки).
    """
    (tmp_path / "data").mkdir(exist_ok=True)
    src = tmp_path / "data" / "p.json"
    src.write_text(json.dumps({"current": {"v": 100}}), encoding="utf-8")
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps({"rules": [
        {"id": "r", "source_file": "data/p.json", "value_path": "current.v",
         "condition": "crosses_above", "threshold": 50, "description": "d", "why_it_matters": "w"}
    ]}), encoding="utf-8")
    out = tmp_path / "events.json"

    assert run(rules_file, out, tmp_path) == 1, "первый прогон: true_at_baseline"
    assert run(rules_file, out, tmp_path) == 0, "второй прогон: значение не менялось — событий нет"

    doc = json.loads(out.read_text(encoding="utf-8"))
    assert len(doc["events"]) == 1
    assert doc["events"][0]["kind"] == "true_at_baseline"


def test_real_run_is_reproducible_and_flags_bip110_deadline(tmp_path):
    """
    Прогон на реальных данных репозитория: детектор должен видеть, что
    высота цепи уже превысила deadline_block BIP-110 (актуальное состояние
    на момент написания теста — именно тот разрыв, ради которого написан
    детектор). Проверяем через временный out, не трогая рабочий файл.
    """
    out = tmp_path / "events.json"
    run(RULES_PATH, out, REPO_ROOT)
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["rules_skipped"] == [], "на реальных данных ни одно правило не должно пропускаться"
    fired = {e["rule_id"] for e in doc["events"]}
    assert "bip110_voluntary_deadline_passed" in fired
