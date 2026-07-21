"""
tests/unit/test_synthesizer.py
Тесты синтезатора: детерминизм, scoring, confidence, bridge selection.
"""
import os
import sys
import subprocess
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import calculate_max_possible_score, calculate_confidence


# ─── Детерминизм ─────────────────────────────────────────────────────────────

def test_bridge_selection_deterministic():
    """
    select_bridge() детерминировано: seed % len(options) не зависит от PYTHONHASHSEED.
    Тест проверяет алгоритм напрямую — subprocess не нужен.
    """
    # seed % len(options) всегда даёт одинаковый результат независимо от PYTHONHASHSEED
    # Потому что % — арифметическая операция, не хэш
    from scripts.synthesizer import select_bridge
    results = {select_bridge("active", 42) for _ in range(3)}
    assert len(results) == 1, f"Non-deterministic: {results}"
    # Убедиться что результат — строка из BRIDGES["active"]
    result = select_bridge("active", 42)
    assert isinstance(result, str) and len(result) > 0


def test_bridge_selection_uses_modulo_not_hash():
    """Формула seed % len(options) — детерминирована по определению."""
    options = ["при этом", "однако", "в то время как", "тогда как"]
    seed = 42
    result_index = seed % len(options)
    assert 0 <= result_index < len(options)
    assert options[result_index] == options[42 % 4]


# ─── MAX_POSSIBLE_SCORE ───────────────────────────────────────────────────────

def test_max_possible_score_single():
    assert calculate_max_possible_score(1) == 11


def test_max_possible_score_five():
    assert calculate_max_possible_score(5) == 55


def test_max_possible_score_zero_safe():
    """Защита от деления на ноль — не должен возвращать 0."""
    result = calculate_max_possible_score(0)
    assert result >= 1


def test_max_possible_score_linear():
    """Линейная зависимость от количества сигналов."""
    assert calculate_max_possible_score(10) == calculate_max_possible_score(5) * 2


# ─── Confidence ───────────────────────────────────────────────────────────────

def test_confidence_always_in_range():
    """Confidence всегда в диапазоне [0.1, 1.0]."""
    cases = [
        (55, 5, True, False, True),    # лучший случай
        (0,  1, False, True, False),   # худший случай
        (11, 1, True, False, True),    # один сигнал
        (6,  3, False, False, False),  # без contradicts
    ]
    for args in cases:
        result = calculate_confidence(*args)
        assert 0.1 <= result <= 1.0, f"Out of range for {args}: {result}"


def test_confidence_higher_with_contradicts():
    """Кластер с contradicts получает выше confidence."""
    with_c = calculate_confidence(20, 3, has_contradicts=True,  all_stale=False, has_tension=True)
    without = calculate_confidence(20, 3, has_contradicts=False, all_stale=False, has_tension=True)
    assert with_c > without


def test_confidence_lower_when_stale():
    """Устаревшие сигналы снижают confidence."""
    fresh = calculate_confidence(20, 3, has_contradicts=True, all_stale=False, has_tension=True)
    stale = calculate_confidence(20, 3, has_contradicts=True, all_stale=True,  has_tension=True)
    assert fresh > stale


def test_confidence_minimum_floor():
    """Confidence не опускается ниже 0.1 даже при худших данных."""
    result = calculate_confidence(0, 1, has_contradicts=False, all_stale=True, has_tension=False)
    assert result >= 0.1


def test_confidence_deterministic():
    """Одинаковые аргументы → одинаковый результат (детерминизм)."""
    args = (20, 3, True, False, True)
    results = {calculate_confidence(*args) for _ in range(5)}
    assert len(results) == 1


# ─── ALGORITHM_VERSION (IRP v1 Wave 3 / REM-M07) ───────────────────────────────

def test_algorithm_version_is_semver():
    """ALGORITHM_VERSION — строка формата MAJOR.MINOR.PATCH (ADDENDUM §25.3)."""
    import re
    from scripts.synthesizer import ALGORITHM_VERSION
    assert re.match(r"^\d+\.\d+\.\d+$", ALGORITHM_VERSION), (
        f"ALGORITHM_VERSION='{ALGORITHM_VERSION}' не соответствует semver MAJOR.MINOR.PATCH"
    )


