# Feature Specification: US Stock Screener MVP

**Feature Branch**: `001-screener-mvp`
**Created**: 2026-06-10
**Status**: Draft
**Input**: User description: "iwant tou build screener for is market for short term and midterm investment screen market and evaluate market for short term and longterm with reliable strategy and give suggestion of entery point stop loss and take profit and should manage user portifilio and divid stocks according to capital size and sectors and giive advice regarding diveristy" — refined in follow-ups to: "mid-term instead of long-term", "test for sharia compliant", and "should take in consideration news and important events".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mid-term screen with entry, stop-loss, and take-profit (Priority: P1)

A retail investor opens the app, picks a documented mid-term strategy (for example a 52-week-high momentum screen or a CAN SLIM-style growth screen), runs it across the US-listed equity universe, and reviews the resulting list of candidate tickers. For each candidate they see the strategy's reason for the match, today's price, a suggested entry price, a suggested stop-loss level, and a suggested first take-profit (price target). The user can save promising candidates to a watchlist or dismiss them. Every result is stamped with the data's as-of date and a non-advice disclaimer.

**Why this priority**: This is the heart of the product. If only this story ships, the investor already gets the core value: trusted, named strategies turning the US market into a short list of actionable candidates with risk-defined levels. It is the MVP.

**Independent Test**: With a known end-of-day data snapshot, run the mid-term screen and verify that (a) the candidate list matches the strategy's documented rules, (b) every candidate shows entry/stop-loss/take-profit levels derived from the rules, (c) the strategy name and citation are displayed, and (d) the disclaimer and as-of date appear on the page.

**Acceptance Scenarios**:

1. **Given** the app has a fresh end-of-day data snapshot and at least one mid-term strategy enabled, **When** the user selects that strategy and clicks "Run screen", **Then** the system displays a ranked list of candidate tickers within 10 seconds, each showing ticker, company name, sector, current price, suggested entry, suggested stop-loss, suggested take-profit, and a one-line "why it matched" reason.
2. **Given** a strategy with no candidates passing its rules on a given day, **When** the user runs the screen, **Then** the system displays a clear "No matches today for [strategy]" message with the as-of date — not an empty page.
3. **Given** the user is reviewing a candidate, **When** they save it to their watchlist, **Then** the candidate persists across page reloads and shows the strategy that produced it, the suggested levels at the time it was saved, and the saved-at timestamp.
4. **Given** any screen result page, **When** the page renders, **Then** the strategy's name, methodology citation, timeframe label ("Mid-term"), data as-of date, and the non-advice disclaimer are all visible without scrolling past the main result table.

---

### User Story 2 - Short-term swing screen with entry, stop-loss, and take-profit (Priority: P2)

A more active investor selects a documented short-term swing strategy (for example a Minervini-style stage-2 breakout, an ATR volatility breakout, or an RSI mean-reversion screen) and runs it on the US-listed universe. They receive a candidate list scoped to the short-term holding period (intraday to a few weeks) with timeframe-appropriate entry, stop-loss, and take-profit levels — typically tighter stops than the mid-term mode.

**Why this priority**: It reuses the screening engine from US1 but serves a different user need (swing/short horizon vs. position/mid horizon). Independently demoable and valuable, but not required for the first user-facing release.

**Independent Test**: With the same end-of-day snapshot, run the short-term swing strategy and verify the candidate set follows the documented short-term rules and the suggested stop distance is tighter (in ATR or percent) than the mid-term strategies on the same tickers.

**Acceptance Scenarios**:

1. **Given** at least one short-term strategy is enabled, **When** the user runs it on the same data snapshot as a mid-term screen, **Then** the candidate list, suggested entry, suggested stop-loss, and suggested take-profit reflect the short-term rules and are clearly labeled "Short-term".
2. **Given** a short-term screen result, **When** the user views a candidate's detail, **Then** the displayed holding period is in the "intraday to a few weeks" range documented for that strategy.
3. **Given** the underlying data is delayed or only end-of-day is available, **When** any short-term screen result is shown, **Then** the delay (or "End-of-day data") is displayed prominently on the page.

---

### User Story 3 - Shariah-compliance filter on the screening universe (Priority: P3)

A Muslim investor turns on "Shariah-compliant only" in settings. From that point on, every screen (mid-term and short-term), every watchlist view, and every portfolio diversification view restricts its candidate universe to tickers flagged as Shariah-compliant by a documented Shariah source (default: SPUS ETF current holdings). Non-compliant tickers are either hidden or shown with a clear "Not Shariah-compliant" tag, depending on context: hidden from screen results, tagged in the user's existing portfolio so the user can see what to divest. Every Shariah-compliance label cites the source and the as-of date of that source.

