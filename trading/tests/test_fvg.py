from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.models import Bar
from strategy.fvg import FVGDirection, find_fair_value_gaps

_T0 = datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc)


def make_bar(i: int, o: float, h: float, l: float, c: float) -> Bar:
    return Bar(ticker="SPY", timestamp=_T0 + timedelta(minutes=i), open=o, high=h, low=l, close=c)


def test_detects_a_bullish_gap() -> None:
    bars = [
        make_bar(0, 98, 100, 95, 99),
        make_bar(1, 99, 110, 98, 109),
        make_bar(2, 109, 112, 103, 110),  # low (103) > bar0.high (100)
    ]

    gaps = find_fair_value_gaps(bars)

    assert len(gaps) == 1
    assert gaps[0].index == 1
    assert gaps[0].direction == FVGDirection.BULLISH
    assert gaps[0].top == 103
    assert gaps[0].bottom == 100
    assert gaps[0].size == 3
    assert gaps[0].midpoint == 101.5


def test_detects_a_bearish_gap() -> None:
    bars = [
        make_bar(0, 102, 105, 100, 101),
        make_bar(1, 101, 102, 92, 93),
        make_bar(2, 93, 98, 90, 95),  # high (98) < bar0.low (100)
    ]

    gaps = find_fair_value_gaps(bars)

    assert len(gaps) == 1
    assert gaps[0].direction == FVGDirection.BEARISH
    assert gaps[0].top == 100
    assert gaps[0].bottom == 98


def test_overlapping_candles_produce_no_gap() -> None:
    bars = [
        make_bar(0, 98, 100, 95, 99),
        make_bar(1, 99, 105, 94, 100),
        make_bar(2, 100, 101, 96, 99),  # low (96) overlaps bar0's range
    ]

    assert find_fair_value_gaps(bars) == []


def test_min_gap_size_filters_out_small_gaps() -> None:
    bars = [
        make_bar(0, 98, 100, 95, 99),
        make_bar(1, 99, 110, 98, 109),
        make_bar(2, 109, 112, 103, 110),  # gap size is 3
    ]

    assert find_fair_value_gaps(bars, min_gap_size=5.0) == []
