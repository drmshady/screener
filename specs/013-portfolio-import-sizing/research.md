# Phase 0 Research: Portfolio Import, Purchase-Anchored Levels & Risk-Aware Sizing

All decisions below resolve the spec's open points. The two load-bearing forks (import
mechanism, lot model) were confirmed directly by the owner.

---

## Decision 1 — Google Sheet import mechanism: browser OAuth token flow

**Decision**: The **browser** reads the owner's sheet. The owner authorizes with Google via
Google Identity Services (GIS) and the app obtains a **short-lived access token** scoped
`https://www.googleapis.com/auth/spreadsheets.readonly`. The browser calls the Google Sheets
REST API v4 (`GET /v4/spreadsheets/{id}/values/{range}`), parses the rows, and POSTs the
**parsed transaction rows as JSON** to `POST /portfolio/import`. The backend never contacts
Google and holds no Google credential.

**Rationale**:
- **Secrets stay runtime-only and never hit a file or the server** — satisfies FR-001 and the
  existing [[api-keys-never-write]] rule. The token is short-lived and browser-resident; it is
  never logged, never persisted, never sent to the backend as a durable secret.
- **Works hosted** on the free Hugging Face Space (backend) + Vercel (frontend) tier without
  baking a Google service-account key into the backend image — consistent with feature 010's
  "secrets are runtime env only" and "no heavy in-host work" posture (see Decision 9).
- **Reuses feature 010's Google sign-in** (NextAuth Google) — the owner is already a Google
  account holder in the allowlist; this adds only the incremental Sheets read scope.
- Keeps the backend a **pure function of supplied rows**, which is exactly what the
  test-first financial logic (Principle IV) and determinism (SC-006) want.

**Alternatives considered**:
- *Server-side service-account key*: backend pulls the sheet itself. Rejected — forces a
  long-lived Google credential into server runtime env, requires sharing the sheet with a
  service-account email, and adds a backend Google dependency on the free box. Heavier with no
  benefit for a single owner.
- *Published-to-web CSV link*: simplest, no login, but makes the sheet link-public and is not
  "the owner's authorized Google account" the spec calls for. Rejected on privacy + fidelity
  to spec.

**Scope note**: The sheet's spreadsheet **id** and the chosen tab/range are owner inputs
stored in the (non-secret) portfolio settings blob so re-import is one click. The OAuth token
is *not* stored.

---

## Decision 2 — Lot model: aggregated, average-cost holding per ticker

**Decision**: Transactions aggregate into **one holding per ticker**: net quantity =
Σ(buys) − Σ(sells); cost basis = **share-weighted average cost of buys**. Sells reduce
quantity and realized P/L but, under average-cost, do **not** change the average cost of the
remaining shares. Anchoring dates recorded per holding: **earliest** buy date (anchors the
"original-plan" levels and conveys plan age) and **most-recent** buy date.

**Rationale**: Matches the spec's default assumption and the owner's confirmation; simplest
correct model; one stop / one target / one P/L per ticker row is the cleanest presentation.
Average cost is the documented (FR-004) basis and is deterministic.

**Alternatives considered**: *Per-lot holdings* (each buy its own lot/stop/target/P-L) —
richer but multiplies rows and complicates the data model and UI. Rejected for v1; the data
model keeps the raw transaction list, so a future per-lot view is non-breaking.

**Cost-basis edge rules** (documented, deterministic):
- A net-negative quantity (more sold than bought in the sheet) is surfaced as a **data
  warning** and the holding is shown as closed/anomalous, never a nonsensical short (edge case
  in spec).
- A fully-sold ticker (net qty = 0) is shown as **closed** with realized P/L and no
  levels/sizing.

---

## Decision 3 — Idempotent re-import: stable transaction identity

**Decision**: Each transaction gets a **stable content hash** =
`sha1(ticker | action | quantity | price | trade_date | row_fingerprint)` where
`row_fingerprint` is the normalized tuple of required fields (and the sheet row index only as
a last-resort tiebreaker for genuinely identical rows). On import the backend de-duplicates by
this id against the rows already in the portfolio blob, so re-importing a sheet that contains
previously-seen rows plus new ones applies **only the net new rows** (FR-005, SC-003).

