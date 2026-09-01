"""
tests/unit/test_fetch_pool_share.py
Bitcoin Intel — тесты scripts/fetch_pool_share.py.

Сеть замокана — тест не должен зависеть от доступности mempool.space
(флаки в CI). Проверяем: (1) корректность сортировки/суммы top-3, (2)
устойчивость к неожиданному формату ответа API, (3) что скрипт не
полагается молча на порядок сортировки самого API.
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from fetch_pool_share import build_payload, fetch_pool_shares  # noqa: E402


# Реальный формат ответа mempool.space (v1/mining/hashrate/pools/:period),
# подтверждён по документации/зеркалам (litecoinspace.org, та же кодовая
# база) — не выдуман, share — доля от 0 до 1.
SAMPLE_RESPONSE = [
    {"timestamp": 1650240000, "avgHashrate": 3.8e19, "share": 0.185366, "poolName": "Foundry USA"},
    {"timestamp": 1650240000, "avgHashrate": 2.98e19, "share": 0.14439, "poolName": "AntPool"},
    {"timestamp": 1650240000, "avgHashrate": 2.90e19, "share": 0.140488, "poolName": "F2Pool"},
    {"timestamp": 1650240000, "avgHashrate": 2.66e19, "share": 0.12878, "poolName": "Binance Pool"},
    {"timestamp": 1650240000, "avgHashrate": 2.17e19, "share": 0.105366, "poolName": "Poolin"},
]


def test_build_payload_top3_sum_and_order():
    payload = build_payload(SAMPLE_RESPONSE, "1w")
    c = payload["current"]
    assert [p["name"] for p in c["top_pools"]] == ["Foundry USA", "AntPool", "F2Pool"]
    assert c["top3_share_pct"] == pytest.approx(18.5366 + 14.439 + 14.0488, abs=0.01)
    assert c["pools_reported"] == 5


def test_build_payload_does_not_trust_input_order():
    """
    Регрессия на конкретное защитное решение в build_payload(): скрипт
    сортирует сам, а не полагается на то, что API всегда отдаёт по
    убыванию share — документация это обещает, но не проверять дешевле,
    чем получить молча неверный 'топ-3' при изменении поведения апстрима.
    """
    shuffled = list(reversed(SAMPLE_RESPONSE))
    payload = build_payload(shuffled, "1w")
    assert [p["name"] for p in payload["current"]["top_pools"]] == ["Foundry USA", "AntPool", "F2Pool"]


def test_build_payload_handles_fewer_than_three_pools():
    """Тестовые сети (signet/testnet) могут иметь < 3 пула в выдаче — не должно падать."""
    payload = build_payload(SAMPLE_RESPONSE[:2], "1w")
    assert len(payload["current"]["top_pools"]) == 2
    assert payload["current"]["top3_share_pct"] == pytest.approx(18.5366 + 14.439, abs=0.01)


def test_build_payload_share_pct_rounds_to_two_decimals():
    payload = build_payload(SAMPLE_RESPONSE, "1w")
    for p in payload["current"]["top_pools"]:
        assert p["share_pct"] == round(p["share_pct"], 2)


@patch("fetch_pool_share.requests.get")
def test_fetch_pool_shares_rejects_non_list_response(mock_get):
    mock_get.return_value = MagicMock(json=lambda: {"unexpected": "shape"}, raise_for_status=lambda: None)
    with pytest.raises(ValueError, match="Неожиданный формат"):
        fetch_pool_shares("1w")


@patch("fetch_pool_share.requests.get")
def test_fetch_pool_shares_rejects_empty_list(mock_get):
    mock_get.return_value = MagicMock(json=lambda: [], raise_for_status=lambda: None)
    with pytest.raises(ValueError, match="Неожиданный формат"):
        fetch_pool_shares("1w")


@patch("fetch_pool_share.requests.get")
def test_fetch_pool_shares_rejects_missing_fields(mock_get):
    """API мог бы прислать записи без poolName/share при смене формата — должны узнать об этом явно, не тихим KeyError глубже в build_payload."""
    mock_get.return_value = MagicMock(json=lambda: [{"timestamp": 123, "avgHashrate": 1.0}], raise_for_status=lambda: None)
    with pytest.raises(ValueError, match="poolName/share"):
        fetch_pool_shares("1w")


@patch("fetch_pool_share.requests.get")
def test_fetch_pool_shares_calls_correct_endpoint(mock_get):
    mock_get.return_value = MagicMock(json=lambda: SAMPLE_RESPONSE, raise_for_status=lambda: None)
    fetch_pool_shares("1m")
    called_url = mock_get.call_args[0][0]
    assert called_url == "https://mempool.space/api/v1/mining/hashrate/pools/1m"
