from pydantic import BaseModel, Field


class RiskLimits(BaseModel):
    """The numeric bounds the risk engine enforces. Defaults here match
    `.env.example` and the README's risk limits table; override via Settings.
    """

    max_daily_loss_pct: float = Field(default=2.0, gt=0)
    max_position_size_pct: float = Field(default=10.0, gt=0)
    max_trades_per_day: int = Field(default=5, gt=0)
    max_concurrent_positions: int = Field(default=2, gt=0)
    max_total_exposure_pct: float = Field(default=50.0, gt=0)
    max_market_data_age_seconds: int = Field(default=60, gt=0)
    anomaly_fill_price_deviation_pct: float = Field(default=1.0, gt=0)
    risk_per_trade_pct: float = Field(default=1.0, gt=0)
