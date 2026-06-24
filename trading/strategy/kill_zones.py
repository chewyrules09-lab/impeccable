"""Phase 1 stub.

Will wire the strategy layer's per-bar evaluation to `core.clock.is_in_killzone`
and `Settings.universe`: no signal is generated outside the configured AM/PM
kill-zone windows, and only for tickers in the configured universe. The
window/universe config itself already lives in `config/settings.py` (see
KILLZONE_* and UNIVERSE in .env.example); this module is where the strategy
loop consumes it.
"""
