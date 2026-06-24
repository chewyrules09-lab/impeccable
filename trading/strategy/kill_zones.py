"""Wires the strategy layer to `core.clock.is_in_killzone` and
`Settings.universe`: a bar is only eligible for signal evaluation if its
ticker is in the configured universe and its timestamp falls inside one of
the configured AM/PM kill-zone windows.
"""
from __future__ import annotations

from config.settings import Settings
from core.clock import is_in_killzone
from core.models import Bar


def tradable_universe(settings: Settings) -> list[str]:
    return settings.universe


def is_killzone_bar(bar: Bar, settings: Settings) -> bool:
    if bar.ticker not in settings.universe:
        return False
    return is_in_killzone(bar.timestamp, settings)
