"""Order Block (OB) detection: the last opposing-color candle immediately
preceding a displacement leg (the move that created an FVG), used as a
value/entry zone on retest.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from core.models import Bar


class OrderBlockDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class OrderBlock(BaseModel):
    index: int
    direction: OrderBlockDirection
    high: float
    low: float


def find_order_block(
    bars: list[Bar], displacement_index: int, direction: OrderBlockDirection, lookback_bars: int
) -> OrderBlock | None:
    """Walks backwards from `displacement_index` (the candle that created the
    displacement/FVG) up to `lookback_bars`, and returns the most recent
    candle of the opposite color: a bearish candle before a bullish
    displacement, or a bullish candle before a bearish displacement.
    """
    want_bearish = direction == OrderBlockDirection.BULLISH
    start = max(0, displacement_index - lookback_bars)
    for i in range(displacement_index - 1, start - 1, -1):
        bar = bars[i]
        if want_bearish and bar.is_bearish:
            return OrderBlock(index=i, direction=direction, high=bar.high, low=bar.low)
        if not want_bearish and bar.is_bullish:
            return OrderBlock(index=i, direction=direction, high=bar.high, low=bar.low)
    return None
