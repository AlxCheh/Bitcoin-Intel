"""
tests/unit/test_fetch_top_addresses.py
Bitcoin Intel — тесты для scripts/fetch_top_addresses.py.

ВАЖНО: тестируется только логика слияния/классификации/сборки payload —
не реальный вызов Blockchair API (недоступен из этой среды, см. шапку
scripts/fetch_top_addresses.py и обсуждение в чате 2026-07-25). Тесты
используют синтетические ответы в ПРЕДПОЛАГАЕМОМ формате Blockchair —
если реальный формат отличается, build_top_addresses_payload() упадёт
с понятной ошибкой при первом реальном прогоне в CI (см. проверку полей
внутри функции), а не тихо даст неверные данные.
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from scripts.fetch_top_addresses import (
    classify_and_label,
    build_top_addresses_payload,
    load_known_addresses,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestClassifyAndLabel:

    def test_known_exchange_address(self):
        known = {"addr1": {"label": "Binance-coldwallet", "category": "exchange"}}
        label, category = classify_and_label("addr1", known)
        assert label == "Binance-coldwallet"
        assert category == "exchange"

    def test_unknown_address_returns_unknown_category(self):
        known = {"addr1": {"label": "Binance-coldwallet", "category": "exchange"}}
        label, category = classify_and_label("addr-not-in-map", known)
        assert label is None
        assert category == "unknown"

    def test_known_address_without_label_still_gets_category(self):
        known = {"addr1": {"label": None, "category": "unknown"}}
        label, category = classify_and_label("addr1", known)
        assert label is None
        assert category == "unknown"


class TestBuildTopAddressesPayload:

    def test_builds_ranked_entries_with_labels(self):
        raw = {
            "data": [
                {"address": "addr1", "balance": 100 * 100_000_000},
                {"address": "addr2", "balance": 50 * 100_000_000},
            ]
        }
        known = {"addr1": {"label": "Binance-coldwallet", "category": "exchange"}}
        payload = build_top_addresses_payload(raw, known)

        assert len(payload["entries"]) == 2
        assert payload["entries"][0]["rank"] == 1
        assert payload["entries"][0]["address"] == "addr1"
        assert payload["entries"][0]["label"] == "Binance-coldwallet"
        assert payload["entries"][0]["category"] == "exchange"
        assert payload["entries"][0]["balance_btc"] == 100.0
        assert payload["entries"][1]["category"] == "unknown"
        assert payload["entries"][1]["label"] is None

    def test_pct_of_supply_computed_correctly(self):
        raw = {"data": [{"address": "addr1", "balance": 210_000 * 100_000_000}]}
        payload = build_top_addresses_payload(raw, {})
        # 210,000 BTC из 21,000,000 = 1%
        assert payload["entries"][0]["pct_of_supply"] == pytest.approx(1.0, abs=1e-6)

    def test_empty_data_raises_value_error(self):
        with pytest.raises(ValueError, match="пустой список"):
            build_top_addresses_payload({"data": []}, {})

    def test_missing_address_field_raises_clear_error(self):
        """Если реальный формат Blockchair отличается от предполагаемого —
        это должно упасть с понятной ошибкой, не тихо дать мусорные данные."""
        raw = {"data": [{"balance": 100}]}  # нет поля 'address'
        with pytest.raises(ValueError, match="Неожиданная структура"):
            build_top_addresses_payload(raw, {})

    def test_missing_balance_field_raises_clear_error(self):
        raw = {"data": [{"address": "addr1"}]}  # нет поля 'balance'
        with pytest.raises(ValueError, match="Неожиданная структура"):
            build_top_addresses_payload(raw, {})

    def test_payload_includes_caveat_and_source(self):
        raw = {"data": [{"address": "addr1", "balance": 100 * 100_000_000}]}
        payload = build_top_addresses_payload(raw, {})
        assert "caveat" in payload
        assert "не сущности" in payload["caveat"]
        assert "Blockchair" in payload["source"]


class TestKnownAddressesFile:
    """Проверяет реальный data/known_addresses.json — валидность структуры,
    не содержимое конкретных меток (то курируется вручную)."""

    def test_real_known_addresses_file_loads_and_has_valid_structure(self):
        path = os.path.join(REPO_ROOT, "data", "known_addresses.json")
        if not os.path.exists(path):
            pytest.skip("data/known_addresses.json недоступен в этом окружении")

        from pathlib import Path
        known = load_known_addresses(Path(path))

        assert isinstance(known, dict)
        assert len(known) > 0
        for address, entry in known.items():
            assert "category" in entry, f"{address}: нет поля category"
            assert entry["category"] in ("exchange", "lost_confiscated", "unknown"), (
                f"{address}: неизвестная категория {entry['category']!r}"
            )

    def test_no_duplicate_addresses_in_known_file(self):
        """JSON-объект сам по себе не допускает дублирующихся ключей на уровне
        Python (последний перезаписывает), но явная проверка — на случай
        будущего рефакторинга в список."""
        path = os.path.join(REPO_ROOT, "data", "known_addresses.json")
        if not os.path.exists(path):
            pytest.skip("data/known_addresses.json недоступен в этом окружении")
        raw = json.loads(open(path, encoding="utf-8").read())
        addresses = list(raw.get("addresses", {}).keys())
        assert len(addresses) == len(set(addresses))
