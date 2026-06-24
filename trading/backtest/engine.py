"""Phase 2 stub.

Will implement a lightweight event-driven backtest loop: replay historical
bars in order, feed each one to the strategy layer (strategy/signals.py),
route any resulting OrderIntent through the same RiskEngine used in
paper/live, fill it against `broker/dryrun.py`-style synthetic logic using the
*next* bar's open (no lookahead), and persist every signal/order/fill exactly
as paper/live would. Output feeds `backtest/metrics.py`.
"""
