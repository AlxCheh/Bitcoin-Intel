"""
tests/unit/test_fetch_bip110_signaling.py
Bitcoin Intel — тесты для scripts/fetch_bip110_signaling.py.

Тестируется логика BIP9-проверки бита и сборки payload — не реальный
вызов mempool.space (недоступен из этой среды, см. шапку скрипта).
Пагинация (collect_period_blocks) тестируется через monkeypatch на
fetch_blocks_page, синтетическими "страницами" — реальный сетевой формат
верифицируется первым прогоном в CI, не здесь.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from scripts.fetch_bip110_signaling import (
    is_bip9_signaling,
    build_payload,
    collect_period_blocks,
    PERIOD_SIZE,
    ACTIVATION_THRESHOLD_PCT,
    DEADLINE_BLOCK,
)


class TestIsBip9Signaling:

    def test_correct_bip9_prefix_and_bit_signals(self):
        # 0x20000000 (BIP9-префикс) | 0x10 (бит 4) = 0x20000010
        assert is_bip9_signaling(0x20000010) is True

    def test_bit_set_without_bip9_prefix_does_not_signal(self):
        """Бит 4 установлен, но верхние 3 бита НЕ равны 001 — не считается
        сигналингом (могло быть случайным совпадением в старом/нестандартном
        version, не намеренным BIP9-сигналом)."""
        assert is_bip9_signaling(0x00000010) is False

    def test_bip9_prefix_without_bit_does_not_signal(self):
        assert is_bip9_signaling(0x20000000) is False

    def test_bip9_prefix_with_different_bit_does_not_signal_bit4(self):
        # Бит 1 (0x2), не бит 4 (0x10)
        assert is_bip9_signaling(0x20000002) is False

    def test_real_world_example_from_bip110monitor(self):
        """0x20000010 — ровно то, что описывает bip110monitor.com FAQ
        (BIP9-префикс 001 + бит 4)."""
        assert is_bip9_signaling(0x20000010, bit=4) is True

    def test_custom_bit_parameter(self):
        assert is_bip9_signaling(0x20000004, bit=2) is True
        assert is_bip9_signaling(0x20000004, bit=4) is False


class TestBuildPayload:

    def test_computes_correct_percentage(self):
        blocks = [
            {"height": 100, "version": 0x20000010},  # сигналит
            {"height": 101, "version": 0x20000010},  # сигналит
            {"height": 102, "version": 0x20000000},  # не сигналит
            {"height": 103, "version": 0x00000000},  # не сигналит
        ]
        payload = build_payload(tip_height=103, blocks=blocks, period=51, period_start=100)
        c = payload["current"]
        assert c["blocks_counted"] == 4
        assert c["signaling_blocks"] == 2
        assert c["signal_pct"] == 50.0

    def test_includes_threshold_and_deadline_constants(self):
        blocks = [{"height": 100, "version": 0x20000010}]
        payload = build_payload(tip_height=100, blocks=blocks, period=0, period_start=100)
        assert payload["current"]["threshold_pct"] == ACTIVATION_THRESHOLD_PCT
        assert payload["current"]["deadline_block"] == DEADLINE_BLOCK
        assert payload["current"]["period_size"] == PERIOD_SIZE

    def test_empty_blocks_raises_value_error(self):
        with pytest.raises(ValueError, match="Не собрано ни одного блока"):
            build_payload(tip_height=100, blocks=[], period=0, period_start=100)

    def test_zero_signaling_gives_zero_percent(self):
        blocks = [{"height": 100, "version": 0x20000000}, {"height": 101, "version": 0x0}]
        payload = build_payload(tip_height=101, blocks=blocks, period=0, period_start=100)
        assert payload["current"]["signal_pct"] == 0.0


class TestCollectPeriodBlocks:
    """Пагинация — через monkeypatch на fetch_blocks_page, без сети."""

    def test_paginates_backward_until_period_start(self, monkeypatch):
        import scripts.fetch_bip110_signaling as mod

        # Симулируем 2 страницы по 3 блока (реальный размер страницы — 15,
        # но логика пагинации не зависит от конкретного числа)
        pages = {
            106: [{"height": 106, "version": 0x20000010}, {"height": 105, "version": 0x0}, {"height": 104, "version": 0x0}],
            103: [{"height": 103, "version": 0x20000010}, {"height": 102, "version": 0x0}, {"height": 101, "version": 0x0}],
        }

        def fake_fetch(start_height):
            return pages.get(start_height, [])

        monkeypatch.setattr(mod, "fetch_blocks_page", fake_fetch)

        blocks = collect_period_blocks(tip_height=106, period_start_height=101)
        heights = sorted(b["height"] for b in blocks)
        assert heights == [101, 102, 103, 104, 105, 106]

    def test_stops_at_period_start_even_if_page_goes_lower(self, monkeypatch):
        import scripts.fetch_bip110_signaling as mod

        def fake_fetch(start_height):
            # Страница всегда возвращает блоки ниже period_start — collect
            # должен отфильтровать их, не включать в результат
            return [
                {"height": start_height, "version": 0x0},
                {"height": start_height - 1, "version": 0x0},
                {"height": start_height - 2, "version": 0x0},
            ]

        monkeypatch.setattr(mod, "fetch_blocks_page", fake_fetch)

        blocks = collect_period_blocks(tip_height=105, period_start_height=104)
        heights = sorted(b["height"] for b in blocks)
        assert all(h >= 104 for h in heights)
        assert 104 in heights
        assert 105 in heights

    def test_raises_on_stalled_pagination(self, monkeypatch):
        """Если страница не продвигается (защита от бесконечного цикла при
        неожиданном формате ответа реального API)."""
        import scripts.fetch_bip110_signaling as mod

        def fake_fetch(start_height):
            # Всегда возвращает блоки с той же или большей высотой — не продвигается
            return [{"height": start_height, "version": 0x0}]

        monkeypatch.setattr(mod, "fetch_blocks_page", fake_fetch)

        with pytest.raises(RuntimeError, match="не продвинулась"):
            collect_period_blocks(tip_height=200, period_start_height=100)
