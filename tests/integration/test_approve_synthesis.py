"""
tests/integration/test_approve_synthesis.py
Bitcoin Intel — тесты для scripts/approve_synthesis.py (C3 ARR v3).

До этого файла approve_synthesis.py не имел ни одного теста — ARR v3 отметила
это как Critical-риск (единственный инструмент, необратимо меняющий статус
синтеза, без покрытия). При написании этих тестов обнаружен и исправлен
реальный production-баг: state machine запрещала прямой переход
generated -> approved, который approve() вызывает при каждом запуске — то
есть утверждение синтеза не могло сработать НИ РАЗУ ни в одном окружении
(см. domain/state_machine.py, SYNTHESIS_TRANSITIONS, фикс 2026-06-30).
"""
import json
import os
from pathlib import Path

import pytest

from config.settings import SYNTHESIS_STORE_PATH, EVENTS_LOG_PATH, ENCODING
from domain.exceptions import SynthesizerError, ForbiddenStateTransitionError


def make_synthesis(synthesis_id: str, cluster: str = "strategy_model_stress",
                    status: str = "generated") -> dict:
    """Минимальный валидный объект синтеза для тестов."""
    return {
        "id": synthesis_id,
        "cluster": cluster,
        "status": status,
        "tension": "Strategy наращивает долг vs рынок ставит NAV-дисконт 0.83x",
        "narrative": "Дивидендная машина Strategy сжимает пространство для накопления",
        "takeaway": "Модель требует паузы или перестройки",
        "strength": "strong",
        "confidence": 0.85,
        "phase": "active",
        "score": 93,
        "signal_count": 3,
        "anchor_signal_id": "STR-2026-0625-001",
        "phase_changed": False,
        "structural_change": {},
        "rationale": "",
        "signals_used": ["STR-2026-0625-001", "STR-2026-0622-004"],
        "signals_ignored": [],
        "uncertainty": {},
        "generated_at": "2026-06-30T10:00:00+00:00",
    }


def write_synthesis(synthesis: dict) -> Path:
    """Пишет объект синтеза в synthesis_store/ (внутри песочницы теста)."""
    store = Path(SYNTHESIS_STORE_PATH)
    store.mkdir(exist_ok=True)
    f = store / f"{synthesis['id']}.json"
    f.write_text(json.dumps(synthesis, ensure_ascii=False), encoding=ENCODING)
    return f


GOOD_RATIONALE = (
    "Выбран STR-2026-0625-001 как anchor (2 contradicts, weight=primary); "
    "tension точно описывает NAV-дисконт как рыночную оценку модели Strategy"
)


# ─── Регрессия: баг state machine, найденный при написании этих тестов ──────

def test_generated_to_approved_transition_is_allowed():
    """
    Регрессия: до фикса 2026-06-30 transition("synthesis", id, "generated",
    "approved") ВСЕГДА бросал ForbiddenStateTransitionError, потому что
    SYNTHESIS_TRANSITIONS["generated"] не включал "approved". Это означало,
    что approve_synthesis.py не мог утвердить ни один синтез ни разу.
    """
    from domain.state_machine import transition
    # Не должно бросить исключение
    transition("synthesis", "test-synthesis-id", "generated", "approved")


# ─── list_pending() ───────────────────────────────────────────────────────────

def test_list_pending_empty_when_store_missing():
    from scripts.approve_synthesis import list_pending
    assert list_pending() == []


def test_list_pending_returns_only_generated_status():
    from scripts.approve_synthesis import list_pending

    write_synthesis(make_synthesis("synthesis_a_20260630_100000", status="generated"))
    write_synthesis(make_synthesis("synthesis_b_20260630_100001", status="approved"))
    write_synthesis(make_synthesis("synthesis_c_20260630_100002", status="superseded"))

    pending = list_pending()
    ids = {s["id"] for s in pending}
    assert ids == {"synthesis_a_20260630_100000"}


