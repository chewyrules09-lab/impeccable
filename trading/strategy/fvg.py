"""Fair Value Gap (FVG) detection: a 3-candle imbalance where candle 1's
high/low does not overlap candle 3's low/high, leaving a gap at candle 2 (the
displacement candle). `min_gap_size` filters out noise-level gaps; it is in
price units, set via `StrategyConfig.min_fvg_size`.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from core.models import Bar


class FVGDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class FairValueGap(BaseModel):
    """`index` is the middle (displacement) candle of the 3-candle pattern.
    For a bullish FVG the gap spans [candle1.high, candle3.low]; for a
    bearish FVG, [candle3.high, candle1.low].
    """

    index: int
    direction: FVGDirection
    top: float
    bottom: float

    @property
    def size(self) -> float:
        return self.top - self.bottom

    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2.0


def find_fair_value_gaps(bars: list[Bar], min_gap_size: float = 0.0) -> list[FairValueGap]:
    gaps: list[FairValueGap] = []
    for i in range(1, len(bars) - 1):
        first, third = bars[i - 1], bars[i + 1]
        if third.low > first.high:
            top, bottom = third.low, first.high
            if top - bottom >= min_gap_size:
                gaps.append(FairValueGap(index=i, direction=FVGDirection.BULLISH, top=top, bottom=bottom))
        elif third.high < first.low:
            top, bottom = first.low, third.high
            if top - bottom >= min_gap_size:
                gaps.append(FairValueGap(index=i, direction=FVGDirection.BEARISH, top=top, bottom=bottom))
    return gaps
