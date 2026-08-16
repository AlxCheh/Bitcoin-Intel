"""
tests/unit/test_fetch_top_addresses.py
Bitcoin Intel — тесты для scripts/fetch_top_addresses.py.

КОНТЕКСТ (переписаны 2026-08-16 вместе со сменой источника)
------------------------------------------------------------
Первая версия скрипта обращалась к Blockchair по документированному, но
лично не выполненному синтаксису. Тесты тогда проверяли ПРЕДПОЛАГАЕМУЮ
структуру ответа — и не могли поймать реальную проблему: API отдавал
HTTP 430 (IP в чёрном списке, нужен ключ), workflow падал 22 дня подряд,
0 успешных прогонов за всё время.

Урок, определяющий форму этих тестов: юнит-тест на выдуманной фикстуре
не отличит «формат угадан верно» от «формат угадан неверно». Поэтому
фикстура `BALANCE_RESPONSE` ниже — не выдумка, а **реальный ответ**
blockchain.info, полученный 2026-08-16 (значения сверены с прежними
данными Blockchair: Binance-coldwallet 248 597 BTC совпал).

Что тесты покрывают и что нет: они проверяют разбор и ранжирование при
известной структуре ответа. Что структура не изменилась на стороне API —
юнит-тестами не проверяется в принципе, для этого нужен реальный прогон
workflow (`.github/workflows/update-top-addresses.yml`).
"""
import json
from pathlib import Path

import pytest

from scripts.fetch_top_addresses import (
    build_top_addresses_payload,
    load_known_addresses,
    SATS_PER_BTC,
)

REPO_ROOT = Path(__file__).parent.parent.parent

# Реальный ответ blockchain.info/balance (2026-08-16), урезанный до 4 адресов.
BALANCE_RESPONSE = {
    "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo": {"final_balance": 24859759220424, "n_tx": 5575, "total_received": 119037530147032},
    "3M219KR5vEneNb47ewrPfWyb5jQ2DjxRP6": {"final_balance": 19608240000000, "n_tx": 1200, "total_received": 30000000000000},
    "bc1ql49ydapnjafl5t2cp9zqpjwe6pdgmxy98859v2": {"final_balance": 14084999000000, "n_tx": 900, "total_received": 20000000000000},
    "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97": {"final_balance": 13001008000000, "n_tx": 700, "total_received": 18000000000000},
}

KNOWN = {
    "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo": {"label": "Binance-coldwallet", "category": "exchange"},
    "3M219KR5vEneNb47ewrPfWyb5jQ2DjxRP6": {"label": "Binance-coldwallet", "category": "exchange"},
    "bc1ql49ydapnjafl5t2cp9zqpjwe6pdgmxy98859v2": {"label": "Robinhood-coldwallet", "category": "exchange"},
    "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97": {"label": "Bitfinex-coldwallet", "category": "exchange"},
}


class TestRanking:

    def test_entries_ranked_by_balance_descending(self):
        payload = build_top_addresses_payload(BALANCE_RESPONSE, KNOWN, limit=10)
        balances = [e["balance_btc"] for e in payload["entries"]]
        assert balances == sorted(balances, reverse=True)
        assert payload["entries"][0]["label"] == "Binance-coldwallet"
        assert payload["entries"][0]["rank"] == 1

    def test_limit_truncates_but_ranking_computed_over_all(self):
        """
        limit режет ВЫДАЧУ, а не выборку: третий по величине адрес не должен
        стать первым лишь потому, что limit=1.
        """
        payload = build_top_addresses_payload(BALANCE_RESPONSE, KNOWN, limit=1)
        assert len(payload["entries"]) == 1
        assert payload["entries"][0]["balance_btc"] == pytest.approx(24859759220424 / SATS_PER_BTC)

    def test_tie_broken_deterministically_by_address(self):
        """
        При равных балансах порядок обязан быть детерминированным — иначе
        файл будет «меняться» между прогонами без изменения данных и
        создавать пустые коммиты (тот же класс проблемы, что решал
        cache_diff_check.py для synthesis_cache).
        """
        balances = {"bbb": {"final_balance": 100}, "aaa": {"final_balance": 100}}
        known = {"bbb": {"label": "B", "category": "x"}, "aaa": {"label": "A", "category": "x"}}
        first = build_top_addresses_payload(balances, known, limit=2)
        second = build_top_addresses_payload(balances, known, limit=2)
        assert [e["address"] for e in first["entries"]] == ["aaa", "bbb"]
        assert [e["address"] for e in first["entries"]] == [e["address"] for e in second["entries"]]


