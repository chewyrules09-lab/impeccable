from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from core.models import (
    AccountState,
    EquityInstrument,
    OptionInstrument,
    OptionRight,
    OrderIntent,
    OrderType,
    Position,
    RiskDecision,
    Side,
)


def test_equity_instrument_symbol() -> None:
    instrument = EquityInstrument(ticker="SPY")
    assert instrument.symbol == "SPY"
    assert instrument.kind == "equity"


def test_option_instrument_symbol() -> None:
    instrument = OptionInstrument(
        underlying="SPY",
        expiry=date(2025, 1, 17),
        strike=450.0,
        right=OptionRight.CALL,
    )
    assert instrument.symbol == "SPY250117C00450000"


def test_order_intent_notional() -> None:
    intent = OrderIntent(
        client_order_id="abc",
        instrument=EquityInstrument(ticker="SPY"),
        side=Side.BUY,
        qty=10,
        order_type=OrderType.MARKET,
        reference_price=100.0,
        created_at=datetime.now(timezone.utc),
    )
    assert intent.notional == 1_000.0


def test_order_intent_requires_positive_qty() -> None:
    with pytest.raises(ValidationError):
        OrderIntent(
            client_order_id="abc",
            instrument=EquityInstrument(ticker="SPY"),
            side=Side.BUY,
            qty=0,
            order_type=OrderType.MARKET,
            reference_price=100.0,
            created_at=datetime.now(timezone.utc),
        )


def test_account_state_total_exposure() -> None:
    position = Position(
        instrument=EquityInstrument(ticker="SPY"),
        qty=10,
        avg_entry_price=100.0,
        market_value=1_000.0,
    )
    account = AccountState(
        equity=100_000.0,
        starting_equity_today=100_000.0,
        cash=99_000.0,
        open_positions=[position],
    )
    assert account.total_exposure == 1_000.0


def test_account_state_daily_loss_pct() -> None:
    account = AccountState(
        equity=98_000.0,
        starting_equity_today=100_000.0,
        cash=98_000.0,
        daily_realized_pnl=-2_000.0,
    )
    assert account.daily_loss_pct == pytest.approx(2.0)


def test_account_state_daily_loss_pct_is_zero_when_profitable() -> None:
    account = AccountState(
        equity=101_000.0,
        starting_equity_today=100_000.0,
        cash=101_000.0,
        daily_realized_pnl=1_000.0,
    )
    assert account.daily_loss_pct == 0.0


def test_risk_decision_allow_and_block() -> None:
    allow = RiskDecision.allow()
    assert allow.allowed
    assert allow.rule is None

    block = RiskDecision.block("max_daily_loss", "over limit")
    assert not block.allowed
    assert block.rule == "max_daily_loss"
    assert block.reason == "over limit"