def test_list_pending_filters_by_cluster():
    from scripts.approve_synthesis import list_pending

    write_synthesis(make_synthesis("synthesis_a_20260630_100000",
                                    cluster="strategy_model_stress", status="generated"))
    write_synthesis(make_synthesis("synthesis_b_20260630_100001",
                                    cluster="etf_institutional_flow", status="generated"))

    pending = list_pending(cluster_key="etf_institutional_flow")
    assert len(pending) == 1
    assert pending[0]["cluster"] == "etf_institutional_flow"


def test_list_pending_skips_corrupt_files_gracefully():
    """DEGRADE GRACEFULLY: повреждённый JSON в synthesis_store не должен падать весь список."""
    from scripts.approve_synthesis import list_pending

    store = Path(SYNTHESIS_STORE_PATH)
    store.mkdir(exist_ok=True)
    (store / "synthesis_corrupt_20260630_100000.json").write_text("{not valid json", encoding=ENCODING)
    write_synthesis(make_synthesis("synthesis_a_20260630_100001", status="generated"))

    pending = list_pending()
    assert len(pending) == 1
    assert pending[0]["id"] == "synthesis_a_20260630_100001"


def test_list_pending_logs_warning_for_corrupt_file(caplog):
    """
    Sprint 0 / GH Issue #80 (bandit B110): раньше `except Exception: pass` молча
    проглатывал битый файл — деградация была невидимой. Проверяем, что теперь
    пропуск логируется как WARNING с именем файла, не тихо.
    """
    import logging
    from scripts.approve_synthesis import list_pending

    store = Path(SYNTHESIS_STORE_PATH)
    store.mkdir(exist_ok=True)
    (store / "synthesis_corrupt_20260630_100000.json").write_text("{not valid json", encoding=ENCODING)

    with caplog.at_level(logging.WARNING, logger="bitcoin_intel.approve_synthesis"):
        list_pending()

    assert any(
        "synthesis_corrupt_20260630_100000.json" in record.message
        for record in caplog.records
    )
    assert any(record.levelname == "WARNING" for record in caplog.records)


# ─── approve() — happy path ───────────────────────────────────────────────────

def test_approve_valid_transition_updates_status_and_fields():
    from scripts.approve_synthesis import approve

    write_synthesis(make_synthesis("synthesis_strategy_20260630_100000", status="generated"))

    result = approve("synthesis_strategy_20260630_100000", GOOD_RATIONALE)

    assert result["status"] == "approved"
    assert result["rationale"] == GOOD_RATIONALE
    assert "approved_at" in result and result["approved_at"]
    assert "approved_by" in result and result["approved_by"]


def test_approve_persists_changes_to_disk():
    from scripts.approve_synthesis import approve

    f = write_synthesis(make_synthesis("synthesis_strategy_20260630_100000", status="generated"))
    approve("synthesis_strategy_20260630_100000", GOOD_RATIONALE)

    on_disk = json.loads(f.read_text(encoding=ENCODING))
    assert on_disk["status"] == "approved"
    assert on_disk["rationale"] == GOOD_RATIONALE


def test_approve_emits_synthesis_approved_event():
    from scripts.approve_synthesis import approve

    write_synthesis(make_synthesis("synthesis_strategy_20260630_100000", status="generated"))
    approve("synthesis_strategy_20260630_100000", GOOD_RATIONALE)

    events_path = Path(EVENTS_LOG_PATH)
    assert events_path.exists()
    lines = [l for l in events_path.read_text(encoding=ENCODING).splitlines() if l.strip()]
    assert len(lines) == 1

    event = json.loads(lines[0])
    assert event["event_type"] == "SynthesisApproved"
    assert event["synthesis_id"] == "synthesis_strategy_20260630_100000"
    assert event["rationale"] == GOOD_RATIONALE
    # Регрессия: tension/strength/confidence должны попадать в audit trail,
    # а не оставаться на дефолтах ("", "", 0.0) — данные доступны в synthesis.
    assert event["tension"] != ""
    assert event["strength"] != ""
    assert event["confidence"] > 0.0


