"""
infrastructure/logger.py
Bitcoin Intel — централизованная стратегия логирования.

Формат:
  local / test  → читаемый цветной вывод в stderr (HumanFormatter)
  production    → JSON строки в stderr (StructuredFormatter)

Уровни:
  DEBUG    — детали алгоритма (score per signal, bridge selection)
  INFO     — значимые действия (signal added, synthesis created)
  WARNING  — деградация без падения (corrupt signal skipped, cache stale)
  ERROR    — ошибка компонента (файл не записан)
  CRITICAL — системная ошибка (диск полон, signals.json corrupted)

Использование:
  from infrastructure.logger import get_logger
  logger = get_logger("synthesizer")
  logger.info("Synthesis started", extra={"cluster": "strategy_model_stress"})
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    """JSON-форматтер для machine-readable логов (CI / production)."""

    EXTRA_FIELDS = (
        "signal_id", "cluster", "synthesis_id",
        "duration_ms", "operation", "error",
    )

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts":        datetime.now(timezone.utc).isoformat(),
            "level":     record.levelname,
            "component": record.name,
            "msg":       record.getMessage(),
        }
        for key in self.EXTRA_FIELDS:
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        return json.dumps(entry, ensure_ascii=False)


class HumanFormatter(logging.Formatter):
    """Читаемый цветной форматтер для локальной разработки."""

    COLORS = {
        "DEBUG":    "\033[36m",   # cyan
        "INFO":     "\033[32m",   # green
        "WARNING":  "\033[33m",   # yellow
        "ERROR":    "\033[31m",   # red
        "CRITICAL": "\033[35m",   # magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts    = datetime.now(timezone.utc).strftime("%H:%M:%S")
        name  = record.name.replace("bitcoin_intel.", "")
        return (
            f"{color}[{ts}] {record.levelname:<8} "
            f"{name}: {record.getMessage()}{self.RESET}"
        )


# Уровни по компонентам
_COMPONENT_LEVELS: dict[str, int] = {
    "validator":              logging.INFO,
    "synthesizer":            logging.DEBUG,
    "contradiction_detector": logging.INFO,
    "cache_builder":          logging.INFO,
    "add_signal":             logging.INFO,
    "lifecycle":              logging.INFO,
    "state_machine":          logging.INFO,
    "file_lock":              logging.WARNING,
    "history_query":          logging.INFO,
    "quality_report":         logging.INFO,
    "migrate_relationships":  logging.INFO,
    "performance":            logging.WARNING,
}


def get_logger(component: str) -> logging.Logger:
    """
    Возвращает настроенный logger для компонента.
    Вызов идемпотентен — повторный get_logger("x") возвращает тот же объект.
    """
    logger_name = f"bitcoin_intel.{component}"
    logger = logging.getLogger(logger_name)

    if logger.handlers:
        return logger   # уже настроен

    handler = logging.StreamHandler(sys.stderr)
    env     = os.environ.get("ENVIRONMENT", "local")

    if env in ("local", "test"):
        handler.setFormatter(HumanFormatter())
    else:
        handler.setFormatter(StructuredFormatter())

    logger.addHandler(handler)
    logger.setLevel(_COMPONENT_LEVELS.get(component, logging.INFO))
    logger.propagate = False
    return logger


# ─── Performance decorator ───────────────────────────────────────────────────

import functools
import time

# Baselines в миллисекундах (нарушение → WARNING, не ошибка)
PERFORMANCE_BASELINES_MS: dict[str, float] = {
    "validate_signal":          10.0,
    "synthesize_cluster":      100.0,
    "detect_contradictions":    50.0,
    "build_cache":             500.0,
    "read_signals_json":        50.0,
    "write_atomic_json":        20.0,
    "health_check":            200.0,
    "quality_report":          300.0,
    "history_query_cluster":   100.0,
}


def measure_performance(operation: str):
    """
    Декоратор: измеряет время выполнения функции.
    Логирует WARNING если превышен baseline из PERFORMANCE_BASELINES_MS.

    Использование:
        @measure_performance("synthesize_cluster")
        def synthesize(cluster_key, signals, ontology):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start   = time.monotonic()
            result  = func(*args, **kwargs)
            elapsed = (time.monotonic() - start) * 1000
            perf_logger = get_logger("performance")
            baseline    = PERFORMANCE_BASELINES_MS.get(operation)
            if baseline and elapsed > baseline:
                perf_logger.warning(
                    f"{operation} exceeded baseline: "
                    f"{elapsed:.0f}ms > {baseline:.0f}ms",
                    extra={"duration_ms": round(elapsed, 1), "operation": operation}
                )
            else:
                perf_logger.debug(
                    f"{operation}: {elapsed:.0f}ms"
                )
            return result
        return wrapper
    return decorator
