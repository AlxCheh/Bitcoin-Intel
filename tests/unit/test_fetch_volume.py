"""
tests/unit/test_fetch_volume.py
Bitcoin Intel — тесты для scripts/fetch_volume.py.

КОНТЕКСТ
--------
Найдено 2026-08-16 при аудите упавших workflow (не связано с их падениями —
отдельная находка по ходу проверки на дыры в данных): `data/volume.json`
содержал 31 запись `history` на 30 уникальных дат — CoinGecko
`market_chart` вернул два разных [timestamp_ms, volume_usd] для одной
календарной даты (последняя точка не всегда выровнена на UTC-полночь,
несмотря на `interval=daily`).

Фикстура `DUPLICATE_TAIL_RESPONSE` ниже — не выдумка, а реконструкция
реального случая: два timestamp в один и тот же день (2026-08-16),
воспроизводящая структуру фактически наблюдавшегося дубля.
"""
import json
from pathlib import Path

import pytest

from scripts.fetch_volume import build_volume_payload

REPO_ROOT = Path(__file__).parent.parent.parent


def _ts(date_str: str, hour: int = 0) -> int:
    from datetime import datetime, timezone
    return int(datetime.strptime(f"{date_str} {hour:02d}:00", "%Y-%m-%d %H:%M")
                       .replace(tzinfo=timezone.utc).timestamp() * 1000)


CLEAN_RESPONSE = {
    "total_volumes": [
        [_ts("2026-08-14"), 18_880_823_922.24],
        [_ts("2026-08-15"), 20_041_539_781.64],
        [_ts("2026-08-16"), 10_409_218_158.40],
    ]
}

# Реконструкция реального случая: два timestamp одного дня подряд в конце —
# ровно так, как обнаружено в data/volume.json (31 запись / 30 дат).
DUPLICATE_TAIL_RESPONSE = {
    "total_volumes": [
        [_ts("2026-08-14"), 18_880_823_922.24],
        [_ts("2026-08-15"), 20_041_539_781.64],
        [_ts("2026-08-16", hour=0), 10_409_218_158.40],
        [_ts("2026-08-16", hour=23), 9_350_065_102.65],
    ]
}


class TestDeduplication:

    def test_no_duplicate_dates_in_history(self):
        payload = build_volume_payload(DUPLICATE_TAIL_RESPONSE)
        dates = [e["date"] for e in payload["history"]]
        assert len(dates) == len(set(dates)), f"дубли дат в history: {dates}"

    def test_duplicate_date_resolved_to_three_unique_entries(self):
        """4 сырые точки, 2 из них — один день -> 3 уникальные даты."""
        payload = build_volume_payload(DUPLICATE_TAIL_RESPONSE)
        assert len(payload["history"]) == 3

    def test_later_timestamp_wins_on_duplicate_date(self):
        """
        При дубле оставляем ПОСЛЕДНЮЮ по времени точку — более свежий снимок
        объёма за форминг-день, не первую по порядку в ответе API.
        """
        payload = build_volume_payload(DUPLICATE_TAIL_RESPONSE)
        entry = next(e for e in payload["history"] if e["date"] == "2026-08-16")
        assert entry["volume_usd"] == pytest.approx(9_350_065_102.65)

    def test_clean_response_unaffected_by_dedup_logic(self):
        """Ответ без дублей ведёт себя как раньше — дедуп не меняет обычный путь."""
        payload = build_volume_payload(CLEAN_RESPONSE)
        assert len(payload["history"]) == 3
        assert [e["date"] for e in payload["history"]] == ["2026-08-14", "2026-08-15", "2026-08-16"]

    def test_current_and_change_pct_computed_after_dedup(self):
        """
        current обязан отражать ПОСЛЕДНЮЮ уникальную дату после дедупа, не
        последнюю сырую точку — иначе change_24h_pct считался бы от дубля
        самого с собой (0% при любом реальном изменении объёма).
        """
        payload = build_volume_payload(DUPLICATE_TAIL_RESPONSE)
        assert payload["current"]["date"] == "2026-08-16"
        assert payload["current"]["volume_usd"] == pytest.approx(9_350_065_102.65)
        # previous — 2026-08-15, не дублирующая точка того же дня
        expected_pct = (9_350_065_102.65 - 20_041_539_781.64) / 20_041_539_781.64 * 100
        assert payload["current"]["change_24h_pct"] == pytest.approx(round(expected_pct, 2))


class TestErrors:

    def test_too_few_raw_points_raises(self):
        with pytest.raises(ValueError, match="недостаточно точек"):
            build_volume_payload({"total_volumes": [[_ts("2026-08-16"), 100.0]]})

    def test_all_points_same_date_raises_with_diagnostic(self):
        """
        Экстремальный край: все сырые точки схлопнулись в одну дату —
        change_24h_pct считать не из чего, падать с внятным сообщением,
        не с IndexError на history[-2].
        """
        same_day = {"total_volumes": [
            [_ts("2026-08-16", hour=0), 100.0],
            [_ts("2026-08-16", hour=12), 110.0],
        ]}
        with pytest.raises(ValueError, match="дедупликации"):
            build_volume_payload(same_day)


class TestPayloadShape:

    def test_source_and_updated_at_present(self):
        payload = build_volume_payload(CLEAN_RESPONSE)
        assert payload["source"] == "CoinGecko market_chart (daily)"
        assert "updated_at" in payload

    def test_volume_rounded_to_two_decimals(self):
        payload = build_volume_payload({"total_volumes": [
            [_ts("2026-08-15"), 100.123456],
            [_ts("2026-08-16"), 200.987654],
        ]})
        assert payload["history"][0]["volume_usd"] == 100.12
        assert payload["history"][1]["volume_usd"] == 200.99


class TestCommittedFile:

    def test_committed_output_has_no_duplicate_dates(self):
        """
        Регрессия на сам факт находки: data/volume.json в репозитории не
        должен содержать двух записей history на одну дату. Ловит ситуацию,
        когда build_volume_payload() починили, но файл не перегенерировали.
        """
        data = json.loads((REPO_ROOT / "data" / "volume.json").read_text(encoding="utf-8"))
        dates = [e["date"] for e in data["history"]]
        assert len(dates) == len(set(dates)), (
            f"data/volume.json содержит дубли дат: {[d for d in dates if dates.count(d) > 1]} — "
            "перегенерировать: python scripts/fetch_volume.py"
        )
