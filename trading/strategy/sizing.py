"""Phase 1 stub.

Will compute position size from `RiskLimits.risk_per_trade_pct` and the
stop distance implied by a signal's entry/stop:

    size = floor((equity * risk_per_trade_pct / 100) / abs(entry - stop))

The risk engine's `max_position_size_pct` / `max_total_exposure_pct` checks in
`risk/engine.py` remain the final, independent gate after this sizing step;
this module only proposes a size, it does not bypass risk checks.
"""
