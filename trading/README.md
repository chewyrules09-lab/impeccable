# ICT/TJR Autonomous Trading System

A daily-running trading system built around one rule: the LLM/MCP layer is an **execution rail only**. It never makes a discretionary trading decision at runtime. Every signal, entry, stop, target, and position size comes from deterministic Python that is read, tested, and backtested before it ever sees real money.

## How it works

1. **Decide** - an explicit ICT/TJR rule set (market structure, fair value gaps, order blocks, liquidity sweeps, kill zones) computes trade signals from price data. Pure Python, no model in the loop.
2. **Validate** - the same logic runs through an event-driven backtest, then a run of Alpaca paper-trading sessions, against a fixed bar it must clear before anything is allowed near real money.
3. **Execute** - once validated, signals are placed as fully-specified orders (ticker, side, qty, order type, limit price, time-in-force) through the Robinhood Agentic Trading MCP. The MCP step has zero discretion: it places exactly what the Python engine decided.

A risk engine runs before every order in every mode. A kill switch and a daily Markdown report run regardless of mode.

## Status

This repo currently implements **Phase 0 (scaffold)**, **Phase 1 (ICT/TJR strategy engine)**, and **Phase 2 (event-driven backtest)**: config, core models, the risk engine, persistence, the broker interface, a `DryRunBroker`, the full market-structure/FVG/order-block/liquidity/kill-zone detectors feeding `strategy/signals.py`, and a backtest engine (`backtest/engine.py`) that replays historical bars through those signals with resting limit-order fills, risk-engine gating, and full audit persistence. Optional `backtest/plot.py` (`pip install .[viz]`) renders an equity curve and a price/trade chart from a `BacktestResult`. Phases 3-5 (paper-validation gate, live execution, daily operation) are stubbed with phase-tagged docstrings and are not implemented yet. See the project plan for the full phase breakdown.

## Mode control

A single setting controls everything: `TRADING_MODE` = `backtest` | `paper` | `live`. The hard-coded fallback for any missing or invalid value is `paper`; there is no code path that defaults to `live`.

`live` additionally requires, simultaneously:
- `LIVE_CONFIRMED=true`
- a `validation_report.json` on disk that meets the Phase 3 validation gate (see below)

`run_session.py` checks both before doing anything else in live mode. Until both exist, live mode is not reachable, not "discouraged."

## Risk limits

Checked by `risk/engine.py` before every order, in every mode:

| Limit | Default |
|---|---|
| Max daily loss | 2% of account equity, halts new orders for the day and flattens |
| Max single position size | 10% of equity (notional) |
| Max trades per day | 5 |
| Max concurrent open positions | 2 |
| Max total exposure at once | 50% of equity (sum of open notional) |
| Max market data age | 60 seconds; no new entries on stale data |
| Anomaly: fill price deviation vs. expected | 1%, halts and notifies, no auto-retry |
| Risk per trade (sizing input) | 1% of equity per trade |

All of these are environment-configurable; the table above lists the hard-coded defaults. See `.env.example`.

## Kill zones

ICT methodology was built on index futures/FX session structure. Equities only have RTH (9:30-16:00 ET), so the kill zones here are the open (09:30-11:00 ET) and an afternoon window (13:30-15:30 ET), against a default universe of liquid index ETFs (`SPY`, `QQQ`) as the closest equities analog. All configurable, not hard-coded.

## Kill switch

Two independent ways to stop:
1. Set `KILL=true` in the environment. `run_session.py` checks this before every cycle; on a true value it refuses new orders, attempts to flatten open positions, and exits.
2. Manually disconnect the Robinhood MCP connector in Claude's connector settings. This severs the execution rail entirely, independent of anything this codebase does.

## Validation gate (Phase 3)

Live mode unlocks only when a `validation_report.json` shows all of the following, generated from a real run of paper sessions:

| Metric | Bar |
|---|---|
| Paper sessions completed | >= 20 |
| Total trades | >= 30 |
| Profit factor | > 1.3 |
| Max drawdown | < 10% |
| Expectancy | > 0 |

This is enforced in code (`validation/gate.py`), not just documentation.

## Quickstart

```bash
cd trading
uv sync --extra dev
cp .env.example .env
uv run pytest -v
```

## Project layout

```
config/        settings, mode gate
core/          models, idempotent order IDs, kill-zone clock
risk/          risk limits + the risk engine
persistence/   SQLite schema, connection, repository
broker/        Broker interface, DryRunBroker (Phase 0), Alpaca/Robinhood adapters (later phases)
strategy/      ICT/TJR signal logic (Phase 1)
backtest/      event-driven backtest harness (Phase 2)
validation/    validation gate enforcement (Phase 3)
reporting/     daily Markdown report generation (Phase 3/5)
run_session.py daily entrypoint (minimal in Phase 0: settings + kill switch + live-mode gate only)
tests/         pytest suite
```

## Reality check

This is autonomous real-money trading. Most retail discretionary strategies — ICT/TJR included — do not survive contact with live markets, and codifying discretion often performs worse than the trader. Robinhood itself warns the agent can misinterpret instructions and you can lose the entire balance. This system is a tool, not an edge; the validation gate exists to find out whether there's an edge BEFORE risking money I'd rather use on debt. I accept full responsibility for every trade it places. (Not financial advice — Claude is not a financial advisor.)
