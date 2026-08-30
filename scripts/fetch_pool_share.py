"""
scripts/fetch_pool_share.py
Bitcoin Intel — совокупная доля топ-3 майнинг-пулов по хешрейту, для
детектора порогов (data/pipeline_watch_rules.json, см. docs/ADR-019).

ЗАЧЕМ
-----
Ту же метрику уже дважды считали вручную в этой сессии: при разборе
INF-2026-0731-001 (закрытие пула SBI — независимая проверка mempool.space
опровергла причинность, подразумеваемую заголовком источника) и при
backfill'е network.top3_pool_share в facts.json. Оба раза — одноразовый
запрос, не живой трекер. Этот скрипт делает то же самое регулярно, тем же
паттерном, что уже работает для data/bip110_signaling.json: сервер считает
сам из первичных данных mempool.space (не сторонний агрегатор), клиент
получает готовый маленький JSON.

Один запрос, без пагинации — /api/v1/mining/hashrate/pools/:period уже
отдаёт агрегированные доли пулов за период, в отличие от bip110_signaling,
которому нужны версии отдельных блоков (такого готового агрегата
mempool.space не даёт).

Период — 1w (неделя): совпадает с методологией верификации в
INF-2026-0731-001 (сравнение недельных бакетов), не 1m — недельное окно
чувствительнее к текущему раскладу, месячное сглаживает недавние сдвиги.

Использование:
    python3 scripts/fetch_pool_share.py
    python3 scripts/fetch_pool_share.py --out data/pool_share.json --period 1w
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "data" / "pool_share.json"

MEMPOOL_BASE = "https://mempool.space/api"
DEFAULT_PERIOD = "1w"
REQUEST_TIMEOUT_SECONDS = 15
TOP_N = 3


def fetch_pool_shares(period: str) -> list[dict]:
    resp = requests.get(f"{MEMPOOL_BASE}/v1/mining/hashrate/pools/{period}", timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list) or not data:
        raise ValueError(f"Неожиданный формат ответа mempool.space: {type(data)} — проверить API")
    for row in data:
        if "poolName" not in row or "share" not in row:
            raise ValueError(f"Отсутствуют ожидаемые поля poolName/share в ответе: {row}")
    return data


def build_payload(pools: list[dict], period: str) -> dict:
    # Защитно сортируем сами, а не полагаемся на то, что API всегда отдаёт
    # по убыванию — документация это обещает, но не проверять дешевле, чем
    # получить молча неверный "топ-3" при изменении поведения апстрима.
    ranked = sorted(pools, key=lambda p: p["share"], reverse=True)
    top = ranked[:TOP_N]
    top_share_pct = round(sum(p["share"] for p in top) * 100, 2)

    return {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "mempool.space (/v1/mining/hashrate/pools, не сторонний агрегатор)",
        "current": {
            "period": period,
            "pools_reported": len(ranked),
            "top_pools": [
                {"name": p["poolName"], "share_pct": round(p["share"] * 100, 2)}
                for p in top
            ],
            "top3_share_pct": top_share_pct,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--period", default=DEFAULT_PERIOD, help="Период mempool.space: 24h/3d/1w/1m/3m/6m/1y/2y/3y")
    args = parser.parse_args()

    try:
        pools = fetch_pool_shares(args.period)
        payload = build_payload(pools, args.period)
    except Exception as exc:  # noqa: BLE001 — любая ошибка сети/данных должна провалить шаг CI явно
        print(f"::error::Не удалось собрать {args.out.name}: {exc}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    c = payload["current"]
    names = ", ".join(p["name"] for p in c["top_pools"])
    print(f"OK: {args.out} обновлён — топ-3 ({names}) = {c['top3_share_pct']}% за {c['period']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
