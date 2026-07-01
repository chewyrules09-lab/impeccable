"""Phase 3 stub.

Will read `validation_report.json` (produced by aggregating `backtest/metrics.py`
output across completed paper sessions) and enforce the live-unlock bar:

    paper sessions completed >= 20
    total trades            >= 30
    profit factor            > 1.3
    max drawdown             < 10%
    expectancy                > 0

`run_session.py`'s `assert_live_allowed()` calls into this module rather than
re-implementing the bar, so the Phase 0 gate and the Phase 3 report use one
definition.
"""
