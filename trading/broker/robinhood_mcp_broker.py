"""Phase 4 stub. Implements the `Broker` protocol as a thin client over the
Robinhood Agentic Trading MCP (`ROBINHOOD_MCP_URL`). This is the live execution
rail: it must place exactly what the deterministic strategy engine decided, as
a fully-specified order (ticker, side, qty, order type, limit price,
time-in-force), with zero discretion at this layer.

TODO-VERIFY: no MCP tool schema was available while building this (OAuth could
not complete in a headless sandbox: see trading/README for context). The tool
names and argument shapes below are assumptions based on the brief's required
fields, NOT a confirmed schema. Before Phase 4 is implemented for real:
  1. Authenticate the MCP in an interactive terminal (`claude mcp login
     robinhood-trading`).
  2. Inspect the actual tools it exposes and their input/output shapes.
  3. Replace every assumed call below with the verified one.

Assumed tool calls (UNVERIFIED):
  - place_order(ticker, side, qty, order_type, limit_price, time_in_force,
    client_order_id) -> { client_order_id, status, fill_price?, fill_qty? }
  - get_positions() -> [{ ticker, qty, avg_entry_price, market_value }]
  - get_account() -> { equity, cash, ... }
  - cancel_order(client_order_id) -> None
  - get_order_status(client_order_id) -> { status }
  - close_position(ticker) / flatten_all() -> [...]

Single-leg options only in v1: this adapter does not assume multi-leg/combo
order support exists in the MCP.
"""

from __future__ import annotations

from core.models import AccountState, OrderAck, OrderIntent, OrderStatusValue, Position


class RobinhoodMCPBroker:
    def __init__(self, mcp_url: str) -> None:
        raise NotImplementedError("RobinhoodMCPBroker is implemented in Phase 4, after MCP schema verification.")

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
