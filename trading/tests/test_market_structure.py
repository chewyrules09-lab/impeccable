from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.models import Bar
from strategy.market_structure import (
    Direction,
    StructureEventKind,
    SwingKind,
    SwingPoint,
    detect_structure_events,
    find_swing_points,
)

_T0 = datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc)


def make_bar(i: int, o: float, h: float, l: float, c: float) -> Bar:
    return Bar(ticker="SPY", timestamp=_T0 + timedelta(minutes=i), open=o, high=h, low=l, close=c)


def test_find_swing_points_confirms_interior_high_and_low() -> None:
    bars = [
        make_bar(0, 98, 100, 95, 97),
        make_bar(1, 99, 105, 96, 101),  # swing high: 105 is the unique max of bars[0:3]
        make_bar(2, 98, 102, 90, 95),  # swing low: 90 is the unique min of bars[1:4]
        make_bar(3, 96, 101, 97, 99),
        make_bar(4, 98, 99, 93, 95),
    ]

    points = find_swing_points(bars, lookback=1)

    assert points == [
        SwingPoint(index=1, kind=SwingKind.HIGH, price=105, timestamp=bars[1].timestamp),
        SwingPoint(index=2, kind=SwingKind.LOW, price=90, timestamp=bars[2].timestamp),
    ]


def test_find_swing_points_does_not_confirm_edge_bars() -> None:
    bars = [
        make_bar(0, 100, 200, 50, 100),  # would be the extreme of the whole series, but unconfirmable
        make_bar(1, 100, 101, 99, 100),
        make_bar(2, 100, 101, 99, 100),
    ]

    points = find_swing_points(bars, lookback=1)

    assert points == []


def test_first_structure_break_is_classified_as_mss() -> None:
    swing_points = [SwingPoint(index=1, kind=SwingKind.HIGH, price=105, timestamp=_T0)]
    bars = [
        make_bar(0, 99, 100, 98, 99),
        make_bar(1, 99, 105, 99, 100),
        make_bar(2, 100, 107, 99, 106),  # closes above the swing high
    ]

    events = detect_structure_events(bars, swing_points)

    assert len(events) == 1
    assert events[0].kind == StructureEventKind.MSS
    assert events[0].direction == Direction.BULLISH
    assert events[0].swing_index == 1
    assert events[0].index == 2


def test_second_break_in_the_same_direction_is_bos_and_third_in_the_opposite_is_mss() -> None:
    swing_points = [
        SwingPoint(index=1, kind=SwingKind.HIGH, price=105, timestamp=_T0),
        SwingPoint(index=2, kind=SwingKind.LOW, price=90, timestamp=_T0),
        SwingPoint(index=5, kind=SwingKind.HIGH, price=120, timestamp=_T0),
        SwingPoint(index=7, kind=SwingKind.LOW, price=80, timestamp=_T0),
    ]
    bars = [
        make_bar(0, 100, 101, 97, 99),
        make_bar(1, 99, 105, 99, 100),
        make_bar(2, 100, 101, 90, 97),
        make_bar(3, 97, 106, 96, 106),  # MSS bullish: closes above 105
        make_bar(4, 106, 109, 105, 108),  # already-broken 105 must not re-fire
        make_bar(5, 108, 120, 107, 115),
        make_bar(6, 115, 126, 114, 125),  # BOS bullish: closes above 120
        make_bar(7, 125, 126, 80, 100),
        make_bar(8, 100, 101, 74, 75),  # MSS bearish: closes below 80
    ]

    events = detect_structure_events(bars, swing_points)

    assert [(e.index, e.swing_index, e.kind, e.direction) for e in events] == [
        (3, 1, StructureEventKind.MSS, Direction.BULLISH),
        (6, 5, StructureEventKind.BOS, Direction.BULLISH),
        (8, 7, StructureEventKind.MSS, Direction.BEARISH),
    ]


def test_no_events_when_no_swing_is_broken() -> None:
    swing_points = [SwingPoint(index=1, kind=SwingKind.HIGH, price=105, timestamp=_T0)]
    bars = [
        make_bar(0, 99, 100, 98, 99),
        make_bar(1, 99, 105, 99, 100),
        make_bar(2, 100, 104, 99, 102),  # never closes above 105
    ]

    assert detect_structure_events(bars, swing_points) == []