**Rationale**: A content hash makes re-import idempotent without requiring the owner to add an
explicit id column. Two genuinely identical fills on the same day (rare) are disambiguated by
row index so they are not collapsed.

**Alternatives considered**: *Require an explicit transaction-id column* (rejected — extra
owner burden, easy to get wrong); *replace-all on every import* (rejected — loses the
idempotent "net change only" property and would clobber any manually added rows).

---

## Decision 4 — Two purchase-anchored level bases (FR-008/FR-009)

**Decision**: Per open holding, derive **both** bases by reusing
`strategies/levels.derive_bounded_levels` (the single feature-011 implementation):

- **Original-plan**: call `build_single_ticker_snapshot(ticker, as_of=earliest_buy_date)` to
  get ATR / SMA-200 / swing-low **as they were on the purchase date**, then derive bounded
  levels but **anchor `entry` to the holding's average cost** (the real fill), not that day's
  close. Frozen — recomputed identically every time because `as_of` pins the inputs.
- **Current-condition**: call `build_single_ticker_snapshot(ticker)` (latest snapshot) for
  current ATR/SMA-200/swing-low, derive bounded levels, again **anchored to the average cost**
  as `entry`. This re-expresses the plan against today's volatility and the elapsed holding
  period.

Both reuse the existing bounded clamps, reward ceiling, `insufficient_data` fallback (FR-012),
and neutral zero-directive rationale (FR-020). The helper already accepts a row; we pass a row
whose `close` is overridden to the average cost so `entry == avg_cost` without touching the
helper's contract.

**Rationale**: `build_single_ticker_snapshot` already supports an `as_of` parameter, so
point-in-time volatility for the purchase date comes for free with no look-ahead and no new
data path (Principle I/III). Anchoring `entry` to the real fill is what makes the levels about
*the position the owner holds* rather than a hypothetical fresh entry. Reusing one helper for
both bases preserves determinism and the documented contract (FR-013, SC-006).

**Alternatives considered**: *Recompute the stop only from purchase-date close* (rejected —
ignores the owner's actual fill); *a brand-new level function* (rejected — would duplicate and
risk diverging from the audited `derive_bounded_levels` contract, and would touch financial
math the spec forbids changing).

**Breach/target status**: purely comparative — `current_price ≤ stop_loss` ⇒ "stop breached
(informational)"; `current_price ≥ take_profit` ⇒ "target reached (informational)". No
directive language (FR-011/FR-020).

---

## Decision 5 — Risk-aware sizing view: reuse the risk-per-trade backbone

**Decision**: Per holding, compute the **recommended** size with the existing
`portfolio/sizing.size_position` using the holding's **current-condition stop** as
`stop_loss`, the owner's capital base + per-trade risk fraction, and the existing caps — then
present recommended size **alongside the actual quantity held**. Separately compute, from the
actual position, **capital-at-risk** = `actual_shares × (entry_basis − stop)` in dollars and
as a percent of capital, and **flag over-risk** when actual capital-at-risk exceeds the
per-trade risk budget (`risk_per_trade_fraction × capital`) or a position/sector cap, **naming
the binding constraint** (FR-014/015/016). Sizing **fails open** to the bounded baseline when
a conviction/modulator input is missing (FR-018) — already the backbone's behavior. Portfolio
totals: **total invested** and **total capital-at-risk** (FR-017).

**Rationale**: `size_position` already encodes the risk-per-trade target, conviction
fail-open, caps, and binding-constraint reasoning (feature 011 US3). We add only the
**actual-vs-recommended comparison** and the **actual capital-at-risk** read-out — descriptive
math, no change to the sizing rules or defaults (FR-021).

**Open knob**: which stop anchors actual capital-at-risk — the **current-condition stop** is
used (it reflects the live risk if the stop were honored today); the original-plan stop is
shown for context. Documented in data-model.md.

