# Feature Specification: Advisor Prompt Export

**Feature Branch**: `004-advisor-prompt-export`
**Created**: 2026-06-13
**Status**: Draft
**Input**: User description: "Add an in-app feature that generates a copy-ready prompt containing the strategy result for a candidate stock plus all required information about this app/strategy, so the user can paste it into an external AI advisor (the Claude Project) and get an expert, honest assessment."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Copy a complete advisor prompt for a candidate (Priority: P1)

While reviewing a single candidate stock that matched the mid-term 52-week-high
momentum strategy, the user clicks one control and receives a ready-to-paste
text prompt. The prompt already contains every figure the app computed for that
candidate (the gate-by-gate result, the entry / stop / tighter-stop /
take-profit levels, the rank, the current market regime, and the data-as-of
date) so the user never has to transcribe numbers by hand.

**Why this priority**: This is the core of the feature and the whole reason it
exists — it eliminates the manual data-gathering that the external advisor
otherwise requires, and it removes the single biggest honesty risk (an AI
inventing the candidate's numbers from stale memory). Delivered alone, it is a
complete, useful capability.

**Independent Test**: Open a candidate that matched the strategy, click "Copy
advisor prompt," paste the clipboard contents into a plain text editor, and
confirm the prompt contains the candidate's ticker, every gate the strategy
declares with its pass/fail/skipped status, the four price levels, the regime,
the data-as-of date, and a disclaimer — with no placeholder gaps.

**Acceptance Scenarios**:

1. **Given** a candidate that matched the strategy on the current snapshot,
   **When** the user clicks "Copy advisor prompt," **Then** a complete prompt is
   placed on the clipboard and a confirmation is shown.
2. **Given** the same candidate and the same data snapshot, **When** the user
   generates the prompt twice, **Then** the two prompts are identical
   character-for-character.
3. **Given** a candidate whose prompt was generated, **When** the user inspects
   it, **Then** every numeric value in it matches what the app displays for that
   candidate (no value differs from the on-screen figures).

---

### User Story 2 - Self-contained prompt that works without any setup (Priority: P2)

The user pastes the generated prompt into a brand-new AI chat that has **no**
preloaded knowledge of the strategy. The prompt still produces a competent,
grounded assessment because it carries all the required context itself: the
strategy's name and citation, the timeframe and holding period, the list of
gates, every modification with its own source, and the honesty caveats.

**Why this priority**: The user explicitly wants the prompt to "contain all
required information about this app." Self-containment makes the feature robust
— it does not depend on the user having configured an external project
correctly, and it stays correct even if that external configuration drifts.

**Independent Test**: Paste a generated prompt into a fresh AI chat with no
project knowledge attached and confirm the response correctly names the
strategy, cites George & Hwang (2004), references the relevant gates, and
repeats the survivorship caveat — without asking the user for missing context.

**Acceptance Scenarios**:

1. **Given** a generated prompt, **When** it is read in isolation, **Then** it
   contains the strategy name, its citation, its timeframe and holding period,
   and the full set of declared modifications each with its own citation.
2. **Given** a change to the strategy's parameters or modifications in the app,
   **When** a new prompt is generated, **Then** the prompt reflects the changed
   declaration (it does not carry stale rules).

---

### User Story 3 - The prompt is honest about limitations (Priority: P1)

Whenever the prompt could lead to a performance judgment, it states the
strategy's current limitations in plain language: that the backtest fails its
survivorship-bias check (so historical results are optimistic), that certain
gates "pass through" names when their data is missing, and that the data is
end-of-day as of a stated date. These caveats are present every time, not
optional.

**Why this priority**: "Expert and honest" is the user's stated requirement. A
prompt that hands an external advisor clean-looking numbers while hiding that
the backtest is survivorship-biased would actively mislead. Honesty is a
correctness property here, not a nicety — hence P1 alongside US1.

**Independent Test**: Generate prompts for several different candidates and
confirm each one contains the survivorship-bias caveat, the data-as-of date,
and a note about any gate that was skipped/passed-through for that candidate.

**Acceptance Scenarios**:

1. **Given** the strategy's backtest still fails its survivorship-bias check,
   **When** any prompt is generated, **Then** the prompt states that historical
   performance is optimistic because delisted companies are absent from the
   data.
2. **Given** a candidate for which one or more gates were skipped or passed
   through on missing data, **When** the prompt is generated, **Then** the
   prompt distinguishes those gates from gates that genuinely passed.
3. **Given** any generated prompt, **When** it is inspected, **Then** it carries
   the standard non-advice disclaimer and the data-as-of date.

---

### User Story 4 - Personal-use scope is enforced (Priority: P2)

Because the external advisor is configured to give directive, personalized
guidance (a take/pass/size call), the prompt may instruct it to do so **only**
while the app is in personal-use mode. When personal-use mode is off, the
generated prompt uses neutral, educational framing instead, and the directive
control is not offered.

**Why this priority**: The project constitution sets a non-negotiable no-advice
boundary that applies the moment output is shared or hosted. Gating the
directive framing keeps the feature compliant by default and makes the
personal-use exception explicit and reversible.

**Independent Test**: With personal-use mode on, confirm the prompt asks the
advisor for a directive call. Turn personal-use mode off, regenerate, and
confirm the prompt instead asks for a neutral analysis and contains no
directive ("buy/sell/recommended") language.

**Acceptance Scenarios**:

1. **Given** personal-use mode is enabled, **When** a prompt is generated,
   **Then** it may include directive-call framing.
2. **Given** personal-use mode is disabled, **When** a prompt is generated,
   **Then** it contains no directive language and uses neutral framing
   ("screen match," "candidate for further research").

---

### Edge Cases

- **Candidate has insufficient indicator data** (no usable entry/stop/target):
  the prompt is either not offered or is generated with the missing levels
  clearly marked as unavailable rather than fabricated.
- **A gate could not be evaluated** (missing fundamentals/volume): the prompt
  marks it "skipped — data unavailable" and the honesty block notes it did not
  exclude the name.
- **The backtest artifact is missing or unreadable**: the prompt still
  generates, and the honesty block states the survivorship/limitation status
  could not be confirmed (it never silently claims the backtest is clean).
- **Stale data snapshot**: the data-as-of date in the prompt reflects the actual
  snapshot, and any stale-source warning the app already tracks is surfaced.
- **A strategy other than the mid-term 52-week-high strategy**: the feature is
  scoped to that strategy in v1; for others the control is not offered (or
  states the prompt is unavailable for that strategy).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a single user control on a candidate that
  generates a copy-ready advisor prompt and places it on the clipboard.
- **FR-002**: The generated prompt MUST include the candidate's identity
  (ticker, name, sector), its rank or matched status, and the data-as-of date.
- **FR-003**: The generated prompt MUST include the candidate's computed price
  levels: entry, stop, tighter-stop alternative (when present), and take-profit,
  plus the resulting reward-to-risk.
- **FR-004**: The generated prompt MUST include the full gate-by-gate result for
  the candidate, with each gate's pass / fail / skipped status and its
  explanatory detail.
- **FR-005**: The generated prompt MUST include the current market regime and
  what that regime implies for this strategy.
- **FR-006**: The generated prompt MUST be self-contained: it MUST include the
  strategy's name, citation, timeframe, holding period, the list of gates, and
  every declared modification together with each modification's own citation,
  sourced from the app's live strategy declaration (not a hand-maintained copy).
- **FR-007**: The generated prompt MUST always include an honesty section that
  states the strategy's backtest survivorship-bias status and, when that check
  is failing, plainly warns that historical performance is optimistic.
- **FR-008**: The generated prompt MUST distinguish gates that genuinely passed
  from gates that were skipped or passed through on missing data.
- **FR-009**: The generated prompt MUST carry the standard non-advice disclaimer.
- **FR-010**: Every numeric value in the prompt MUST originate from the app's
  computed candidate result; the feature MUST NOT require or rely on any figure
  being computed by the external advisor.
- **FR-011**: Generating a prompt for the same candidate on the same data
  snapshot MUST produce an identical prompt on every run (deterministic).
- **FR-012**: When the app's strategy declaration changes (parameters,
  modifications, citations), a newly generated prompt MUST reflect the change
  without separate manual edits.
