from __future__ import annotations

from datetime import datetime, time
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from risk.limits import RiskLimits
from strategy.config import StrategyConfig

TradingMode = Literal["backtest", "paper", "live"]
_DEFAULT_MODE: TradingMode = "paper"
_VALID_MODES = {"backtest", "paper", "live"}


class Settings(BaseSettings):
    """Single source of truth for runtime config. TRADING_MODE has a hard-coded
    fallback to "paper": there is no code path, valid or invalid input, that
    produces "live" by default.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    trading_mode: TradingMode = _DEFAULT_MODE
    live_confirmed: bool = False
    kill: bool = False

    # Risk limits (flat to mirror .env.example; see risk_limits() below).
    max_daily_loss_pct: float = 2.0
    max_position_size_pct: float = 10.0
    max_trades_per_day: int = 5
    max_concurrent_positions: int = 2
    max_total_exposure_pct: float = 50.0
    max_market_data_age_seconds: int = 60
    anomaly_fill_price_deviation_pct: float = 1.0
    risk_per_trade_pct: float = 1.0

    # Strategy config (ICT/TJR detector thresholds; see strategy/config.py).
    strategy_swing_lookback: int = 2
    strategy_min_fvg_size: float = 0.0
    strategy_equal_level_tolerance_pct: float = 0.05
    strategy_liquidity_lookback_bars: int = 20
    strategy_order_block_lookback_bars: int = 10
    strategy_stop_buffer_pct: float = 0.05
    strategy_target_r_multiple: float = 2.0

    # Kill zones (RTH only, ET).
    killzone_am_start: time = time(9, 30)
    killzone_am_end: time = time(11, 0)
    killzone_pm_start: time = time(13, 30)
    killzone_pm_end: time = time(15, 30)
    # NoDecode: pydantic-settings otherwise tries to JSON-decode env values
    # for list-typed fields before any validator runs, which fails on a
    # plain comma-separated string like "SPY,QQQ".
    universe: Annotated[list[str], NoDecode] = ["SPY", "QQQ"]

    # Phase 3 validation gate.
    validation_min_paper_sessions: int = 20
    validation_min_trades: int = 30
    validation_min_profit_factor: float = 1.3
    validation_max_drawdown_pct: float = 10.0
    validation_min_expectancy_r: float = 0.0

    # Informational only; this code never moves funds into the account.
    live_starting_balance_usd: float = 200.0

    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_paper_base_url: str = "https://paper-api.alpaca.markets"

    robinhood_mcp_url: str = "https://agent.robinhood.com/mcp/trading"

    database_path: str = "./trading.db"

    @field_validator("trading_mode", mode="before")
    @classmethod
    def _fallback_invalid_mode(cls, v: object) -> TradingMode:
        if isinstance(v, str) and v.strip().lower() in _VALID_MODES:
            return v.strip().lower()  # type: ignore[return-value]
        return _DEFAULT_MODE

    @field_validator("universe", mode="before")
    @classmethod
    def _split_universe(cls, v: object) -> object:
        if isinstance(v, str):
            return [ticker.strip().upper() for ticker in v.split(",") if ticker.strip()]
        return v

    @field_validator(
        "killzone_am_start", "killzone_am_end", "killzone_pm_start", "killzone_pm_end",
        mode="before",
    )
    @classmethod
    def _parse_clock_time(cls, v: object) -> object:
        if isinstance(v, str):
            for fmt in ("%H:%M:%S", "%H:%M"):
                try:
                    return datetime.strptime(v, fmt).time()
                except ValueError:
                    continue
            raise ValueError(f"Invalid time format: {v!r}, expected HH:MM")
        return v

    def risk_limits(self) -> RiskLimits:
        return RiskLimits(
            max_daily_loss_pct=self.max_daily_loss_pct,
            max_position_size_pct=self.max_position_size_pct,
            max_trades_per_day=self.max_trades_per_day,
            max_concurrent_positions=self.max_concurrent_positions,
            max_total_exposure_pct=self.max_total_exposure_pct,
            max_market_data_age_seconds=self.max_market_data_age_seconds,
            anomaly_fill_price_deviation_pct=self.anomaly_fill_price_deviation_pct,
            risk_per_trade_pct=self.risk_per_trade_pct,
        )

    def strategy_config(self) -> StrategyConfig:
        return StrategyConfig(
            swing_lookback=self.strategy_swing_lookback,
            min_fvg_size=self.strategy_min_fvg_size,
            equal_level_tolerance_pct=self.strategy_equal_level_tolerance_pct,
            liquidity_lookback_bars=self.strategy_liquidity_lookback_bars,
            order_block_lookback_bars=self.strategy_order_block_lookback_bars,
            stop_buffer_pct=self.strategy_stop_buffer_pct,
            target_r_multiple=self.strategy_target_r_multiple,
        )
