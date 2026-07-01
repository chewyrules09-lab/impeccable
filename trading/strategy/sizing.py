"""Position sizing: risk a fixed % of equity per trade, sized by the stop
distance implied by a signal's entry/stop. The risk engine's
`max_position_size_pct` / `max_total_exposure_pct` checks in `risk/engine.py`
remain the final, independent gate after this — sizing only proposes a size,
it never bypasses risk checks.
"""
from __future__ import annotations

import math


def position_size(equity: float, risk_per_trade_pct: float, entry: float, stop: float) -> int:
    distance = abs(entry - stop)
    if distance <= 0:
        return 0
    risk_amount = equity * risk_per_trade_pct / 100.0
    return math.floor(risk_amount / distance)
