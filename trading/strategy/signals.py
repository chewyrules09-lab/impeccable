"""The Phase 1 centerpiece: combines kill_zones/market_structure/fvg/
order_blocks/liquidity into a single per-bar evaluation.

`evaluate()` is a pure function (no DB, no network): it returns a `Signal`
for `bars[index]`, looking only at `bars[: index + 1]` so it never sees the
future. The caller (the backtest engine in Phase 2, or the live run loop in
later phases) is responsible for persisting every `Signal` — taken or not —
via `persistence.repository.insert_signal(..., taken=..., rules_failed=...)`.

Standard ICT/TJR confluence chain, in order:
  1. kill zone + universe gate (strategy/kill_zones.py)
  2. a structure break (BOS/MSS) on this bar (strategy/market_structure.py)
  3. a fair value gap in the break's direction, formed after the broken swing
     (strategy/fvg.py)
  4. an order block before that FVG's displacement candle (strategy/order_blocks.py)
  5. optional: a liquidity sweep just before the order block — bullish
     reversals pair with a sell-side (lows) sweep, bearish reversals with a
     buy-side (highs) sweep (strategy/liquidity.py)

Entry is the FVG midpoint; stop is the order block's far extreme plus a
buffer; target is the nearest opposing liquidity pool, falling back to a
fixed R-multiple when no pool exists. `confidence` is the fraction of the
four confluence checks (structure break, FVG, order block, liquidity sweep)
that fired.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from config.settings import Settings
from core.models import Bar, Side
from strategy.fvg import FVGDirection, find_fair_value_gaps
from strategy.kill_zones import is_killzone_bar
from strategy.liquidity import LiquidityPoolKind, find_equal_levels, find_recent_sweep
from strategy.market_structure import (
    Direction,
    StructureEventKind,
    detect_structure_events,
    find_swing_points,
)
from strategy.order_blocks import OrderBlockDirection, find_order_block
from strategy.sizing import position_size


class Signal(BaseModel):
    timestamp: datetime
    ticker: str
    side: Side | None = None
    entry: float | None = None
    stop: float | None = None
    target: float | None = None
    size: int | None = None
    confidence: float = 0.0
    rules_fired: list[str] = Field(default_factory=list)
    rules_failed: list[str] = Field(default_factory=list)
    taken: bool = False
    skip_reason: str | None = None


_CONFLUENCE_TAGS = ("structure_break", "fair_value_gap", "order_block", "liquidity_sweep")


def evaluate(bars: list[Bar], index: int, settings: Settings, equity: float) -> Signal:
    bar = bars[index]
    history = bars[: index + 1]
    config = settings.strategy_config()
    rules_fired: list[str] = []
    rules_failed: list[str] = []

    def skip(reason: str) -> Signal:
        return Signal(
            timestamp=bar.timestamp,
            ticker=bar.ticker,
            rules_fired=rules_fired,
            rules_failed=rules_failed,
            taken=False,
            skip_reason=reason,
        )

    if not is_killzone_bar(bar, settings):
        rules_failed.append("kill_zone")
        return skip("outside kill zone or universe")
    rules_fired.append("kill_zone")

    swing_points = find_swing_points(history, lookback=config.swing_lookback)
    structure_events = detect_structure_events(history, swing_points)
    current_events = [e for e in structure_events if e.index == index]
    if not current_events:
        rules_failed.append("structure_break")
        return skip("no structure break at this bar")
    event = next((e for e in current_events if e.kind == StructureEventKind.MSS), current_events[0])
    rules_fired.append(f"structure_break:{event.kind.value}:{event.direction.value}")

    fvg_direction = FVGDirection.BULLISH if event.direction == Direction.BULLISH else FVGDirection.BEARISH
    all_gaps = find_fair_value_gaps(history, min_gap_size=config.min_fvg_size)
    candidate_gaps = [
        g for g in all_gaps if g.direction == fvg_direction and event.swing_index <= g.index <= index
    ]
    if not candidate_gaps:
        rules_failed.append("fair_value_gap")
        return skip("no matching FVG after structure break")
    gap = candidate_gaps[-1]
    rules_fired.append("fair_value_gap")

    ob_direction = (
        OrderBlockDirection.BULLISH if event.direction == Direction.BULLISH else OrderBlockDirection.BEARISH
    )
    order_block = find_order_block(
        history,
        displacement_index=gap.index,
        direction=ob_direction,
        lookback_bars=config.order_block_lookback_bars,
    )
    if order_block is None:
        rules_failed.append("order_block")
        return skip("no order block found before displacement")
    rules_fired.append("order_block")

    pools = find_equal_levels(swing_points, tolerance_pct=config.equal_level_tolerance_pct)
    sweep_kind = (
        LiquidityPoolKind.SELL_SIDE if event.direction == Direction.BULLISH else LiquidityPoolKind.BUY_SIDE
    )
    sweep = find_recent_sweep(
        history,
        pools,
        end_index=order_block.index,
        lookback_bars=config.liquidity_lookback_bars,
        direction_kind=sweep_kind,
    )
    if sweep is not None:
        rules_fired.append("liquidity_sweep")

    side = Side.BUY if event.direction == Direction.BULLISH else Side.SELL
    entry = gap.midpoint
    if side == Side.BUY:
        stop = order_block.low - order_block.low * config.stop_buffer_pct / 100.0
    else:
        stop = order_block.high + order_block.high * config.stop_buffer_pct / 100.0

    opposing_kind = LiquidityPoolKind.BUY_SIDE if side == Side.BUY else LiquidityPoolKind.SELL_SIDE
    opposing_pools = [p for p in pools if p.kind == opposing_kind]
    if side == Side.BUY:
        target_candidates = [p.price for p in opposing_pools if p.price > entry]
        target = min(target_candidates) if target_candidates else None
    else:
        target_candidates = [p.price for p in opposing_pools if p.price < entry]
        target = max(target_candidates) if target_candidates else None

    if target is None:
        risk_distance = abs(entry - stop)
        target = (
            entry + risk_distance * config.target_r_multiple
            if side == Side.BUY
            else entry - risk_distance * config.target_r_multiple
        )
        rules_fired.append("target:r_multiple_fallback")
    else:
        rules_fired.append("target:liquidity_pool")

    size = position_size(equity, settings.risk_per_trade_pct, entry, stop)

    confluence_count = sum(
        1 for tag in _CONFLUENCE_TAGS if any(fired.startswith(tag) for fired in rules_fired)
    )
    confidence = confluence_count / len(_CONFLUENCE_TAGS)

    return Signal(
        timestamp=bar.timestamp,
        ticker=bar.ticker,
        side=side,
        entry=entry,
        stop=stop,
        target=target,
        size=size,
        confidence=confidence,
        rules_fired=rules_fired,
        rules_failed=rules_failed,
        taken=True,
    )
