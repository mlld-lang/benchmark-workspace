# Utility baseline (pre-cutover)

Snapshot from `STATUS.md` headline table (last full sweep 2026-05-04, archived in `archive/SCIENCE.md`). Post-cutover sweeps at each phase boundary must hit at least these numbers (allowing ±2 stochastic noise per the migration plan).

## Per-suite (97 tasks total)

| Suite | Tasks | Pre-cutover PASS | Run id |
|---|---|---|---|
| workspace | 40 | 36 | 25324557648 |
| banking | 16 | 11 | 25324559458 |
| slack | 21 | 13 | 25324561113 |
| travel | 20 | 18 | 25324563037 |
| **total** | **97** | **78** | — |

The 2026-05-06 batched sweep (workspace-a/b split, run ids `25417255652` `25417483572` `25417256831` `25417833945` `25417986076`) hit 73/97 — the deterministic PASS floor (no OPEN-bucket luck). The 73 vs 78 gap is the difference between "PASS-classified count" (deterministic floor) and "PASS + occasional OPEN-item lucky pass" (what observed sweeps can hit). Use 73 as the strict floor and 78 as the central expectation; ±2 stochastic noise applies to the central expectation.

## Phase boundaries

- **Post-Phase-1 cutover sweep**: re-run all 4 suites, expect ≥ 73/97 (deterministic floor) with central expectation 78/97 ±2.
- **Post-Phase-2 verification**: same threshold; the bucket→shelf collapse must not regress utility.
- **Phase 3 closeout sweep**: same threshold; planner-prompt revision must not regress utility beyond ±2.

If a phase boundary sweep regresses below the deterministic floor (73/97), the regression is structural — bisect the phase commit before continuing. If it lands within ±2 of 78 but below 78 itself, the regression is within stochastic noise; rerun once before treating as a real signal.

## Source

`STATUS.md` line 23-27 (Headline table, last full sweep 2026-05-04). Renew when STATUS.md's headline updates.
