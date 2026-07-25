"""
scripts/fetch_top_addresses.py
Bitcoin Intel — Топ-100 богатейших BTC-адресов для панели вкладки ХОЛДЕРЫ.

⚠️ НЕПРОВЕРЕНО ПРИ НАПИСАНИИ (2026-07-25) — см. обсуждение в чате. Написан
по задокументированному, но лично не выполненному синтаксису Blockchair API
(интерактивная сессия не имеет сетевого доступа к blockchair.com — тот же
класс ограничения, что обсуждался для эмбеддингов, ADR-018 Фаза 3). ПЕРЕД
тем, как полагаться на данные этого скрипта, требуется хотя бы один
успешный прогон в GitHub Actions CI (обычный доступ в интернет) — см.
.github/workflows/update-top-addresses.yml. Если реальный формат ответа
API отличается от предполагаемого здесь — это обнаружится там, не раньше.

ИСТОЧНИК ДАННЫХ: Blockchair (api.blockchair.com) — общедоступный,
бесплатный без ключа тариф (1000-1440 запросов/день, см. обсуждение).
Предполагаемый эндпоинт (по документированному синтаксису Infinitable-
запросов, НЕ проверен лично):
    https://api.blockchair.com/bitcoin/addresses?limit=100&s=balance(desc)

МЕТОДОЛОГИЧЕСКОЕ ОГРАНИЧЕНИЕ (тот же класс, что уже зафиксирован в
SUP-2026-0702-001/SUP-2026-0719-001): это сырые адреса, не сущности.
Один держатель может владеть несколькими адресами; биржевой холодный
кошелёк считается наравне с частным китом. Glassnode's own research
прямо критикует именно такой подход (entity-adjusted кластеризация
доступна только в их платном Professional-тарифе — см. обсуждение в чате).

МЕТКИ: Blockchair не даёт публичной базы меток известных адресов (только
пользовательские теги). Читаемые названия (Binance-coldwallet и т.п.)
берутся из data/known_addresses.json — курируется вручную, тот же
принцип, что TREASURY_HOLDERS.json/ENTITIES.json, не обновляется этим
скриптом автоматически. Адрес без записи в known_addresses.json получает
category="unknown".

Использование:
    python3 scripts/fetch_top_addresses.py
    python3 scripts/fetch_top_addresses.py --out data/top_addresses.json --limit 100
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

BLOCKCHAIR_URL = "https://api.blockchair.com/bitcoin/addresses"
LIMIT_DEFAULT = 100
REQUEST_TIMEOUT_SECONDS = 20


def load_known_addresses(path: Path = KNOWN_ADDRESSES_PATH) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("addresses", {})


def fetch_top_addresses(limit: int) -> dict:
    """
    Запрашивает топ-N адресов по балансу у Blockchair.

    ⚠️ Синтаксис параметров (s=balance(desc)) — по документированному
    формату Infinitable-запросов Blockchair (аналогичному их же примерам
    для /bitcoin/blocks: ?a=month,sum(size)), НЕ подтверждён личным
    вызовом. Реальные имена полей ответа могут отличаться от
    предполагаемых build_top_addresses_payload() ниже — это первое, что
    нужно сверить при первом реальном прогоне в CI.
    """
    params = {"limit": limit, "s": "balance(desc)"}
    resp = requests.get(BLOCKCHAIR_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()


def classify_and_label(address: str, known: dict) -> tuple[str | None, str]:
    """Возвращает (label, category) для адреса — из known_addresses.json,
    либо (None, 'unknown') если записи нет."""
    entry = known.get(address)
    if entry is None:
        return None, "unknown"
    return entry.get("label"), entry.get("category", "unknown")


def build_top_addresses_payload(raw: dict, known: dict) -> dict:
    """
    Строит финальный JSON панели из сырого ответа Blockchair.

    ⚠️ ПРЕДПОЛАГАЕМАЯ структура raw['data'] — список объектов с полями
    'address' (str) и 'balance' (int, сатоши) — стандартный для
    dashboard-эндпоинтов Blockchair формат, но НЕ подтверждён лично для
    именно этого эндпоинта. Сверить при первом реальном прогоне.
    """
    rows = raw.get("data", [])
    if not rows:
        raise ValueError("Blockchair вернул пустой список адресов — проверить структуру ответа")

    total_supply_sats = 21_000_000 * 100_000_000
    entries = []
    for i, row in enumerate(rows, start=1):
        address = row.get("address")
        balance_sats = row.get("balance")
        if address is None or balance_sats is None:
            raise ValueError(
                f"Неожиданная структура строки #{i} от Blockchair: {row!r} — "
                "проверить реальный формат ответа API (см. предупреждение в шапке файла)"
            )
        balance_btc = balance_sats / 100_000_000
        label, category = classify_and_label(address, known)
        entries.append({
            "rank": i,
            "address": address,
            "label": label,
            "category": category,
            "balance_btc": round(balance_btc, 8),
            "pct_of_supply": round(balance_sats / total_supply_sats * 100, 6),
        })

    return {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "Blockchair API (api.blockchair.com/bitcoin/addresses)",
        "labels_source": "data/known_addresses.json (курируется вручную)",
        "caveat": (
            "Сырые адреса, не сущности — один держатель может владеть несколькими "
            "адресами; биржевой холодный кошелёк считается наравне с частным китом. "
            "Метки за пределами known_addresses.json помечены как unknown."
        ),
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=LIMIT_DEFAULT)
    args = parser.parse_args()

    try:
        known = load_known_addresses()
        raw = fetch_top_addresses(args.limit)
        payload = build_top_addresses_payload(raw, known)
    except Exception as exc:  # noqa: BLE001 — любая ошибка сети/данных должна провалить шаг CI явно
        print(f"::error::Не удалось собрать {DEFAULT_OUT.name}: {exc}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: {args.out} обновлён, {len(payload['entries'])} адресов")
    return 0


if __name__ == "__main__":
    sys.exit(main())
