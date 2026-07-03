# Bias Check: midterm_52w_high_momentum

Window: 2008-01-01 to 2024-12-31.

- [ ] survivorship_bias: Stooq deep-history bundle used (full live universe, 2008-2009 covered), but the free bundle contains NO delisted tickers — survivor-bias-free coverage requires a delisted source (e.g., EOD Historical Data).
- [x] lookahead_bias: Candidate selection uses prices at or before each rebalance as-of date.
- [x] point_in_time_fundamentals: Point-in-time fundamentals were available.
- [x] costs: modeled: 10 bps/side
