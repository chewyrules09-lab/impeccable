from __future__ import annotations

from pydantic import BaseModel, Field


class StrategyConfig(BaseModel):
    """Thresholds for the ICT/TJR detectors in `strategy/`. Defaults here
    match `.env.example`; override via `Settings.strategy_config()`.
    """

    swing_lookback: int = Field(default=2, gt=0)
    min_fvg_size: float = Field(default=0.0, ge=0)
    equal_level_tolerance_pct: float = Field(default=0.05, ge=0)
    liquidity_lookback_bars: int = Field(default=20, gt=0)
    order_block_lookback_bars: int = Field(default=10, gt=0)
    stop_buffer_pct: float = Field(default=0.05, ge=0)
    target_r_multiple: float = Field(default=2.0, gt=0)
