from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from config.settings import Settings
from core.models import Bar
from strategy.kill_zones import is_killzone_bar, tradable_universe

_EASTERN = ZoneInfo("America/New_York")


def make_bar(ticker: str, ts: datetime) -> Bar:
    return Bar(ticker=ticker, timestamp=ts, open=100, high=101, low=99, close=100)


def test_tradable_universe_reflects_settings() -> None:
    settings = Settings(universe=["SPY", "QQQ"])
    assert tradable_universe(settings) == ["SPY", "QQQ"]


def test_bar_inside_kill_zone_and_universe_is_tradable() -> None:
    settings = Settings()
    bar = make_bar("SPY", datetime(2024, 1, 2, 9, 45, tzinfo=_EASTERN))
    assert is_killzone_bar(bar, settings)


def test_bar_outside_kill_zone_window_is_not_tradable() -> None:
    settings = Settings()
    bar = make_bar("SPY", datetime(2024, 1, 2, 8, 0, tzinfo=_EASTERN))
    assert not is_killzone_bar(bar, settings)


def test_bar_outside_the_configured_universe_is_not_tradable() -> None:
    settings = Settings(universe=["SPY", "QQQ"])
    bar = make_bar("TSLA", datetime(2024, 1, 2, 9, 45, tzinfo=_EASTERN))
    assert not is_killzone_bar(bar, settings)