**Alternatives considered**: *Size against the original-plan stop* (rejected for the live
risk read-out — it understates/overstates today's risk; kept only as context).

---

## Decision 6 — Persistence: extend the existing single-owner blob, no new store

**Decision**: Persist imported transactions, the derived holdings cache is **not** persisted
(holdings + levels + sizing are recomputed deterministically from transactions + snapshot on
each `/portfolio/holdings` call). The raw `transactions[]`, the sheet id/range settings, and
the capital/risk config live in the existing opaque portfolio blob
(`data/portfolio_store.py` → `portfolio_state.json`), mirrored from the browser by
`PortfolioSync`. A "clear/replace portfolio" action empties `transactions[]` (FR-007).

**Rationale**: Reuses the proven single-owner persistence (server blob + localStorage mirror)
with zero new infrastructure. Storing transactions (the source of truth) and recomputing
holdings keeps the import idempotent and the levels/sizing always consistent with the current
snapshot (determinism, FR-013).

**Alternatives considered**: *Persist computed holdings* (rejected — risks stale/divergent
levels and duplicates the source of truth); *new SQLite table* (rejected — unnecessary for one
owner, breaks the established blob pattern).

---

## Decision 7 — Out-of-coverage tickers (FR-023)

**Decision**: When `build_single_ticker_snapshot` raises (no OHLCV, not in universe, delisted,
typo), the holding is returned with `priceable=false`, a human-readable note, its cost-basis
facts and quantity intact, and `levels_state="insufficient_data"` / no sizing — the import and
the rest of the view are unaffected.

**Rationale**: Mirrors the existing `/portfolio/quotes` stale-fallback behavior (it already
appends a note and returns the row). Honest, non-breaking, consistent with Principle I.

---

## Decision 8 — Validation & honest rejection (FR-003, SC-002)

**Decision**: Row validation is a **pure function** returning `(accepted[], rejected[])` where
each rejected entry carries `{row_ref, reason}`. Rejections: missing/!buy-or-sell action,
non-positive/non-numeric quantity or price, unparseable trade date, missing ticker. Optional
columns (fees, notes) are tolerated. Nothing is silently dropped; the import response returns
the full summary and the accepted rows are still aggregated (FR-003).

**Rationale**: Pure + fixture-tested (Principle IV); guarantees SC-002 (100% of bad rows
reported with row ref + reason, 0% silently dropped).

---

## Decision 8a — Real-sheet schema: header aliases, type taxonomy, day-first dates, currency cleaning

**Decision** (confirmed by the owner against their actual sheet): the parser maps the owner's
descriptive headers to canonical fields (case-insensitive) — `Date→trade_date`, `Type→action`,
`Stock→ticker`, `Transacted Units→quantity`, `Transacted Price (per unit)→price`, `Fees→fees` —
and ignores all of the sheet's computed columns (`Stock Split Ratio`, `Cumulative Units`,
`Cost of Transaction`, `Realised Gains/Losses %`, …). Normalization before validation:
- **Type** is lower-cased; only `buy`/`sell` are aggregated. The complete type set in the
  owner's sheet is **Buy / Sell / Div** (owner-confirmed) — no DRIP/split/transfer rows that
  change share count, so the `Stock Split Ratio` column needs no handling in v1.
- **Dividends (`Div`)** are **rejected as unsupported** (Decision: surfaced in the import
  summary with a clear reason, not silently dropped, not tracked into P/L for v1). A `Div`
  row's recorded "units" never change holdings — consistent with the sheet's own
  `Cumulative Units` staying flat across the dividend row.
- **Slash dates are day-first** (`28/7/2025` ⇒ 28 Jul; `5/9/2025` ⇒ 5 Sep), with the
  month-name form (`9-Oct-2025`) and ISO also accepted. Day-first is fixed ⇒ deterministic.
- **Money cells** carry `$` and thousands separators (`$1,025.32`) and are stripped before
  `Decimal` parsing; a `-`/empty cell in an optional column is "absent", in a required column
  is rejected.

