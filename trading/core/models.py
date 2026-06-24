from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class TimeInForce(str, Enum):
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"


class OptionRight(str, Enum):
    CALL = "call"
    PUT = "put"


class EquityInstrument(BaseModel):
    kind: Literal["equity"] = "equity"
    ticker: str

    @property
    def symbol(self) -> str:
        return self.ticker


class OptionInstrument(BaseModel):
    """v1 scope is single-leg only (long calls/puts). Multi-leg/spread combos
    are out of scope until the broker adapters support combo orders.
    """

    kind: Literal["option"] = "option"
    underlying: str
    expiry: date
    strike: float
    right: OptionRight

    @property
    def symbol(self) -> str:
        right_code = "C" if self.right is OptionRight.CALL else "P"
        strike_code = f"{round(self.strike * 1000):08d}"
        return f"{self.underlying}{self.expiry:%y%m%d}{right_code}{strike_code}"


Instrument = Annotated[Union[EquityInstrument, OptionInstrument], Field(discriminator="kind")]


class OrderIntent(BaseModel):
    """A fully-specified order. `reference_price` is always populated (equal to
    `limit_price` for limit orders, or the last quote/mark for market orders) so
    risk sizing checks never depend on order type.
    """

    client_order_id: str
    instrument: Instrument
    side: Side
    qty: int = Field(gt=0)
    order_type: OrderType
    limit_price: float | None = None
    reference_price: float = Field(gt=0)
    time_in_force: TimeInForce = TimeInForce.DAY
    created_at: datetime

    @property
    def notional(self) -> float:
        return self.qty * self.reference_price


class Fill(BaseModel):
    client_order_id: str
    fill_price: float
    fill_qty: int
    filled_at: datetime


class Position(BaseModel):
    """`market_value` is the current notional value of the position (always
    non-negative); direction is carried by the sign of `qty`.
    """

    instrument: Instrument
    qty: int
    avg_entry_price: float
    market_value: float = Field(ge=0)


class AccountState(BaseModel):
    """A snapshot of account + market state at decision time. `starting_equity_today`
    is the equity value at the start of the trading day and is the denominator for
    the daily-loss-limit check (not current equity, which already reflects the loss).
    """

    equity: float
    starting_equity_today: float
    cash: float
    daily_realized_pnl: float = 0.0
    trades_today: int = 0
    open_positions: list[Position] = Field(default_factory=list)
    market_data_age_seconds: float = 0.0

    @property
    def total_exposure(self) -> float:
        return sum(p.market_value for p in self.open_positions)

    @property
    def daily_loss_pct(self) -> float:
        if self.starting_equity_today <= 0:
            return 0.0
        loss = max(-self.daily_realized_pnl, 0.0)
        return (loss / self.starting_equity_today) * 100.0


class OrderStatusValue(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"


class OrderAck(BaseModel):
    client_order_id: str
    status: OrderStatusValue
    fill: Fill | None = None


class RiskDecision(BaseModel):
    allowed: bool
    rule: str | None = None
    reason: str | None = None

    @classmethod
    def allow(cls) -> "RiskDecision":
        return cls(allowed=True)

    @classmethod
    def block(cls, rule: str, reason: str) -> "RiskDecision":
        return cls(allowed=False, rule=rule, reason=reason)
