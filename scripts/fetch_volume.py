"""
scripts/fetch_volume.py
Bitcoin Intel — дневной объём торгов BTC/USD для карточки на сайте.

Источник — CoinGecko API, эндпоинт market_chart (days=30, interval=daily).
Используется только он: total_volumes уже содержит дневные точки объёма,
последняя точка приближает текущий 24ч объём — второй эндпоинт (coins/bitcoin)
не нужен, это экономит вызов API и не критично для точности здесь: карточка
показывает дневную (не секундную) метрику, обновляется раз в сутки.

Не относится к сигналам (signals.json/SIGNALS.md) — это техническая метрика
сайта, а не элемент нарративного анализа (см. CLAUDE.md).

Использование:
    python3 scripts/fetch_volume.py
    python3 scripts/fetch_volume.py --out data/volume.json --days 30
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "data" / "volume.json"

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
DAYS_DEFAULT = 30
REQUEST_TIMEOUT_SECONDS = 15


def fetch_market_chart(days: int) -> dict:
    """Запрашивает market_chart у CoinGecko. Поднимает исключение при ошибке —
    вызывающий код (main) решает, что делать (в workflow это провалит шаг,
    и волатильные данные CoinGecko не запишутся поверх последних валидных)."""
    params = {"vs_currency": "usd", "days": days, "interval": "daily"}
    resp = requests.get(COINGECKO_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()


def build_volume_payload(raw: dict) -> dict:
    """Строит финальный JSON карточки из сырого ответа CoinGecko.

    raw['total_volumes'] — список [timestamp_ms, volume_usd], по одному в день.
    """
    points = raw.get("total_volumes", [])
    if len(points) < 2:
        raise ValueError(
            f"CoinGecko вернул недостаточно точек объёма: {len(points)} (нужно ≥2)"
        )

    history = [
        {
            "date": datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
            "volume_usd": round(volume, 2),
        }
        for ts_ms, volume in points
    ]

    current = history[-1]
    previous = history[-2]
    change_pct = (
        (current["volume_usd"] - previous["volume_usd"]) / previous["volume_usd"] * 100
        if previous["volume_usd"]
        else None
    )

    return {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "CoinGecko market_chart (daily)",
        "current": {
            "date": current["date"],
            "volume_usd": current["volume_usd"],
            "change_24h_pct": round(change_pct, 2) if change_pct is not None else None,
        },
        "history": history,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--days", type=int, default=DAYS_DEFAULT)
    args = parser.parse_args()

    try:
        raw = fetch_market_chart(args.days)
        payload = build_volume_payload(raw)
    except Exception as exc:  # noqa: BLE001 — любая ошибка сети/данных должна провалить шаг CI явно
        print(f"::error::Не удалось собрать data/volume.json: {exc}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: {args.out} обновлён, {len(payload['history'])} точек, "
          f"текущий объём {payload['current']['volume_usd']:,.0f} USD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