- **FR-013**: The directive (take/pass/size) framing in the prompt MUST be
  emitted only when the app is in personal-use mode; otherwise the prompt MUST
  use neutral framing and contain no directive trading language.
- **FR-014**: When personal-use mode is off, no part of the app's own visible
  interface introduced by this feature may contain directive trading language
  (so the existing no-directive-copy guarantee is preserved).
- **FR-015**: The feature MUST be available from the candidate detail view and
  from the single-ticker analysis view; availability from the screener results
  list is desirable but secondary.
- **FR-016**: The feature MUST be scoped to the mid-term 52-week-high momentum
  strategy in v1; for unsupported strategies the control MUST NOT present a
  misleading prompt.
- **FR-017**: When required candidate data is missing, the prompt MUST mark the
  missing items as unavailable rather than fabricate values, or the control MUST
  be withheld with a clear reason.

### Key Entities

- **Advisor Prompt**: The generated, copy-ready text artifact. Composed of a
  task instruction, the strategy context block, the candidate result block, the
  gate breakdown, the regime note, and the honesty/caveat block. Carries a
  data-as-of date and a disclaimer.
- **Candidate Result**: The app's already-computed assessment of one stock under
  the strategy — gate results, price levels, rank/matched status, regime
  context.
- **Strategy Declaration**: The strategy's self-described identity used to make
  the prompt self-contained — name, citation, timeframe, holding period,
  parameters, and modifications-with-citations.