def test_synthesis_result_default_algorithm_version_matches_constant():
    """SynthesisResult.algorithm_version по умолчанию равен модульной константе."""
    from scripts.synthesizer import ALGORITHM_VERSION, SynthesisResult, SignalScore
    result = SynthesisResult(
        cluster="test", tension="X vs Y", narrative="n", takeaway="t",
        strength="weak", confidence=0.5, phase="active",
        score=SignalScore(), anchor_signal_id="X-1", signal_count=1,
    )
    assert result.algorithm_version == ALGORITHM_VERSION


# ─── _get_contradicts / relationships.json (bugfix 2026-07-04, ALGORITHM_VERSION 2.1.1) ──
#
# КОНТЕКСТ: до этой правки _get_contradicts() при LEGACY_LINKS_ENABLED=False
# безусловно возвращала [] — relationships.json существовал (мигрирован IRP v1
# Wave 1 / REM-B2, 2026-07-01), но никогда не читался. Contradiction bonus был
# равен 0 для всех сигналов с даты миграции. Обнаружено вручную при инженерной
# сверке (не автоматикой) — эти тесты закрывают тот пробел покрытия.

def test_load_contradicts_map_filters_by_type_and_status(tmp_path, monkeypatch):
    """_load_contradicts_map() берёт только type=contradicts, исключая retracted."""
    import json as _json
    from scripts import synthesizer as _syn

    rel_path = tmp_path / "relationships.json"
    rel_path.write_text(_json.dumps([
        {"from_id": "A-1", "to_id": "B-1", "type": "contradicts", "status": "active"},
        {"from_id": "A-1", "to_id": "C-1", "type": "confirms",    "status": "active"},
        {"from_id": "A-2", "to_id": "D-1", "type": "contradicts", "status": "retracted"},
    ]), encoding="utf-8")

    monkeypatch.setattr(_syn, "RELATIONSHIPS_PATH", str(rel_path))
    result = _syn._load_contradicts_map()

    assert result == {"A-1": {"B-1"}}, (
        "Должен остаться только type=contradicts + status!=retracted; "
        f"получено {result}"
    )


def test_get_contradicts_reads_relationships_when_legacy_disabled(monkeypatch):
    """LEGACY_LINKS_ENABLED=False → читает contradicts_map, не links.* сигнала."""
    from scripts import synthesizer as _syn

    monkeypatch.setattr(_syn, "LEGACY_LINKS_ENABLED", False)
    signal = {"id": "STR-2026-0701-002", "links": {"contradicts": ["IGNORED"]}}
    contradicts_map = {"STR-2026-0701-002": {"STR-2026-0623-006"}}

    result = _syn._get_contradicts(signal, contradicts_map)

    assert result == ["STR-2026-0623-006"], (
        "При LEGACY_LINKS_ENABLED=False должен игнорировать links.* сигнала "
        f"и брать из contradicts_map; получено {result}"
    )


def test_get_contradicts_falls_back_to_links_when_legacy_enabled(monkeypatch):
    """LEGACY_LINKS_ENABLED=True → читает links.contradicts сигнала, игнорируя map."""
    from scripts import synthesizer as _syn

    monkeypatch.setattr(_syn, "LEGACY_LINKS_ENABLED", True)
    signal = {"id": "X-1", "links": {"contradicts": ["Y-1"]}}

    result = _syn._get_contradicts(signal, contradicts_map={"X-1": {"Z-1"}})

    assert result == ["Y-1"], (
        "При LEGACY_LINKS_ENABLED=True должен игнорировать contradicts_map "
        f"и брать из links.*; получено {result}"
    )


