"""Phase 1 stub.

Will implement Fair Value Gap (FVG) detection: a 3-candle imbalance where
candle 1's high/low does not overlap candle 3's low/high, leaving a gap in
candle 2. Parameterized by a `min_gap_size` (in price or % terms) so noise-level
gaps don't fire signals. Config, not hard-coded.
"""