- **Honesty/Caveat Block**: The mandatory limitations section — survivorship
  status, fail-open gate notes, data freshness, non-advice disclaimer, and the
  personal-use scope note.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can obtain a complete advisor prompt for a candidate in a
  single action (one control click) without typing any of the candidate's data.
- **SC-002**: 100% of generated prompts include every gate the strategy declares
  for that candidate and every modification the strategy declares.
- **SC-003**: While the strategy's backtest fails its survivorship-bias check,
  100% of generated prompts contain the survivorship caveat and the data-as-of
  date.
- **SC-004**: Regenerating a prompt for the same candidate on the same data
  snapshot yields a byte-identical result 100% of the time.
- **SC-005**: 100% of numeric values in a generated prompt match the values the
  app displays for that candidate (zero discrepancies).
- **SC-006**: With personal-use mode off, 0 occurrences of directive trading
  language ("buy," "sell," "recommended," "strong buy") appear in the feature's
  visible interface and in the generated prompt.
- **SC-007**: A generated prompt pasted into an AI chat with no preloaded
  context still elicits a response that correctly names the strategy, cites its
  source, and repeats the survivorship caveat — demonstrating self-containment.

## Assumptions

- **Single source of truth**: The strategy context in the prompt is derived from
  the app's live strategy declaration and backtest artifact, so it cannot drift
  from the implemented rules. This is preferred over a hand-maintained prompt
  template.
- **Personal-use directive scope**: The app is a single-user, personal-use tool,
  so directive framing is permitted by default in personal-use mode; the
  no-advice boundary re-applies automatically if the output is ever shared or
  hosted. This mirrors the existing operator-override and personal-use posture
  already established in the project.
- **v1 strategy scope**: Only the mid-term 52-week-high momentum strategy is
  supported, matching the depth of single-ticker analysis already available for
  it. Short-term strategies are out of scope for v1 of this feature.
- **No new data sources**: The feature composes data the app already computes and
  serves; it introduces no new external data dependency.
- **External advisor is out of scope**: This feature produces the prompt only.
  The behavior of the external AI tool that consumes the prompt is governed by
  the separately-maintained Claude Project knowledge files, not by this feature.
- **Determinism**: The app already produces deterministic results on a frozen
  snapshot; the prompt inherits that determinism.