**Why this priority**: Without this filter, the entire product is unusable for an observant Muslim investor — non-compliant candidates would dominate the result list. It is a universe-level constraint that wraps every screen. The default OFF position means non-Muslim users are unaffected; turning it ON converts the product into a halal screener equivalent.

**Independent Test**: Enable Shariah filter; load a known data snapshot in which 5 of the top 10 mid-term screen candidates are non-compliant (per SPUS membership); verify those 5 are excluded from the screen result, the remaining 5 carry a "Shariah-compliant" badge with the SPUS as-of date, and a portfolio holding for a non-compliant ticker shows the "Not Shariah-compliant" tag.

**Acceptance Scenarios**:

1. **Given** the Shariah filter is OFF (default), **When** the user runs any screen, **Then** results include all eligible US-listed tickers regardless of Shariah status and no Shariah-related UI appears.
2. **Given** the Shariah filter is ON, **When** the user runs any screen, **Then** only tickers flagged Shariah-compliant by the configured Shariah source appear in candidate results, and each result row displays a "Shariah-compliant" badge with the Shariah source name and its as-of date.
3. **Given** the Shariah filter is ON and the user has portfolio holdings, **When** they open the Portfolio view, **Then** any holding not flagged Shariah-compliant is marked "Not Shariah-compliant" with the source and as-of date, and the portfolio summary shows a count of non-compliant holdings.
4. **Given** the Shariah filter is ON, **When** the Shariah source is stale (older than the documented refresh interval), **Then** the app warns the user, names the as-of date, and continues to filter using the most recent available list.
5. **Given** the Shariah filter is ON and the user has zero Shariah-compliant matches for a strategy on a given day, **When** they run the screen, **Then** the empty state explains both the strategy and the Shariah filter, and offers a one-click "Show all matches (ignoring Shariah filter)" override that requires explicit user confirmation each time.

---

### User Story 4 - News and important events awareness (Priority: P4)

A user reviewing a screen candidate wants to avoid stepping into a known catalyst they did not see coming. Each candidate row carries an "Events" badge that surfaces: days to next earnings (when within the next 14 calendar days), recent material-news count (8-K filings in the trailing 30 days), and a quick link to the source filing on EDGAR. A user-toggleable filter on each screen excludes candidates with earnings within the next N days (default N = 7 for short-term strategies, N = 0 / disabled for mid-term). The home dashboard shows a "Market Events This Week" panel listing scheduled US macroeconomic releases (FOMC, CPI, NFP, PCE, PPI) from a documented economic calendar, each with its scheduled time and (after release) actual vs. expected values.

**Why this priority**: A momentum or breakout setup that runs into an earnings release can blow through the stop in a single overnight gap; ignoring that is the kind of obvious miss a "reliable strategy" product should not produce. Independent of portfolio and regime work, but builds on US1/US2 because event badges decorate candidates from those screens.

**Independent Test**: With a known data snapshot where ticker XYZ has earnings 3 days out, verify the candidate row shows "Earnings in 3 days"; turn on the "Exclude earnings within 7 days" filter and verify XYZ is removed; check the dashboard shows the next FOMC meeting from the configured economic calendar with its scheduled date.

**Acceptance Scenarios**:

1. **Given** a screen candidate whose next earnings date is within 14 days, **When** the candidate row is rendered, **Then** an "Earnings in N days" badge is displayed alongside the ticker, with a link to the source (EDGAR filing or calendar entry) and the as-of date of the calendar data.
2. **Given** a screen candidate that has filed one or more 8-K reports in the trailing 30 days, **When** the candidate row is rendered, **Then** a "Material news (N in 30d)" badge is displayed and the user can click through to the EDGAR 8-K listing for that ticker.
3. **Given** the user enables "Exclude earnings within 7 days" on a short-term screen, **When** the screen runs, **Then** candidates whose next earnings date is within 7 calendar days are filtered out and the filter shows how many candidates were excluded.
4. **Given** the home dashboard is open, **When** the page renders, **Then** the "Market Events This Week" panel lists scheduled FOMC/CPI/NFP/PCE/PPI events with their scheduled date and time and the as-of date of the calendar source, sorted by date ascending.
5. **Given** a market event has already passed, **When** the panel renders, **Then** the event displays its actual value vs. consensus expected value (when both are available in the source) and is grayed-out / marked "Released".
6. **Given** the earnings calendar or economic calendar source has not refreshed within its documented interval, **When** any view that uses events is rendered, **Then** the as-of date is shown and a "Stale events data" warning is displayed adjacent to the affected badges or panel.

---

