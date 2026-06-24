from __future__ import annotations

from strategy.sizing import position_size


def test_position_size_floors_to_the_nearest_whole_share() -> None:
    # risk_amount = 100,000 * 1% = 1,000; distance = 1 -> 1,000 shares
    assert position_size(equity=100_000.0, risk_per_trade_pct=1.0, entry=100.0, stop=99.0) == 1_000


def test_position_size_floors_a_fractional_result() -> None:
    # risk_amount = 1,000; distance = 5.5 -> floor(181.81...) = 181
    assert position_size(equity=100_000.0, risk_per_trade_pct=1.0, entry=100.5, stop=95.0) == 181


def test_position_size_is_zero_when_stop_equals_entry() -> None:
    assert position_size(equity=100_000.0, risk_per_trade_pct=1.0, entry=100.0, stop=100.0) == 0
