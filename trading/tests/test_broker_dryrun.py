from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from broker.dryrun import DryRunBroker
from core.models import EquityInstrument, OrderIntent, OrderStatusValue, OrderType, Side
from persistence import repository


def make_intent(client_order_id: str, side: Side, qty: int, price: float) -> OrderIntent:
    return OrderIntent(
        client_order_id=client_order_id,
        instrument=EquityInstrument(ticker="SPY"),
        side=side,
        qty=qty,
        order_type=OrderType.LIMIT,
        limit_price=price,
        reference_price=price,
        created_at=datetime.now(timezone.utc),
    )


def test_get_account_defaults_to_starting_equity(conn: sqlite3.Connection) -> None:
    broker = DryRunBroker(conn, starting_equity=50_000.0)
    account = broker.get_account()
    assert account.equity == 50_000.0
    assert account.cash == 50_000.0
    assert account.open_positions == []
    assert account.trades_today == 0


def test_place_order_opens_a_position_and_debits_cash(conn: sqlite3.Connection) -> None:
    broker = DryRunBroker(conn, starting_equity=100_000.0)
    intent = make_intent("order-buy-1", Side.BUY, 10, 100.0)

    broker.place_order(intent)

    positions = broker.get_positions()
    assert len(positions) == 1
    assert positions[0].qty == 10
    assert positions[0].avg_entry_price == 100.0

    account = broker.get_account()
    assert account.cash == 100_000.0 - 1_000.0
    assert account.trades_today == 1


def test_selling_a_full_position_closes_it(conn: sqlite3.Connection) -> None:
    broker = DryRunBroker(conn, starting_equity=100_000.0)
    broker.place_order(make_intent("order-buy-1", Side.BUY, 10, 100.0))
    broker.place_order(make_intent("order-sell-1", Side.SELL, 10, 100.0))

    assert broker.get_positions() == []


def test_flatten_all_closes_open_positions(conn: sqlite3.Connection) -> None:
    broker = DryRunBroker(conn, starting_equity=100_000.0)
    broker.place_order(make_intent("order-buy-1", Side.BUY, 10, 100.0))

    acks = broker.flatten_all()

    assert len(acks) == 1
    assert acks[0].status == OrderStatusValue.FILLED
    assert broker.get_positions() == []


def test_cancel_order_updates_status(conn: sqlite3.Connection) -> None:
    broker = DryRunBroker(conn, starting_equity=100_000.0)
    intent = make_intent("order-cancel-1", Side.BUY, 10, 100.0)
    repository.insert_order(conn, intent, mode="dryrun", status="pending")

    broker.cancel_order(intent.client_order_id)

    assert broker.get_order_status(intent.client_order_id) == OrderStatusValue.CANCELED
