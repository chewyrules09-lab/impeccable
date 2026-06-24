"""Phase 1 stub.

Will implement, as parameterized + unit-testable pure functions over OHLCV bars:
  - swing highs/lows
  - Break of Structure (BOS): price closes beyond the most recent confirmed
    swing in the direction of the prevailing trend
  - Market Structure Shift (MSS): a break of structure against the prevailing
    trend, signaling a potential reversal

Each function will carry its exact rule in its docstring and a hand-built
fixture test in tests/ (not implemented yet).
"""
