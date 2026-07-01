"""Historical OHLCV bar loader, used by `backtest/engine.py` to source the
bars it replays.

`alpaca-py` is imported lazily inside `load_bars()`, not at module scope, so
the base package (`pip install .`) never requires it — only `pip install
.[live]` does. This is the only place outside `broker/alpaca_broker.py` that
talks to Alpaca.
"""
from __future__ import annotations

from datetime import datetime

from config.settings import Settings
from core.models import Bar


def load_bars(
    ticker: str,
    start: datetime,
    end: datetime,
    settings: Settings,
    timeframe_minutes: int = 1,
) -> list[Bar]:
    """Fetch historical bars for `ticker` between `start` and `end`
    (inclusive) from Alpaca's historical data API, in `core.models.Bar` shape.
    """
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    client = StockHistoricalDataClient(settings.alpaca_api_key, settings.alpaca_secret_key)
    timeframe = TimeFrame.Minute if timeframe_minutes == 1 else TimeFrame(timeframe_minutes, TimeFrame.Unit.Minute)
    request = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=timeframe,
        start=start,
        end=end,
    )
    bar_set = client.get_stock_bars(request)
    return [
        Bar(
            ticker=ticker,
            timestamp=raw.timestamp,
            open=raw.open,
            high=raw.high,
            low=raw.low,
            close=raw.close,
            volume=raw.volume or 0.0,
        )
        for raw in bar_set[ticker]
    ]