### User Story 5 - Portfolio, capital, sector exposure, diversification advice, and position sizing (Priority: P5)

The investor records their current holdings (ticker, share count, average cost) and their total capital figure. The app computes total portfolio value, dollar and percent exposure per sector, and flags concentration risks against documented thresholds (default: any single position over 10% of capital, any single sector over 25%). When the user clicks "Size this trade" on any screen candidate from US1 or US2, the app suggests a share count and dollar amount that respects per-position and per-sector caps given the user's current portfolio and capital.

**Why this priority**: This delivers the "manage portfolio and divide stocks by capital size and sector" part of the user's request. Highly valuable but builds on US1 (it needs candidates to size against) and is independent enough to demo by itself with manually entered data.

**Independent Test**: Enter a 6-stock portfolio with known sector classifications and a $10,000 capital figure, then verify that (a) sector percentages are correct, (b) any position above 10% of capital is flagged, (c) any sector above 25% is flagged, and (d) clicking "Size this trade" on a candidate returns a share count that does not push that position or its sector over the documented caps.

**Acceptance Scenarios**:

1. **Given** the user has not yet entered a portfolio, **When** they open the Portfolio view, **Then** they see an empty state with a clear "Add holding" action and a field to enter total capital.
2. **Given** the user enters 5 holdings and a $10,000 total capital, **When** they view the portfolio summary, **Then** the system displays total portfolio value, cash balance (capital minus holdings value), per-sector dollar and percent exposure, and any concentration flag against the default caps.
3. **Given** the user selects a candidate from a screen and clicks "Size this trade", **When** the suggestion is shown, **Then** it lists a suggested share count, the resulting dollar position, the resulting per-position percent of capital, the resulting per-sector percent of capital, and an explicit statement of whether any cap would be breached (the suggestion never breaches the cap).
4. **Given** a candidate whose minimum buyable position would exceed the per-position cap (for example a high-priced stock against a small capital base), **When** the user requests sizing, **Then** the system displays "Position sizing would breach per-position cap" with the relevant numbers rather than recommending a partial fractional position.
5. **Given** the user changes the per-position or per-sector cap in settings, **When** they re-open any portfolio or sizing view, **Then** the new caps are applied immediately.

---

### User Story 6 - Market regime evaluation (Priority: P6)

