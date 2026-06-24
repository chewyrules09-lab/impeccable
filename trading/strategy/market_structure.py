"""ICT/TJR market structure detection: swing highs/lows via fractal detection,
and structure breaks classified as BOS (break of structure: a close beyond
the prevailing trend's most recent swing, i.e. continuation) or MSS (market
structure shift: a close beyond a swing against the prevailing trend, i.e. a
potential reversal — also used for the very first break, before any trend is
established).

Swing-point confirmation inherently lags by `lookback` bars: a swing point at
index i isn't visible until bars exist on both sides of it, i.e. not before
`bars[i + lookback]` has arrived. That lag is correct no-lookahead behavior,
not a bug.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from core.models import Bar


class SwingKind(str, Enum):
    HIGH = "high"
    LOW = "low"


class SwingPoint(BaseModel):
    index: int
    kind: SwingKind
    price: float
    timestamp: datetime


class Direction(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class StructureEventKind(str, Enum):
    BOS = "bos"
    MSS = "mss"


class StructureEvent(BaseModel):
    """`index` is the bar whose close broke `level`; `swing_index` is the
    swing point that was broken.
    """

    index: int
    swing_index: int
    kind: StructureEventKind
    direction: Direction
    level: float


def find_swing_points(bars: list[Bar], lookback: int = 2) -> list[SwingPoint]:
    """A bar is a confirmed swing high/low if its high/low is the strict
    extreme within the `2 * lookback + 1` bar window centered on it. Only
    interior bars (with `lookback` bars on both sides) can be confirmed.
    """
    points: list[SwingPoint] = []
    n = len(bars)
    for i in range(lookback, n - lookback):
        window = bars[i - lookback : i + lookback + 1]
        bar = bars[i]
        highs = [b.high for b in window]
        lows = [b.low for b in window]
        if bar.high == max(highs) and highs.count(bar.high) == 1:
            points.append(SwingPoint(index=i, kind=SwingKind.HIGH, price=bar.high, timestamp=bar.timestamp))
        if bar.low == min(lows) and lows.count(bar.low) == 1:
            points.append(SwingPoint(index=i, kind=SwingKind.LOW, price=bar.low, timestamp=bar.timestamp))
    return points


def detect_structure_events(bars: list[Bar], swing_points: list[SwingPoint]) -> list[StructureEvent]:
    """Walks bars in order, tracking the most recently confirmed swing high
    and swing low (i.e. with `swing.index < current bar index`) as the
    reference level for a break. Each swing point triggers at most one event:
    the first close beyond it.
    """
    events: list[StructureEvent] = []
    highs = sorted((p for p in swing_points if p.kind == SwingKind.HIGH), key=lambda p: p.index)
    lows = sorted((p for p in swing_points if p.kind == SwingKind.LOW), key=lambda p: p.index)

    trend: Direction | None = None
    high_ptr = 0
    low_ptr = 0
    ref_high: SwingPoint | None = None
    ref_low: SwingPoint | None = None
    broken_high_indices: set[int] = set()
    broken_low_indices: set[int] = set()

    for i, bar in enumerate(bars):
        while high_ptr < len(highs) and highs[high_ptr].index < i:
            ref_high = highs[high_ptr]
            high_ptr += 1
        while low_ptr < len(lows) and lows[low_ptr].index < i:
            ref_low = lows[low_ptr]
            low_ptr += 1

        if ref_high is not None and ref_high.index not in broken_high_indices and bar.close > ref_high.price:
            kind = StructureEventKind.BOS if trend == Direction.BULLISH else StructureEventKind.MSS
            events.append(
                StructureEvent(
                    index=i,
                    swing_index=ref_high.index,
                    kind=kind,
                    direction=Direction.BULLISH,
                    level=ref_high.price,
                )
            )
            broken_high_indices.add(ref_high.index)
            trend = Direction.BULLISH

        if ref_low is not None and ref_low.index not in broken_low_indices and bar.close < ref_low.price:
            kind = StructureEventKind.BOS if trend == Direction.BEARISH else StructureEventKind.MSS
            events.append(
                StructureEvent(
                    index=i,
                    swing_index=ref_low.index,
                    kind=kind,
                    direction=Direction.BEARISH,
                    level=ref_low.price,
                )
            )
            broken_low_indices.add(ref_low.index)
            trend = Direction.BEARISH

    return events
