"""Backtest visualization. Not part of the original Phase 0 file tree — added
so a backtest run can be inspected visually, not just through metrics.

Optional dependency on `matplotlib` (`pip install .[viz]`); importing this
module without it installed raises ImportError only when a plot function is
actually called, not at import time.
"""
from __future__ import annotations

from pathlib import Path

from backtest.engine import BacktestResult
from core.models import Bar


def plot_equity_curve(result: BacktestResult, path: str | Path, title: str = "Equity Curve") -> Path:
    import matplotlib.pyplot as plt

    out_path = Path(path)
    times = [ts for ts, _ in result.equity_curve]
    values = [v for _, v in result.equity_curve]

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(times, values, color="#1f6feb", linewidth=1.4)
    ax.axhline(result.starting_equity, color="#888888", linestyle="--", linewidth=0.8, label="Starting equity")
    ax.set_title(title)
    ax.set_ylabel("Equity ($)")
    ax.set_xlabel("Time")
    ax.legend(loc="upper left", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path


def plot_price_with_trades(bars: list[Bar], result: BacktestResult, path: str | Path, ticker: str) -> Path:
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    out_path = Path(path)
    times = [b.timestamp for b in bars]
    closes = [b.close for b in bars]

    fig, ax = plt.subplots(figsize=(13, 5.5))
    ax.plot(times, closes, color="#444444", linewidth=0.9, zorder=1, label="Close")

    for trade in result.trades:
        win = (trade.pnl or 0) >= 0
        exit_color = "#1a7f37" if win else "#cf222e"
        exit_end = trade.exit_time or times[-1]
        ax.hlines(trade.stop, trade.entry_time, exit_end, color="#cf222e", linestyle=":", linewidth=1.1, zorder=2)
        ax.hlines(trade.target, trade.entry_time, exit_end, color="#1a7f37", linestyle=":", linewidth=1.1, zorder=2)
        ax.scatter([trade.entry_time], [trade.entry_price], marker="^", color="#1f6feb", s=70, zorder=3)
        if trade.exit_time is not None:
            ax.scatter([trade.exit_time], [trade.exit_price], marker="v", color=exit_color, s=70, zorder=3)

    legend_handles = [
        Line2D([0], [0], marker="^", color="w", markerfacecolor="#1f6feb", markersize=9, label="Entry"),
        Line2D([0], [0], marker="v", color="w", markerfacecolor="#1a7f37", markersize=9, label="Exit (win)"),
        Line2D([0], [0], marker="v", color="w", markerfacecolor="#cf222e", markersize=9, label="Exit (loss)"),
        Line2D([0], [0], color="#cf222e", linestyle=":", label="Stop"),
        Line2D([0], [0], color="#1a7f37", linestyle=":", label="Target"),
    ]
    ax.legend(handles=legend_handles, loc="upper left", fontsize=8)
    ax.set_title(f"{ticker} — price with ICT/TJR signals")
    ax.set_ylabel("Price")
    ax.set_xlabel("Time")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path
