"""
scripts/check_synthesis_freshness.py
Bitcoin Intel — IRP v1 Wave 4 / OP05 (MON03/MON04: Alerting при деградации
synthesis, synthesis freshness мониторинг).

Проверяет две независимые вещи:

1. АБСОЛЮТНАЯ СВЕЖЕСТЬ: ни один кластер в synthesis_cache.json не
   перестраивался дольше STALE_THRESHOLD_DAYS. Это канарейка на случай,
   если сама "Synthesize Narratives" job в deploy.yml молча ломается
   (permissions, quota, баг) — при рабочем пайплайне generated_at
   обновляется почти сразу после каждого push с изменением signals.json
   (deploy.yml job "Synthesize Narratives"), поэтому реалистичный порог
   заведомо больше типичного интервала между сигналами.

2. РАССИНХРОНИЗАЦИЯ С СИГНАЛАМИ: есть ли сигнал в signals.json новее, чем
   generated_at его кластера в synthesis_cache.json — конкретный признак
   того, что кеш пропустил реальное обновление (не просто "давно не
   было новых сигналов", а "новый сигнал есть, а кеш его не увидел").
   Это сильнее и специфичнее (1), не привязано к произвольному порогу.

Exit codes (см. config/settings.py ERROR_EXIT_CODES):
    0 — всё свежо
    1 — обнаружена деградация (стухший кеш и/или рассинхронизация)
    2 — файлы не найдены / не парсятся (system_error)

Использование:
    python3 scripts/check_synthesis_freshness.py [--stale-days N]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SIGNALS_PATH = REPO_ROOT / "signals.json"
SYNTHESIS_CACHE_PATH = REPO_ROOT / "data" / "synthesis_cache.json"

STALE_THRESHOLD_DAYS_DEFAULT = 14  # см. docstring выше про почему не 1-2 дня


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def check_absolute_staleness(cache: dict, threshold_days: int) -> list[str]:
    """Возвращает список проблем: кластеры старше threshold_days."""
    problems = []
    now = datetime.now(timezone.utc)
    for cluster_key, entry in cache.items():
        generated_at = entry.get("generated_at")
        if not generated_at:
            problems.append(f"{cluster_key}: нет поля generated_at")
            continue
        age_days = (now - _parse_iso(generated_at)).total_seconds() / 86400
        if age_days > threshold_days:
            problems.append(
                f"{cluster_key}: не перестраивался {age_days:.1f} дней "
                f"(порог {threshold_days})"
            )
    return problems


def check_signal_cache_desync(signals: list[dict], cache: dict) -> list[str]:
    """
    Возвращает список проблем: сигналы новее generated_at своего кластера.
    """
    problems = []
    cluster_generated_at = {
        k: _parse_iso(v["generated_at"])
        for k, v in cache.items()
        if v.get("generated_at")
    }
    for s in signals:
        cluster = s.get("cluster")
        if cluster not in cluster_generated_at:
            continue  # кластер ещё не синтезирован — не проблема freshness
        try:
            signal_date = datetime.fromisoformat(s["date"]).replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        if signal_date > cluster_generated_at[cluster]:
            problems.append(
                f"{s.get('id', '?')}: дата сигнала {s['date']} новее "
                f"generated_at кластера '{cluster}' "
                f"({cluster_generated_at[cluster].date().isoformat()})"
            )
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stale-days", type=int, default=STALE_THRESHOLD_DAYS_DEFAULT,
        help=f"Порог абсолютной свежести в днях (default: {STALE_THRESHOLD_DAYS_DEFAULT})"
    )
    args = parser.parse_args()

    try:
        with open(SIGNALS_PATH, encoding="utf-8") as f:
            signals = json.load(f)["signals"]
        with open(SYNTHESIS_CACHE_PATH, encoding="utf-8") as f:
            cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"✗ Не удалось прочитать входные файлы: {e}")
        sys.exit(2)

    staleness_problems = check_absolute_staleness(cache, args.stale_days)
    desync_problems = check_signal_cache_desync(signals, cache)
    all_problems = staleness_problems + desync_problems

    if not all_problems:
        print(
            f"✓ synthesis_cache.json свеж: {len(cache)} кластеров, "
            f"все моложе {args.stale_days} дней, рассинхронизации с "
            f"signals.json не обнаружено"
        )
        sys.exit(0)

    print(f"✗ Обнаружена деградация freshness ({len(all_problems)}):")
    for p in staleness_problems:
        print(f"  [STALE] {p}")
    for p in desync_problems:
        print(f"  [DESYNC] {p}")
    sys.exit(1)


if __name__ == "__main__":
    main()
