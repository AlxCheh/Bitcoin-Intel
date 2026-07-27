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


def _engine(id_: str, entity_id: str, entity_name: str) -> dict:
    return {"id": id_, "entity_id": entity_id, "entity_name": entity_name}


def _write_revenue_engines(engines: list[dict]) -> None:
    Path("REVENUE_ENGINES.json").write_text(
        json.dumps({"meta": {}, "engines": engines}, ensure_ascii=False),
        encoding="utf-8",
    )


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


class TestRevenueEnginesEntityIntegrity:
    """LLM Wiki Пара 2 (2026-07-25): REVENUE_ENGINES.json.entity_id/entity_name
    должны быть согласованы с ENTITIES.json — та же дисциплина, что уже есть
    для signal_refs выше, распространённая на новую пару файлов."""

    def test_valid_engine_entity_link_passes(self, capsys):
        _write_signals([])
        _write_entities([_entity("e1", [])])
        _write_revenue_engines([_engine("eng1", "e1", "e1")])

        ok = validate()
        captured = capsys.readouterr()
        assert ok
        assert "все entity_id/entity_name согласованы" in captured.out

    def test_orphan_entity_id_fails_validation(self, capsys):
        """entity_id ссылается на несуществующую сущность."""
        _write_signals([])
        _write_entities([_entity("e1", [])])
        _write_revenue_engines([_engine("eng1", "nonexistent", "Ghost Corp")])

        ok = validate()
        captured = capsys.readouterr()
        assert not ok
        assert "entity_id без соответствующей записи" in captured.out
        assert "eng1→nonexistent" in captured.out

    def test_entity_name_drift_fails_validation(self, capsys):
        """Регрессия: именно этот случай был найден и исправлен при внедрении
        проверки (strive_sata.entity_name разошёлся с ENTITIES.json.strive.name)."""
        _write_signals([])
        _write_entities([_entity("strive", [])])  # name == "strive"
        _write_revenue_engines([_engine("strive_sata", "strive", "Strive (ASST)")])

        ok = validate()
        captured = capsys.readouterr()
        assert not ok
        assert "entity_name разошёлся" in captured.out
        assert "Strive (ASST)" in captured.out

    def test_multiple_engines_all_checked_independently(self, capsys):
        _write_signals([])
        _write_entities([_entity("e1", []), _entity("e2", [])])
        _write_revenue_engines([
            _engine("eng1", "e1", "e1"),   # корректный — не должен попасть в ошибку
            _engine("eng2", "e2", "WRONG NAME"),  # разошёлся — должен быть найден
        ])

        ok = validate()
        captured = capsys.readouterr()
        assert not ok
        assert "eng2" in captured.out
        assert "WRONG NAME" in captured.out

    def test_missing_revenue_engines_file_skips_check_silently(self, capsys):
        """Файл REVENUE_ENGINES.json может отсутствовать (напр. в изолированном
        тестовом окружении без него) — не должно ломать остальную валидацию."""
        _write_signals([])
        _write_entities([_entity("e1", [])])
        # REVENUE_ENGINES.json намеренно не создаём

        ok = validate()
        captured = capsys.readouterr()
        assert ok
        assert "REVENUE_ENGINES.json" not in captured.out


def _miner(id_: str, entity_id: str, name: str, signal_refs: list[str] | None = None) -> dict:
    return {
        "id": id_, "entity_id": entity_id, "name": name,
        "signal_refs": signal_refs or [],
    }


def _write_mining_companies(miners: list[dict]) -> None:
    Path("MINING_COMPANIES.json").write_text(
        json.dumps({"meta": {}, "miners": miners}, ensure_ascii=False),
        encoding="utf-8",
    )


class TestMiningCompaniesIntegrity:
    """MINING_COMPANIES.json (2026-07-26) — тот же паттерн, что Пара 2
    LLM Wiki (REVENUE_ENGINES.json ↔ ENTITIES.json), плюс проверка
    signal_refs (тот же класс, что ENTITIES.json.signal_refs) и дублей id
    внутри самого файла."""

    def test_valid_miner_passes(self, capsys):
        _write_signals([_signal("INF-2026-0629-001")])
        _write_entities([_entity("e1", ["INF-2026-0629-001"])])
        _write_mining_companies([_miner("m1", "e1", "e1", ["INF-2026-0629-001"])])

        ok = validate()
        captured = capsys.readouterr()
        assert ok
        assert "всё согласовано" in captured.out

    def test_orphan_entity_id_fails(self, capsys):
        _write_signals([])
        _write_entities([_entity("e1", [])])
        _write_mining_companies([_miner("m1", "nonexistent", "Ghost Miner")])

        ok = validate()
        captured = capsys.readouterr()
        assert not ok
        assert "entity_id без соответствующей записи" in captured.out
        assert "m1→nonexistent" in captured.out

    def test_name_drift_fails(self, capsys):
        """Регрессия: именно этот случай был найден и исправлен при внедрении
        проверки (ionic_digital/keel — name содержал историческую приставку,
        не совпадавшую с ENTITIES.json.name)."""
        _write_signals([])
        _write_entities([_entity("keel", [])])  # name == "keel"
        _write_mining_companies([_miner("m1", "keel", "Keel Infrastructure (экс-Bitfarms)")])

        ok = validate()
        captured = capsys.readouterr()
        assert not ok
        assert "name разошёлся" in captured.out

    def test_duplicate_miner_id_fails(self, capsys):
        _write_signals([])
        _write_entities([_entity("e1", []), _entity("e2", [])])
        _write_mining_companies([
            _miner("m1", "e1", "e1"),
            _miner("m1", "e2", "e2"),  # дублирующийся id внутри файла
        ])

        ok = validate()
        captured = capsys.readouterr()
        assert not ok
        assert "дублирующиеся id" in captured.out
        assert "m1" in captured.out

    def test_bad_signal_ref_fails(self, capsys):
        _write_signals([_signal("INF-2026-0001-001")])
        _write_entities([_entity("e1", [])])
        _write_mining_companies([_miner("m1", "e1", "e1", ["INF-2026-9999-999"])])

        ok = validate()
        captured = capsys.readouterr()
        assert not ok
        assert "signal_refs без соответствующего сигнала" in captured.out
        assert "m1→INF-2026-9999-999" in captured.out

    def test_missing_mining_companies_file_skips_check_silently(self, capsys):
        """Файл может отсутствовать — не должен ломать остальную валидацию."""
        _write_signals([])
        _write_entities([_entity("e1", [])])
        # MINING_COMPANIES.json намеренно не создаём

        ok = validate()
        captured = capsys.readouterr()
        assert ok
        assert "MINING_COMPANIES.json" not in captured.out
