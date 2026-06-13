# Spec Coverage Matrix - 001 Screener MVP

Updated: 2026-06-11

This file maps every functional requirement and success criterion in `spec.md` to implementation tasks and verification tasks. Caveat: broad non-Shariah screening now uses the local Stooq archive when present and a disk-warmed computed snapshot, but survivor-bias-free backtests still require a delisted-inclusive source.

## Functional Requirements

| Requirement | Implementation coverage | Verification coverage |
| --- | --- | --- |
| FR-001 | T031, T047, T050-T053, T118-T123 | T048, T060, T109, T110, T113 |
| FR-002 | T061-T064, T067 | T062, T064, T068, T109, T113 |
| FR-003 | T031, T047, T054, T058 | T048, T060, T068, T109 |
| FR-004 | T029, T047, T050, T055, T058 | T060, T068, T114 |
| FR-005 | T009, T035, T037, T043, T123 | T043, T060, T068, T091, T108, T114 |
| FR-006 | T035, T038, T043 | T043, T060, T068, T091, T101, T108 |
| FR-007 | T041, T042 | T042 plus Playwright full-suite validation |
| FR-008 | T096, T097 | T101 |
| FR-009 | T092, T096, T097 | T101 |
| FR-010 | T092, T097 | T101 |
| FR-011 | T075, T093, T096, T097 | T095, T101 |
| FR-012 | T093, T094, T098 | T095, T101, T109 |
| FR-013 | T093, T094, T098 | T095, T101 |
| FR-014 | T040, T054, T058, T096, T099 | T060, T101 |
| FR-015 | T102-T104, T106-T107 | T105, T108, T110 |
| FR-016 | T029, T102, T104, T106-T107 | T105, T108 |
| FR-017 | T047, T061, T063, T065-T066 | T112, T114 |
| FR-018 | T031, T093, T102-T105, T113 | T105, T113 |
| FR-019 | T096, T099 | T101 |
| FR-020 | T096, T100 | T101 |
| FR-021 | T070-T071, T075-T077 | T073, T078 |
| FR-022 | T069-T072, T124-T127 | T073, T078, T109 |
| FR-023 | T070-T077 | T073, T078 |
| FR-024 | T070, T074, T077, T097 | T078, T101 |
| FR-025 | T070-T071, T074, T077, T123 | T073, T078 |
| FR-026 | T071, T077 | T078 |
| FR-027 | T080, T082-T087 | T091 |
| FR-028 | T079, T082, T085-T087 | T091 |
| FR-029 | T080, T083, T090 | T091 |
| FR-030 | T081, T082, T084, T088-T089 | T091, T110 |
| FR-031 | T081, T082, T088 | T091 |
| FR-032 | T082, T088, T123 | T091, T110 |
| FR-033 | T079-T085 | T091, T109 |
| FR-034 | T016, T075, T118-T123 | T111 |
| FR-035 | T049, T065-T066, T052, T056 | T112, T114 |
| FR-036 | T049, T052, T056 | T109, T114 |
| FR-037 | T029, T047, T055 | T060, T068, T114 |
| FR-038 | T070, T075-T076 | T073, T078 |
| FR-039 | T070, T075-T076 | T073, T078 |
| FR-040 | T070-T071 | T073, T078 |
| FR-041 | T075-T076, T099 | T078, T101 |

## Success Criteria

| Criterion | Verification task/test |
| --- | --- |
| SC-001 | T060; T110 covers returning-run budget |
| SC-002 | T110. Current proof is broad local Stooq + disk-warmed computed snapshot, not live yfinance over every listed name. |
| SC-003 | T112, T114. Strategy metadata/backtest windows are audited; survivorship caveat remains visible in backtest bias checks. |
| SC-004 | T060, T068, T098, T101 |
| SC-005 | T043, T060, T068, T078, T091, T101, T108, T114 |
| SC-006 | T101 |
| SC-007 | T095, T101 |
| SC-008 | T105, T113 |
| SC-009 | T114 |
| SC-010 | T042 plus full Playwright suite |
| SC-011 | T071, T073, T078 |
| SC-012 | T074, T077, T078, T101 |
| SC-012a | T078 |
| SC-012b | T078 |
| SC-013 | T086, T087, T091 |
| SC-014 | T083, T090, T091 |
| SC-015 | T091, T110 |
| SC-016 | T111 |
| SC-017 | T112, T114 |
| SC-018 | T114 |

## Open Caveats

- Survivor-bias-free backtests are not fully closed until T049b or a delisted-inclusive data provider is added. The app surfaces the survivorship caveat through the bias-check artifacts instead of hiding it.
- Phase 10 reduces yfinance dependence materially, but yfinance remains a fallback for missing explicit ticker price/profile data and for name/sector fields when no local EDGAR profile is available.
