"""Phase 2 stub.

Will load historical OHLCV bars from Alpaca (equities) for the configured
universe and timeframe via `alpaca-py`'s historical data client, returned in
whatever bar shape `backtest/engine.py` and `strategy/` consume. Options
historical data sourcing (for backtesting the options leg of v1) is decided
when this module is implemented, not in Phase 0.
"""
