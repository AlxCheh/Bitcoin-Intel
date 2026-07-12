"""
scripts/build_facts.py
Bitcoin Intel — сборка data/facts.json из структурированного поля `facts`
сигналов signals.json, плюс синхронизация TREASURY_HOLDERS.json.

Архитектурная роль (см. CLAUDE.md, раздел "FACTS — машиночитаемые факты"):
signals.json остаётся единственным источником истины (BDKS: Single Source
of Truth, "производные ссылаются, не копируют"). data/facts.json —
ПРОИЗВОДНЫЙ, механически регенерируемый индекс: последнее по `as_of`
значение на каждый `key` среди всех сигналов, где он встречается.

TREASURY_HOLDERS.json (100 публичных компаний-держателей BTC) —
ОТДЕЛЬНЫЙ производный файл с собственным ручным процессом обновления,
который на практике уже расходился с ENTITIES.json/сигналами (Strategy,
Strive, OranjeBTC — обнаружено 2026-07-11). Для сущностей с известным
facts-ключом (см. TREASURY_NAME_TO_FACT_KEY) этот скрипт сверяет и правит
поле `btc`, логируя расхождение явно (::warning::) — не тихая правка.

data/facts.json и исправления в TREASURY_HOLDERS.json НИКОГДА не вносятся
руками — только этим скриптом, по тому же принципу, что SIGNALS.md
регенерируется из signals.json. Ручная правка будет молча перезаписана
следующим прогоном CI.

Правило разрешения: при нескольких сигналах с одним `key` побеждает тот,
у кого `as_of` позже (не дата сигнала, не порядок в файле).

Использование:
    python3 scripts/build_facts.py
    python3 scripts/build_facts.py --out data/facts.json
"""
import argparse
import json
import sys
from collections import OrderedDict
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SIGNALS_PATH = REPO_ROOT / "signals.json"
TREASURY_PATH = REPO_ROOT / "TREASURY_HOLDERS.json"
DEFAULT_OUT = REPO_ROOT / "data" / "facts.json"

# Явный маппинг "name как в TREASURY_HOLDERS.json" → "facts key" — намеренно
# explicit, не fuzzy-match по строке: имена в TREASURY_HOLDERS.json не всегда
# совпадают с entity_id (суффиксы "Inc.", ", Inc." и т.п.), а угадывание
# точно когда-нибудь смэтчит не ту компанию. Расширять только вручную,
# синхронно с добавлением facts[] на соответствующую сущность.
TREASURY_NAME_TO_FACT_KEY = {
    "Strategy": "strategy.btc_holdings",
    "Twenty One Capital": "twenty_one_capital.btc_holdings",
    "Metaplanet Inc.": "metaplanet.btc_holdings",
    "MARA Holdings, Inc.": "mara_holdings.btc_holdings",
    "Bitcoin Standard Treasury Company": "bstr.btc_holdings",
    "Strive": "strive.btc_holdings",
    "OranjeBTC": "oranjebtc.btc_holdings",
}


def load_signals() -> list[dict]:
    with open(SIGNALS_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("signals", raw) if isinstance(raw, dict) else raw


def history_of_facts(signals: list[dict]) -> dict[str, list[dict]]:
    """В отличие от resolve_facts() (только текущее значение), возвращает
    ВСЕ значения, когда-либо встреченные на каждый key — нужно, чтобы
    найти значения, которые были актуальны раньше, но с тех пор устарели
    (см. superseded_values() и scripts/check_stale_facts.py)."""
    history: dict[str, list[dict]] = {}
    for sig in signals:
        for fact in sig.get("facts", []) or []:
            key = fact["key"]
            history.setdefault(key, []).append({
                "value": fact["value"],
                "unit": fact["unit"],
                "as_of": fact["as_of"],
                "signal_id": sig["id"],
            })
    return history


def superseded_values(signals: list[dict]) -> dict[str, list]:
    """Для каждого key с более чем одним значением в истории — список
    значений (уникальных), которые НЕ являются текущим (по as_of). Именно
    эти значения не должны встречаться голым текстом в index.html вне
    data-fact-key — если встречаются, это забытая при миграции копия
    (см. scripts/check_stale_facts.py)."""
    history = history_of_facts(signals)
    resolved = resolve_facts(signals)
    result: dict[str, list] = {}
    for key, entries in history.items():
        current_value = resolved[key]["value"]
        stale = sorted({e["value"] for e in entries if e["value"] != current_value})
        if stale:
            result[key] = stale
    return result


def resolve_facts(signals: list[dict]) -> dict[str, dict]:
    """Для каждого встреченного key оставляет запись с максимальным as_of.
    При равенстве as_of — оставляет ту, что встретилась раньше в signals.json
    и печатает предупреждение (двусмысленность должна быть исправлена в
    данных, не молча замаскирована)."""
    resolved: dict[str, dict] = {}
    for sig in signals:
        for fact in sig.get("facts", []) or []:
            key = fact["key"]
            as_of = fact["as_of"]
            entry = {
                "value": fact["value"],
                "unit": fact["unit"],
                "as_of": as_of,
                "signal_id": sig["id"],
            }
            existing = resolved.get(key)
            if existing is None or as_of > existing["as_of"]:
                resolved[key] = entry
            elif as_of == existing["as_of"] and existing["signal_id"] != sig["id"]:
                print(
                    f"::warning::facts key '{key}' has two signals with the same "
                    f"as_of={as_of} ({existing['signal_id']} vs {sig['id']}) — "
                    f"keeping first encountered, resolve ambiguity in source data",
                    file=sys.stderr,
                )
    return resolved


def sync_treasury_holders(resolved: dict[str, dict]) -> int:
    """Сверяет TREASURY_HOLDERS.json.holders[].btc с фактами по известному
    маппингу имён. Правит и логирует расхождение — молчаливая правка
    без объяснения хуже, чем её отсутствие (принцип FACTS: видимость
    расхождения важнее тихой синхронизации). Возвращает число исправлений."""
    if not TREASURY_PATH.exists():
        return 0
    with open(TREASURY_PATH, encoding="utf-8") as f:
        treasury = json.load(f)
    holders = treasury.get("holders", [])
    fixed = 0
    for h in holders:
        key = TREASURY_NAME_TO_FACT_KEY.get(h.get("name"))
        if not key or key not in resolved:
            continue
        new_val = resolved[key]["value"]
        old_val = h.get("btc")
        if old_val != new_val:
            print(
                f"::warning::TREASURY_HOLDERS.json '{h['name']}': btc {old_val} → {new_val} "
                f"(по {resolved[key]['signal_id']}, as_of {resolved[key]['as_of']})",
                file=sys.stderr,
            )
            h["btc"] = new_val
            fixed += 1
    if fixed:
        with open(TREASURY_PATH, "w", encoding="utf-8") as f:
            json.dump(treasury, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return fixed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    signals = load_signals()
    resolved = resolve_facts(signals)

    payload = OrderedDict([
        ("_generated_by", "scripts/build_facts.py — не редактировать руками"),
        ("_source", "signals.json (facts[] по каждому сигналу)"),
        ("generated_at", date.today().isoformat()),
        ("facts", OrderedDict(sorted(resolved.items()))),
    ])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    fixed = sync_treasury_holders(resolved)
    print(f"OK: {args.out} — {len(resolved)} фактов из {len(signals)} сигналов"
          + (f"; TREASURY_HOLDERS.json: исправлено {fixed}" if fixed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
