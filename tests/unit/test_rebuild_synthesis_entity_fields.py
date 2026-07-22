"""
tests/unit/test_rebuild_synthesis_entity_fields.py
Bitcoin Intel — регрессионные тесты для scripts/rebuild_synthesis.py:
(1) entity_count/anchor_entity_share/is_minority_anchor (Фаза B синтезатора,
    2026-07) должны попадать в data/synthesis_cache.json;
(2) rebuild() должен считать их на РЕАЛЬНЫХ contradicts/entity данных, не
    вслепую (найденный и исправленный в этой же сессии отдельный баг).

КОНТЕКСТ
--------
SynthesisResult (scripts/synthesizer.py) считает три diagnostic-поля с
PR #399, synthesizer.py main() уже писал их в кеш напрямую. Но
scripts/rebuild_synthesis.py — отдельная точка входа (используется при
MAJOR-изменении алгоритма для ревью диффа) — строила свой собственный
словарь `new` и молча отбрасывала эти поля (найдено и исправлено первым).

Второй, более серьёзный баг найден при написании этого теста: rebuild()
вообще не передавала contradicts_map/signal_entity_map в
synthesize_cluster() — в отличие от main(). На реальных данных (2026-07-22)
это меняло anchor/tension в 5 из 7 живых кластеров относительно прода:
dry-run diff инструмента был неверен не только по этим трём полям, а в
принципе — победитель tension считался без реальных contradicts-связей.
Исправлено тем же коммитом, что и (1) — оба бага в одном месте кода.
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.unit.test_synthesizer import _minimal_signal  # переиспользуем фикстуру

_SIGNALS = [
    _minimal_signal("SIG-MINORITY", "2026-07-01", "complication"),
    _minimal_signal("SIG-B", "2026-07-02", "trigger"),
    _minimal_signal("SIG-C", "2026-07-03", "complication"),
    _minimal_signal("SIG-D", "2026-07-04", "complication"),
    _minimal_signal("SIG-E", "2026-07-05", "complication"),
    _minimal_signal("SIG-F", "2026-07-06", "complication"),
    _minimal_signal("SIG-G", "2026-07-07", "complication"),
]
for _s in _SIGNALS:
    _s["cluster"] = "test_multi_entity_cluster"


def test_rebuild_propagates_entity_diagnostic_fields(monkeypatch, tmp_path):
    """(1) Поля не теряются при записи через rebuild_synthesis.py.

    Без ENTITIES.json-фикстуры сигналы не находят себя ни в одной сущности —
    _load_signal_entity_map() (теперь честно читаемая, см. тест ниже) вернёт
    {} для этих id, deduplicate_signals() упадёт на фолбэк-идентичность по
    actor='corporate' → entity_count=1. Это ожидаемо: тест здесь проверяет
    ПРОБРАСЫВАНИЕ полей, не корректность значений на реальных сущностях —
    для этого следующий тест.
    """
    import scripts.rebuild_synthesis as rb

    signals_path = tmp_path / "signals.json"
    cache_path   = tmp_path / "synthesis_cache.json"
    store_path   = tmp_path / "synthesis_store"

    signals_path.write_text(json.dumps(_SIGNALS), encoding="utf-8")

    monkeypatch.setattr(rb, "SIGNALS_PATH", str(signals_path))
    monkeypatch.setattr(rb, "SYNTHESIS_CACHE_PATH", str(cache_path))
    monkeypatch.setattr(rb, "SYNTHESIS_STORE_PATH", str(store_path))

    stats = rb.rebuild(cluster_filter="test_multi_entity_cluster", apply=True)

    assert stats["errors"] == 0
    written = json.loads(cache_path.read_text(encoding="utf-8"))
    entry = written["test_multi_entity_cluster"]

    for key in ("entity_count", "anchor_entity_share", "is_minority_anchor"):
        assert key in entry, f"'{key}' пропало при записи через rebuild_synthesis.py"

    assert entry["entity_count"] == 1
    assert isinstance(entry["anchor_entity_share"], float)
    assert isinstance(entry["is_minority_anchor"], bool)


def test_rebuild_uses_real_entity_map_not_blind_fallback(monkeypatch, tmp_path):
    """(2) Регрессия на найденный баг: rebuild() должна честно считать
    entity_count через ENTITIES.json, а не всегда фолбэчиться на actor.

    Даём каждому из 7 сигналов свою сущность в фиктивном ENTITIES.json —
    если rebuild() по-прежнему не подключает signal_entity_map, все 7
    схлопнутся в 1 (общий actor='corporate') и тест провалится.
    """
    import scripts.rebuild_synthesis as rb
    import scripts.synthesizer as synth

    signals_path   = tmp_path / "signals.json"
    cache_path     = tmp_path / "synthesis_cache.json"
    store_path     = tmp_path / "synthesis_store"
    entities_path  = tmp_path / "ENTITIES.json"

    signals_path.write_text(json.dumps(_SIGNALS), encoding="utf-8")
    entities_path.write_text(json.dumps({
        "entities": [
            {"id": f"entity_{s['id'].lower()}", "signal_refs": [s["id"]]}
            for s in _SIGNALS
        ]
    }), encoding="utf-8")

    monkeypatch.setattr(rb, "SIGNALS_PATH", str(signals_path))
    monkeypatch.setattr(rb, "SYNTHESIS_CACHE_PATH", str(cache_path))
    monkeypatch.setattr(rb, "SYNTHESIS_STORE_PATH", str(store_path))
    monkeypatch.setattr(synth, "ENTITIES_PATH", str(entities_path))

    stats = rb.rebuild(cluster_filter="test_multi_entity_cluster", apply=True)

    assert stats["errors"] == 0
    entry = json.loads(cache_path.read_text(encoding="utf-8"))["test_multi_entity_cluster"]
    assert entry["entity_count"] == 7, (
        "entity_count=1 означало бы, что rebuild() снова не подключает "
        "signal_entity_map и вслепую фолбэчится на actor"
    )
