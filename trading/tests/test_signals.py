from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config.settings import Settings
from core.models import Bar, Side
from persistence import repository
from strategy.signals import evaluate

_EASTERN = ZoneInfo("America/New_York")
_T0 = datetime(2024, 1, 2, 9, 30, tzinfo=_EASTERN)


def make_bar(i: int, o: float, h: float, l: float, c: float, ticker: str = "SPY") -> Bar:
    return Bar(ticker=ticker, timestamp=_T0 + timedelta(minutes=i), open=o, high=h, low=l, close=c)


def _bullish_confluence_bars() -> list[Bar]:
    # idx1/idx3: an equal-low sell-side liquidity pool (~95.0/95.05).
    # idx5: the swing high that the signal bar eventually breaks (110.0).
    # idx7/idx8: wicks below the pool and closes back above it -> a sweep.
    # idx8: also the last bearish candle before the displacement -> the order block.
    # idx9: the bullish displacement candle (FVG's middle candle).
    # idx10: FVG's third candle, and the bar whose close (111) breaks the 110 swing high.
    return [
        make_bar(0, 100, 101, 97, 100),
        make_bar(1, 99, 100, 95.00, 99.5),
        make_bar(2, 99.5, 100, 97, 99.8),
        make_bar(3, 99.8, 100, 95.05, 99.0),
        make_bar(4, 99, 100, 98, 99.5),
        make_bar(5, 99.5, 110.00, 99, 105),
        make_bar(6, 105, 108, 104, 106),
        make_bar(7, 106, 107, 94.0, 96.5),
        make_bar(8, 96.5, 97, 95.0, 95.5),
        make_bar(9, 95.5, 110.5, 95.2, 109),
        make_bar(10, 106, 112, 104, 111),
    ]


def _settings() -> Settings:
    return Settings(
        strategy_swing_lookback=1,
        strategy_equal_level_tolerance_pct=0.5,
        strategy_stop_buffer_pct=0.0,
        strategy_target_r_multiple=2.0,
    )


def test_evaluate_fires_a_full_confluence_signal() -> None:
    bars = _bullish_confluence_bars()
    settings = _settings()

    signal = evaluate(bars, index=10, settings=settings, equity=100_000.0)

    assert signal.taken
    assert signal.side == Side.BUY
    assert signal.entry == 100.5
    assert signal.stop == 95.0
    assert signal.target == 111.5
    assert signal.size == 181
    assert signal.confidence == 1.0
    assert signal.rules_fired == [
        "kill_zone",
        "structure_break:mss:bullish",
        "fair_value_gap",
        "order_block",
        "liquidity_sweep",
        "target:r_multiple_fallback",
    ]
    assert signal.rules_failed == []


def test_evaluate_skips_bars_outside_the_kill_zone() -> None:
    bars = [make_bar(0, 100, 101, 99, 100)]
    bars[0] = bars[0].model_copy(update={"timestamp": datetime(2024, 1, 2, 8, 0, tzinfo=_EASTERN)})
    settings = _settings()

    signal = evaluate(bars, index=0, settings=settings, equity=100_000.0)

    assert not signal.taken
    assert signal.side is None
    assert signal.rules_failed == ["kill_zone"]
    assert signal.skip_reason is not None


def test_evaluate_skips_bars_with_no_structure_break() -> None:
    bars = [make_bar(i, 100, 100.5, 99.5, 100) for i in range(5)]
    settings = _settings()

    signal = evaluate(bars, index=4, settings=settings, equity=100_000.0)

    assert not signal.taken
    assert signal.rules_fired == ["kill_zone"]
    assert signal.rules_failed == ["structure_break"]


def test_taken_signal_round_trips_through_the_signals_table(conn: sqlite3.Connection) -> None:
    bars = _bullish_confluence_bars()
    settings = _settings()
    signal = evaluate(bars, index=10, settings=settings, equity=100_000.0)
    assert signal.side is not None

    repository.insert_signal(
        conn,
        ts=signal.timestamp,
        ticker=signal.ticker,
        side=signal.side.value,
        entry=signal.entry,
        stop=signal.stop,
        target=signal.target,
        size=signal.size,
        confidence=signal.confidence,
        rules_fired=signal.rules_fired,
        rules_failed=signal.rules_failed,
        taken=signal.taken,
        skip_reason=signal.skip_reason,
    )

    row = conn.execute("SELECT * FROM signals WHERE ticker = ?", (signal.ticker,)).fetchone()
    assert row is not None
    assert row["taken"] == 1
    assert row["side"] == "buy"
    assert row["size"] == 181
