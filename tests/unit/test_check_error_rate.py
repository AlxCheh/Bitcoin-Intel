"""
tests/unit/test_check_error_rate.py
MON07 — юнит-тесты count_log_levels().

count_log_levels() принимает список строк напрямую (не читает файл сама)
— тестируется без file I/O, без конфликта с autouse isolated_environment
(тот же паттерн, что в остальных проверках IRP Wave 3-4).
"""
import json

from scripts.check_error_rate import count_log_levels


def _log(level: str, msg: str = "test") -> str:
    return json.dumps({"ts": "2026-07-02T00:00:00+00:00", "level": level,
                        "component": "test", "msg": msg})


def test_empty_input_zero_total():
    result = count_log_levels([])
    assert result["total_log_entries"] == 0
    assert result["error_count"] == 0
    assert result["error_rate"] == 0.0


def test_no_errors_all_info():
    lines = [_log("INFO"), _log("INFO"), _log("DEBUG")]
    result = count_log_levels(lines)
    assert result["total_log_entries"] == 3
    assert result["error_count"] == 0
    assert result["by_level"] == {"INFO": 2, "DEBUG": 1}


def test_error_and_critical_both_counted():
    lines = [_log("INFO"), _log("ERROR"), _log("CRITICAL"), _log("WARNING")]
    result = count_log_levels(lines)
    assert result["total_log_entries"] == 4
    assert result["error_count"] == 2  # ERROR + CRITICAL
    assert result["error_rate"] == 0.5


def test_warning_not_counted_as_error():
    """WARNING — деградация без падения (см. logger.py docstring), не error."""
    lines = [_log("WARNING"), _log("WARNING")]
    result = count_log_levels(lines)
    assert result["error_count"] == 0
    assert result["total_log_entries"] == 2


def test_non_json_lines_silently_skipped():
    """
    CI stderr — смешанный поток: структурированные логи logger.py вперемешку
    с обычным текстом (progress bars, посторонние print). Не-JSON строки не
    должны падать с исключением и не должны попадать в total.
    """
    lines = [
        "Some random CI output",
        _log("INFO"),
        "",
        "   ",
        "another non-json line {not valid json",
        _log("ERROR"),
    ]
    result = count_log_levels(lines)
    assert result["total_log_entries"] == 2
    assert result["error_count"] == 1


def test_json_without_level_field_skipped():
    """JSON-строка без поля 'level' (не наш формат) не считается."""
    lines = [json.dumps({"foo": "bar"}), _log("INFO")]
    result = count_log_levels(lines)
    assert result["total_log_entries"] == 1


def test_error_rate_rounded():
    lines = [_log("ERROR")] + [_log("INFO")] * 2  # 1/3 = 0.333...
    result = count_log_levels(lines)
    assert result["error_rate"] == 0.3333