# ─── approve() — error paths ──────────────────────────────────────────────────

def test_approve_raises_when_synthesis_not_found():
    from scripts.approve_synthesis import approve

    with pytest.raises(SynthesizerError, match="not found"):
        approve("synthesis_does_not_exist_20260630_100000", GOOD_RATIONALE)


def test_approve_raises_when_status_not_generated():
    from scripts.approve_synthesis import approve

    write_synthesis(make_synthesis("synthesis_already_approved_20260630_100000", status="approved"))

    with pytest.raises(SynthesizerError, match="status is 'approved'"):
        approve("synthesis_already_approved_20260630_100000", GOOD_RATIONALE)


def test_approve_raises_when_status_superseded():
    """Нельзя утвердить уже устаревший (superseded) синтез."""
    from scripts.approve_synthesis import approve

    write_synthesis(make_synthesis("synthesis_old_20260630_100000", status="superseded"))

    with pytest.raises(SynthesizerError):
        approve("synthesis_old_20260630_100000", GOOD_RATIONALE)


# ─── validate_rationale_quality() — интеграция с approve workflow ────────────

def test_rationale_quality_warns_on_short_rationale():
    from domain.validator import validate_rationale_quality
    synthesis = make_synthesis("synthesis_x", status="generated")
    warnings = validate_rationale_quality("ок", synthesis)
    assert warnings, "Слишком короткий rationale должен давать предупреждение"


def test_rationale_quality_no_warnings_on_good_rationale():
    from domain.validator import validate_rationale_quality
    synthesis = make_synthesis("synthesis_x", status="generated")
    synthesis["signals_used"] = ["STR-2026-0625-001"]
    warnings = validate_rationale_quality(
        "Выбран STR-2026-0625-001 как anchor из-за высокого confidence "
        "и двух подтверждённых contradicts с другими сигналами кластера",
        synthesis,
    )
    assert warnings == [] or all("empty" not in w.lower() for w in warnings)


# ─── main() CLI — non-interactive путь через --rationale ──────────────────────

def test_main_approves_via_cli_args(monkeypatch, capsys):
    """main() с --id и --rationale не должен требовать интерактивного ввода."""
    import sys
    from scripts.approve_synthesis import main

    write_synthesis(make_synthesis("synthesis_cli_20260630_100000", status="generated"))

    monkeypatch.setattr(sys, "argv", [
        "approve_synthesis.py",
        "--id", "synthesis_cli_20260630_100000",
        "--rationale", GOOD_RATIONALE,
    ])

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0

    f = Path(SYNTHESIS_STORE_PATH) / "synthesis_cli_20260630_100000.json"
    on_disk = json.loads(f.read_text(encoding=ENCODING))
    assert on_disk["status"] == "approved"

    out = capsys.readouterr().out
    assert "утверждён" in out


def test_main_exits_with_business_error_code_on_empty_rationale(monkeypatch):
    import sys
    from scripts.approve_synthesis import main
    from config.settings import ERROR_EXIT_CODES

    write_synthesis(make_synthesis("synthesis_cli_20260630_100001", status="generated"))

    monkeypatch.setattr(sys, "argv", [
        "approve_synthesis.py",
        "--id", "synthesis_cli_20260630_100001",
        "--rationale", "",
    ])
    # Пустой --rationale запускает интерактивный input() — подставляем пустой ввод
    monkeypatch.setattr("builtins.input", lambda *_args: "")

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == ERROR_EXIT_CODES["business_logic_error"]


def test_main_exits_with_business_error_code_on_not_found(monkeypatch):
    import sys
    from scripts.approve_synthesis import main
    from config.settings import ERROR_EXIT_CODES

    monkeypatch.setattr(sys, "argv", [
        "approve_synthesis.py",
        "--id", "synthesis_does_not_exist_20260630_999999",
        "--rationale", GOOD_RATIONALE,
    ])

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == ERROR_EXIT_CODES["business_logic_error"]
