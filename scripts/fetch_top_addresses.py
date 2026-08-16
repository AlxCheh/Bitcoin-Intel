"""
scripts/fetch_top_addresses.py
Bitcoin Intel — крупнейшие известные BTC-адреса для панели вкладки ХОЛДЕРЫ.

ЧТО ЭТО ЗА ВЫБОРКА — ЧИТАТЬ ПЕРВЫМ
-----------------------------------
Скрипт считает балансы адресов из курируемого списка `data/known_addresses.json`
и ранжирует ИХ. Это **не** рейтинг богатейших адресов сети Bitcoin: адрес, не
попавший в курируемый список, здесь не появится, каким бы крупным он ни был.

Разница принципиальная и отражена в названии панели («Крупнейшие известные
адреса», не «Топ-100 богатейших»). Бесплатного API, отдающего ранжированный
топ всех адресов сети, найти не удалось — см. историю ниже.

ИСТОРИЯ ИСТОЧНИКА (2026-07-25 → 2026-08-16)
--------------------------------------------
Первая версия обращалась к Blockchair (`api.blockchair.com/bitcoin/addresses`)
и была написана по документированному, но лично не выполненному синтаксису —
в шапке файла честно стояло предупреждение «требуется хотя бы один успешный
прогон в CI, прежде чем полагаться на данные».

Прогон состоялся — и провалился. Workflow падал **ежедневно 22 дня подряд,
0 успешных прогонов за всё время существования**, а панель показывала данные
от 25 июля (честно датированные, читателя они не вводили в заблуждение).
Никто не смотрел результат, потому что красный шедулер не блокирует PR.

Причина, установленная прямым запросом 2026-08-16:

    HTTP 430: "Your IP address is temporary blacklisted due to exceeding
    usage of API resources. Please apply for an API key by contacting us
    at info@blockchair.com"

430 приходит и с раннеров GitHub Actions, и с локальной машины, притом что
проект делал 1 запрос в сутки — то есть блокировка вызвана не его нагрузкой,
бесплатный тариф без ключа для этих диапазонов IP просто закрыт.

Заодно опровергнуто утверждение прежней шапки, будто интерактивная сессия не
имеет сетевого доступа к blockchair.com. Доступ есть; проверка занимает
10 секунд. Из-за той записи никто не проверил очевидное.

ТЕКУЩИЙ ИСТОЧНИК
----------------
`blockchain.info/balance?active=<addr1|addr2|...>` — публичный эндпоинт без
ключа, **проверен фактически** (2026-08-16): один запрос на все 38 адресов
списка, HTTP 200, балансы сходятся с прежними данными Blockchair
(Binance-coldwallet 248 597 BTC).

Один batch-запрос вместо N поштучных — и вежливее к бесплатному сервису,
и устойчивее: нет частичного результата, когда половина адресов получена.

МЕТОДОЛОГИЧЕСКОЕ ОГРАНИЧЕНИЕ (не изменилось, тот же класс, что в
SUP-2026-0702-001/SUP-2026-0719-001): это сырые адреса, не сущности. Один
держатель может владеть несколькими адресами; биржевой холодный кошелёк
считается наравне с частным китом.

МЕТКИ: `data/known_addresses.json` курируется вручную — тот же принцип, что
`TREASURY_HOLDERS.json`/`ENTITIES.json`. Этот скрипт список НЕ пополняет.

Использование:
    python3 scripts/fetch_top_addresses.py
    python3 scripts/fetch_top_addresses.py --out data/top_addresses.json --limit 10
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "data" / "top_addresses.json"
KNOWN_ADDRESSES_PATH = REPO_ROOT / "data" / "known_addresses.json"

BALANCE_URL = "https://blockchain.info/balance"
LIMIT_DEFAULT = 10
REQUEST_TIMEOUT_SECONDS = 30
SATS_PER_BTC = 100_000_000
TOTAL_SUPPLY_SATS = 21_000_000 * SATS_PER_BTC


def load_known_addresses(path: Path = KNOWN_ADDRESSES_PATH) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("addresses", {})


def fetch_balances(addresses: list[str]) -> dict:
    """
    Балансы всех адресов ОДНИМ запросом (blockchain.info принимает список
    через `|`). Формат ответа проверен вживую 2026-08-16:

        {"<address>": {"final_balance": <сатоши>, "n_tx": ..., "total_received": ...}}

    Одиночный batch выбран сознательно: N поштучных запросов к бесплатному
    сервису и невежливы, и дают частичный результат при обрыве на середине.
    """
    if not addresses:
        raise ValueError("Пустой список адресов — проверить data/known_addresses.json")

    resp = requests.get(
        BALANCE_URL,
        params={"active": "|".join(addresses)},
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={"User-Agent": "Bitcoin-Intel/1.0 (github.com/AlxCheh/Bitcoin-Intel)"},
    )
    resp.raise_for_status()
    return resp.json()


def build_top_addresses_payload(balances: dict, known: dict, limit: int) -> dict:
    """
    Ранжирует известные адреса по балансу и берёт top-N.

    Адрес, который есть в курируемом списке, но не вернулся из API,
    пропускается с явной пометкой в `missing_addresses` — молча терять
    записи нельзя: это выглядело бы как «баланс упал до нуля».
    """
    if not balances:
        raise ValueError("API вернул пустой ответ — проверить структуру blockchain.info/balance")

    rows = []
    missing = []
    for address in known:
        record = balances.get(address)
        if record is None or "final_balance" not in record:
            missing.append(address)
            continue
        rows.append((address, int(record["final_balance"])))

    if not rows:
        raise ValueError(
            "Ни по одному адресу не получен баланс — формат ответа изменился? "
            f"Ключи ответа: {list(balances)[:3]}"
        )

    # Сортировка: баланс DESC, затем адрес ASC — детерминированность при равных
    # балансах (тот же принцип, что 4-уровневый tiebreaker в synthesizer.py)
    rows.sort(key=lambda r: (-r[1], r[0]))

    entries = []
    for rank, (address, balance_sats) in enumerate(rows[:limit], start=1):
        entry = known[address]
        entries.append({
            "rank": rank,
            "address": address,
            "label": entry.get("label"),
            "category": entry.get("category", "unknown"),
            "balance_btc": round(balance_sats / SATS_PER_BTC, 8),
            "pct_of_supply": round(balance_sats / TOTAL_SUPPLY_SATS * 100, 6),
        })

    payload = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "blockchain.info/balance (балансы) + data/known_addresses.json (состав выборки)",
        "labels_source": "data/known_addresses.json (курируется вручную)",
        "caveat": (
            "ВЫБОРКА ОГРАНИЧЕНА КУРИРУЕМЫМ СПИСКОМ: это крупнейшие среди "
            f"{len(known)} отслеживаемых адресов, а НЕ рейтинг богатейших адресов сети — "
            "адрес, не попавший в data/known_addresses.json, здесь не появится, каким бы "
            "крупным он ни был. Кроме того это сырые адреса, не сущности: один держатель "
            "может владеть несколькими адресами; биржевой холодный кошелёк считается "
            "наравне с частным китом."
        ),
        "tracked_addresses": len(known),
        "entries": entries,
    }
    if missing:
        payload["missing_addresses"] = sorted(missing)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=LIMIT_DEFAULT)
    args = parser.parse_args()

    try:
        known = load_known_addresses()
        balances = fetch_balances(list(known))
        payload = build_top_addresses_payload(balances, known, args.limit)
    except Exception as exc:  # noqa: BLE001 — любая ошибка сети/данных должна провалить шаг CI явно
        print(f"::error::Не удалось собрать {DEFAULT_OUT.name}: {exc}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    missing = payload.get("missing_addresses", [])
    note = f", пропущено без баланса: {len(missing)}" if missing else ""
    print(f"OK: {args.out} обновлён, {len(payload['entries'])} адресов из {payload['tracked_addresses']} отслеживаемых{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
