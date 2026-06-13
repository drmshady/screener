# Strategy Comparison Study

Window: 2008-01-01 to 2024-12-31. Costs: 0.20% round-trip. Top 5 per rebalance.

Validity criteria (pre-registered): valid iff trades>=50 and expectancy>0 and t_stat>=2.0; ranked by t_stat

| strategy | variant | trades | hit | avg win | avg loss | expectancy | PF | t-stat | +yrs | maxDD | valid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| midterm_52w_high_momentum | regime_gated | 237 | 43% | 21.4% | 12.3% | 2.02% | 1.29 | 1.51 | 60% | 60% | no |
| midterm_52w_high_momentum | baseline | 283 | 42% | 21.2% | 12.6% | 1.60% | 1.22 | 1.31 | 53% | 73% | no |
| shortterm_minervini_vcp | baseline | 76 | 43% | 4.3% | 4.7% | -0.83% | 0.69 | -1.28 | 33% | 43% | no |
| shortterm_atr_breakout | regime_gated | 782 | 39% | 6.4% | 4.7% | -0.40% | 0.86 | -1.56 | 44% | 62% | no |
| shortterm_minervini_vcp | regime_gated | 68 | 41% | 4.2% | 4.8% | -1.10% | 0.61 | -1.61 | 27% | 43% | no |
| shortterm_atr_breakout | baseline | 995 | 38% | 6.6% | 5.0% | -0.67% | 0.79 | -2.89 | 29% | 83% | no |

Survivorship caveat: the free Stooq bundle has no delisted tickers; absolute numbers
are survivor-inflated for every variant. The comparison is internally fair.
