from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.models import (
    AccountState,
    EquityInstrument,
    Fill,
    OrderIntent,
    OrderType,
    Position,
    Side,
)
from risk.engine import RiskEngine
from risk.limits import RiskLimits

# Each test hand-builds the minimal AccountState/OrderIntent that isolates a
# single rule: every field checked *before* the rule under test is left at a
# safe default so the engine actually reaches that rule.


@pytest.fixture
def limits() -> RiskLimits:
    return RiskLimits()


@pytest.fixture
def engine(limits: RiskLimits) -> RiskEngine:
    return RiskEngine(limits)


def make_intent(qty: int = 1, reference_price: float = 100.0) -> OrderIntent:
    return OrderIntent(
        client_order_id="test-order-1",
        instrument=EquityInstrument(ticker="SPY"),
        side=Side.BUY,
        qty=qty,
        order_type=OrderType.MARKET,
        reference_price=reference_price,
        created_at=datetime.now(timezone.utc),
    )


def make_account(
    equity: float = 100_000.0,
    starting_equity_today: float = 100_000.0,
    daily_realized_pnl: float = 0.0,
    trades_today: int = 0,
    open_positions: list[Position] | None = None,
    market_data_age_seconds: float = 0.0,
) -> AccountState:
    return AccountState(
        equity=equity,
        starting_equity_today=starting_equity_today,
        cash=equity,
        daily_realized_pnl=daily_realized_pnl,
        trades_today=trades_today,
        open_positions=open_positions or [],
        market_data_age_seconds=market_data_age_seconds,
    )


def make_position(market_value: float, qty: int = 1) -> Position:
    return Position(
        instrument=EquityInstrument(ticker="QQQ"),
        qty=qty,
        avg_entry_price=market_value / qty,
        market_value=market_value,
    )


def test_allow_when_all_limits_respected(engine: RiskEngine) -> None:
    intent = make_intent(qty=10, reference_price=100.0)  # $1,000 notional
    account = make_account()
    decision = engine.evaluate(intent, account)
    assert decision.allowed
    assert decision.rule is None


def test_blocks_on_stale_market_data(engine: RiskEngine, limits: RiskLimits) -> None:
    intent = make_intent()
    account = make_account(market_data_age_seconds=limits.max_market_data_age_seconds + 1)
    decision = engine.evaluate(intent, account)
    assert not decision.allowed
    assert decision.rule == "stale_market_data"


def test_allows_when_market_data_fresh(engine: RiskEngine, limits: RiskLimits) -> None:
    intent = make_intent()
    account = make_account(market_data_age_seconds=limits.max_market_data_age_seconds - 1)
    decision = engine.evaluate(intent, account)
    assert decision.allowed


def test_blocks_on_max_daily_loss(engine: RiskEngine, limits: RiskLimits) -> None:
    intent = make_intent()
    account = make_account(daily_realized_pnl=-(100_000.0 * limits.max_daily_loss_pct / 100.0))
    decision = engine.evaluate(intent, account)
    assert not decision.allowed
    assert decision.rule == "max_daily_loss"


def test_allows_under_max_daily_loss(engine: RiskEngine, limits: RiskLimits) -> None:
    intent = make_intent()
    account = make_account(daily_realized_pnl=-(100_000.0 * limits.max_daily_loss_pct / 100.0 - 1.0))
    decision = engine.evaluate(intent, account)
    assert decision.allowed


def test_blocks_on_max_trades_per_day(engine: RiskEngine, limits: RiskLimits) -> None:
    intent = make_intent()
    account = make_account(trades_today=limits.max_trades_per_day)
    decision = engine.evaluate(intent, account)
    assert not decision.allowed
    assert decision.rule == "max_trades_per_day"


def test_allows_under_max_trades_per_day(engine: RiskEngine, limits: RiskLimits) -> None:
    intent = make_intent()
    account = make_account(trades_today=limits.max_trades_per_day - 1)
    decision = engine.evaluate(intent, account)
    assert decision.allowed


def test_blocks_on_max_concurrent_positions(engine: RiskEngine, limits: RiskLimits) -> None:
    intent = make_intent()
    positions = [make_position(1_000.0) for _ in range(limits.max_concurrent_positions)]
    account = make_account(open_positions=positions)
    decision = engine.evaluate(intent, account)
    assert not decision.allowed
    assert decision.rule == "max_concurrent_positions"


def test_allows_under_max_concurrent_positions(engine: RiskEngine, limits: RiskLimits) -> None:
    intent = make_intent()
    positions = [make_position(1_000.0) for _ in range(limits.max_concurrent_positions - 1)]
    account = make_account(open_positions=positions)
    decision = engine.evaluate(intent, account)
    assert decision.allowed


def test_blocks_on_max_position_size(engine: RiskEngine, limits: RiskLimits) -> None:
    equity = 100_000.0
    max_notional = equity * limits.max_position_size_pct / 100.0
    account = make_account(equity=equity)
    intent = make_intent(qty=1, reference_price=max_notional + 100.0)
    decision = engine.evaluate(intent, account)
    assert not decision.allowed
    assert decision.rule == "max_position_size"


def test_allows_under_max_position_size(engine: RiskEngine, limits: RiskLimits) -> None:
    equity = 100_000.0
    max_notional = equity * limits.max_position_size_pct / 100.0
    account = make_account(equity=equity)
    intent = make_intent(qty=1, reference_price=max_notional - 100.0)
    decision = engine.evaluate(intent, account)
    assert decision.allowed


def test_blocks_on_max_total_exposure(engine: RiskEngine, limits: RiskLimits) -> None:
    equity = 100_000.0
    max_position_notional = equity * limits.max_position_size_pct / 100.0
    max_exposure = equity * limits.max_total_exposure_pct / 100.0
    existing_position = make_position(max_exposure - max_position_notional + 1_000.0)
    account = make_account(equity=equity, open_positions=[existing_position])
    intent = make_intent(qty=1, reference_price=max_position_notional - 1.0)
    decision = engine.evaluate(intent, account)
    assert not decision.allowed
    assert decision.rule == "max_total_exposure"


def test_allows_under_max_total_exposure(engine: RiskEngine, limits: RiskLimits) -> None:
    equity = 100_000.0
    max_exposure = equity * limits.max_total_exposure_pct / 100.0
    existing_position = make_position(max_exposure / 2)
    account = make_account(equity=equity, open_positions=[existing_position])
    intent = make_intent(qty=1, reference_price=100.0)
    decision = engine.evaluate(intent, account)
    assert decision.allowed


def test_check_fill_anomaly_blocks_on_large_deviation(engine: RiskEngine) -> None:
    fill = Fill(
        client_order_id="test-order-1",
        fill_price=110.0,
        fill_qty=10,
        filled_at=datetime.now(timezone.utc),
    )
    decision = engine.check_fill_anomaly(fill, expected_price=100.0)
    assert not decision.allowed
    assert decision.rule == "anomaly_fill_price"


def test_check_fill_anomaly_allows_small_deviation(engine: RiskEngine) -> None:
    fill = Fill(
        client_order_id="test-order-1",
        fill_price=100.5,
        fill_qty=10,
        filled_at=datetime.now(timezone.utc),
    )
    decision = engine.check_fill_anomaly(fill, expected_price=100.0)
    assert decision.allowed
