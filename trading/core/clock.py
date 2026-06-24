from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from config.settings import Settings

EASTERN = ZoneInfo("America/New_York")

_MARKET_OPEN = time(9, 30)
_MARKET_CLOSE = time(16, 0)


def now_et() -> datetime:
    """The one function in this module that reads the real wall clock. Every
    other function takes `ts` as a parameter so tests can inject a fixed time.
    """
    return datetime.now(EASTERN)


def is_market_hours(ts: datetime) -> bool:
    ts_et = ts.astimezone(EASTERN)
    if ts_et.weekday() >= 5:
        return False
    return _MARKET_OPEN <= ts_et.time() < _MARKET_CLOSE


def is_in_killzone(ts: datetime, settings: Settings) -> bool:
    ts_et = ts.astimezone(EASTERN)
    if ts_et.weekday() >= 5:
        return False
    t = ts_et.time()
    in_am = settings.killzone_am_start <= t < settings.killzone_am_end
    in_pm = settings.killzone_pm_start <= t < settings.killzone_pm_end
    return in_am or in_pm
