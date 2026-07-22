"""
scripts/rebuild_synthesis.py
Bitcoin Intel — пересчёт синтезов при MAJOR изменении алгоритма (C3 ARR v2).

Создаёт diff между старым и новым синтезом для ревью аналитиком.
Без --apply — только показывает что изменится.

Использование:
    python scripts/rebuild_synthesis.py                          # diff для всех
    python scripts/rebuild_synthesis.py --cluster strategy_model_stress
    python scripts/rebuild_synthesis.py --apply                  # перезаписать кеш
    python scripts/rebuild_synthesis.py --apply --cluster etf_institutional_flow
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    SIGNALS_PATH, SYNTHESIS_CACHE_PATH, SYNTHESIS_STORE_PATH,
    ENCODING, ERROR_EXIT_CODES,
)
from infrastructure.file_lock import safe_read_json, atomic_write_json_safe
from infrastructure.logger import get_logger
from domain.exceptions import BitcoinIntelError, EmptyClusterError

logger = get_logger("rebuild_synthesis")


def rebuild(cluster_filter: str | None = None, apply: bool = False) -> dict:
    """
    Пересчитывает синтезы и создаёт diff для ревью.

    apply=False: только показать что изменится (безопасно запускать многократно)
    apply=True:  перезаписать synthesis_cache.json

    Возвращает статистику: {total, changed, unchanged, errors}
    """
    from scripts.synthesizer import (
        synthesize_cluster, _load_contradicts_map, _load_signal_entity_map,
    )

    raw     = safe_read_json(SIGNALS_PATH, default=[], raise_on_corrupt=True)
    signals = raw.get("signals", raw) if isinstance(raw, dict) else raw

    old_cache = safe_read_json(SYNTHESIS_CACHE_PATH, default={})

    # §17: загружаем те же карты, что main() — иначе синтез здесь слеп к
    # реальным contradicts-связям (relationships.json) и к entity-identity
    # (ENTITIES.json), и dry-run диф врёт о том, что реально изменится.
    # Обнаружено 2026-07-22: без них anchor/tension расходится с продом в
    # 5 из 7 живых кластеров, не только количеством сигналов.
    contradicts_map   = _load_contradicts_map()
    signal_entity_map = _load_signal_entity_map()

    # Группировка по кластерам
    clusters: dict[str, list] = {}
    for s in signals:
        key = s.get("cluster")
        if key:
            clusters.setdefault(key, []).append(s)

    if cluster_filter:
        clusters = {k: v for k, v in clusters.items() if k == cluster_filter}

    if not clusters:
        print(f"Кластеры не найдены{f' для {cluster_filter}' if cluster_filter else ''}")
        return {"total": 0, "changed": 0, "unchanged": 0, "errors": 0}

    stats   = {"total": len(clusters), "changed": 0, "unchanged": 0, "errors": 0}
    new_cache = dict(old_cache)
    ts      = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    print(f"\nРебилд синтезов ({len(clusters)} кластеров){'  [DRY RUN]' if not apply else ''}")
    print("─" * 60)

    for cluster_key, cluster_signals in clusters.items():
        try:
            # Получить предыдущий синтез
            old = old_cache.get(cluster_key, {})

            # Новый синтез с текущим алгоритмом
            result = synthesize_cluster(
                cluster_key, cluster_signals,
                contradicts_map=contradicts_map,
                signal_entity_map=signal_entity_map,
            )

            new = {
                "tension":          result.tension,
                "narrative":        result.narrative,
                "takeaway":         result.takeaway,
                "strength":         result.strength,
                "confidence":       round(result.confidence, 3),
                "phase":            result.phase,
                "score":            result.score.total,
                "signal_count":     result.signal_count,
                "anchor_signal_id": result.anchor_signal_id,
                "uncertainty":      result.uncertainty,
                "entity_count":        result.entity_count,
                "anchor_entity_share": round(result.anchor_entity_share, 3),
                "is_minority_anchor":  result.is_minority_anchor,
                "generated_at":     datetime.now(timezone.utc).isoformat(),
            }

            # Diff
            changed = (
                old.get("tension")   != new["tension"]   or
                old.get("phase")     != new["phase"]     or
                old.get("narrative") != new["narrative"]
            )

            if changed:
                stats["changed"] += 1
                print(f"\n⚡ {cluster_key}: ИЗМЕНИЛСЯ")
                if old.get("tension") != new["tension"]:
                    print(f"  tension WAS: {old.get('tension','—')[:70]}")
                    print(f"  tension NOW: {new['tension'][:70]}")
                if old.get("phase") != new["phase"]:
                    print(f"  phase: {old.get('phase','—')} → {new['phase']}")
                print(f"  Рекомендация: REVIEW")
            else:
                stats["unchanged"] += 1
                print(f"  ✓ {cluster_key}: без изменений "
                      f"(phase={new['phase']}, strength={new['strength']})")

            # Сохранить diff в synthesis_store
            if apply:
                store = Path(SYNTHESIS_STORE_PATH)
                store.mkdir(exist_ok=True)
                diff_path = store / f"{cluster_key}_rebuild_{ts}.json"
                diff_path.write_text(
                    json.dumps({
                        "cluster": cluster_key,
                        "rebuilt_at": new["generated_at"],
                        "changed": changed,
                        "old": {"tension": old.get("tension"), "phase": old.get("phase")},
                        "new": {"tension": new["tension"], "phase": new["phase"]},
                    }, ensure_ascii=False, indent=2),
                    encoding=ENCODING
                )

            new_cache[cluster_key] = new

        except EmptyClusterError as e:
            stats["errors"] += 1
            print(f"  ⚠ {cluster_key}: {e}")
        except Exception as e:
            stats["errors"] += 1
            print(f"  ✗ {cluster_key}: ERROR — {e}")
            logger.error(f"Rebuild error for {cluster_key}: {e}")

    print(f"\n{'─'*60}")
    print(f"Итог: {stats['changed']} изменились, "
          f"{stats['unchanged']} без изменений, "
          f"{stats['errors']} ошибок")

    if apply:
        atomic_write_json_safe(SYNTHESIS_CACHE_PATH, new_cache)
        print(f"\n✓ synthesis_cache.json обновлён ({len(new_cache)} кластеров)")
        print("  Рекомендуется: проверить сайт и утвердить изменения")
    else:
        print(f"\nDRY RUN — файлы не изменены.")
        print(f"Запустить реальный ребилд: python scripts/rebuild_synthesis.py --apply")

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Пересчёт синтезов при MAJOR изменении алгоритма"
    )
    parser.add_argument("--cluster", help="Пересчитать только один кластер")
    parser.add_argument("--apply",   action="store_true",
                        help="Применить изменения (default: dry run)")
    args = parser.parse_args()

    try:
        stats = rebuild(cluster_filter=args.cluster, apply=args.apply)
        sys.exit(ERROR_EXIT_CODES["success"] if stats["errors"] == 0
                 else ERROR_EXIT_CODES["business_logic_error"])
    except BitcoinIntelError as e:
        print(f"⛔ {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["data_integrity_error"])
    except Exception as e:
        logger.exception("Unexpected error in rebuild_synthesis")
        print(f"💥 {e}", file=sys.stderr)
        sys.exit(ERROR_EXIT_CODES["system_error"])


if __name__ == "__main__":
    main()