def test_get_contradicts_empty_map_returns_empty_list(monkeypatch):
    """Сигнал без записи в contradicts_map → пустой список, не ошибка."""
    from scripts import synthesizer as _syn

    monkeypatch.setattr(_syn, "LEGACY_LINKS_ENABLED", False)
    signal = {"id": "NO-RELATIONSHIPS-1"}

    assert _syn._get_contradicts(signal, contradicts_map={}) == []


def test_get_contradicts_result_is_sorted_deterministic(monkeypatch):
    """Результат — sorted list, не произвольный порядок set() (детерминизм)."""
    from scripts import synthesizer as _syn

    monkeypatch.setattr(_syn, "LEGACY_LINKS_ENABLED", False)
    signal = {"id": "A-1"}
    contradicts_map = {"A-1": {"Z-1", "B-1", "M-1"}}

    result = _syn._get_contradicts(signal, contradicts_map)

    assert result == sorted(result), "Должен быть отсортирован для детерминизма"
    assert result == ["B-1", "M-1", "Z-1"]


# ═══════════════════════════════════════════════════════════════════════
# Фаза A плана entity-aware усилений (2026-07-20) — эксперимент на кластере
# btc_treasury_competition (21 сигнал, см. обсуждение в чате).
#
# Ключ дедупликации (date, actor, cluster, dir) слишком груб для кластера
# с несколькими компаниями одного actor-типа ('corporate') — реально ронял
# 3 пары РАЗНЫХ сигналов о РАЗНЫХ компаниях как "дубликаты" только из-за
# совпадения даты+actor+dir. Тесты ниже используют настоящие ID из
# signals.json/ENTITIES.json (не синтетику) — прямая проверка, что находка
# действительно устранена, а не только теоретически.
# ═══════════════════════════════════════════════════════════════════════

def test_deduplicate_signals_entity_map_prevents_real_false_positives(tmp_path, monkeypatch):
    """
    Три пары сигналов из btc_treasury_competition, ранее ложно
    схлопывавшиеся как "дубликаты" (см. rationale synthesis_cache.json на
    момент находки: ignored_duplicates содержал все три вторых элемента пар
    ниже). Настоящие ID сигналов, ENTITIES.json собран здесь же во временной
    директории (isolated_environment из conftest.py делает CWD временным для
    КАЖДОГО теста и кладёт пустой ENTITIES.json — читать реальный файл
    репозитория из теста нельзя, см. докстринг conftest.py). С
    signal_entity_map, построенной из этого файла, все 6 сигналов выживают.
    """
    import json as json_module
    from scripts.synthesizer import deduplicate_signals, _load_signal_entity_map

    entities = {"entities": [
        {"id": "strive",    "signal_refs": ["STR-2026-0623-002", "STR-2026-0706-003"]},
        {"id": "oranjebtc", "signal_refs": ["STR-2026-0706-002"]},
        {"id": "cryl",      "signal_refs": ["STR-2026-0709-002"]},
        # STR-2026-0624-001 (H100) и STR-2026-0709-001 (агрегат Q2) намеренно
        # НЕ упомянуты — воспроизводит реальный случай: не каждый сигнал
        # привязан к сущности, такие используют фолбэк на actor.
    ]}
    (tmp_path / "ENTITIES.json").write_text(
        json_module.dumps(entities, ensure_ascii=False), encoding="utf-8"
    )

    signal_entity_map = _load_signal_entity_map()

    def sig(id_, date, dir_="pos"):
        return {"id": id_, "date": date, "actor": "corporate",
                "cluster": "btc_treasury_competition", "dir": dir_, "weight": "primary"}

    signals = [
        sig("STR-2026-0623-002", "2026-06-23"),  # Strive
        sig("STR-2026-0624-001", "2026-06-23"),  # H100 (не в ENTITIES.json — фолбэк на actor)
        sig("STR-2026-0706-002", "2026-07-06"),  # OranjeBTC
        sig("STR-2026-0706-003", "2026-07-06"),  # Strive
        sig("STR-2026-0709-001", "2026-07-09"),  # агрегат Q2 (не привязан к 1 компании)
        sig("STR-2026-0709-002", "2026-07-09"),  # CRYL
    ]

    deduped, ignored = deduplicate_signals(signals, signal_entity_map)

    assert ignored == [], f"Ложные дубликаты всё ещё возникают: {ignored}"
    assert len(deduped) == 6
    assert {s["id"] for s in deduped} == {s["id"] for s in signals}


