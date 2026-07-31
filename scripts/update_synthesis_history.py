"""
scripts/update_synthesis_history.py
Bitcoin Intel — поддерживает data/synthesis_history_count.json в актуальном
состоянии: реальный, самоподдерживающийся счётчик "кластеро-периодов"
(ADR-011) — единиц наблюдения, на которых предполагается когда-нибудь
калибровать calculate_confidence().

КОНТЕКСТ (см. полную историю в docs/ADR-011-confidence-calibration-deferred.md,
заметка 2026-07-31): до этой даты calibration readiness считалась файлами в
synthesis_store/ — механизм, который перестал обновляться 2026-06-29 (10
файлов, оба с того дня), пока реальный пайплайн синтеза (запускается на
каждый push в main, см. .github/workflows/deploy.yml) давно писал прямо в
data/synthesis_cache.json (132 коммита на момент находки). Счётчик был
навсегда заморожен на "10/30", хотя по факту порог был пройден ещё
2026-07-02 (backfill из git-истории — см. ту же заметку).

Этот скрипт — фикс: считает, какие кластеры СОДЕРЖАТЕЛЬНО изменились между
двумя прогонами synthesizer.py (через scripts.cache_diff_check.changed_clusters
— та же нормализация volatile-полей, что уже использовалась для решения
"открывать ли sync-PR"), и инкрементирует персистентный счётчик на это число.
Привязан к РЕАЛЬНОМУ пайплайну (data/synthesis_cache.json), не к устаревшему.

Использование (вызывается из .github/workflows/deploy.yml сразу после
"Run synthesizer", до Check for meaningful diff — работает независимо от
того, откроется ли sync-PR):
    python3 scripts/update_synthesis_history.py <old_cache.json> <new_cache.json>

Идемпотентность: если ни один кластер содержательно не изменился (0
изменённых), файл НЕ перезаписывается — не создаёт шума в git diff (тот же
урок, что уже был выучен для cache_diff_check.py — см. его докстринг про
зацикливание auto-merge на PR #10-#17).

DEGRADE GRACEFULLY: если history-файл не существует или повреждён —
начинает с cluster_periods=0, не падает (тот же принцип, что и
safe_read_json для synthesis_cache в остальном коде).
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import SYNTHESIS_HISTORY_PATH
from infrastructure.file_lock import safe_read_json, atomic_write_json_safe
from scripts.cache_diff_check import changed_clusters

DEFAULT_HISTORY = {
    "cluster_periods": 0,
    "last_updated_at": None,
    "last_run_changed_clusters": [],
    "note": (
        "Самоподдерживающийся счётчик кластеро-периодов (ADR-011). "
        "Обновляется scripts/update_synthesis_history.py на каждый прогон "
        "synthesizer.py в CI. НЕ редактировать руками — см. ADR-011, "
        "заметка 2026-07-31, для полной истории и метода backfill "
        "первоначального значения."
    ),
}


def update_history(
    old_cache: dict,
    new_cache: dict,
    history_path: str = SYNTHESIS_HISTORY_PATH,
) -> dict:
    """
    Считает changed_clusters(old_cache, new_cache), инкрементирует счётчик
    в history_path на это число. Возвращает итоговое состояние истории
    (даже если 0 изменений — для тестируемости; файл на диске в этом
    случае не трогается, см. докстринг модуля).
    """
    changed = changed_clusters(old_cache, new_cache)
    history = safe_read_json(history_path, default=None)
    if history is None:
        history = dict(DEFAULT_HISTORY)

    if not changed:
        # Идемпотентность: не пишем файл заново, если нечего добавлять —
        # иначе last_updated_at/шум в diff на КАЖДЫЙ прогон, даже без
        # единого реально изменившегося кластера.
        return history

    history = dict(history)
    history["cluster_periods"] = history.get("cluster_periods", 0) + len(changed)
    history["last_updated_at"] = datetime.now(timezone.utc).isoformat()
    history["last_run_changed_clusters"] = changed
    atomic_write_json_safe(history_path, history)
    return history


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("old_cache")
    parser.add_argument("new_cache")
    parser.add_argument("--history-path", default=SYNTHESIS_HISTORY_PATH)
    args = parser.parse_args()

    old = safe_read_json(args.old_cache, default={})
    new = safe_read_json(args.new_cache, default={})

    if new is None:
        print(f"⚠ Не удалось прочитать {args.new_cache} — история не обновлена", file=sys.stderr)
        sys.exit(1)

    result = update_history(old, new, args.history_path)
    changed = result.get("last_run_changed_clusters", [])
    print(
        f"cluster_periods={result['cluster_periods']} "
        f"(+{len(changed)} за этот прогон: {changed or '[]'})"
    )


if __name__ == "__main__":
    main()