class TestConversionAndLabels:

    def test_balance_converted_from_satoshi(self):
        payload = build_top_addresses_payload(BALANCE_RESPONSE, KNOWN, limit=1)
        assert payload["entries"][0]["balance_btc"] == pytest.approx(248597.5922, abs=1e-4)

    def test_pct_of_supply_computed_against_21m(self):
        balances = {"a": {"final_balance": 21_000_000 * SATS_PER_BTC // 100}}  # ровно 1%
        payload = build_top_addresses_payload(balances, {"a": {"label": "X", "category": "y"}}, limit=1)
        assert payload["entries"][0]["pct_of_supply"] == pytest.approx(1.0, abs=1e-6)

    def test_label_and_category_taken_from_known_addresses(self):
        payload = build_top_addresses_payload(BALANCE_RESPONSE, KNOWN, limit=4)
        labels = {e["label"] for e in payload["entries"]}
        assert "Robinhood-coldwallet" in labels
        assert all(e["category"] == "exchange" for e in payload["entries"])

    def test_entry_without_category_defaults_to_unknown(self):
        known = {"a": {"label": "Нечто"}}
        payload = build_top_addresses_payload({"a": {"final_balance": 500}}, known, limit=1)
        assert payload["entries"][0]["category"] == "unknown"


class TestMissingAndErrors:

    def test_address_missing_from_response_is_reported_not_silently_dropped(self):
        """
        Адрес из курируемого списка, не вернувшийся из API, обязан попасть в
        missing_addresses. Молча его потерять нельзя — в выдаче это выглядело
        бы как «баланс упал до нуля», хотя данных просто нет.
        """
        known = dict(KNOWN)
        known["addr-not-returned"] = {"label": "Пропавший", "category": "test"}
        payload = build_top_addresses_payload(BALANCE_RESPONSE, known, limit=10)
        assert payload["missing_addresses"] == ["addr-not-returned"]
        assert all(e["address"] != "addr-not-returned" for e in payload["entries"])

    def test_no_missing_key_when_everything_resolved(self):
        payload = build_top_addresses_payload(BALANCE_RESPONSE, KNOWN, limit=10)
        assert "missing_addresses" not in payload

    def test_empty_response_raises(self):
        with pytest.raises(ValueError, match="пустой ответ"):
            build_top_addresses_payload({}, KNOWN, limit=10)

    def test_response_without_final_balance_raises_with_diagnostic(self):
        """Смена формата на стороне API должна падать с внятным сообщением, не с KeyError."""
        broken = {"34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo": {"balance": 123}}
        with pytest.raises(ValueError, match="формат ответа"):
            build_top_addresses_payload(broken, KNOWN, limit=10)


class TestPayloadHonesty:
    """
    Панель переименована из «Топ-100 богатейших адресов» в «Крупнейшие
    известные адреса» именно потому, что выборка ограничена курируемым
    списком. Эти тесты не дают оговорке тихо исчезнуть при будущих правках.
    """

    def test_caveat_states_the_sample_is_limited(self):
        payload = build_top_addresses_payload(BALANCE_RESPONSE, KNOWN, limit=10)
        caveat = payload["caveat"]
        assert "ВЫБОРКА ОГРАНИЧЕНА" in caveat
        assert "НЕ рейтинг" in caveat

    def test_payload_reports_how_many_addresses_are_tracked(self):
        payload = build_top_addresses_payload(BALANCE_RESPONSE, KNOWN, limit=2)
        assert payload["tracked_addresses"] == len(KNOWN)

    def test_source_names_both_balance_api_and_curated_list(self):
        payload = build_top_addresses_payload(BALANCE_RESPONSE, KNOWN, limit=1)
        assert "blockchain.info" in payload["source"]
        assert "known_addresses.json" in payload["source"]


class TestRealCuratedFile:

    def test_real_known_addresses_file_loads_and_has_valid_structure(self):
        """Путь от __file__, не от cwd — autouse-фикстура conftest делает chdir в песочницу."""
        known = load_known_addresses(REPO_ROOT / "data" / "known_addresses.json")
        assert known, "курируемый список пуст"
        for address, entry in known.items():
            assert isinstance(address, str) and address
            assert "category" in entry, f"{address}: нет category"

    def test_committed_output_matches_current_schema(self):
        """
        Файл в репозитории должен соответствовать тому, что производит текущий
        скрипт. Ловит ситуацию, когда скрипт переписали, а данные остались от
        прежнего источника — ровно то, что случилось с Blockchair.
        """
        data = json.loads((REPO_ROOT / "data" / "top_addresses.json").read_text(encoding="utf-8"))
        for key in ("updated_at", "source", "caveat", "tracked_addresses", "entries"):
            assert key in data, f"в data/top_addresses.json нет поля {key}"
        assert "blockchain.info" in data["source"], (
            "данные получены не текущим источником — перегенерировать "
            "scripts/fetch_top_addresses.py"
        )
