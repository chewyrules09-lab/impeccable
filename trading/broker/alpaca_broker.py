"""Phase 2/3 stub. Implements the `Broker` protocol against Alpaca's paper (and
later, live) trading API for equities and single-leg options, using `alpaca-py`.
Backtest historical bar loading is a separate concern (see `backtest/data.py`);
this module is execution only.

Not implemented in Phase 0: `alpaca-py` is an optional dependency
(`pip install .[live]`) precisely so Phase 0 doesn't require it.
"""

from __future__ import annotations

from core.models import AccountState, OrderAck, OrderIntent, OrderStatusValue, Position


class AlpacaBroker:
    def __init__(self, api_key: str, secret_key: str, base_url: str) -> None:
        raise NotImplementedError("AlpacaBroker is implemented in Phase 2/3.")

    def get_account(self) -> AccountState:
        raise NotImplementedError

    def get_positions(self) -> list[Position]:
        raise NotImplementedError

    def place_order(self, intent: OrderIntent) -> OrderAck:
        raise NotImplementedError

    def cancel_order(self, client_order_id: str) -> None:
        raise NotImplementedError

    def get_order_status(self, client_order_id: str) -> OrderStatusValue:
        raise NotImplementedError

    def flatten_all(self) -> list[OrderAck]:
        raise NotImplementedError
