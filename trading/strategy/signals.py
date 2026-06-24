"""Phase 1 stub.

Will combine market_structure/fvg/order_blocks/liquidity/kill_zones into a
single per-bar evaluation that emits a structured object for every bar in the
universe during a kill zone:

    Signal { timestamp, ticker, side, entry, stop, target, size,
             rules_fired: list[str], confidence }

A bar that doesn't qualify is still logged, with `rules_failed: list[str]`,
via `persistence.repository.insert_signal(..., taken=False, ...)`. The
`signals` table in `persistence/schema.sql` already has both columns.
"""
