"""
scripts/history_query.py
Bitcoin Intel — исторические запросы к synthesis_store.

Использование:
    python scripts/history_query.py --cluster strategy_model_stress
    python scripts/history_query.py --cluster strategy_model_stress --since 2026-01-01
    python scripts/history_query.py --id syn-strategy_model_stress-20260628-001
    python scripts/history_query.py --tension-history strategy_model_stress
    python scripts/history_query.py --list-clusters
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    SYNTHESIS_STORE_PATH, ENCODING, ERROR_EXIT_CODES
)
from infrastructure.logger import get_logger
from domain.exceptions import BitcoinIntelError

logger = get_logger("history_query")


# ─── Загрузка synthesis_store ─────────────────────────────────────────────────

def load_synthesis_store() -> list[dict]:
    """Загружает все файлы синтезов из synthesis_store/. Пропускает повреждённые."""
    store = Path(SYNTHESIS_STORE_PATH)
    if not store.exists():
        return []
    syntheses = []
    for f in sorted(store.glob("synthesis_*.json")):
        try:
            syntheses.append(json.loads(f.read_text(encoding=ENCODING)))
        except json.JSONDecodeError as e:
            logger.warning(f"Skipping corrupted synthesis file {f.name}: {e}")
    return syntheses


# ─── Запросы ─────────────────────────────────────────────────────────────────

def query_by_cluster(cluster_key: str,
                     since: str | None = None,
                     status: str | None = None) -> list[dict]:
    """Все синтезы кластера, опционально фильтр по дате и статусу."""
    results = [
        s for s in load_synthesis_store()
        if s.get("cluster") == cluster_key
    ]
    if since:
        results = [s for s in results if s.get("computed_at", "") >= since]
    if status:
        results = [s for s in results if s.get("status") == status]
    return sorted(results, key=lambda s: s.get("computed_at", ""))


def query_by_id(synthesis_id: str) -> dict | None:
    """Конкретный синтез по ID."""
    for s in load_synthesis_store():
        if s.get("id") == synthesis_id:
            return s
    return None


def list_clusters() -> dict[str, int]:
    """Список кластеров и количество синтезов по каждому."""
    counts: dict[str, int] = {}
    for s in load_synthesis_store():
        cluster = s.get("cluster", "unknown")
        counts[cluster] = counts.get(cluster, 0) + 1
    return dict(sorted(counts.items()))


def tension_history(cluster_key: str) -> list[dict]:
    """
    История изменений tension для кластера.
    Возвращает список в хронологическом порядке.
    """
    syntheses = query_by_cluster(cluster_key)
    return [
        {
            "date":     s.get("computed_at", "")[:10],
            "tension":  s.get("tension", ""),
            "strength": s.get("strength", ""),
            "status":   s.get("status", ""),
            "id":       s.get("id", ""),
            "signals":  len(s.get("signals_used", [])),
        }
        for s in syntheses
    ]


# ─── Форматирование вывода ────────────────────────────────────────────────────

def _print_table(rows: list[dict], columns: list[tuple]) -> None:
    """Печатает таблицу. columns = [(key, label, width), ...]"""
    header = " | ".join(f"{label:<{w}}" for _, label, w in columns)
    sep    = "-" * len(header)
    print(f"\n{header}\n{sep}")
    for row in rows:
        line = " | ".join(
            f"{str(row.get(k, ''))[:w]:<{w}}" for k, _, w in columns
        )
        print(line)
    print()


def _print_synthesis(s: dict) -> None:
    """Детальный вывод одного синтеза."""
    print(f"\n{'─'*60}")
    print(f"  ID:       {s.get('id', '—')}")
    print(f"  Cluster:  {s.get('cluster', '—')}")
    print(f"  Status:   {s.get('status', '—')}")
    print(f"  Date:     {s.get('computed_at', '—')[:19]}")
    print(f"  Strength: {s.get('strength', '—')}")
    print(f"  Phase:    {s.get('phase', '—')}")
    tension = s.get("tension", "")
    if tension:
        print(f"  Tension:  {tension[:70]}{'…' if len(tension) > 70 else ''}")
    narrative = s.get("narrative", "")
    if narrative:
        print(f"  Narrative:{narrative[:100]}{'…' if len(narrative) > 100 else ''}")
    signals = s.get("signals_used", [])
    if signals:
        print(f"  Signals:  {', '.join(signals[:5])}{'…' if len(signals)>5 else ''}")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Исторические запросы к synthesis_store",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cluster",        help="Кластер для поиска")
    parser.add_argument("--since",          help="Дата с (YYYY-MM-DD)")
    parser.add_argument("--status",         help="Фильтр по статусу (approved, published...)")
    parser.add_argument("--id",             help="ID конкретного синтеза")
    parser.add_argument("--tension-history",metavar="CLUSTER",
                                            help="История изменений tension кластера")
    parser.add_argument("--list-clusters",  action="store_true",
                                            help="Показать все кластеры с количеством синтезов")
    parser.add_argument("--format",         choices=["table", "json"], default="table")

    args = parser.parse_args()

    try:
        if args.list_clusters:
            clusters = list_clusters()
            if not clusters:
                print("synthesis_store пуст или не существует")
                return
            print(f"\nКластеры в synthesis_store ({sum(clusters.values())} синтезов):")
            for cluster, count in clusters.items():
                print(f"  {cluster:<40} {count} синтезов")
            return

        if args.tension_history:
            rows = tension_history(args.tension_history)
            if not rows:
                print(f"Нет синтезов для кластера '{args.tension_history}'")
                return
            if args.format == "json":
                print(json.dumps(rows, ensure_ascii=False, indent=2))
            else:
                print(f"\nTension history: {args.tension_history} ({len(rows)} записей)")
                _print_table(rows, [
                    ("date",    "Date",    10),
                    ("status",  "Status",  12),
                    ("strength","Strength", 8),
                    ("signals", "Signals",  7),
                    ("tension", "Tension", 60),
                ])
            return

        if args.id:
            s = query_by_id(args.id)
            if not s:
                print(f"Синтез '{args.id}' не найден", file=sys.stderr)
                sys.exit(ERROR_EXIT_CODES["business_logic_error"])
            if args.format == "json":
                print(json.dumps(s, ensure_ascii=False, indent=2))
            else:
                _print_synthesis(s)
            return

        if args.cluster:
            results = query_by_cluster(args.cluster, args.since, args.status)
            if not results:
                print(f"Нет синтезов для кластера '{args.cluster}'")
                return
            if args.format == "json":
                print(json.dumps(results, ensure_ascii=False, indent=2))
            else:
                print(f"\nКластер '{args.cluster}': {len(results)} синтезов")
                for s in results:
                    _print_synthesis(s)
            return

        parser.print_help()

    except BitcoinIntelError as e:
        print(f"⛔ {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["business_logic_error"])
    except Exception as e:
        logger.exception("Unexpected error in history_query")
        print(f"💥 Unexpected error: {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["system_error"])


if __name__ == "__main__":
    main()
