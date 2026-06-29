"""
domain/lifecycle.py
Bitcoin Intel — Lifecycle Hooks.

Реакции системы на доменные события. Вызываются ПОСЛЕ записи события
в events.jsonl. Не блокируют основной flow — только side effects.

Hooks:
  on_signal_archived(signal_id)            — инвалидирует cache кластера
  on_synthesis_superseded(old_id, new_id)  — помечает старый синтез, пересчитывает
  on_relationship_retracted(rel_id)        — инвалидирует cache затронутых кластеров
"""

import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    SIGNALS_PATH, EVENTS_LOG_PATH, SYNTHESIS_CACHE_PATH,
    SYNTHESIS_STORE_PATH, RELATIONSHIPS_PATH, ENCODING,
)
from infrastructure.file_lock import safe_read_json
from infrastructure.logger import get_logger
from domain.events import EventLog, SynthesisExpired

logger = get_logger("lifecycle")


# ─── Hooks ────────────────────────────────────────────────────────────────────

def on_signal_archived(signal_id: str) -> None:
    """
    Вызывается когда сигнал переходит в статус archived.

    Действия:
      1. Найти кластер сигнала
      2. Инвалидировать synthesis_cache для этого кластера
      3. Логировать если сигнал был anchor (много contradicts)
    """
    logger.info(f"Hook: signal archived → {signal_id}")

    signals = safe_read_json(SIGNALS_PATH, default=[])
    signal  = next((s for s in signals if s.get("id") == signal_id), None)

    if not signal:
        logger.warning(f"on_signal_archived: signal {signal_id} not found in signals.json")
        return

    cluster = signal.get("cluster")
    if not cluster:
        return

    # Предупреждение если сигнал был anchor (много contradicts)
    contradicts_count = len(signal.get("links", {}).get("contradicts", []))
    if contradicts_count >= 2:
        logger.warning(
            f"Archiving anchor signal {signal_id} "
            f"({contradicts_count} contradicts) — cluster '{cluster}' narrative may weaken",
            extra={"signal_id": signal_id, "cluster": cluster}
        )

    _invalidate_cache_for_cluster(cluster, f"anchor signal {signal_id} archived")


def on_synthesis_superseded(old_synthesis_id: str, new_synthesis_id: str) -> None:
    """
    Вызывается когда новый синтез утверждён и заменяет предыдущий.

    Действия:
      1. Пометить старый синтез как superseded
      2. Испустить SynthesisExpired событие
    """
    logger.info(f"Hook: synthesis superseded → {old_synthesis_id} by {new_synthesis_id}")

    store    = Path(SYNTHESIS_STORE_PATH)
    old_file = store / f"{old_synthesis_id}.json"

    if old_file.exists():
        try:
            synthesis = json.loads(old_file.read_text(encoding=ENCODING))
            synthesis["status"]        = "superseded"
            synthesis["superseded_by"] = new_synthesis_id
            synthesis["superseded_at"] = datetime.now(timezone.utc).isoformat()
            old_file.write_text(
                json.dumps(synthesis, ensure_ascii=False, indent=2),
                encoding=ENCODING
            )
            logger.info(f"Marked {old_synthesis_id} as superseded")
        except Exception as e:
            logger.error(f"Failed to update superseded synthesis {old_synthesis_id}: {e}")
    else:
        logger.warning(f"on_synthesis_superseded: {old_synthesis_id}.json not found in store")

    # Испустить событие
    try:
        log = EventLog(EVENTS_LOG_PATH)
        log.emit(SynthesisExpired(
            cluster      = "",   # неизвестен без чтения файла
            synthesis_id = old_synthesis_id,
            last_signal_date    = "",
            expired_after_days  = 0,
        ))
    except Exception as e:
        logger.error(f"Failed to emit SynthesisExpired event: {e}")


def on_relationship_retracted(relationship_id: str) -> None:
    """
    Вызывается когда аналитик ретрактует связь между сигналами.

    Действия:
      1. Найти затронутые кластеры
      2. Инвалидировать synthesis_cache для них
    """
    logger.info(f"Hook: relationship retracted → {relationship_id}")

    rel_file = Path(RELATIONSHIPS_PATH)
    if not rel_file.exists():
        logger.debug("relationships.json not found — legacy links mode, skipping hook")
        return

    relationships = safe_read_json(RELATIONSHIPS_PATH, default=[])
    retracted     = next(
        (r for r in relationships if r.get("id") == relationship_id), None
    )
    if not retracted:
        logger.warning(f"on_relationship_retracted: {relationship_id} not found")
        return

    # Найти кластеры обоих сигналов
    signals = safe_read_json(SIGNALS_PATH, default=[])
    signals_map = {s["id"]: s for s in signals if "id" in s}

    affected_clusters: set = set()
    for signal_id in [retracted.get("from_id"), retracted.get("to_id")]:
        if signal_id and signal_id in signals_map:
            cluster = signals_map[signal_id].get("cluster")
            if cluster:
                affected_clusters.add(cluster)

    for cluster in affected_clusters:
        _invalidate_cache_for_cluster(
            cluster,
            f"relationship {relationship_id} retracted"
        )


# ─── Вспомогательные ─────────────────────────────────────────────────────────

def _invalidate_cache_for_cluster(cluster_key: str, reason: str) -> None:
    """
    Помечает synthesis_cache как устаревший для кластера.
    Следующий запрос к cache_builder перестроит кеш.
    """
    cache_file = Path(SYNTHESIS_CACHE_PATH)
    if not cache_file.exists():
        return

    try:
        cache = json.loads(cache_file.read_text(encoding=ENCODING))
        if cluster_key in cache:
            cache[cluster_key]["_stale"]        = True
            cache[cluster_key]["_stale_reason"] = reason
            cache[cluster_key]["_stale_at"]     = datetime.now(timezone.utc).isoformat()
            cache_file.write_text(
                json.dumps(cache, ensure_ascii=False, indent=2),
                encoding=ENCODING
            )
            logger.info(
                f"Cache invalidated for cluster '{cluster_key}': {reason}",
                extra={"cluster": cluster_key}
            )
        else:
            logger.debug(f"Cluster '{cluster_key}' not in cache — nothing to invalidate")
    except Exception as e:
        logger.error(f"Failed to invalidate cache for '{cluster_key}': {e}")
