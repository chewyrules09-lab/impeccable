from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.models import Bar
from strategy.liquidity import (
    LiquidityPoolKind,
    find_equal_levels,
    find_liquidity_sweep,
    find_recent_sweep,
)
from strategy.market_structure import SwingKind, SwingPoint

_T0 = datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc)


def make_bar(i: int, o: float, h: float, l: float, c: float) -> Bar:
    return Bar(ticker="SPY", timestamp=_T0 + timedelta(minutes=i), open=o, high=h, low=l, close=c)


def test_groups_nearby_equal_highs_into_one_buy_side_pool() -> None:
    swing_points = [
        SwingPoint(index=1, kind=SwingKind.HIGH, price=105.0, timestamp=_T0),
        SwingPoint(index=4, kind=SwingKind.HIGH, price=105.05, timestamp=_T0),
        SwingPoint(index=7, kind=SwingKind.HIGH, price=120.0, timestamp=_T0),  # too far to group
        SwingPoint(index=2, kind=SwingKind.LOW, price=90.0, timestamp=_T0),  # lone low: no pool
    ]

    pools = find_equal_levels(swing_points, tolerance_pct=0.1)

    assert len(pools) == 1
    assert pools[0].kind == LiquidityPoolKind.BUY_SIDE
    assert pools[0].price == 105.025
    assert sorted(pools[0].swing_indices) == [1, 4]


def test_groups_nearby_equal_lows_into_one_sell_side_pool() -> None:
    swing_points = [
        SwingPoint(index=1, kind=SwingKind.LOW, price=95.0, timestamp=_T0),
        SwingPoint(index=4, kind=SwingKind.LOW, price=95.05, timestamp=_T0),
    ]

    pools = find_equal_levels(swing_points, tolerance_pct=0.5)

    assert len(pools) == 1
    assert pools[0].kind == LiquidityPoolKind.SELL_SIDE
    assert sorted(pools[0].swing_indices) == [1, 4]


def test_find_liquidity_sweep_detects_a_wick_through_and_close_back_below() -> None:
    pools = find_equal_levels(
        [
            SwingPoint(index=1, kind=SwingKind.HIGH, price=105.0, timestamp=_T0),
            SwingPoint(index=4, kind=SwingKind.HIGH, price=105.05, timestamp=_T0),
        ],
        tolerance_pct=0.1,
    )
    bars = [make_bar(i, 104, 104.5, 103.5, 104) for i in range(10)]
    bars[7] = make_bar(7, 104, 106.0, 103.5, 104.5)  # wicks above the pool, closes back below

    sweep = find_liquidity_sweep(bars, pools, index=7, direction_kind=LiquidityPoolKind.BUY_SIDE)

    assert sweep is not None
    assert sweep.index == 7
    assert sweep.pool.kind == LiquidityPoolKind.BUY_SIDE


def test_find_liquidity_sweep_returns_none_without_rejection() -> None:
    pools = find_equal_levels(
        [
            SwingPoint(index=1, kind=SwingKind.HIGH, price=105.0, timestamp=_T0),
            SwingPoint(index=4, kind=SwingKind.HIGH, price=105.05, timestamp=_T0),
        ],
        tolerance_pct=0.1,
    )
    bars = [make_bar(i, 104, 104.5, 103.5, 104) for i in range(10)]
    bars[7] = make_bar(7, 104, 106.0, 103.5, 106.0)  # closes through the pool, no rejection

    sweep = find_liquidity_sweep(bars, pools, index=7, direction_kind=LiquidityPoolKind.BUY_SIDE)

    assert sweep is None


def test_find_recent_sweep_scans_backwards_within_the_lookback_window() -> None:
    pools = find_equal_levels(
        [
            SwingPoint(index=1, kind=SwingKind.HIGH, price=105.0, timestamp=_T0),
            SwingPoint(index=4, kind=SwingKind.HIGH, price=105.05, timestamp=_T0),
        ],
        tolerance_pct=0.1,
    )
    bars = [make_bar(i, 104, 104.5, 103.5, 104) for i in range(13)]
    bars[10] = make_bar(10, 104, 106.0, 103.5, 104.5)  # the only sweep bar

    sweep = find_recent_sweep(bars, pools, end_index=12, lookback_bars=5, direction_kind=LiquidityPoolKind.BUY_SIDE)

    assert sweep is not None
    assert sweep.index == 10


def test_find_recent_sweep_returns_none_outside_the_lookback_window() -> None:
    pools = find_equal_levels(
        [
            SwingPoint(index=1, kind=SwingKind.HIGH, price=105.0, timestamp=_T0),
            SwingPoint(index=4, kind=SwingKind.HIGH, price=105.05, timestamp=_T0),
        ],
        tolerance_pct=0.1,
    )
    bars = [make_bar(i, 104, 104.5, 103.5, 104) for i in range(13)]
    bars[2] = make_bar(2, 104, 106.0, 103.5, 104.5)  # the only sweep bar, outside the window

    sweep = find_recent_sweep(bars, pools, end_index=12, lookback_bars=5, direction_kind=LiquidityPoolKind.BUY_SIDE)

    assert sweep is None
