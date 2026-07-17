# Implementation Plan: Daily AI Portfolio Brief (Email Digest)

**Branch**: `018-daily-portfolio-brief` | **Date**: 2026-07-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/018-daily-portfolio-brief/spec.md`

## Summary

Add an automated, once-per-trading-session **daily brief loop** that, without the owner
opening the app, assembles one self-contained email covering (a) market news and sentiment
that may affect the owner's held/watched US stocks plus a market-context line, (b) a
portfolio-status summary (value, overall + per-holding P&L, risk exposure/heat, and
holdings needing attention), and (c) exactly **five** prioritized next-step recommendations.
The brief is delivered to the single owner's own allowlisted inbox via Gmail SMTP.

This is a **synthesis + delivery** feature over analysis the app already produces — it adds
**no** screening rule, gate threshold, indicator definition, citation, sizing model, or
backtest baseline (FR-002). The recommendation list is a **deterministic rule-based ranking
over existing signals** (holdings-attention → news/sentiment materiality → portfolio-level
fill-to-five), exactly analogous to feature 016's pure `score_fit` synthesis layer; any AI
narrative model only *phrases* the selected items, never selects them and never invents
signals (FR-005).

**Where it runs (settled in spec Clarifications).** The loop is part of the **always-on
hosted deployment** (feature 010). Compute happens on the hosted backend, which already holds
the baked read-only snapshot, the persisted single-owner portfolio blob, and the runtime
secrets. A new owner-secret-gated endpoint `POST /brief/run` assembles + sends the brief.
The **trigger** is the existing feature-011 daily-refresh CI job: after it bakes the fresh
snapshot and Factory-rebuilds the Space, a new final workflow step calls `POST /brief/run`
so the brief reflects the freshest completed session and is ready before the next open
(FR-001). Idempotency (FR-010) and the owner-visible run record (FR-014) are enforced by a
per-session Delivery Run Record so a re-trigger for the same session sends at most one email.

**Directive wording (constitution v1.2.0 + FR-007/FR-007a).** Because the brief provably
reaches only the owner's own allowlisted inbox, it qualifies for the re-scoped personal-use
directive exception even though it runs hosted. Feature 010 force-disables
`personal_use_directive()` under `hosted_mode()`; this plan adds a **narrow single-owner-gated
carve-out** — a new `brief_directive_enabled()` helper that permits directive framing **only**
when the personal-use flag is ON **and** the enforced single-owner access gate is present
(owner secret configured) **and** the instance is not multi-user. Every other surface keeps
today's hosted force-OFF untouched. When the carve-out does not hold, the brief falls back to
neutral, non-directive framing (FR-006) rather than dropping the recommendation section
(FR-007a). Either way every brief carries `data_as_of`, the non-advice disclaimer, and the
relevant strategy citation(s) (FR-008).

**Technical approach.** One new backend package `backend/src/brief/` holding pure, test-first
logic (`assemble.py` — gather existing outputs into a `BriefModel`; `recommend.py` — the
deterministic five-item ranker; `render.py` — deterministic text/HTML rendering + optional
narrative phrasing) and one impure edge (`email.py` — Gmail SMTP via the stdlib `smtplib`, no
new dependency). A new router `api/brief.py` exposes `POST /brief/run` and `GET /brief/status`
behind the existing owner-secret dependency. A Delivery Run Record persists next to the
portfolio blob. Everything rides existing idioms: a master `brief_enabled()` flag (default OFF
→ endpoint 404s, no scheduled call, no email), the baked-snapshot + BFF/owner-secret envelope,
the feature-014 sentiment pipeline (budget-capped, degrade-to-template), and the feature-011
publish chain as the trigger. No new external data source; SMTP creds + recipient are
process-local runtime secrets only (FR-015).

## Technical Context

**Language/Version**: Python 3.12 (backend). No frontend surface is required for the P1–P3 slices (the brief is delivered by email); an optional enable/disable + last-run status control reuses the existing settings blob and BFF proxy if added.
**Primary Dependencies**: FastAPI, Pydantic v2, pandas/numpy, pytest + hypothesis (backend). Email uses the Python **stdlib `smtplib` + `email.message`** — **no new dependency**. Reuses feature 014 sentiment (`sentiment/composite.py`, `sentiment/narrative.py`, budget guard), regime (`regime/calculator.py`), events (`events/service.py`), and portfolio (`portfolio/*`, `api/portfolio._assemble_holdings`).
**Storage**: Baked read-only Parquet/JSON snapshot under `backend/data/`; single-owner `portfolio_state.json` blob (holdings/transactions/watchlist/settings); a new `brief_runs.json` Delivery Run Record next to it (same `SCREENER_DATA_DIR` root). Captured sentiment reports in the existing durable store.
**Testing**: pytest golden-fixture + contract + regression. Test-first for the two genuinely new pure units — the five-item recommendation ranker (deterministic ordering/selection) and the brief renderer (determinism + no-directive lint in the neutral path). SMTP send is tested against a stub transport (no live network).
**Target Platform**: Hosted = HF backend Space (GHCR Docker image, factory-rebuild) + Vercel BFF frontend; local = `py -3.12` backend. The loop trigger is the existing GitHub Actions daily-refresh workflow.
**Project Type**: Web application (FastAPI backend + Next.js BFF frontend) — this feature is backend + CI-workflow only.
**Performance Goals**: Not latency-critical (a once-daily unattended job). The brief assembles over the owner's held + watched tickers (tens of names), reusing single-ticker-budget computations; sentiment reuses captured reports and the budget-capped generate-once path. Target: one brief assembled + sent in well under the workflow's 30-minute budget.
**Constraints**: Determinism (same snapshot + same portfolio → byte-identical brief content, FR-013/SC-005); `data_as_of` + non-advice disclaimer on every brief (FR-008); zero directive language whenever the carve-out does not hold (FR-006, lint-tested, SC-004); at-most-one email per completed session (FR-010, idempotent); never a misleading "today" brief on a non-trading day (FR-011); SMTP app-password + recipient are runtime-env only, never written to an artifact or logged in plaintext (FR-015); delivered only to the single allowlisted owner address (FR-009).
**Scale/Scope**: Single owner / single recipient. One email per enabled trading session.

**Deployment-compatibility notes** (compatible with the 010/011 hosted architecture):
- New behavior is gated by `brief_enabled()` (default OFF). With it off, `POST /brief/run`
  404s, the CI trigger step is a no-op, and no email is ever sent — byte-identical to feature
  017. No new in-host ingest, no baked-snapshot change, no new external data source.
- `POST /brief/run` and `GET /brief/status` register behind the existing owner-secret
  dependency + CORS pin — no new auth surface. The CI trigger authenticates with the same
  `SCREENER_OWNER_SECRET` already provisioned on the Space.
- Gmail SMTP host/port and the app password + recipient are read from process env only
  (`SCREENER_BRIEF_*`), configured as HF Space runtime secrets alongside the existing feature-014
  sentiment keys — never committed, never logged (FR-015, secret-scan clean).
- The Delivery Run Record (`brief_runs.json`) is written under `SCREENER_DATA_DIR` like the
  portfolio blob. Its **persistence across a factory rebuild** is the one open architectural
  question resolved in research.md (Decision 2): idempotency is keyed on the target session
  and re-verified against the just-sent record, and the single daily trigger fires once per
  session, so at-most-once holds even if the record is ephemeral.

**NEEDS CLARIFICATION**: none blocking. All product decisions are settled in the spec's six
Clarifications + Assumptions (hosted execution, news window = since-last-brief, deterministic
rule-ranked five, trigger = after the 011 refresh, Gmail SMTP app-password, directive wording
flag+access-gated). The two implementation-level unknowns (run-record persistence across
rebuild; how the CI step distinguishes a real publish from a `noop` guard exit) are resolved
in research.md, not deferred.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| **I. Data Integrity & Provenance** (NON-NEGOTIABLE) | ✅ PASS | No new data source. The brief reuses the existing point-in-time snapshot, EDGAR/events overlay, quotes, regime, and captured sentiment; every section carries its source + as-of, and the brief surfaces active staleness/integrity warnings rather than presenting affected numbers as fresh (FR-008, edge cases). |
| **II. Strategy Transparency & Peer-Reviewed Foundations** | ✅ PASS | Zero change to any `rules()`, gate, threshold, ranking, citation, or backtest baseline (FR-002). The five recommendations are a *presentation/synthesis* ranking over signals the app already produces (like 016's `score_fit`), with the ranking priority documented as constants in `recommend.py`; the AI narrative only phrases, never selects (FR-005). Each directive item still carries its strategy citation(s). |
| **III. Reproducible Backtesting & Bias Avoidance** (NON-NEGOTIABLE) | ✅ PASS | No backtest, window, cost model, or re-baseline touched. The brief performs no strategy backtest; recommendation selection is deterministic and reproducible from the same snapshot + portfolio (FR-013/SC-005). |
| **IV. Test-First for Financial Logic** | ✅ PASS | The two new pure units — the deterministic five-item ranker and the renderer — land golden-fixture + determinism + no-directive lint tests before the logic (Phase 0/1). No indicator or screening rule is added, so no new fixture-anchored indicator is required; existing suites stay green with zero silent skips. |
| **V. User Safety, Risk Disclosure & No-Advice Boundary** | ✅ PASS (with recorded amendment acceptance) | Default (carve-out absent) is zero-directive, lint-tested (FR-006, SC-004). Directive framing is a *separate gated path* permitted **only** under the constitution v1.2.0 single-owner access-gated exception — flag ON + enforced single-email allowlist + not multi-user + output reaching only the owner's own inbox (FR-007/FR-007a). Even then each item carries citation + `data_as_of` + non-advice/limitations disclosure. Delivered solely to the owner's allowlisted address (FR-009). SMTP app-password is a runtime secret, never logged (FR-015). See Complexity Tracking for the amendment-acceptance record. |

**Result**: No violations. The v1.2.0 amendment that enables the hosted directive carve-out is
recorded in Complexity Tracking (single-operator acceptance, per the amendment's follow-up TODO).

## Project Structure

### Documentation (this feature)

```text
specs/018-daily-portfolio-brief/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output — decisions + rationale
├── data-model.md        # Phase 1 output — new entities
├── quickstart.md        # Phase 1 output — local runbook + manual verification + deploy
├── contracts/           # Phase 1 output — API + integration contracts
│   ├── brief-run.md            # POST /brief/run, GET /brief/status
│   ├── recommendation-ranking.md   # deterministic five-item selection/ordering
│   ├── email-delivery.md       # Gmail SMTP transport, secrets, retry/idempotency
│   └── directive-carveout.md   # brief_directive_enabled() gating truth table
├── checklists/
│   └── requirements.md  # (pre-existing, from /speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

New: one backend `brief/` package (pure assemble/recommend/render + impure email edge) + one
router + one Delivery Run Record store helper + one CI trigger step. Extends `flags.py` and the
daily-refresh workflow in place. No new subsystem beyond the `brief/` package, no new data
source, no new auth surface, no frontend change required for P1–P3.

```text
backend/
├── src/
│   ├── lib/
│   │   └── flags.py                    # + brief_enabled() (default OFF); + brief_directive_enabled() single-owner-gated carve-out (FR-007a); + brief_* SMTP/recipient accessors (runtime env only)
│   ├── brief/                          # NEW package
│   │   ├── assemble.py                 # pure — gather existing outputs (holdings/totals/attention, sentiment, regime+events, news window) → BriefModel
│   │   ├── recommend.py                # pure — deterministic five-item ranker: attention → news/sentiment materiality → portfolio-level fill-to-five; documented priority constants; neutral + gated directive vocab
│   │   ├── render.py                   # pure — deterministic text + minimal HTML render; disclosures/citations/warnings; optional AI narrative *phrasing only* (budget-capped, degrade-to-template)
│   │   └── email.py                    # impure edge — Gmail SMTP send via stdlib smtplib; bounded retry; owner-only recipient guard
│   ├── data/
│   │   └── brief_store.py              # NEW — Delivery Run Record load/save (brief_runs.json under SCREENER_DATA_DIR); idempotency + GET /brief/status
│   ├── models/
│   │   └── brief.py                    # NEW — BriefModel, RecommendationItem, NewsItem, BriefDeliveryRecord, BriefRunResponse/StatusResponse
│   └── api/
│       ├── brief.py                    # NEW router — POST /brief/run (flag-off ⇒ 404; idempotent per session; non-trading-day skip; bounded retry + owner-visible failure), GET /brief/status
│       └── app.py                      # register brief router
└── tests/
    ├── brief/         # test-first: recommendation ranking table, renderer determinism + no-directive lint, directive carve-out truth table, assemble fail-soft
    ├── contract/      # brief-run + brief-status contract tests
    └── automation/    # CI-trigger idempotency / non-trading-day skip (mirrors feature-011 automation tests)

.github/workflows/
└── daily-refresh.yml                   # + final step (post-rebuild): call POST /brief/run with the owner secret, only when a real session was published (not a guard noop); never fails the publish job
```

**Structure Decision**: Web application (existing `backend/` + `frontend/` split). One new
backend package (`brief/`) plus one store helper and one router — everything else is an
in-place extension of `flags.py` and the existing daily-refresh workflow. No frontend surface
is required to satisfy P1–P3 (delivery is by email); an optional in-app enable/disable + last-run
status indicator can reuse the existing settings blob + `GET /brief/status` if the owner wants
it, and is called out as optional in quickstart. The deploy surface (baked snapshot + BFF proxy
+ owner-secret + env flags + the 011 publish chain) is exactly as 010/011 established it,
extended only additively.

## Complexity Tracking

> No Constitution Check violations. The single entry below records the governance acceptance the
> v1.2.0 amendment requires, not a violation.

| Item | Why Needed | Note |
|------|------------|------|
| Constitution v1.2.0 amendment acceptance (Principle V re-scope) | FR-007/FR-007a require directive wording on a single-owner, access-gated hosted instance whose output reaches only the owner's own inbox. v1.2.0 permits exactly this and ties the no-advice boundary to *third-party exposure* rather than hosting. | The amendment's follow-up TODO asks a non-author maintainer to record acceptance; for this single-operator repo the owner records acceptance here. The carve-out stays flag-gated (OFF by default) + single-owner-access-gated + full-disclosure; it reverts automatically to neutral framing the moment the instance becomes multi-user/shared/third-party-exposed. |
