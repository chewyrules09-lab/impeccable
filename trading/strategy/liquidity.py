"""Liquidity detection: equal highs/lows (resting liquidity pools within a
tolerance) and sweep detection (a wick pierces a pool and then closes back on
the other side — a stop hunt, often the trigger for an entry once paired
with an FVG or order block).
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from core.models import Bar
from strategy.market_structure import SwingKind, SwingPoint


class LiquidityPoolKind(str, Enum):
    BUY_SIDE = "buy_side"  # resting above equal highs
    SELL_SIDE = "sell_side"  # resting below equal lows


class LiquidityPool(BaseModel):
    kind: LiquidityPoolKind
    price: float
    swing_indices: list[int]


class LiquiditySweep(BaseModel):
    index: int
    pool: LiquidityPool


def find_equal_levels(swing_points: list[SwingPoint], tolerance_pct: float) -> list[LiquidityPool]:
    """Groups swing highs (-> buy-side pools) and swing lows (-> sell-side
    pools) whose prices sit within `tolerance_pct` of each other. Each group
    of >= 2 swing points becomes one pool, priced at the group's average.
    """
    pools: list[LiquidityPool] = []
    for swing_kind, pool_kind in (
        (SwingKind.HIGH, LiquidityPoolKind.BUY_SIDE),
        (SwingKind.LOW, LiquidityPoolKind.SELL_SIDE),
    ):
        points = sorted((p for p in swing_points if p.kind == swing_kind), key=lambda p: p.price)
        used: set[int] = set()
        for i, point in enumerate(points):
            if point.index in used:
                continue
            group = [point]
            tolerance = point.price * tolerance_pct / 100.0
            for other in points[i + 1 :]:
                if other.index in used:
                    continue
                if abs(other.price - point.price) <= tolerance:
                    group.append(other)
            if len(group) >= 2:
                used.update(g.index for g in group)
                avg_price = sum(g.price for g in group) / len(group)
                pools.append(
                    LiquidityPool(kind=pool_kind, price=avg_price, swing_indices=[g.index for g in group])
                )
    return pools


def find_liquidity_sweep(
    bars: list[Bar], pools: list[LiquidityPool], index: int, direction_kind: LiquidityPoolKind
) -> LiquiditySweep | None:
    """A sweep at `index` is a wick that pierces a pool of `direction_kind`
    while the close rejects back on the other side: for BUY_SIDE (resting
    above price), `high > pool.price > close`; for SELL_SIDE (resting below
    price), `low < pool.price < close`.
    """
    bar = bars[index]
    for pool in pools:
        if pool.kind != direction_kind:
            continue
        if direction_kind == LiquidityPoolKind.BUY_SIDE and bar.high > pool.price > bar.close:
            return LiquiditySweep(index=index, pool=pool)
        if direction_kind == LiquidityPoolKind.SELL_SIDE and bar.low < pool.price < bar.close:
            return LiquiditySweep(index=index, pool=pool)
    return None


def find_recent_sweep(
    bars: list[Bar],
    pools: list[LiquidityPool],
    end_index: int,
    lookback_bars: int,
    direction_kind: LiquidityPoolKind,
) -> LiquiditySweep | None:
    """Scans backwards from `end_index` (inclusive) up to `lookback_bars` for
    the most recent sweep of `direction_kind`.
    """
    start = max(0, end_index - lookback_bars)
    for i in range(end_index, start - 1, -1):
        sweep = find_liquidity_sweep(bars, pools, i, direction_kind)
        if sweep is not None:
            return sweep
    return None
