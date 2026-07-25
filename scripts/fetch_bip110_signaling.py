"""
scripts/fetch_bip110_signaling.py
Bitcoin Intel — процент майнерского сигналинга BIP-110 за текущий период
сложности, для мини-панели на вкладке АНАЛИТИКА (рядом со "Сложность
сети"/"Хешрейт сети").

⚠️ ЧАСТИЧНО НЕПРОВЕРЕНО ПРИ НАПИСАНИИ (2026-07-25) — см. обсуждение в чате.
mempool.space уже используется сайтом для diff-chart/hashrateChart (клиент-
ские live-fetch'и, проверенные в проде), поэтому базовый эндпоинт доверия
заслуживает больше, чем непроверенный Blockchair — но конкретно пагинация
по 15 блоков назад до начала периода (см. ниже) лично не прогонялась
(сессия не имеет сетевого доступа к mempool.space). Первый прогон в CI
(.github/workflows/update-bip110-signaling.yml) — первая реальная проверка.

ПОЧЕМУ НЕ BGeometrics / bip110monitor.com — см. обсуждение в чате:
BGeometrics даёт эту метрику только начиная с платного тарифа (не
проверено бесплатно), у bip110monitor.com robots.txt явно запрещает
автоматический доступ к /api. Считаем сами — mempool.space уже разрешён
и используется сайтом, у BIP9-сигналинга простая, документированная
формула (см. is_bip9_signaling ниже), сторонний посредник не нужен.

ПОЧЕМУ СЕРВЕРНЫЙ СКРИПТ, А НЕ CLIENT-SIDE LIVE-FETCH (как diff-chart):
один период сложности — 2016 блоков; публичный тариф mempool.space отдаёт
максимум 15 блоков за вызов (/api/v1/blocks) — то есть ~135 запросов на
полный период. Делать это в браузере КАЖДОГО посетителя при каждой
загрузке страницы — нагружало бы mempool.space пропорционально трафику
сайта. Здесь — один периодический прогон в CI, клиент читает готовый
маленький JSON (тот же паттерн, что data/volume.json/top_addresses.json).

Использование:
    python3 scripts/fetch_bip110_signaling.py
    python3 scripts/fetch_bip110_signaling.py --out data/bip110_signaling.json
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "data" / "bip110_signaling.json"

MEMPOOL_BASE = "https://mempool.space/api"
PERIOD_SIZE = 2016  # блоков в периоде сложности (BIP9 tally window)
BIP110_BIT = 4  # см. NAR-2026-0717-002 / bip110monitor.com FAQ
DEADLINE_BLOCK = 961_632  # см. NAR-2026-0717-002 — конец добровольного окна
ACTIVATION_THRESHOLD_PCT = 55.0
REQUEST_TIMEOUT_SECONDS = 15
MAX_PAGES_SAFETY = 200  # 200*15=3000 блоков — с запасом больше одного периода; защита от бесконечного цикла при неожиданном формате ответа


def is_bip9_signaling(version: int, bit: int = BIP110_BIT) -> bool:
    """
    BIP9: top 3 бита version должны быть 001 (маска 0xE0000000 == 0x20000000)
    — отличает намеренный BIP9-сигналинг от произвольных версий старых
    майнеров, которые могут случайно иметь этот бит выставленным. Плюс сам
    бит должен быть установлен. См. bip110monitor.com FAQ (та же логика).
    """
    return (version & 0xE0000000) == 0x20000000 and bool(version & (1 << bit))


def fetch_tip_height() -> int:
    resp = requests.get(f"{MEMPOOL_BASE}/blocks/tip/height", timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return int(resp.text)


def fetch_blocks_page(start_height: int) -> list[dict]:
    """Возвращает до 15 блоков, заканчивая на start_height (по убыванию высоты)."""
    resp = requests.get(f"{MEMPOOL_BASE}/v1/blocks/{start_height}", timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()


def collect_period_blocks(tip_height: int, period_start_height: int) -> list[dict]:
    """
    Постранично (по 15 блоков) собирает все блоки текущего периода —
    от tip_height назад до period_start_height включительно.
    """
    blocks: dict[int, dict] = {}
    cursor = tip_height
    pages = 0
    while cursor >= period_start_height:
        pages += 1
        if pages > MAX_PAGES_SAFETY:
            raise RuntimeError(
                f"Превышен предохранитель в {MAX_PAGES_SAFETY} страниц — "
                "вероятно, реальный формат ответа mempool.space отличается "
                "от предполагаемого (высоты не убывают как ожидалось)"
            )
        page = fetch_blocks_page(cursor)
        if not page:
            break
        for b in page:
            h = b.get("height")
            if h is not None and h >= period_start_height:
                blocks[h] = b
        min_height_on_page = min(b["height"] for b in page if "height" in b)
        if min_height_on_page >= cursor:
            # Страница не продвинулась — защита от зацикливания при
            # неожиданной структуре ответа.
            raise RuntimeError(
                f"Страница блоков не продвинулась (cursor={cursor}, "
                f"min_height={min_height_on_page}) — проверить формат ответа API"
            )
        cursor = min_height_on_page - 1
        time.sleep(0.05)  # вежливая пауза между запросами, не бьём API как можно чаще
    return list(blocks.values())


def build_payload(tip_height: int, blocks: list[dict], period: int, period_start: int) -> dict:
    if not blocks:
        raise ValueError("Не собрано ни одного блока текущего периода — проверить формат ответа API")

    signaling = [b for b in blocks if is_bip9_signaling(b.get("version", 0))]
    blocks_counted = len(blocks)
    signal_pct = round(len(signaling) / blocks_counted * 100, 4) if blocks_counted else 0.0

    return {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "mempool.space (посчитано самостоятельно из nVersion, не сторонний агрегатор)",
        "current": {
            "period": period,
            "tip_height": tip_height,
            "period_start_height": period_start,
            "blocks_counted": blocks_counted,
            "period_size": PERIOD_SIZE,
            "signaling_blocks": len(signaling),
            "signal_pct": signal_pct,
            "threshold_pct": ACTIVATION_THRESHOLD_PCT,
            "deadline_block": DEADLINE_BLOCK,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    try:
        tip_height = fetch_tip_height()
        period = tip_height // PERIOD_SIZE
        period_start = period * PERIOD_SIZE
        blocks = collect_period_blocks(tip_height, period_start)
        payload = build_payload(tip_height, blocks, period, period_start)
    except Exception as exc:  # noqa: BLE001 — любая ошибка сети/данных должна провалить шаг CI явно
        print(f"::error::Не удалось собрать {DEFAULT_OUT.name}: {exc}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    c = payload["current"]
    print(f"OK: {args.out} обновлён — период {c['period']}, {c['signal_pct']}% "
          f"({c['signaling_blocks']}/{c['blocks_counted']} блоков)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
