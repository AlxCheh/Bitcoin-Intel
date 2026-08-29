"""
scripts/detect_pipeline_events.py
Bitcoin Intel — общий детектор порогов в live-пайплайнах.

ЗАЧЕМ
-----
Аудит корпуса (2026-08-29) выявил разрыв: пайплайны (bip110_signaling каждые
3 часа, volume и top_addresses ежедневно) исправно обновляются и рисуются на
сайте, но НИКОГДА не порождают сигнал. Пороговое событие в них замечается
только если о нём напишет CoinDesk — то есть проект узнаёт о собственных
данных из вторых рук. Показательный случай: BIP-110 прошёл deadline_block
(961 632) и сигналинг упал до 0 — при том, что NAR-2026-0803-001 прямо
предсказывал этот переход, ни один сигнал этого не зафиксировал.

ЧЕГО ЭТОТ СКРИПТ НАМЕРЕННО НЕ ДЕЛАЕТ
------------------------------------
Не создаёт сигналы. Ни автоматически, ни «черновиками». Правило Шага 1
CLAUDE.md — «Claude не наполняет сигналы из собственных знаний, только из
материала пользователя» — остаётся в силе; автогенерация сигналов из
метрики обошла бы Шаги 2-7 (исследование, альтернативы, честный тест
связей) и наполнила бы корпус записями, которых никто не разбирал.
Детектор только ФИКСИРУЕТ, что порог пересечён, и передаёт это человеку.

СОСТОЯНИЕ И ЧЕСТНОСТЬ ПЕРВОГО ЗАПУСКА
-------------------------------------
Чтобы отличать ПЕРЕСЕЧЕНИЕ порога от «условие и так выполнено», скрипт
хранит последнее наблюдённое значение каждого правила в выходном файле.
На первом наблюдении правила предыдущего значения нет, поэтому:
  - если условие уже выполнено → статус `true_at_baseline`, НЕ `crossed`.
    Это честная разница: мы не видели самого перехода, только застали
    результат (ровно случай BIP-110 — дедлайн прошёл до появления детектора).
  - если не выполнено → просто запоминаем базовую линию, событий нет.

Использование:
    python3 scripts/detect_pipeline_events.py
    python3 scripts/detect_pipeline_events.py --rules … --out … --repo-root …
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RULES = REPO_ROOT / "data" / "pipeline_watch_rules.json"
DEFAULT_OUT = REPO_ROOT / "data" / "pipeline_events.json"

VALID_CONDITIONS = {
    "crosses_above",
    "crosses_below",
    "pct_change_exceeds",
    "changes_by_at_least",
}
MAX_EVENT_LOG = 100  # держим лог событий ограниченным, чтобы файл не рос бесконечно


def resolve_path(data, dotted: str):
    """
    Достаёт значение по точечному пути ('current.signal_pct', 'entries.0.balance_btc').
    Числовой сегмент трактуется как индекс списка. Возвращает None, если путь
    не разрешается — отсутствующее поле не должно ронять весь прогон,
    пайплайны меняют формат независимо от этого скрипта.
    """
    cur = data
    for seg in dotted.split("."):
        if isinstance(cur, list):
            if not seg.isdigit() or int(seg) >= len(cur):
                return None
            cur = cur[int(seg)]
        elif isinstance(cur, dict):
            if seg not in cur:
                return None
            cur = cur[seg]
        else:
            return None
    return cur if isinstance(cur, (int, float)) and not isinstance(cur, bool) else None


def evaluate(condition: str, value: float, threshold: float, previous):
    """
    Возвращает (is_true_now, is_event, kind).

    is_true_now — выполнено ли условие на текущем значении (для порогов).
    is_event    — нужно ли создавать запись о событии ИМЕННО СЕЙЧАС.
    kind        — 'crossed' | 'true_at_baseline' | None.

    Для дельта-условий (pct_change_exceeds/changes_by_at_least) понятия
    "выполнено сейчас" без предыдущего значения не существует — на первом
    наблюдении события нет по построению, только базовая линия.
    """
    if condition == "crosses_above":
        now = value > threshold
        if previous is None:
            return now, now, ("true_at_baseline" if now else None)
        was = previous > threshold
        return now, (now and not was), ("crossed" if (now and not was) else None)

    if condition == "crosses_below":
        now = value < threshold
        if previous is None:
            return now, now, ("true_at_baseline" if now else None)
        was = previous < threshold
        return now, (now and not was), ("crossed" if (now and not was) else None)

    if condition == "changes_by_at_least":
        if previous is None:
            return False, False, None
        moved = abs(value - previous) >= threshold
        return moved, moved, ("crossed" if moved else None)

    if condition == "pct_change_exceeds":
        if previous is None or previous == 0:
            return False, False, None
        pct = abs((value - previous) / previous) * 100.0
        moved = pct >= threshold
        return moved, moved, ("crossed" if moved else None)

    raise ValueError(f"Unknown condition: {condition}")


def load_previous_state(out_path: Path) -> dict:
    if not out_path.exists():
        return {}
    try:
        return json.loads(out_path.read_text(encoding="utf-8")).get("state", {})
    except (json.JSONDecodeError, OSError):
        # Повреждённый выходной файл не должен блокировать детект — начинаем
        # состояние заново (потеряем историю пересечений, но не упадём).
        print("::warning::data/pipeline_events.json нечитаем — состояние сброшено", file=sys.stderr)
        return {}


def load_existing_events(out_path: Path) -> list:
    if not out_path.exists():
        return []
    try:
        return json.loads(out_path.read_text(encoding="utf-8")).get("events", [])
    except (json.JSONDecodeError, OSError):
        return []


def run(rules_path: Path, out_path: Path, repo_root: Path) -> int:
    rules_doc = json.loads(rules_path.read_text(encoding="utf-8"))
    rules = rules_doc.get("rules", [])
    state = load_previous_state(out_path)
    events = load_existing_events(out_path)

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_events = []
    new_state = {}
    skipped = []

    for rule in rules:
        rid = rule["id"]
        condition = rule["condition"]
        if condition not in VALID_CONDITIONS:
            raise ValueError(f"[{rid}] неизвестное condition: {condition}")

        src = repo_root / rule["source_file"]
        if not src.exists():
            skipped.append(f"{rid}: нет файла {rule['source_file']}")
            continue
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            skipped.append(f"{rid}: {rule['source_file']} не парсится")
            continue

        value = resolve_path(data, rule["value_path"])
        if value is None:
            skipped.append(f"{rid}: путь {rule['value_path']} не разрешается")
            continue

        if "threshold_path" in rule:
            threshold = resolve_path(data, rule["threshold_path"])
            if threshold is None:
                skipped.append(f"{rid}: threshold_path {rule['threshold_path']} не разрешается")
                continue
        elif "threshold" in rule:
            threshold = float(rule["threshold"])
        else:
            raise ValueError(f"[{rid}] нужен threshold или threshold_path")

        previous = state.get(rid, {}).get("value")
        is_true_now, is_event, kind = evaluate(condition, value, threshold, previous)

        new_state[rid] = {
            "value": value,
            "threshold": threshold,
            "condition_true": bool(is_true_now),
            "observed_at": now_iso,
        }

        if is_event:
            new_events.append({
                "rule_id": rid,
                "kind": kind,
                "detected_at": now_iso,
                "value": value,
                "previous_value": previous,
                "threshold": threshold,
                "condition": condition,
                "source_file": rule["source_file"],
                "description": rule.get("description", ""),
                "why_it_matters": rule.get("why_it_matters", ""),
                "suggested_cluster": rule.get("suggested_cluster"),
                "reviewed": False,
            })

    # Новые события — в начало, лог обрезается по MAX_EVENT_LOG.
    all_events = (new_events + events)[:MAX_EVENT_LOG]

    out_doc = {
        "_generated_by": "scripts/detect_pipeline_events.py",
        "_note": "ПРОИЗВОДНЫЙ ФАЙЛ — не редактировать руками, кроме поля reviewed. События НЕ являются сигналами: это пометка, что порог пересечён и стоит разобрать материал по Шагам 1-8.",
        "generated_at": now_iso,
        "rules_evaluated": len(rules),
        "rules_skipped": skipped,
        "unreviewed_count": sum(1 for e in all_events if not e.get("reviewed")),
        "events": all_events,
        "state": new_state,
    }
    out_path.write_text(json.dumps(out_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for s in skipped:
        print(f"::warning::пропущено правило — {s}")
    for e in new_events:
        marker = "НОВОЕ ПЕРЕСЕЧЕНИЕ" if e["kind"] == "crossed" else "УЖЕ ВЕРНО НА БАЗОВОЙ ЛИНИИ"
        print(f"::notice::[{marker}] {e['rule_id']}: {e['description']} (value={e['value']}, threshold={e['threshold']})")

    print(f"OK: {out_path} — правил {len(rules)}, новых событий {len(new_events)}, пропущено {len(skipped)}")
    return len(new_events)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = ap.parse_args()
    run(args.rules, args.out, args.repo_root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
