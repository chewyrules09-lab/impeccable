"""Event-driven backtest loop.

Replays a single ticker's historical bars in order, calling
`strategy.signals.evaluate()` on every bar (no lookahead: it only ever sees
`bars[:index+1]`). A taken signal's entry is a *limit* order at the FVG zone,
not the current price — by the time a confluence chain confirms, price has
typically already displaced away from that zone. So a taken signal becomes a
*resting* `PendingOrder` rather than an immediate fill: it fills the first
time a later bar's range trades through the limit price, or is canceled if
price closes back through the stop first (the setup is invalidated before
the entry was ever reached). Every working/filled/canceled order and every
signal (taken or not) is persisted through `persistence.repository`, exactly
as paper/live would.

v1 manages at most one commitment (a pending order or an open trade) per
ticker at a time, so `RiskLimits.max_concurrent_positions` > 1 is exercised
in paper/live with multiple tickers, not by this single-ticker engine.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date as date_
from datetime import datetime

from config.settings import Settings
from core.ids import new_client_order_id
from core.models import AccountState, Bar, EquityInstrument, Fill, OrderIntent, OrderType, Side, TimeInForce
from persistence import repository
from risk.engine import RiskEngine
from strategy.signals import Signal, evaluate


@dataclass
class PendingOrder:
    """A working limit order, resting between the bar it was confirmed on
    and the bar it either fills or gets invalidated.
    """

    client_order_id: str
    ticker: str
    side: Side
    signal_index: int
    limit_price: float
    stop: float
    target: float
    size: int
    placed_at: datetime


@dataclass
class Trade:
    ticker: str
    side: Side
    signal_index: int
    entry_index: int
    entry_time: datetime
    entry_price: float
    stop: float
    target: float
    size: int
    exit_index: int | None = None
    exit_time: datetime | None = None
    exit_price: float | None = None
    exit_reason: str | None = None

    @property
    def pnl(self) -> float | None:
        if self.exit_price is None:
            return None
        direction = 1.0 if self.side == Side.BUY else -1.0
        return (self.exit_price - self.entry_price) * self.size * direction

    @property
    def r_multiple(self) -> float | None:
        if self.exit_price is None:
            return None
        risk = abs(self.entry_price - self.stop)
        if risk <= 0:
            return None
        direction = 1.0 if self.side == Side.BUY else -1.0
        return ((self.exit_price - self.entry_price) * direction) / risk


@dataclass
class BacktestResult:
    starting_equity: float
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)

    @property
    def final_equity(self) -> float:
        return self.equity_curve[-1][1] if self.equity_curve else self.starting_equity


def run_backtest(
    bars: list[Bar],
    settings: Settings,
    conn: sqlite3.Connection,
    starting_equity: float = 100_000.0,
) -> BacktestResult:
    result = BacktestResult(starting_equity=starting_equity)
    risk_engine = RiskEngine(settings.risk_limits())

    equity = starting_equity
    realized_pnl_today = 0.0
    trades_today = 0
    current_day: date_ | None = bars[0].timestamp.date() if bars else None
    open_trade: Trade | None = None
    pending: PendingOrder | None = None

    for i, bar in enumerate(bars):
        if bar.timestamp.date() != current_day:
            current_day = bar.timestamp.date()
            realized_pnl_today = 0.0
            trades_today = 0

        if open_trade is not None:
            is_long = open_trade.side == Side.BUY
            hit_stop = bar.low <= open_trade.stop if is_long else bar.high >= open_trade.stop
            hit_target = bar.high >= open_trade.target if is_long else bar.low <= open_trade.target
            is_last_bar = i == len(bars) - 1

            if hit_stop or hit_target or is_last_bar:
                if hit_stop:
                    exit_price, exit_reason = open_trade.stop, "stop"
                elif hit_target:
                    exit_price, exit_reason = open_trade.target, "target"
                else:
                    exit_price, exit_reason = bar.close, "data_end"

                open_trade.exit_index = i
                open_trade.exit_time = bar.timestamp
                open_trade.exit_price = exit_price
                open_trade.exit_reason = exit_reason
                _close_trade(conn, open_trade, bar.timestamp)

                equity += open_trade.pnl or 0.0
                realized_pnl_today += open_trade.pnl or 0.0
                result.trades.append(open_trade)
                open_trade = None

        elif pending is not None:
            is_long = pending.side == Side.BUY
            crossed = bar.low <= pending.limit_price <= bar.high
            invalidated = bar.close < pending.stop if is_long else bar.close > pending.stop

            if crossed:
                repository.insert_fill(
                    conn,
                    Fill(
                        client_order_id=pending.client_order_id,
                        fill_price=pending.limit_price,
                        fill_qty=pending.size,
                        filled_at=bar.timestamp,
                    ),
                )
                repository.update_order_status(conn, pending.client_order_id, "filled")
                open_trade = Trade(
                    ticker=pending.ticker,
                    side=pending.side,
                    signal_index=pending.signal_index,
                    entry_index=i,
                    entry_time=bar.timestamp,
                    entry_price=pending.limit_price,
                    stop=pending.stop,
                    target=pending.target,
                    size=pending.size,
                )
                trades_today += 1
                pending = None
            elif invalidated:
                repository.update_order_status(conn, pending.client_order_id, "canceled")
                repository.insert_risk_event(
                    conn,
                    ts=bar.timestamp,
                    rule="setup_invalidated",
                    action="canceled",
                    client_order_id=pending.client_order_id,
                    detail=(
                        f"price closed through stop {pending.stop} before the limit "
                        f"at {pending.limit_price} filled"
                    ),
                )
                pending = None

        else:
            signal = evaluate(bars, index=i, settings=settings, equity=equity)
            repository.insert_signal(
                conn,
                ts=signal.timestamp,
                ticker=signal.ticker,
                side=signal.side.value if signal.side is not None else "buy",
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
            result.signals.append(signal)

            if signal.taken and signal.size and signal.side is not None:
                account = AccountState(
                    equity=equity,
                    starting_equity_today=equity - realized_pnl_today,
                    cash=equity,
                    daily_realized_pnl=realized_pnl_today,
                    trades_today=trades_today,
                    open_positions=[],
                    market_data_age_seconds=0.0,
                )
                client_order_id = new_client_order_id()
                intent = OrderIntent(
                    client_order_id=client_order_id,
                    instrument=EquityInstrument(ticker=signal.ticker),
                    side=signal.side,
                    qty=signal.size,
                    order_type=OrderType.LIMIT,
                    limit_price=signal.entry,
                    reference_price=signal.entry,
                    time_in_force=TimeInForce.GTC,
                    created_at=signal.timestamp,
                )
                decision = risk_engine.evaluate(intent, account)
                if decision.allowed:
                    repository.insert_order(conn, intent, mode="backtest", status="pending")
                    pending = PendingOrder(
                        client_order_id=client_order_id,
                        ticker=signal.ticker,
                        side=signal.side,
                        signal_index=i,
                        limit_price=signal.entry,
                        stop=signal.stop,
                        target=signal.target,
                        size=signal.size,
                        placed_at=signal.timestamp,
                    )
                else:
                    repository.insert_risk_event(
                        conn,
                        ts=bar.timestamp,
                        rule=decision.rule or "unknown",
                        action="blocked",
                        detail=decision.reason,
                    )

        result.equity_curve.append((bar.timestamp, equity))

    return result


def _close_trade(conn: sqlite3.Connection, trade: Trade, ts: datetime) -> None:
    """Persists the exit as its own market order + fill, mirroring how a
    real stop/target exit would be routed through a broker.
    """
    exit_side = Side.SELL if trade.side == Side.BUY else Side.BUY
    client_order_id = new_client_order_id()
    intent = OrderIntent(
        client_order_id=client_order_id,
        instrument=EquityInstrument(ticker=trade.ticker),
        side=exit_side,
        qty=trade.size,
        order_type=OrderType.MARKET,
        reference_price=trade.exit_price,
        created_at=ts,
    )
    repository.insert_order(conn, intent, mode="backtest", status="filled")
    repository.insert_fill(
        conn,
        Fill(client_order_id=client_order_id, fill_price=trade.exit_price, fill_qty=trade.size, filled_at=ts),
    )
