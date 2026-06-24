from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from broker.dryrun import DryRunBroker
from core.models import EquityInstrument, OrderIntent, OrderStatusValue, OrderType, Side
from persistence import repository


def make_intent(client_order_id: str = "order-1") -> OrderIntent:
    return OrderIntent(
        client_order_id=client_order_id,
        instrument=EquityInstrument(ticker="SPY"),
        side=Side.BUY,
        qty=10,
        order_type=OrderType.LIMIT,
        limit_price=100.0,
        reference_price=100.0,
        created_at=datetime.now(timezone.utc),
    )


def test_duplicate_place_order_returns_the_original_fill(conn: sqlite3.Connection) -> None:
    broker = DryRunBroker(conn)
    intent = make_intent()

    first_ack = broker.place_order(intent)
    second_ack = broker.place_order(intent)

    assert first_ack.status == OrderStatusValue.FILLED
    assert second_ack.status == OrderStatusValue.FILLED
    assert first_ack.fill is not None
    assert second_ack.fill is not None
    assert first_ack.fill.fill_price == second_ack.fill.fill_price


def test_duplicate_place_order_does_not_create_a_second_row(conn: sqlite3.Connection) -> None:
    broker = DryRunBroker(conn)
    intent = make_intent()

    broker.place_order(intent)
    broker.place_order(intent)

    orders = conn.execute(
        "SELECT COUNT(*) AS n FROM orders WHERE client_order_id = ?", (intent.client_order_id,)
    ).fetchone()
    assert orders["n"] == 1

    fills = repository.get_fills(conn, intent.client_order_id)
    assert len(fills) == 1


def test_duplicate_place_order_does_not_double_count_trades(conn: sqlite3.Connection) -> None:
    broker = DryRunBroker(conn)
    intent = make_intent()

    broker.place_order(intent)
    broker.place_order(intent)

    account = broker.get_account()
    assert account.trades_today == 1


def test_inserting_order_twice_via_repository_is_a_no_op(conn: sqlite3.Connection) -> None:
    intent = make_intent("order-2")

    repository.insert_order(conn, intent, mode="dryrun", status="pending")
    repository.insert_order(conn, intent, mode="dryrun", status="pending")

    rows = conn.execute(
        "SELECT COUNT(*) AS n FROM orders WHERE client_order_id = ?", (intent.client_order_id,)
    ).fetchone()
    assert rows["n"] == 1