The investor sees a dashboard-level "Market regime" indicator (for example trending up, range-bound, trending down) derived from a documented index-level rule (such as the S&P 500's position relative to its 200-day moving average and breadth). Each shipped strategy is labeled "Favorable", "Neutral", or "Unfavorable" given the current regime, based on a documented mapping (for example trend-following strategies are favorable in a trending-up regime).

**Why this priority**: Adds market context so the user does not blindly run a trend-following strategy in a downtrend. Useful but not blocking; the screens still work without it.

**Independent Test**: With a known historical snapshot where the S&P 500 was below its 200-day moving average, verify the regime indicator reads "Trending down" and that documented trend-following strategies are labeled "Unfavorable".

**Acceptance Scenarios**:

1. **Given** an end-of-day snapshot, **When** the user opens the home dashboard, **Then** the current market regime is shown with the rule that produced it (cited in plain language) and its as-of date.
2. **Given** the regime is shown, **When** the user views the list of available strategies, **Then** each strategy carries a "Favorable", "Neutral", or "Unfavorable" tag for the current regime, with a one-line explanation.
3. **Given** the same data snapshot, **When** the regime is computed twice in the same session, **Then** the result is identical (deterministic).

---

### Edge Cases

- A strategy returns zero candidates on a given day: show "No matches today" with the as-of date; do not show a blank table.
- The data snapshot is more than one trading day stale: surface a "Stale data" warning on every screen view and disable "Run screen" until refreshed (or allow the user to proceed with an explicit acknowledgement).
- The user enters a ticker that is not in the US-listed common-equity universe (delisted, ADR, OTC, ETF, foreign): flag the holding as "Not screened" and exclude from screen-based features, but include in portfolio value and sector exposure if a sector classification is known.
- Sector classification is missing for a candidate or holding: assign it to "Unclassified" and exclude it from sector-cap enforcement, with a visible warning.
- The user's total capital is set to zero or omitted: position sizing is unavailable until capital is entered; portfolio sector breakdown still works.
- The user's capital is small enough that any single share of the candidate exceeds the per-position cap: show "Position sizing would breach per-position cap" rather than rounding down to zero.
- Browser storage is cleared: the portfolio is lost. The app warns the user on first save that holdings are stored locally and offers a manual export/import.
- The strategy's required indicator window (for example a 200-day moving average) is not available for a recently IPO'd ticker: exclude that ticker from the candidate list silently, but make it explicit if the user looks it up directly.
- The user disables every strategy: the home view shows an empty-state message and a link to the strategy library.
- A ticker the user holds in their portfolio is excluded from screens by the universe-wide liquidity gate (low ADV or sub-$5 price): the holding still appears in the Portfolio view with sector exposure, but is tagged "Excluded by liquidity gate" so the user understands why no screen will ever surface it as a candidate.
- A strategy's walk-forward backtest cannot include 2008-2009 because the deep-history data source is unavailable: the strategy's detail page displays the actual window used, a "Limited backtest window" warning, and the v1 launch checklist requires explicit operator sign-off before enabling the strategy by default.
- Shariah filter ON and the Shariah source list has not been refreshed within the documented interval: warn the user, name the as-of date, and continue filtering on the last-known list.
- A ticker that was Shariah-compliant when the user bought it is no longer in the current Shariah source list: tag it "Compliance changed" in the portfolio with both the prior and current as-of dates, but do not force any action.
- A ticker appears in both the user's inclusion list AND the user's exclusion list (data error): exclusion wins (the user has explicitly said "not for me") and a "Conflicting overrides" warning surfaces on the Settings page so the user can resolve.
- A ticker the user added to their inclusion list is later added to SPUS as well: the badge collapses to the more-authoritative source (SPUS) for cleanliness; the user's note is preserved in case they remove SPUS later.
- Shariah filter ON and the strategy returns zero compliant candidates: show an empty-state explaining both the strategy and the filter, with an explicit per-run override option.
- Earnings date is unknown for a candidate (recently IPO'd, late filer, or missing from the calendar source): show "Earnings date unknown" rather than hiding the badge, and exclude the ticker from the earnings-window filter (so an unknown date does not silently filter the candidate in or out).
- 8-K filing count is high but the filings are administrative (Item 5.07 shareholder votes, Item 8.01 boilerplate): the count is shown as-is in v1; semantic classification is deferred. The user clicks through to read filings themselves.
- Economic calendar source is unreachable or stale beyond the documented refresh interval: the "Market Events This Week" panel still renders with the last-known data and a "Stale events data" warning; screens and badges keep working independently.
- The user is on a short-term screen but the active strategy itself targets a pre-earnings setup (rare): the per-strategy default for the earnings-exclusion filter is exposed in the strategy definition so it does not silently filter out the strategy's own intended setups.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow the user to run a mid-term screen on the US-listed common-equity universe (NYSE, NASDAQ, NYSE American) and return zero or more candidate tickers ordered by the strategy's documented ranking rule.
- **FR-002**: System MUST allow the user to run a short-term swing screen on the same universe using its own documented strategy rules.
- **FR-003**: For each candidate, the system MUST display ticker symbol, company name, sector, current price, suggested entry price, suggested stop-loss price, suggested first take-profit price, and a one-line reason explaining why the candidate matched.
- **FR-004**: System MUST display the strategy's name, its timeframe label (Short-term or Mid-term), and its methodology citation (a recognizable name plus link or reference) on every screen result and candidate detail view.
- **FR-005**: System MUST display the underlying data's as-of timestamp on every screen result, dashboard, and portfolio view.
- **FR-006**: System MUST display a clearly worded non-advice disclaimer on every screen result, candidate detail, portfolio view, and shareable export.
- **FR-007**: System MUST use neutral framing for candidates ("Screen match", "Candidate", "Potential entry") and MUST NOT use directive trading language ("Buy", "Sell", "Recommended", "Strong buy") anywhere in the user interface.
- **FR-008**: System MUST allow the user to add, edit, and remove holdings in a portfolio. Each holding records ticker, share count, and average cost.
- **FR-009**: System MUST allow the user to record a total capital figure (cash + invested) and MUST compute cash balance as total capital minus current invested value.
- **FR-010**: System MUST compute and display, for the current portfolio, total portfolio value, dollar and percent exposure per sector, and any concentration flags against the configured per-position and per-sector caps.
- **FR-011**: System MUST allow the user to configure the per-position cap (default 10%) and the per-sector cap (default 25%) of total capital.
- **FR-012**: When the user requests sizing for a screen candidate, the system MUST suggest a whole-share count and resulting dollar amount that does not breach the per-position or per-sector caps given the user's current portfolio.
- **FR-013**: When a candidate cannot be sized without breaching a cap (for example because the candidate's price exceeds the cap with one share), the system MUST display a clear "Cannot size without breaching cap" message with the relevant numbers, rather than suggesting a fractional or zero position.
- **FR-014**: System MUST allow the user to save a candidate to a watchlist, dismiss a candidate, or mark it "Acted on" with a free-text note. Watchlist state MUST persist across page reloads.
- **FR-015**: System MUST display a market regime indicator on the home dashboard with a plain-language statement of the rule that produced it and the as-of date.
- **FR-016**: System MUST tag each available strategy as "Favorable", "Neutral", or "Unfavorable" for the current regime using a documented strategy-to-regime mapping.
- **FR-017**: System MUST ship with at least one peer-reviewed mid-term strategy and at least one peer-reviewed short-term strategy enabled by default at v1 launch.
- **FR-018**: System MUST be deterministic on a fixed data snapshot — running any screen, regime calculation, or sizing suggestion twice on the same snapshot produces identical results.
- **FR-019**: System MUST allow the user to export their portfolio (holdings + capital + settings) and watchlist as a single human-readable file and import it back on the same device or a different one.
- **FR-020**: System MUST warn the user, on their first portfolio save, that holdings are stored locally on the device and are not backed up to a server.
- **FR-021**: System MUST provide a user-toggleable "Shariah-compliant only" setting that, when ON, restricts every screen's candidate universe to tickers flagged Shariah-compliant by the configured Shariah source.
- **FR-022**: System MUST ship with at least one external Shariah source that covers the US-listed universe (default: SPUS ETF current holdings). The external source MUST be replaceable in configuration without code changes. SPUS is recognized as a curated large/mid-cap subset of compliant tickers (it tracks the FTSE USA Shariah index) and is therefore extended at runtime by a user-managed list (FR-038, FR-039) so the universe is not artificially capped at SPUS membership.
- **FR-023**: When the Shariah filter is ON, every candidate row and candidate detail MUST display a "Shariah-compliant" badge. The badge MUST identify the source kind that produced the compliance verdict — "SPUS" (or whatever external source is active) versus "User" — and MUST display that source's name and as-of date. For user-marked tickers, the user's optional rationale note (if present) MUST be visible on hover or expand. When OFF, no Shariah UI is shown.
- **FR-024**: When the Shariah filter is ON, the Portfolio view MUST tag each holding as "Shariah-compliant", "Not Shariah-compliant", or "Unknown" with the source and as-of date, and MUST show a count of non-compliant holdings in the summary.
- **FR-025**: System MUST warn the user when the Shariah source list is older than the documented refresh interval, naming the as-of date, but MUST continue to filter on the last-known list rather than failing closed.
- **FR-026**: When the Shariah filter is ON and a screen returns zero compliant candidates, the system MUST show an empty state that explains both the strategy and the filter and MUST require explicit per-run confirmation before showing the unfiltered result.
- **FR-027**: System MUST display, on every candidate row whose next earnings date is within the next 14 calendar days, an "Earnings in N days" badge with a link to the source filing or calendar entry and the as-of date of the calendar data.
- **FR-028**: System MUST display, on every candidate row that has one or more 8-K filings in the trailing 30 days, a "Material news (N in 30d)" badge with a link to the ticker's 8-K filings on EDGAR.
- **FR-029**: System MUST allow the user to enable a per-screen "Exclude earnings within N days" filter (default N = 7 for short-term strategies, default N = 0 / disabled for mid-term strategies, both user-editable) that removes candidates whose next earnings date falls within N calendar days of the as-of date. Candidates with an unknown earnings date MUST NOT be excluded by this filter.
- **FR-030**: System MUST display a "Market Events This Week" panel on the home dashboard listing scheduled US macroeconomic releases (at minimum FOMC, CPI, NFP, PCE, PPI) from a documented economic calendar source, each with its scheduled date and time, and the as-of date of the source.
- **FR-031**: For market events that have already passed within the displayed week, the system MUST show actual vs. expected values when the source provides them, and visually mark the event as "Released".
- **FR-032**: System MUST display a "Stale events data" warning whenever the earnings calendar or economic calendar source has not refreshed within its documented refresh interval, but MUST continue to render the last-known data rather than failing closed.
- **FR-033**: The earnings calendar source, the 8-K filing source, and the economic calendar source MUST each be replaceable in configuration without code changes, and each MUST carry a source name and as-of date visible to the user wherever its data appears.
- **FR-034**: System MUST apply a universe-wide liquidity gate before any strategy runs, excluding tickers whose trailing-20-day average daily dollar volume is below the configured threshold (default $1,000,000) or whose price is below the configured floor (default $5). Both thresholds MUST be user-configurable in settings.
- **FR-035**: System MUST display, on each shipped strategy's detail page, walk-forward backtest metrics including per-year hit rate, average win, average loss, max drawdown, total return, and the data window used. Metrics MUST cover at least one bull and one bear market cycle (target: ≥ 15 years where data permits, explicitly including the 2008-2009 drawdown).
- **FR-036**: System MUST name the data source(s) used to produce each strategy's backtest metrics, with as-of dates, on the same page as the metrics, so the user can audit the backtest's provenance.
- **FR-037**: System MUST surface a "Strategy gates" panel on each strategy's detail page that lists every rule and parameter the strategy applies (including modifications to the cited methodology, such as a trend filter overlay or a volume confirmation requirement), with the citation for any modification distinct from the citation for the core methodology.
- **FR-038**: System MUST allow the user to add tickers to a personal "Additional Shariah-compliant" list. Each entry records the ticker, the timestamp the user added it, and an optional free-text rationale (e.g., "verified low-debt + halal business — see <link>"). When the Shariah filter is ON, these tickers are treated as compliant **in addition to** the configured external source (e.g., SPUS).
- **FR-039**: System MUST allow the user to add tickers to a personal "Excluded — not Shariah-compliant for me" list. Each entry records the ticker, the timestamp added, and an optional free-text note. When the Shariah filter is ON, these tickers are treated as NON-compliant **even if** the configured external source includes them. User exclusion overrides external inclusion.
- **FR-040**: The effective Shariah-compliance verdict for a ticker is computed as: `(ticker ∈ active_external_sources OR ticker ∈ user_inclusion_list) AND (ticker ∉ user_exclusion_list)`. The badge MUST display the highest-precedence source that contributed to a compliant verdict (User > external source) and MUST label exclusions as "Excluded by user" when applicable.
- **FR-041**: Both the user inclusion list and the user exclusion list MUST be editable from the Settings page, exportable as part of the existing settings/portfolio export (FR-019), and persist in browser-local storage like other user state.

### Key Entities *(include if feature involves data)*

- **Strategy**: A named, documented methodology with a timeframe (Short-term or Mid-term), a citation, a deterministic rule set, parameters with documented defaults, an expected holding period, and an entry/stop/target derivation rule. Each strategy has a regime-favorability mapping.
- **Screen Result**: A snapshot of one strategy's output against one data as-of date, containing zero or more Candidates.
- **Candidate**: A single ticker matched by a strategy, with the suggested entry, stop-loss, take-profit, ranking score, the strategy's "why it matched" reason, the Shariah-compliance flag (if filter is ON), and the data as-of date.
- **Portfolio**: The user's record of total capital plus zero or more Holdings, with derived total value, cash balance, sector exposure, concentration flags, and Shariah-compliance summary (if filter is ON).
- **Holding**: A single open position within a Portfolio: ticker, share count, average cost, derived current value, derived sector, and derived Shariah-compliance status.
- **Watchlist Entry**: A Candidate that the user has saved, dismissed, or marked acted-on, with the saved-at timestamp, the strategy it came from, the levels at the time it was saved, and an optional user note.
- **Market Regime**: A computed state of the broad US equity market (for example Trending up / Range-bound / Trending down), produced by a documented index-level rule, with the as-of date and the rule's plain-language statement.
- **Shariah Source**: A configurable reference list of Shariah-compliant US tickers with a source name, citation, refresh interval, and as-of date (default source: SPUS ETF current holdings).
- **Ticker Event**: A per-ticker event record — type (earnings, 8-K material news), scheduled or released date, link to source (EDGAR filing URL or calendar entry), and the as-of date of the source.
- **Market Event**: A market-wide scheduled economic release (FOMC, CPI, NFP, PCE, PPI, etc.) with scheduled date and time, source name, expected (consensus) value, actual value (post-release), and the as-of date of the source.
- **Events Source**: A configurable provider of either ticker events (earnings calendar, EDGAR 8-K feed) or market events (economic calendar), with source name, citation, refresh interval, and as-of date.
- **Sector**: The classification used to bucket holdings and candidates for diversification (using a standard industry classification scheme).
- **User Settings**: The user-configurable values that shape advice: per-position cap, per-sector cap, default strategy selection, Shariah filter toggle, selected Shariah source, per-strategy "Exclude earnings within N days" defaults.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time user can run their first mid-term screen and view a ranked candidate list with entry, stop-loss, and take-profit for every candidate in under 90 seconds from first opening the app.
- **SC-002**: A returning user can run any single screen (short-term or mid-term) on the full US-listed common-equity universe and see results in under 10 seconds from a cold start, and under 2 seconds when results are cached for the same data snapshot.
- **SC-003**: At least 2 peer-reviewed strategies (1 short-term + 1 mid-term) ship enabled in v1, each with a visible citation. The v1 launch target is 3 fully-gated strategies (1 mid-term + 2 short-term), each backed by walk-forward backtest metrics meeting SC-017. A name-only "lite" version of a multi-signal strategy (e.g., CAN SLIM without the I and N inputs) MUST NOT ship under the original author's citation; such variants are deferred until the missing data sources are integrated.
- **SC-004**: For every candidate the screener produces, the user can answer "what's the entry, stop-loss, and take-profit?" without leaving the candidate's detail view.
- **SC-005**: Every screen result, candidate detail, portfolio view, and shareable export displays the data as-of timestamp and the non-advice disclaimer; a manual audit of 20 sample screens finds zero pages missing either.
- **SC-006**: A user with a 10-stock portfolio can record holdings and total capital and see correct sector exposure percentages within 3 minutes of first opening the Portfolio view.
- **SC-007**: For a user with $5,000 capital and a 6-stock portfolio, position-sizing suggestions never exceed the configured per-position or per-sector cap across 50 candidate sizing requests sampled from a representative trading week.
- **SC-008**: The market regime indicator and per-strategy favorability tags are deterministic — across 20 repeated runs on the same data snapshot, the regime and tags are identical every time.
- **SC-009**: A randomly chosen reviewer who is not the strategy's author can read the strategy's in-app description and citation and locate the source methodology (paper, book chapter, or recognized writeup) in under 5 minutes.
- **SC-010**: Zero pieces of UI copy across the v1 product use directive trading language ("Buy", "Sell", "Recommended", "Strong buy"), verified by a manual review against a checklist.
- **SC-011**: With the Shariah filter ON and a known data snapshot, 100% of candidates surfaced by every shipped screen are flagged Shariah-compliant by the configured Shariah source, verified by cross-checking against the source list.
- **SC-012**: With the Shariah filter ON, the Shariah source name and as-of date are visible on every screen result, candidate detail, and on every holding in the portfolio; a manual audit of 20 sample views finds zero pages missing either. The source kind (External / User) is also visible on every badge.
- **SC-012a**: With the Shariah filter ON, a ticker added to the user inclusion list appears as a candidate (when it otherwise matches the strategy) and is badged "Shariah-compliant (User)" with the user's rationale note; verified by a deterministic test that adds a known non-SPUS ticker, runs the matching strategy, and asserts the ticker is in the result with the correct badge.
- **SC-012b**: With the Shariah filter ON, a SPUS-listed ticker that the user has added to their exclusion list does NOT appear in any candidate result and is tagged "Excluded by user" in the portfolio view; verified by a deterministic test.
- **SC-013**: For a known data snapshot, every candidate whose next earnings date is within 14 days of the snapshot's as-of date displays an "Earnings in N days" badge; verified by sampling 20 candidates with known earnings dates and confirming 100% accuracy of the badge presence and N value.
- **SC-014**: Enabling "Exclude earnings within N days" on a short-term screen removes exactly the candidates whose next earnings date falls within N days and leaves candidates with unknown earnings dates in the result; verified by a deterministic test on a fixed snapshot.
- **SC-015**: The home dashboard's "Market Events This Week" panel always renders within 1 second on a returning user's session, even when the underlying economic calendar source is offline (rendering the last-known data with the stale-data warning).
- **SC-016**: With the universe-wide liquidity gate at default thresholds, ≥ 95% of US-listed tickers whose trailing-20-day average daily dollar volume is below $1M are excluded from every screen's candidate universe, verified on a known data snapshot.
- **SC-017**: Every shipped strategy's detail page displays walk-forward backtest metrics whose data window covers at least one full bull and one full bear market cycle (≥ 15 years where data permits and explicitly including 2008-2009); verified by a manual audit of all enabled strategies at launch.
- **SC-018**: A reviewer looking at any shipped strategy's detail page can identify (a) the core methodology citation, (b) every gate or modification applied to that methodology with its own citation, and (c) the backtest data source and as-of dates, in under 5 minutes.

## Assumptions

- **Universe**: The screenable universe is US-listed common equities on NYSE, NASDAQ, and NYSE American. ETFs, ADRs, OTC pink sheets, options, futures, and cryptocurrencies are out of scope for v1; the user may record them as portfolio holdings (so sector exposure stays accurate) but they are excluded from screens.
- **Horizons**: Only short-term (intraday to a few weeks) and mid-term (roughly 1-12 months) strategies ship in v1, per the project constitution. Pure long-term buy-and-hold is deferred to a future release.
- **Data**: End-of-day market data is sufficient for both short-term and mid-term screens in v1; intraday quoting may be added later. Fundamentals refresh within 2 business days of the underlying SEC filing.
- **Deployment & user model**: Single-user, no-authentication web app for v1 (matching the precedent set by the related Muhallib v1 project). Portfolio, watchlist, and settings persist in browser-local storage. No multi-user accounts, no cloud sync, and no cross-device sync beyond manual export/import.
- **Scope of "personal use"**: v1 is operated by one user on their own machine, for their own decisions. The product is never hosted for other users and never redistributes vendor data. This makes a vendor's "no redistribution" TOS clause (notably yfinance) moot at this scale, but the constraint is reinstated at the moment of any hosted / multi-user deployment.
- **Trading scope**: The app is advisory and read-only. There is no brokerage integration, no order placement, and no real money flows through the product. Position-sizing output is a suggestion the user acts on through their own broker.
- **No personalized advice**: The product is an information and screening tool. It does not provide personalized investment advice, tax advice, or jurisdictional/regulatory guidance. Every output carries that disclaimer.
- **Sector classification**: A standard industry classification (sectors and industries) is used; the specific provider is an implementation detail captured in the plan.
- **Default caps**: Per-position cap defaults to 10% of total capital; per-sector cap defaults to 25% of total capital. Both are user-editable.
- **Universe-wide liquidity gate defaults**: Trailing-20-day average daily dollar volume ≥ $1,000,000 and share price ≥ $5.00. Both user-configurable. Applied at the universe level so every strategy benefits; eliminates microcap pump candidates that would otherwise dominate certain breakout strategies.
- **Backtest window discipline**: Every strategy enabled by default at v1 launch MUST be backtested across a window that includes at least one bull and one bear market cycle, with explicit inclusion of the 2008-2009 drawdown wherever the data source permits. Strategies whose backtest window is shorter ship as "Available but disabled by default" with a visible "Limited backtest window" warning.
- **Strategy slate at v1 launch**: 3 fully-gated strategies (1 mid-term + 2 short-term), each with the cited methodology plus any documented modifications listed in research.md. A CAN SLIM-style growth strategy is deferred to v1.x until the insider-buying (Form 4) and earnings-revision data pipelines are added; we will not ship a name-only "lite" version under O'Neil's citation.
- **Default holding periods**: Short-term strategies default to a 1-15 trading-day holding period; mid-term strategies default to a 1-6 month holding period. Each strategy may override its own default.
- **Strategy provenance**: Every strategy that ships in v1 references a published, recognizable methodology and is reviewed against the constitution's strategy-review checklist before merge.
- **Shariah source (v1 default)**: SPUS ETF current holdings (~200+ US-listed tickers) is the default Shariah-compliant universe, mirroring the Muhallib v1 precedent. The source is configurable; replacing it requires updating settings, not code. A more comprehensive Shariah screening (debt ratio, interest income, business activity tests on a per-ticker basis) is out of scope for v1.
- **Shariah filter default**: OFF by default so the product is usable for the general audience without surfacing any Shariah UI; opt-in via settings.
- **Shariah source refresh**: The SPUS holdings list is expected to be refreshed at least monthly; a warning surfaces if the local list is older than 45 days.
- **SPUS coverage limitation acknowledged**: SPUS tracks the FTSE USA Shariah index and is therefore biased toward US large/mid-cap names. Compliant small-caps, recent IPOs, and any compliant ticker that Wahed has chosen not to include are not in SPUS by construction. The user inclusion list (FR-038) is the v1 mechanism by which a user extends the compliant universe beyond SPUS membership using their own due diligence. The app does NOT certify user-added tickers as Shariah-compliant in any authoritative sense; the badge plainly labels them "User" so the provenance distinction is always visible.
- **Earnings calendar source (v1 default)**: A free/permissive earnings calendar provider seeded daily (for v1 prototyping); production swap-in for a licensed vendor is captured in research. Refresh interval: at least once per US trading day; warning surfaces if older than 3 trading days.
- **8-K filing source (v1)**: SEC EDGAR feed for 8-K filings is the v1 default — free, authoritative, publicly redistributable. Refresh interval: at least once per US trading day.
- **Economic calendar source (v1)**: A documented economic calendar (FOMC schedule from the Federal Reserve, BLS release calendar for CPI/NFP/PPI, BEA for PCE) is the v1 default. Refresh interval: at least once per week.
- **News sentiment / NLP**: Out of scope for v1. Events surface as badges and links, not as sentiment scores. Semantic classification of 8-K items is deferred.
- **Currency**: All monetary values are USD. Localization is out of scope for v1.
- **Backtesting**: In-app backtesting is out of scope for v1. Backtests exist as developer-side artifacts (per the constitution) but are not exposed as an interactive feature for end users.
- **Browser support**: Modern desktop browsers (latest two versions of Chrome, Edge, Safari, Firefox). Mobile-responsive layout is a nice-to-have for v1 but not a blocker.
