from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backtest.engine import run_backtest
from config.settings import Settings
from core.models import Bar, Side

_EASTERN = ZoneInfo("America/New_York")
_T0 = datetime(2024, 1, 2, 9, 30, tzinfo=_EASTERN)


def make_bar(i: int, o: float, h: float, l: float, c: float, ticker: str = "SPY") -> Bar:
    return Bar(ticker=ticker, timestamp=_T0 + timedelta(minutes=i), open=o, high=h, low=l, close=c)


def _confluence_bars() -> list[Bar]:
    # Bars 0-10 are the same hand-traced setup as test_signals.py's
    # _bullish_confluence_bars(): a sell-side sweep + bullish MSS + FVG +
    # order block confirm at index 10, with entry=100.5 (FVG midpoint),
    # stop=95.0, target=111.5 (the 2R fallback).
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


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = dict(
        strategy_swing_lookback=1,
        strategy_equal_level_tolerance_pct=0.5,
        strategy_stop_buffer_pct=0.0,
        strategy_target_r_multiple=2.0,
        # The hand-crafted fixture's stop is wide relative to entry (~5.5%),
        # so 1%-of-equity risk sizing alone produces an order whose notional
        # is ~18% of equity -- above the real 10% default. Raise the cap here
        # so these fill/exit tests aren't incidentally blocked by a risk rule
        # that test_risk_engine_blocks_an_oversized_signal already covers.
        max_position_size_pct=25.0,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def test_pending_limit_order_fills_on_retracement_and_exits_at_target(conn: sqlite3.Connection) -> None:
    bars = _confluence_bars() + [
        make_bar(11, 111, 111.5, 108, 108.5),
        make_bar(12, 108.5, 109, 103, 104),
        make_bar(13, 104, 105, 100.0, 102),  # crosses the 100.5 limit -> fills here
        make_bar(14, 102, 106, 101, 105),
        make_bar(15, 105, 112, 104, 110),  # high=112 clears the 111.5 target
    ]
    settings = _settings()

    result = run_backtest(bars, settings, conn, starting_equity=100_000.0)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.side == Side.BUY
    assert trade.entry_index == 13
    assert trade.entry_price == 100.5
    assert trade.stop == 95.0
    assert trade.target == 111.5
    assert trade.size == 181
    assert trade.exit_index == 15
    assert trade.exit_price == 111.5
    assert trade.exit_reason == "target"
    assert trade.pnl == 1991.0
    assert trade.r_multiple == 2.0
    assert result.final_equity == 101_991.0
    assert len(result.equity_curve) == len(bars)

    orders = conn.execute("SELECT status FROM orders ORDER BY ts_created").fetchall()
    assert [o["status"] for o in orders] == ["filled", "filled"]  # entry, then exit


def test_pending_limit_order_fills_then_exits_at_stop(conn: sqlite3.Connection) -> None:
    bars = _confluence_bars() + [
        make_bar(11, 111, 111.5, 108, 108.5),
        make_bar(12, 108.5, 109, 103, 104),
        make_bar(13, 104, 105, 100.0, 102),  # fills at the 100.5 limit
        make_bar(14, 102, 103, 90, 92),  # low=90 trades through the 95.0 stop
    ]
    settings = _settings()

    result = run_backtest(bars, settings, conn, starting_equity=100_000.0)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_index == 14
    assert trade.exit_price == 95.0
    assert trade.exit_reason == "stop"
    assert trade.pnl == -995.5
    assert trade.r_multiple == -1.0


def test_a_close_back_through_the_stop_cancels_an_unfilled_limit_order(conn: sqlite3.Connection) -> None:
    bars = _confluence_bars() + [
        make_bar(11, 111, 111.5, 108, 108.5),
        make_bar(12, 99, 99.5, 90, 92),  # gaps down under the 100.5 limit and closes below the 95.0 stop
    ]
    settings = _settings()

    result = run_backtest(bars, settings, conn, starting_equity=100_000.0)

    assert result.trades == []
    orders = conn.execute("SELECT status FROM orders").fetchall()
    assert [o["status"] for o in orders] == ["canceled"]
    risk_events = conn.execute("SELECT rule, action FROM risk_events").fetchall()
    assert risk_events[0]["rule"] == "setup_invalidated"
    assert risk_events[0]["action"] == "canceled"


def test_risk_engine_blocks_an_oversized_signal(conn: sqlite3.Connection) -> None:
    bars = _confluence_bars()
    settings = _settings(max_position_size_pct=0.01)

    result = run_backtest(bars, settings, conn, starting_equity=100_000.0)

    assert result.trades == []
    risk_events = conn.execute("SELECT rule, action FROM risk_events").fetchall()
    assert len(risk_events) == 1
    assert risk_events[0]["rule"] == "max_position_size"
    assert risk_events[0]["action"] == "blocked"


def test_every_bar_evaluated_gets_a_persisted_signal_row(conn: sqlite3.Connection) -> None:
    bars = _confluence_bars()
    settings = _settings()

    run_backtest(bars, settings, conn, starting_equity=100_000.0)

    total = conn.execute("SELECT COUNT(*) AS n FROM signals").fetchone()["n"]
    taken = conn.execute("SELECT COUNT(*) AS n FROM signals WHERE taken = 1").fetchone()["n"]
    assert total == len(bars)
    assert taken == 1
