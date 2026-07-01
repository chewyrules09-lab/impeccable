"""Summary statistics computed from a completed `BacktestResult`. Feeds
`validation/gate.py` (Phase 3) and backtest/paper session reports.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from backtest.engine import BacktestResult


@dataclass
class Metrics:
    total_trades: int
    win_rate: float
    profit_factor: float | None
    max_drawdown_pct: float
    sharpe_ratio: float | None
    avg_r_multiple: float | None
    expectancy_r: float | None
    total_return_pct: float


def compute_metrics(result: BacktestResult) -> Metrics:
    closed = [t for t in result.trades if t.pnl is not None]
    total_trades = len(closed)
    wins = [t for t in closed if (t.pnl or 0) > 0]
    losses = [t for t in closed if (t.pnl or 0) <= 0]
    win_rate = len(wins) / total_trades if total_trades else 0.0

    gross_profit = sum(t.pnl or 0.0 for t in wins)
    gross_loss = abs(sum(t.pnl or 0.0 for t in losses))
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = math.inf if gross_profit > 0 else None

    r_multiples = [t.r_multiple for t in closed if t.r_multiple is not None]
    avg_r_multiple = sum(r_multiples) / len(r_multiples) if r_multiples else None

    max_drawdown_pct = _max_drawdown_pct(result)
    sharpe_ratio = _daily_sharpe_ratio(result)

    total_return_pct = (
        (result.final_equity - result.starting_equity) / result.starting_equity * 100.0
        if result.starting_equity > 0
        else 0.0
    )

    return Metrics(
        total_trades=total_trades,
        win_rate=win_rate,
        profit_factor=profit_factor,
        max_drawdown_pct=max_drawdown_pct,
        sharpe_ratio=sharpe_ratio,
        avg_r_multiple=avg_r_multiple,
        expectancy_r=avg_r_multiple,
        total_return_pct=total_return_pct,
    )


def _max_drawdown_pct(result: BacktestResult) -> float:
    values = [v for _, v in result.equity_curve] or [result.starting_equity]
    peak = values[0]
    max_dd = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_dd = max(max_dd, (peak - value) / peak * 100.0)
    return max_dd


def _daily_sharpe_ratio(result: BacktestResult) -> float | None:
    """Annualized Sharpe over end-of-day equity (252 trading days/year), not
    per-bar returns — intraday bars are far noisier than the daily horizon
    this ratio is conventionally interpreted at.
    """
    daily_equity: dict[object, float] = {}
    for ts, value in result.equity_curve:
        daily_equity[ts.date()] = value
    daily_values = list(daily_equity.values())
    daily_returns = [
        (curr - prev) / prev for prev, curr in zip(daily_values, daily_values[1:]) if prev > 0
    ]
    if len(daily_returns) < 2:
        return None
    mean_r = statistics.mean(daily_returns)
    std_r = statistics.stdev(daily_returns)
    if std_r == 0:
        return None
    return (mean_r / std_r) * math.sqrt(252)
