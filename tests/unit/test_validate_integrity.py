"""
tests/unit/test_validate_integrity.py
Bitcoin Intel — тесты scripts/validate_integrity.py.

Покрывает:
  - Регрессия: ENTITIES.json раньше считался как len({meta, entities}) == 2
    вместо реального числа сущностей (баг обнаружен при реализации M6).
  - M6 ARR v3: referential integrity ENTITIES.json.signal_refs -> signals.json
    (раньше не проверялась вовсе — только relationships.json).

cwd уже = tmp_path благодаря autouse-фикстуре isolated_environment в
conftest.py, поэтому файлы пишутся напрямую по относительным путям.
"""
import json
from pathlib import Path

from scripts.validate_integrity import validate


def _write_signals(signals: list[dict]) -> None:
    Path("signals.json").write_text(
        json.dumps({"meta": {}, "signals": signals}, ensure_ascii=False),
        encoding="utf-8",
    )


def _write_entities(entities: list[dict]) -> None:
    Path("ENTITIES.json").write_text(
        json.dumps({"meta": {}, "entities": entities}, ensure_ascii=False),
        encoding="utf-8",
    )


def _signal(id_: str) -> dict:
    return {
        "id": id_, "date": "2026-06-29", "signal": "x", "cluster": "c",
        "narrative_role": "trigger", "tension": "X vs Y",
        "macro_implication": "X" * 50,
    }


def _entity(id_: str, signal_refs: list[str]) -> dict:
    return {"id": id_, "name": id_, "type": "l2", "signal_refs": signal_refs}


class TestEntitiesCountRegression:
    """ENTITIES.json раньше считался как len(raw_dict) == 2, а не len(entities)."""

    def test_entities_count_reflects_actual_entities_not_wrapper_keys(self, capsys):
        _write_signals([_signal("STR-2026-0629-001")])
        _write_entities([_entity("e1", []), _entity("e2", []), _entity("e3", [])])

        ok = validate()
        captured = capsys.readouterr()
        assert ok
        assert "3 entities" in captured.out
        assert "2 entities" not in captured.out

    def test_bare_list_entities_json_also_counted_correctly(self, capsys):
        """Обратная совместимость: ENTITIES.json без {meta, entities} обёртки."""
        _write_signals([])
        Path("ENTITIES.json").write_text(
            json.dumps([_entity("e1", []), _entity("e2", [])]), encoding="utf-8"
        )
        ok = validate()
        captured = capsys.readouterr()
        assert "2 entities" in captured.out


class TestSignalRefsReferentialIntegrity:
    """M6 ARR v3."""

    def test_valid_signal_refs_pass(self, capsys):
        _write_signals([_signal("STR-2026-0629-001"), _signal("STR-2026-0629-002")])
        _write_entities([_entity("e1", ["STR-2026-0629-001"])])

        ok = validate()
        captured = capsys.readouterr()
        assert ok
        assert "все валидны" in captured.out

    def test_orphan_signal_ref_fails_validation(self, capsys):
        _write_signals([_signal("STR-2026-0629-001")])
        _write_entities([_entity("e1", ["STR-2026-0629-999"])])

        ok = validate()
        captured = capsys.readouterr()
        assert not ok
        assert "orphan signal_refs" in captured.out
        assert "e1→STR-2026-0629-999" in captured.out

    def test_multiple_orphan_refs_all_reported(self, capsys):
        _write_signals([_signal("STR-2026-0629-001")])
        _write_entities([
            _entity("e1", ["STR-2026-0629-999"]),
            _entity("e2", ["STR-2026-0629-888"]),
        ])

        ok = validate()
        captured = capsys.readouterr()
        assert not ok
        assert "e1→STR-2026-0629-999" in captured.out
        assert "e2→STR-2026-0629-888" in captured.out

    def test_entity_with_no_signal_refs_does_not_break_check(self, capsys):
        _write_signals([_signal("STR-2026-0629-001")])
        _write_entities([_entity("e1", [])])

        ok = validate()
        assert ok

    def test_no_entities_skips_signal_refs_check_silently(self, capsys):
        """Пустая ENTITIES.json — не ошибка, просто нечего проверять."""
        _write_signals([_signal("STR-2026-0629-001")])
        _write_entities([])

        ok = validate()
        captured = capsys.readouterr()
        assert ok
        assert "signal_refs" not in captured.out  # секция вообще не печаталась