def test_deduplicate_signals_still_collapses_true_duplicate_same_entity():
    """
    Фикс не должен ослаблять защиту: два сигнала ОДНОЙ сущности, та же
    дата+dir — по-прежнему считаются дублями (это и есть настоящий дубль,
    ровно то, для чего механизм создавался изначально).
    """
    from scripts.synthesizer import deduplicate_signals

    signal_entity_map = {"SIG-A": "strive", "SIG-B": "strive"}
    signals = [
        {"id": "SIG-A", "date": "2026-07-01", "actor": "corporate",
         "cluster": "btc_treasury_competition", "dir": "pos", "weight": "media"},
        {"id": "SIG-B", "date": "2026-07-01", "actor": "corporate",
         "cluster": "btc_treasury_competition", "dir": "pos", "weight": "primary"},
    ]

    deduped, ignored = deduplicate_signals(signals, signal_entity_map)

    assert ignored == ["SIG-A"], "SIG-A (media, ниже весом) должен быть выброшен как дубль SIG-B (primary)"
    assert len(deduped) == 1
    assert deduped[0]["id"] == "SIG-B"


def test_deduplicate_signals_backward_compatible_default_none():
    """
    Вызов без signal_entity_map (или с None) — прежнее поведение 1-в-1:
    ключ по actor, как до Фазы A. Обратная совместимость для любого
    существующего вызова без нового параметра.
    """
    from scripts.synthesizer import deduplicate_signals

    signals = [
        {"id": "SIG-A", "date": "2026-07-01", "actor": "corporate",
         "cluster": "btc_treasury_competition", "dir": "pos", "weight": "media"},
        {"id": "SIG-B", "date": "2026-07-01", "actor": "corporate",
         "cluster": "btc_treasury_competition", "dir": "pos", "weight": "primary"},
    ]

    deduped_default, ignored_default = deduplicate_signals(signals)
    deduped_none,    ignored_none    = deduplicate_signals(signals, None)

    assert ignored_default == ["SIG-A"] == ignored_none
    assert len(deduped_default) == 1 == len(deduped_none)


def test_load_signal_entity_map_builds_correctly_from_entities_json(tmp_path):
    """
    _load_signal_entity_map() строит {signal_id: entity_id} корректно.
    ENTITIES.json собран здесь же во временной директории (см. докстринг
    conftest.py — реальный файл репозитория тестам недоступен по дизайну,
    isolated_environment всегда подставляет пустой placeholder).
    """
    import json as json_module
    from scripts.synthesizer import _load_signal_entity_map

    entities = {"entities": [
        {"id": "oranjebtc", "signal_refs": ["STR-2026-0706-002"]},
        {"id": "cryl",      "signal_refs": ["STR-2026-0709-002", "STR-2026-0715-002"]},
    ]}
    (tmp_path / "ENTITIES.json").write_text(
        json_module.dumps(entities, ensure_ascii=False), encoding="utf-8"
    )

    m = _load_signal_entity_map()
    assert isinstance(m, dict)
    assert len(m) == 3
    assert m.get("STR-2026-0706-002") == "oranjebtc"
    assert m.get("STR-2026-0709-002") == "cryl"
    assert m.get("STR-2026-0715-002") == "cryl"


def test_load_signal_entity_map_degrades_gracefully_on_missing_file(monkeypatch, tmp_path):
    """DEGRADE GRACEFULLY: несуществующий путь → пустой dict, не исключение."""
    import scripts.synthesizer as synthesizer_module

    monkeypatch.setattr(synthesizer_module, "ENTITIES_PATH", str(tmp_path / "nope.json"))
    m = synthesizer_module._load_signal_entity_map()
    assert m == {}
