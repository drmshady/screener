# Bias Check: shortterm_minervini_vcp

Window: 2008-01-01 to 2024-12-31.

- [ ] survivorship_bias: Stooq deep-history bundle used (full live universe, 2008-2009 covered), but the free bundle contains NO delisted tickers — survivor-bias-free coverage requires a delisted source (e.g., EOD Historical Data).
- [x] lookahead_bias: Candidate selection uses prices at or before each annual as-of date.
- [x] point_in_time_fundamentals: No fundamentals are used by this strategy; price signals are evaluated only from bars visible at the rebalance date.
- [x] costs: Turnover is recorded in summary metrics; explicit slippage/commission modeling is not included in this MVP backtest.
