from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from core.ids import new_client_order_id
from core.models import (
    AccountState,
    Fill,
    OrderAck,
    OrderIntent,
    OrderStatusValue,
    OrderType,
    Position,
    Side,
)
from persistence import repository


class DryRunBroker:
    """Reference implementation of the `Broker` protocol. No network calls:
    every order fills synthetically at its limit price (or reference price for
    market orders), and all state is written through the same SQLite
    repository the rest of the system uses. This is what Phase 0's tests run
    against, and the safe default outside paper/live.
    """

    def __init__(self, conn: sqlite3.Connection, starting_equity: float = 100_000.0) -> None:
        self.conn = conn
        self._equity = starting_equity
        self._cash = starting_equity
        self._starting_equity_today = starting_equity
        self._daily_realized_pnl = 0.0
        self._trades_today = 0
        self._positions: dict[str, Position] = {}

    def get_account(self) -> AccountState:
        return AccountState(
            equity=self._equity,
            starting_equity_today=self._starting_equity_today,
            cash=self._cash,
            daily_realized_pnl=self._daily_realized_pnl,
            trades_today=self._trades_today,
            open_positions=list(self._positions.values()),
            market_data_age_seconds=0.0,
        )

    def get_positions(self) -> list[Position]:
        return list(self._positions.values())

    def place_order(self, intent: OrderIntent) -> OrderAck:
        existing = repository.get_order(self.conn, intent.client_order_id)
        if existing is not None and existing["status"] == "filled":
            fills = repository.get_fills(self.conn, intent.client_order_id)
            fill = self._fill_from_row(fills[0]) if fills else None
            return OrderAck(client_order_id=intent.client_order_id, status=OrderStatusValue.FILLED, fill=fill)

        repository.insert_order(self.conn, intent, mode="dryrun", status="pending")

        fill_price = intent.limit_price if intent.limit_price is not None else intent.reference_price
        fill = Fill(
            client_order_id=intent.client_order_id,
            fill_price=fill_price,
            fill_qty=intent.qty,
            filled_at=datetime.now(timezone.utc),
        )
        repository.insert_fill(self.conn, fill)
        repository.update_order_status(self.conn, intent.client_order_id, "filled")

        self._apply_fill(intent, fill)
        self._trades_today += 1

        return OrderAck(client_order_id=intent.client_order_id, status=OrderStatusValue.FILLED, fill=fill)

    def cancel_order(self, client_order_id: str) -> None:
        repository.update_order_status(self.conn, client_order_id, "canceled")

    def get_order_status(self, client_order_id: str) -> OrderStatusValue:
        row = repository.get_order(self.conn, client_order_id)
        if row is None:
            raise KeyError(client_order_id)
        return OrderStatusValue(row["status"])

    def flatten_all(self) -> list[OrderAck]:
        acks: list[OrderAck] = []
        for position in list(self._positions.values()):
            if position.qty == 0:
                continue
            side = Side.SELL if position.qty > 0 else Side.BUY
            closing_intent = OrderIntent(
                client_order_id=new_client_order_id(),
                instrument=position.instrument,
                side=side,
                qty=abs(position.qty),
                order_type=OrderType.MARKET,
                reference_price=position.avg_entry_price,
                created_at=datetime.now(timezone.utc),
            )
            acks.append(self.place_order(closing_intent))
        return acks

    def _apply_fill(self, intent: OrderIntent, fill: Fill) -> None:
        symbol = intent.instrument.symbol
        signed_qty = fill.fill_qty if intent.side == Side.BUY else -fill.fill_qty
        existing = self._positions.get(symbol)

        self._cash -= signed_qty * fill.fill_price

        if existing is None:
            new_qty = signed_qty
        else:
            new_qty = existing.qty + signed_qty

        if new_qty == 0:
            self._positions.pop(symbol, None)
            return

        avg_price = fill.fill_price if existing is None else existing.avg_entry_price
        self._positions[symbol] = Position(
            instrument=intent.instrument,
            qty=new_qty,
            avg_entry_price=avg_price,
            market_value=abs(new_qty) * fill.fill_price,
        )

    @staticmethod
    def _fill_from_row(row: sqlite3.Row) -> Fill:
        return Fill(
            client_order_id=row["client_order_id"],
            fill_price=row["fill_price"],
            fill_qty=row["fill_qty"],
            filled_at=datetime.fromisoformat(row["ts"]),
        )