**Rationale**: Grounds the validator in the owner's real data rather than the originally
assumed `ticker|action|quantity|price|trade_date` schema, so the first import works without the
owner re-formatting their sheet. All rules are pure/deterministic and fixture-tested.

**Coverage note**: the owner's holdings are largely **ETFs** (SPUS, SLV, IBIT, GLD), which are
outside the screener's US-common-equity universe ⇒ shown as `priceable=false` (Decision 7).
This means the out-of-coverage and closed-holding paths are the common case for this owner, not
an edge — the holdings view must read cleanly when few/no holdings have live levels.

---

## Cross-cutting confirmations

- **Determinism (SC-006)**: same snapshot + same `transactions[]` ⇒ byte-identical holdings,
  levels, and sizing. Enforced by an integration test that runs `/portfolio/holdings` twice
  and diffs.
- **`data_as_of` + `disclaimer` (FR-019)**: both new responses carry them, using the newest
  contributing snapshot `data_as_of` (same idiom as `/portfolio/quotes`).
- **Zero directive language (FR-020)**: new copy ("breached", "target reached", "over per-trade
  risk budget", "out of coverage") is descriptive; the existing Playwright
  `no-directive-copy.spec.ts` is extended to cover the import + holdings surfaces.
- **Hosted directive OFF (FR-022)**: unchanged — `flags.personal_use_directive()` already
  returns False in hosted mode; this feature adds no directive output.
- **No strategy/baseline change (FR-021)**: no file under `strategies/` rules, no
  `PARAMETERS`, no backtest baseline touched; only `levels.derive_bounded_levels` and
  `sizing.size_position` are *called*, not modified.

---

## Decision 9 — Fit the live GitHub + Hugging Face + Vercel pipeline with no infra change

**Decision**: Implement so the existing deployment chain — GitHub Actions `daily-refresh.yml`
→ GHCR image → **Hugging Face Space** `occlusion2/screener` (baked read-only snapshot) +
**Vercel** frontend — needs **no CI/image/hosting change**, only one new *public* frontend env
var (`NEXT_PUBLIC_GOOGLE_CLIENT_ID`). Backend adds no dependency and no ingest; new routes
write only the existing small portfolio blob and sit behind the feature-010 BFF owner-secret
gate. See the plan's "Deployment Compatibility" section for the five concrete constraints.

**Rationale**:
- The backend is a **baked, read-only, no-ingest** image on a **free, ephemeral, daily-rebuilt**
  HF Space. Adding a Google dependency or a writable datastore there would fight the platform.
  Keeping Google entirely browser-side and treating the HF disk as throwaway cache (durable
  state mirrored to the browser via `PortfolioSync`) is the only design that survives daily
  rebuilds without new infra.
- `/portfolio/holdings` deliberately reuses the **already-deployed** `build_single_ticker_snapshot`
  path (proven by the live `/portfolio/quotes`), so it inherits HF's working behavior; original-plan
  `as_of` levels read from the baked `prices/` snapshot and need no network.
- Reusing feature 010's Google OAuth app + the public client id keeps secrets out of every build
  artifact (`NEXT_PUBLIC_*` is public by design); the import UI degrades gracefully when the id
  or GIS script is absent so headless prod-build e2e never depends on Google.

**Alternatives considered**: *Server-side Google pull on HF* (rejected — needs a long-lived
credential + writable state on an ephemeral free box, fights 010's no-ingest posture);
*persist computed holdings server-side* (rejected — wiped on daily rebuild and non-deterministic
vs the snapshot); *a separate always-on backend host* (rejected — abandons the free-tier
constraint and the proven HF/Vercel split for no functional gain).

**Note**: CLAUDE.md still says "Render" from the 010 spec text; the live backend has since moved
to Hugging Face ([[deploy-012-and-code-only-deploys]]). This plan uses the HF reality; the stale
CLAUDE.md wording is cosmetic and out of this feature's scope to rewrite.
