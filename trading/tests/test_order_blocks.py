from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.models import Bar
from strategy.order_blocks import OrderBlockDirection, find_order_block

_T0 = datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc)


def make_bar(i: int, o: float, h: float, l: float, c: float) -> Bar:
    return Bar(ticker="SPY", timestamp=_T0 + timedelta(minutes=i), open=o, high=h, low=l, close=c)


def test_finds_the_last_bearish_candle_before_a_bullish_displacement() -> None:
    bars = [
        make_bar(0, 100, 101, 99, 99),  # bearish, too far back given lookback=3
        make_bar(1, 99, 100, 98, 100),  # bullish
        make_bar(2, 100, 100, 98, 98),  # bearish, too far back given lookback=3
        make_bar(3, 98, 99, 95, 96),  # bearish: the expected order block
        make_bar(4, 96, 97, 95, 97),  # bullish, immediately before displacement
        make_bar(5, 97, 111, 96, 110),  # the displacement candle
    ]

    order_block = find_order_block(bars, displacement_index=5, direction=OrderBlockDirection.BULLISH, lookback_bars=3)

    assert order_block is not None
    assert order_block.index == 3
    assert order_block.direction == OrderBlockDirection.BULLISH
    assert order_block.high == 99
    assert order_block.low == 95


def test_finds_the_last_bullish_candle_before_a_bearish_displacement() -> None:
    bars = [
        make_bar(0, 96, 97, 95, 97),  # bullish: the expected order block
        make_bar(1, 97, 98, 96, 96),  # bearish, immediately before displacement
        make_bar(2, 96, 97, 85, 86),  # the displacement candle
    ]

    order_block = find_order_block(bars, displacement_index=2, direction=OrderBlockDirection.BEARISH, lookback_bars=2)

    assert order_block is not None
    assert order_block.index == 0
    assert order_block.direction == OrderBlockDirection.BEARISH


def test_returns_none_when_no_opposing_candle_is_within_lookback() -> None:
    bars = [
        make_bar(0, 98, 99, 95, 96),  # bearish, but out of range
        make_bar(1, 96, 97, 95, 97),  # bullish, immediately before displacement
        make_bar(2, 97, 111, 96, 110),  # the displacement candle
    ]

    order_block = find_order_block(bars, displacement_index=2, direction=OrderBlockDirection.BULLISH, lookback_bars=1)

    assert order_block is None
