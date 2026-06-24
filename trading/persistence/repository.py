from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from core.models import AccountState, Fill, OrderIntent


def insert_order(conn: sqlite3.Connection, intent: OrderIntent, mode: str, status: str = "pending") -> None:
    """Idempotent: `client_order_id` is the primary key, so re-inserting the
    same intent (e.g. on a retry) is a no-op rather than a duplicate row.
    Must be called *before* the broker is asked to place the order.
    """
    conn.execute(
        """
        INSERT OR IGNORE INTO orders (
            client_order_id, ts_created, ticker, side, qty, order_type,
            limit_price, reference_price, time_in_force, instrument_json, status, mode
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            intent.client_order_id,
            intent.created_at.isoformat(),
            intent.instrument.symbol,
            intent.side.value,
            intent.qty,
            intent.order_type.value,
            intent.limit_price,
            intent.reference_price,
            intent.time_in_force.value,
            intent.instrument.model_dump_json(),
            status,
            mode,
        ),
    )
    conn.commit()


def get_order(conn: sqlite3.Connection, client_order_id: str) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM orders WHERE client_order_id = ?", (client_order_id,))
    return cur.fetchone()


def update_order_status(conn: sqlite3.Connection, client_order_id: str, status: str) -> None:
    conn.execute(
        "UPDATE orders SET status = ? WHERE client_order_id = ?",
        (status, client_order_id),
    )
    conn.commit()


def insert_fill(conn: sqlite3.Connection, fill: Fill) -> None:
    conn.execute(
        "INSERT INTO fills (client_order_id, ts, fill_price, fill_qty) VALUES (?, ?, ?, ?)",
        (fill.client_order_id, fill.filled_at.isoformat(), fill.fill_price, fill.fill_qty),
    )
    conn.commit()


def get_fills(conn: sqlite3.Connection, client_order_id: str) -> list[sqlite3.Row]:
    cur = conn.execute("SELECT * FROM fills WHERE client_order_id = ?", (client_order_id,))
    return cur.fetchall()


def insert_signal(
    conn: sqlite3.Connection,
    *,
    ts: datetime,
    ticker: str,
    side: str,
    entry: float | None,
    stop: float | None,
    target: float | None,
    size: int | None,
    confidence: float | None,
    rules_fired: list[str],
    rules_failed: list[str],
    taken: bool,
    skip_reason: str | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO signals (
            ts, ticker, side, entry, stop, target, size, confidence,
            rules_fired_json, rules_failed_json, taken, skip_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ts.isoformat(),
            ticker,
            side,
            entry,
            stop,
            target,
            size,
            confidence,
            json.dumps(rules_fired),
            json.dumps(rules_failed),
            int(taken),
            skip_reason,
        ),
    )
    conn.commit()
    return cur.lastrowid


def insert_risk_event(
    conn: sqlite3.Connection,
    *,
    ts: datetime,
    rule: str,
    action: str,
    client_order_id: str | None = None,
    detail: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO risk_events (ts, rule, client_order_id, action, detail)
        VALUES (?, ?, ?, ?, ?)
        """,
        (ts.isoformat(), rule, client_order_id, action, detail),
    )
    conn.commit()


def insert_account_snapshot(conn: sqlite3.Connection, ts: datetime, account: AccountState, mode: str) -> None:
    conn.execute(
        """
        INSERT INTO account_snapshots (ts, equity, cash, daily_realized_pnl, trades_today, mode)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (ts.isoformat(), account.equity, account.cash, account.daily_realized_pnl, account.trades_today, mode),
    )
    conn.commit()
