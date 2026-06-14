# Quickstart: Mid-Term Side-by-Side Variant Comparison

Personal-use, single-machine (Windows). Assumes the frozen `backend/data/`
snapshot and both mid-term strategies already exist (features 001/005).

## 1. Backend tests first (TDD)

```powershell
# New orchestration/presentation tests — write these to fail first, then implement:
py -3.12 -m pytest backend/tests/screening/test_midterm_matrix.py
py -3.12 -m pytest backend/tests/agent/test_midterm_matrix_prompt.py
py -3.12 -m pytest backend/tests/api/test_midterm_compare_api.py
```

What they assert:
- exactly four labelled variants in fixed order;
- all four share one `data_as_of`, one universe, one regime (FR-002);
- within each strategy pair, only the toggled parameter differs (SC-003);
- determinism: two runs on the same snapshot are identical (SC-002);
- an empty variant is shown with notes and does not drop the others (FR-016);
- the combined prompt has four delimited sections each with declaration / gates /
  levels / regime / bias-check, and is byte-identical on re-export (SC-006/SC-007).

## 2. Run the matrix from the API

```powershell
# Start the backend (see Windows dev runbook), then:
curl -s -X POST http://localhost:8000/strategies/midterm-compare `
  -H "Content-Type: application/json" `
  -d '{}' | python -m json.tool
```

Expect `variants` of length 4 (`momentum_sector_on`, `momentum_sector_off`,
`value_floor_on`, `value_floor_off`), a shared `regime`, and `data_as_of` +
`disclaimer`. Each `variants[*].screen` is a normal `ScreenResult`.

Verify determinism:

```powershell
curl -s -X POST http://localhost:8000/strategies/midterm-compare -d '{}' > a.json
curl -s -X POST http://localhost:8000/strategies/midterm-compare -d '{}' > b.json
fc.exe a.json b.json   # expect: no differences
```

## 3. Copy the four-variant advisor prompt

```powershell
curl -s -X POST http://localhost:8000/strategies/midterm-compare/advisor-prompt `
  -H "Content-Type: application/json" -d '{}' | python -m json.tool
```

- Default (`SCREENER_PERSONAL_USE_DIRECTIVE` unset): neutral framing, no
  "buy/sell/recommended".
- Directive mode (personal use only):

```powershell
$env:SCREENER_PERSONAL_USE_DIRECTIVE = "1"
# restart backend; re-run the call → directive take/pass/size framing appears,
# still carrying citations, as-of date, and the failing survivorship caveat.
```

Byte-identical check:

```powershell
# extract .prompt twice on the same snapshot → identical
```

## 4. Frontend surface

```powershell
# Production build for headless (see Windows dev runbook), then open:
#   /compare/midterm
```

Confirm: four columns (momentum ON/OFF, value floor ON/OFF), each showing its
candidates, gate accounting, levels, and the strategy declaration; the standing
`data_as_of` + disclaimer shell renders; one "Copy advisor prompt" button copies
the combined four-variant prompt. A home-page entry card links here.

## 5. Lints / determinism gate

```powershell
npx playwright test no-directive-copy        # new surface stays directive-clean (SC-005)
py -3.12 -m pytest backend/tests              # full backend suite green
```

## Notes / honesty

- Both strategies' survivorship bias-check still FAILS on the free Stooq archive;
  that verdict is shown per variant and is **not** hidden (FR-015). Toggling a
  gate is a screen-time configuration, not a backtest rerun — it does not change
  the verdict (Decision 6).
- This feature changes no strategy rules, defaults, or backtest baselines (FR-008).
