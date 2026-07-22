"""
tests/unit/test_cross_cluster_entities_consistency.py
Bitcoin Intel — regression: scripts/synthesizer.py main() и
scripts/rebuild_synthesis.py rebuild() должны писать ОДИНАКОВЫЙ
_cross_cluster_entities (ADR-017) при одинаковых входных данных.

КОНТЕКСТ
--------
Ранее в этой же сессии обнаружилось, что rebuild_synthesis.py — второй
потребитель synthesis_cache.json — молча не пробрасывал Фазу B, и
отдельно не подключал contradicts_map/signal_entity_map вовсе. ADR-017
прямо требует синхронизировать оба потребителя с самого начала (см.
"Оба существующих потребителя... синхронизированы с самого начала").
Этот тест — механическая защита данного требования, не только текстовая.
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.unit.test_synthesizer import _minimal_signal


def _build_signals():
    signals = []
    # entity_x: весомо в cluster_a (3), слабо в cluster_b (1) — должен пройти
    for i in range(3):
        s = _minimal_signal(f"SIG-X-A-{i}", "2026-07-01", "complication")
        s["cluster"] = "cluster_a"
        signals.append(s)
    s = _minimal_signal("SIG-X-B-0", "2026-07-02", "complication")
    s["cluster"] = "cluster_b"
    signals.append(s)
    # entity_y: только в cluster_a — не должен пройти
    s = _minimal_signal("SIG-Y-A-0", "2026-07-03", "trigger")
    s["cluster"] = "cluster_a"
    signals.append(s)
    return signals


def _build_entity_map():
    return {
        "SIG-X-A-0": "entity_x", "SIG-X-A-1": "entity_x", "SIG-X-A-2": "entity_x",
        "SIG-X-B-0": "entity_x",
        "SIG-Y-A-0": "entity_y",
    }


def test_main_and_rebuild_produce_identical_cross_cluster_entities(monkeypatch, tmp_path):
    import scripts.synthesizer as synth
    import scripts.rebuild_synthesis as rb

    signals = _build_signals()
    emap = _build_entity_map()

    signals_path  = tmp_path / "signals.json"
    entities_path = tmp_path / "ENTITIES.json"
    cache_a       = tmp_path / "cache_main.json"
    cache_b       = tmp_path / "cache_rebuild.json"
    store_path    = tmp_path / "synthesis_store"

    signals_path.write_text(json.dumps({"signals": signals}), encoding="utf-8")
    entities_path.write_text(json.dumps({
        "entities": [
            {"id": "entity_x", "signal_refs": ["SIG-X-A-0", "SIG-X-A-1", "SIG-X-A-2", "SIG-X-B-0"]},
            {"id": "entity_y", "signal_refs": ["SIG-Y-A-0"]},
        ]
    }), encoding="utf-8")

    monkeypatch.setattr(synth, "ENTITIES_PATH", str(entities_path))
    monkeypatch.setattr(synth, "SIGNALS_PATH", str(signals_path))
    monkeypatch.setattr(synth, "SYNTHESIS_CACHE_PATH", str(cache_a))
    monkeypatch.setattr(synth, "SYNTHESIS_STORE_PATH", str(store_path))

    monkeypatch.setattr(rb, "SIGNALS_PATH", str(signals_path))
    monkeypatch.setattr(rb, "SYNTHESIS_CACHE_PATH", str(cache_b))
    monkeypatch.setattr(rb, "SYNTHESIS_STORE_PATH", str(store_path))

    # main() читает sys.argv/делает sys.exit — вызываем напрямую логику
    # через приватный путь main() использует; проще продублировать её
    # решающую часть напрямую через синтезатор, т.к. main() сама не
    # параметризована по путям кроме модульных констант (уже monkeypatched).
    try:
        synth.main()
    except SystemExit:
        pass

    rb.rebuild(apply=True)

    written_main    = json.loads(cache_a.read_text(encoding="utf-8"))
    written_rebuild = json.loads(cache_b.read_text(encoding="utf-8"))

    assert "_cross_cluster_entities" in written_main
    assert "_cross_cluster_entities" in written_rebuild
    assert written_main["_cross_cluster_entities"] == written_rebuild["_cross_cluster_entities"]
    assert written_main["_cross_cluster_entities"] == {"entity_x": ["cluster_a", "cluster_b"]}
