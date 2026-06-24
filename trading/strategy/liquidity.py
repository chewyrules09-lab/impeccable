"""Phase 1 stub.

Will implement liquidity detection:
  - equal highs/lows (resting liquidity pools, within a tolerance parameter)
  - sweep detection: a wick pierces through a liquidity level and then closes
    back on the other side (rejection), often the trigger for an entry once
    paired with an FVG or order block.
"""
