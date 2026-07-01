from __future__ import annotations

from typing import Protocol

from core.models import AccountState, OrderAck, OrderIntent, OrderStatusValue, Position


class Broker(Protocol):
    """Every execution path (dry-run, Alpaca paper/live, Robinhood MCP) speaks
    this interface. The risk engine, persistence layer, and run_session never
    depend on a concrete broker, only on this contract.
    """

    def get_account(self) -> AccountState: ...

    def get_positions(self) -> list[Position]: ...

    def place_order(self, intent: OrderIntent) -> OrderAck:
        """Must be idempotent on `intent.client_order_id`: calling this twice
        with the same intent returns the original result, never a second order.
        """
        ...

    def cancel_order(self, client_order_id: str) -> None: ...

    def get_order_status(self, client_order_id: str) -> OrderStatusValue: ...

    def flatten_all(self) -> list[OrderAck]:
        """Used by the kill switch: close every open position immediately."""
        ...
