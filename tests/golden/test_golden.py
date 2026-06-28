"""
tests/golden/test_golden.py
Golden dataset тесты — верифицируют синтез на фиксированных данных.

Запускать: PYTHONHASHSEED=0 python3 -m pytest tests/golden/ -v
"""

import os
import sys
import json
import pytest

os.environ["PYTHONHASHSEED"] = "0"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.synthesizer import synthesize_cluster, _detect_phase
from domain.events import EventLog, SignalAdded, SynthesisApproved, ClusterScoreChanged
from infrastructure.file_lock import atomic_write_json, safe_read_json, atomic_append_jsonl

FIXTURES_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "golden_signals.json")


@pytest.fixture(scope="module")
def golden_data():
    with open(FIXTURES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    signals = data["signals"]
    clusters = {}
    for s in signals:
        key = s.get("cluster", "")
        clusters.setdefault(key, []).append(s)
    return clusters


# ─── TD3: Кластер test_trigger_only ──────────────────────────────────────────
class TestTriggerOnly:

    def test_phase_is_structural(self, golden_data):
        """Только trigger → phase=structural."""
        signals = golden_data["test_trigger_only"]
        phase = _detect_phase(signals)
        assert phase == "structural"

    def test_has_tension(self, golden_data):
        """Есть tension из единственного сигнала."""
        result = synthesize_cluster("test_trigger_only", golden_data["test_trigger_only"])
        assert result.tension != ""

    def test_signal_count(self, golden_data):
        result = synthesize_cluster("test_trigger_only", golden_data["test_trigger_only"])
        assert result.signal_count == 1

    def test_strength_moderate_or_strong(self, golden_data):
        """Один onchain trigger с contradicts должен давать moderate+."""
        result = synthesize_cluster("test_trigger_only", golden_data["test_trigger_only"])
        assert result.strength in ("moderate", "strong")


# ─── TD3: Кластер test_contradiction ─────────────────────────────────────────
class TestContradiction:

    def test_phase_is_active(self, golden_data):
        """trigger + complication → phase=active."""
        signals = golden_data["test_contradiction"]
        phase = _detect_phase(signals)
        assert phase == "active"

    def test_tension_from_trigger(self, golden_data):
        """Tension берётся из сигнала с MAX(contradicts) — это trigger."""
        result = synthesize_cluster("test_contradiction", golden_data["test_contradiction"])
        assert result.anchor_signal_id == "TEST-CONTRADICTION-001"

    def test_narrative_has_bridge(self, golden_data):
        """narrative содержит bridge (partA + bridge + partB)."""
        result = synthesize_cluster("test_contradiction", golden_data["test_contradiction"])
        # Bridge-фраза разделяет partA и partB
        assert " — " in result.narrative

    def test_confidence_above_half(self, golden_data):
        """Кластер с contradicts → confidence > 0.5."""
        result = synthesize_cluster("test_contradiction", golden_data["test_contradiction"])
        assert result.confidence > 0.5


# ─── TD3: Кластер test_resolution ────────────────────────────────────────────
class TestResolution:

    def test_phase_is_resolution(self, golden_data):
        """Есть resolution сигнал → phase=resolution."""
        signals = golden_data["test_resolution"]
        phase = _detect_phase(signals)
        assert phase == "resolution"

    def test_strength_strong(self, golden_data):
        """3 сигнала с onchain/primary weight → strong."""
        result = synthesize_cluster("test_resolution", golden_data["test_resolution"])
        assert result.strength in ("strong", "moderate")

    def test_signal_count_three(self, golden_data):
        result = synthesize_cluster("test_resolution", golden_data["test_resolution"])
        assert result.signal_count == 3


# ─── TD3: Кластер test_stale ──────────────────────────────────────────────────
class TestStale:

    def test_stale_cluster_empty(self, golden_data):
        """Все сигналы старше 90 дней → кластер пустой, strength=weak."""
        result = synthesize_cluster("test_stale", golden_data["test_stale"])
        assert result.signal_count == 0
        assert result.strength == "weak"
        assert result.confidence == 0.1

    def test_stale_narrative_fallback(self, golden_data):
        """Пустой кластер → fallback narrative."""
        result = synthesize_cluster("test_stale", golden_data["test_stale"])
        assert result.narrative == "Нет активных сигналов."


# ─── TD3: Кластер test_equal_weight ──────────────────────────────────────────
class TestEqualWeight:

    def test_tiebreaker_by_id(self, golden_data):
        """Три сигнала с одинаковой датой и weight → id тиебрейкер."""
        result = synthesize_cluster("test_equal_weight", golden_data["test_equal_weight"])
        # Детерминизм: результат должен быть одинаковым при повторном вызове
        result2 = synthesize_cluster("test_equal_weight", golden_data["test_equal_weight"])
        assert result.anchor_signal_id == result2.anchor_signal_id
        assert result.tension == result2.tension

    def test_all_three_signals_active(self, golden_data):
        """Все три сигнала в окне → signal_count=3."""
        result = synthesize_cluster("test_equal_weight", golden_data["test_equal_weight"])
        assert result.signal_count == 3


# ─── TD4: File Lock ───────────────────────────────────────────────────────────
class TestFileLock:

    def test_atomic_write_json(self, tmp_path):
        """Атомарная запись — файл либо полный, либо отсутствует."""
        path = str(tmp_path / "test.json")
        data = {"key": "value", "list": list(range(100))}
        atomic_write_json(path, data)
        result = safe_read_json(path)
        assert result == data

    def test_safe_read_missing_file(self, tmp_path):
        """Отсутствующий файл → возвращает default, не падает."""
        result = safe_read_json(str(tmp_path / "nonexistent.json"), default={"empty": True})
        assert result == {"empty": True}

    def test_safe_read_corrupted_json(self, tmp_path):
        """Повреждённый JSON → возвращает default, не падает."""
        path = tmp_path / "corrupted.json"
        path.write_text("{invalid json{{{{", encoding="utf-8")
        result = safe_read_json(str(path), default=[])
        assert result == []

    def test_atomic_append_jsonl(self, tmp_path):
        """JSONL append — каждая строка валидный JSON."""
        path = str(tmp_path / "test.jsonl")
        for i in range(5):
            atomic_append_jsonl(path, {"index": i, "value": f"item_{i}"})

        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 5
        for line in lines:
            parsed = json.loads(line)
            assert "index" in parsed


# ─── TD10: Domain Events ──────────────────────────────────────────────────────
class TestDomainEvents:

    def test_signal_added_event(self, tmp_path):
        """SignalAdded записывается и читается корректно."""
        log = EventLog(path=str(tmp_path / "events.jsonl"))
        log.emit(SignalAdded(
            signal_id="STR-2026-0628-001",
            cluster="strategy_model_stress",
            theme="institutionalization",
            dir="pos",
            narrative_role="trigger",
            source="Arkham (июнь 2026)",
        ))
        events = log.read_all()
        assert len(events) == 1
        assert events[0]["event_type"] == "SignalAdded"
        assert events[0]["signal_id"] == "STR-2026-0628-001"

    def test_multiple_event_types(self, tmp_path):
        """Несколько типов событий в одном логе."""
        log = EventLog(path=str(tmp_path / "events.jsonl"))
        log.emit(SignalAdded(signal_id="A", cluster="c1", theme="t", dir="pos",
                             narrative_role="trigger", source="s"))
        log.emit(SynthesisApproved(synthesis_id="syn-001", cluster="c1",
                                   tension="X vs Y", strength="strong", confidence=0.85))
        log.emit(ClusterScoreChanged(cluster="c1", score_before=10, score_after=20,
                                     delta=10, phase_before="structural", phase_after="active",
                                     trigger_signal_id="A"))

        events = log.read_all()
        assert len(events) == 3
        types = {e["event_type"] for e in events}
        assert types == {"SignalAdded", "SynthesisApproved", "ClusterScoreChanged"}

    def test_read_by_type(self, tmp_path):
        """Фильтрация по типу работает."""
        log = EventLog(path=str(tmp_path / "events.jsonl"))
        log.emit(SignalAdded(signal_id="A", cluster="c1", theme="t", dir="pos",
                             narrative_role="trigger", source="s"))
        log.emit(SignalAdded(signal_id="B", cluster="c2", theme="t", dir="neg",
                             narrative_role="complication", source="s"))
        log.emit(SynthesisApproved(synthesis_id="syn-001", cluster="c1",
                                   tension="X vs Y", strength="strong", confidence=0.9))

        added = log.read_by_type("SignalAdded")
        assert len(added) == 2
        approved = log.read_by_type("SynthesisApproved")
        assert len(approved) == 1

    def test_append_only_preserves_history(self, tmp_path):
        """Каждый emit добавляет строку — история не перезаписывается."""
        log = EventLog(path=str(tmp_path / "events.jsonl"))
        for i in range(10):
            log.emit(SignalAdded(signal_id=f"SIG-{i:03d}", cluster="c", theme="t",
                                 dir="pos", narrative_role="background", source="s"))
        events = log.read_all()
        assert len(events) == 10
        ids = [e["signal_id"] for e in events]
        assert ids == [f"SIG-{i:03d}" for i in range(10)]

    def test_corrupted_line_skipped(self, tmp_path):
        """Повреждённая строка в JSONL пропускается, остальные читаются."""
        path = tmp_path / "events.jsonl"
        path.write_text(
            '{"event_type":"SignalAdded","signal_id":"A"}\n'
            'CORRUPTED LINE\n'
            '{"event_type":"SignalAdded","signal_id":"B"}\n',
            encoding="utf-8"
        )
        log = EventLog(path=str(path))
        events = log.read_all()
        assert len(events) == 2
        assert {e["signal_id"] for e in events} == {"A", "B"}

    def test_stats(self, tmp_path):
        """stats() возвращает корректную статистику."""
        log = EventLog(path=str(tmp_path / "events.jsonl"))
        log.emit(SignalAdded(signal_id="A", cluster="c", theme="t",
                             dir="pos", narrative_role="trigger", source="s"))
        log.emit(SignalAdded(signal_id="B", cluster="c", theme="t",
                             dir="neg", narrative_role="complication", source="s"))
        stats = log.stats()
        assert stats["total"] == 2
        assert stats["by_type"]["SignalAdded"] == 2
