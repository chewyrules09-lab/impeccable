from __future__ import annotations

from core.models import AccountState, Fill, OrderIntent, RiskDecision
from risk.limits import RiskLimits


class RiskEngine:
    """Always-on, checked before every order in every mode (backtest, paper,
    live). Rules run in a fixed order; the first violated rule blocks the
    order with a machine-readable `rule` name and a human `reason`.
    `check_fill_anomaly` is the post-fill counterpart for the "anomaly auto-halt"
    requirement and is called separately once a fill is reported.
    """

    def __init__(self, limits: RiskLimits) -> None:
        self.limits = limits

    def evaluate(self, intent: OrderIntent, account: AccountState) -> RiskDecision:
        if account.market_data_age_seconds > self.limits.max_market_data_age_seconds:
            return RiskDecision.block(
                "stale_market_data",
                f"Market data is {account.market_data_age_seconds:.0f}s old, "
                f"exceeds the {self.limits.max_market_data_age_seconds}s limit.",
            )

        if account.daily_loss_pct >= self.limits.max_daily_loss_pct:
            return RiskDecision.block(
                "max_daily_loss",
                f"Daily loss {account.daily_loss_pct:.2f}% has reached the "
                f"{self.limits.max_daily_loss_pct}% limit; halt for the day.",
            )

        if account.trades_today >= self.limits.max_trades_per_day:
            return RiskDecision.block(
                "max_trades_per_day",
                f"Already placed {account.trades_today} trade(s) today, "
                f"at the {self.limits.max_trades_per_day} limit.",
            )

        if len(account.open_positions) >= self.limits.max_concurrent_positions:
            return RiskDecision.block(
                "max_concurrent_positions",
                f"Already holding {len(account.open_positions)} open position(s), "
                f"at the {self.limits.max_concurrent_positions} limit.",
            )

        max_position_notional = account.equity * (self.limits.max_position_size_pct / 100.0)
        if intent.notional > max_position_notional:
            return RiskDecision.block(
                "max_position_size",
                f"Order notional ${intent.notional:,.2f} exceeds the "
                f"{self.limits.max_position_size_pct}% (${max_position_notional:,.2f}) limit.",
            )

        max_exposure = account.equity * (self.limits.max_total_exposure_pct / 100.0)
        projected_exposure = account.total_exposure + intent.notional
        if projected_exposure > max_exposure:
            return RiskDecision.block(
                "max_total_exposure",
                f"Projected exposure ${projected_exposure:,.2f} would exceed the "
                f"{self.limits.max_total_exposure_pct}% (${max_exposure:,.2f}) limit.",
            )

        return RiskDecision.allow()

    def check_fill_anomaly(self, fill: Fill, expected_price: float) -> RiskDecision:
        if expected_price <= 0:
            return RiskDecision.allow()
        deviation_pct = abs(fill.fill_price - expected_price) / expected_price * 100.0
        if deviation_pct > self.limits.anomaly_fill_price_deviation_pct:
            return RiskDecision.block(
                "anomaly_fill_price",
                f"Fill price {fill.fill_price} deviates {deviation_pct:.2f}% from the "
                f"expected {expected_price}, exceeds the "
                f"{self.limits.anomaly_fill_price_deviation_pct}% anomaly bound.",
            )
        return RiskDecision.allow()
