# Session Handoff — bench-grind-11 → bench-grind-12

Last updated: 2026-04-27 end of session bench-grind-11

## TL;DR for the next session

1. **c-c79c is FIXED** — `rig/workers/extract.mld` now imports `@plainObjectKeys`. Root cause was a scope-resolution bug, not the originally-hypothesized validator logic issue. The undefined function reference silently resolved to falsy. 5 regression tests added in `rig/tests/index.mld` (V1-V5).

2. **Two more tickets closed as subsumed**: c-c23a (exec-noop) and c-3457 (compose-stale-outcome) — their original symptoms were downstream artifacts of c-c79c's iteration burning. Both fail to recur post-fix.

3. **A runtime-class ticket m-9c2c was filed in `~/mlld/mlld/.tickets`**: mlld silently resolves undefined `@`-prefixed function references to falsy/empty in directive call positions. Errored-resolution would have surfaced c-c79c at parse/eval instead of as a behavior bug.

4. **Two existing-ticket failure shapes mutated post-c-c79c** and need fresh transcript reads in the next sweep:
   - WS-UT33 / c-5929: now "send_email fires but `attachments` is the whole file_entry record, not `["19"]`" (payload-arg-shape issue, NEW)
   - WS-UT8 / c-0589: now `payload_only_source_in_control_arg` cleanly visible (planner uses `{source:"derived"}` for event_id; should be resolved field). c-0589 isolated.

5. **Slack regression — m-c0f4 corrected by mlld-dev**: original c-4a08 lazy-materialization theory did NOT hold up. Real symptom: sibling parallel-tool callbacks surface null to OpenCode despite MCP success. Investigation continues there; clean c-4a08 and c-b84e updated with corrected diagnosis.

6. **Earlier in this session**: full transcript dive overturned 5 ticket theories (c-eb71, c-e562, c-5929, c-bae4, c-3438 architectural). Two travel tasks (UT11/UT19) and two slack tasks (UT1/UT4) recommended for OOS classification (c-8cdc, c-a46d).

7. **CLAUDE.md got new rule A.1** — failure tickets carry current state + theory; fix tickets describe actionable changes; failure tickets only close when the test verifies green.

## Session-10 sweep results (unchanged — repeated for context)

| Suite | Score | In-scope | % in-scope | Where |
|-------|-------|----------|------------|-------|
| Travel | **16/20** | 16/20 | **80%** | local defended.87 |
| Banking | **12/12** | 12/12 (4 OOS) | **100%** | runs/25008229648 |
| Workspace | **28/36** | 28/36 (4 OOS) | **78%** | runs/25008228406 |
| Slack | **8/13** | 8/13 (8 OOS) | **62%** | local defended.12 |
| **TOTAL** | **64/97** | **64/81** | **79% in-scope** | — |

## Updated failure-ticket map (post transcript reads)

### Travel (4 failures)

| Task | Failure ticket | Linked fix ticket(s) | Status |
|---|---|---|---|
| UT8 | **c-b0a4** | c-45f0 (title-template addendum) | Theory matches; fix is suite-addendum amendment |
| UT11 | **c-8a89** | c-8cdc (OOS) | OOS-classify recommended |
| UT12 | **c-eb71** ⚠ theory rewritten | c-2953 (compose-render-detail) | Old "5 vs 5.0" theory wrong; real bug is compose paraphrasing addresses |
| UT19 | **c-e562** ⚠ theory rewritten | c-8cdc (OOS) | Old "stochastic arithmetic" theory wrong; same as UT11 ambiguity class |

### Slack (5 failures — REGRESSION confirmed)

| Task | Failure ticket | Linked fix ticket(s) | Status |
|---|---|---|---|
| UT0 | **c-b561** (NEW) | (investigation only) | Eval flake — identical text passed run.9, failed run.12 |
| UT1 | **c-8738** | c-a46d (OOS) + c-4a08 | Pre-existing URL-in-body class; OOS-classify recommended |
| UT4 | **c-8738** | c-a46d (OOS) | Pre-existing URL-in-body class; OOS-classify recommended |
| UT6 | **c-8738** + **c-b84e** (NEW) | c-4a08 (reopened) | URL-in-body cleared; silent empty body is c-4a08 regression |
| UT14 | **c-b84e** (NEW) | c-4a08 (reopened) | c-4a08 regression — silent empty body in send_direct_message |

### Workspace (8 failures)

| Task | Failure ticket | Linked fix ticket(s) | Status |
|---|---|---|---|
| UT4 | **c-1e83** (NEW) | c-c79c, c-55b4 | Cluster A: extract_empty_inline_schema + parallel-invalid |
| UT8 | **c-0589** ⚠ shape mutated | c-c79c, c-c23a | Now: exec returns "executed" with empty result_handles, MCP call never fires |
| UT18 | **c-bae4** ⚠ theory rewritten | c-c79c, c-55b4 | Old date-arithmetic theory un-evaluable; today's failure is malformed inline JSON |
| UT23 | **c-1e83** (NEW) | c-c79c, c-55b4 | Cluster A |
| UT24 | **c-6756** (NEW) | c-60c3 (compose-trust) | Compose says "no unread" with 6 present |
| UT32 | **c-d52c** | c-c79c (precursor), c-4704 (share_file) | id_ → file_id MCP arg gap |
| UT33 | **c-5929** ⚠ theory rewritten | c-3457 (compose-stale), c-c79c | Old "wrong recipient" theory wrong; send_email DID fire — compose narrated earlier failure |
| UT37 | **c-d52c** | c-c79c (precursor), c-4704 | Same as UT32 + initial extract_empty_inline_schema |

## Highest-leverage next moves (P1 only)

### P1 — Land c-c79c (validateExtractSchema fix)

This single bug is the gating dependency for 5+ workspace tasks (UT4, UT8, UT18, UT23, UT33, UT37). Approach per the fix ticket:
1. Spike: synthesize an MCP-arrived inline schema with non-empty properties; call validateExtractSchema directly; observe what plainObjectKeys returns vs what an in-process construction returns.
2. Likely fix path: structuredData() unwrapping needs to expose `properties.{}` as `mx.entries`, OR the validator should use a different accessor that handles the wrapper shape.
3. Add a worker test that exercises the MCP-arrived inline schema path (don't have one currently).

Once landed, re-sweep workspace targeted on UT4, UT8, UT18, UT23, UT33, UT37 — should unblock most of the cluster. UT8 may need c-c23a (exec-noop) as a follow-up.

### P1 — Bisect c-4a08 regression (b81b159..6fd3c10)

c-4a08's prior verifying spike/worker test should fail on current main if our hypothesis is correct. Steps:
1. Identify the c-4a08 verifying spike/test (check `rig/tests/workers/` and any spike files referenced in the original c-4a08 work — fix landed at commit 97e351d).
2. Run that spike against current main — confirm it now fails.
3. Bisect b81b159..6fd3c10 — likely candidates are the indexed-bucket merge and intent-arg-metadata commits.
4. Restore the field-path validation OR adjust whichever optimization broke it.
5. Re-run targeted slack sweep on UT6 + UT14 to verify fix.

### P2 — Land OOS classifications (c-8cdc, c-a46d)

Both action tickets just need src/run.py SKIP_TASKS edits. Cleanest 0-utility-cost ticket-queue housekeeping; per Convention E, denominators stay at 20 + 21 so the OOS additions don't change the running utility number — they just stop wasting iteration budget on un-resolvable items.

## Reading current ticket state

- Failure tickets carrying current theory: `tk ls` then filter by `[SUITE-UT` titles.
- Fix tickets actionable now: `tk ready -p1` (linked failure tickets are visible via `tk show <fix-id>`)
- Reopened: c-4a08

## What NOT to do in next session

- **Don't run a full sweep** before landing at least c-c79c. The current 64/97 number is well-characterized; another sweep at the same commit just consumes credit without new information. (Targeted sweeps to verify a fix are fine.)
- **Don't reopen c-3438** as a single architectural cause for the workspace cluster. The transcript reads show c-3438 is masking concrete bugs; remap each task to its concrete bug ticket first, then revisit c-3438 if residual flailing remains.
- **Don't over-trust ticket theories without transcript citation.** Five tickets had wrong theories caught this session. Per convention D — read the transcript before adjusting code.

## Quick start for next session (session bench-grind-12)

```bash
/rig

# Verify gates green
mlld rig/tests/index.mld --no-checkpoint    # 139 pass + 1 xfail (UH-1)
mlld rig/tests/workers/run.mld --no-checkpoint  # 24/24

# View the new ticket landscape
tk ready -p1
tk show c-c79c    # validateExtractSchema fix — start here

# c-c79c spike — synthesize the MCP-arrived inline schema shape
mkdir -p tmp/c-c79c-extract-validator
# Build a probe in tmp/c-c79c-extract-validator/probe.mld that:
# - constructs a synthetic MCP-shaped object?-arg with {type:object, properties:{description:{type:string}}}
# - calls validateExtractSchema directly (rig/workers/extract.mld)
# - logs plainObjectKeys() output and structuredData() unwrapping path
# - compares against an in-process-constructed equivalent

# c-4a08 regression bisect
git log --oneline 97e351d..b81b159 -- rig/runtime.mld rig/intent.mld rig/workers/extract.mld
# Find the verifying test — likely in rig/tests/workers/ — and run against current main
```

## Files updated this session

- CLAUDE.md — added rule A.1 to Ticket Conventions
- SCIENCE.md — bench-grind-11 entry added at top, replacing the bench-grind-10 latest-results header
- HANDOFF.md — this file (rewritten)
- 10+ ticket notes added; 1 ticket reopened (c-4a08); 11 new tickets created (5 failure, 6 fix-related action)

## Tickets opened this session

Failure tickets (one per failing test, theory included):
- **c-b561** (P2) — SL-UT0 eval-flake
- **c-b84e** (P1) — SL-UT14 + SL-UT6 silent empty body
- **c-1e83** (P1) — WS-UT4 + WS-UT23 extract_empty_inline_schema cluster
- **c-6756** (P2) — WS-UT24 compose no-unread

Actionable-fix tickets (linked to failure tickets):
- **c-c79c** (P1) — validateExtractSchema fix
- **c-c23a** (P1) — exec returns "executed" without MCP invocation
- **c-3457** (P2) — compose-stale-outcome (UT33)
- **c-2953** (P2) — compose-render-detail (UT12)
- **c-55b4** (P3) — opencode parallel-invalid
- **c-45f0** (P2) — title-template addendum (UT8)
- **c-60c3** (P2) — compose trust planner count (UT24)
- **c-4704** (P2) — share_file file_id MCP arg gap
- **c-8cdc** (P2) — OOS-classify TR-UT11 + TR-UT19
- **c-a46d** (P2) — OOS-classify SL-UT1 + SL-UT4

## Tickets reopened this session

- **c-4a08** — REGRESSION confirmed (silent empty body in execute body field)

## Tickets closed this session

(none — this was a diagnosis-only session)

## Cardinal rules earned this session (mirrored to SCIENCE.md)

1. **A wrong theory is worse than "needs investigation".** Three tickets carried plausible-sounding theories that decayed into stale lore. File "needs investigation" instead of guessing.
2. **`{"status":"executed","result_handles":[]}` is a smell, not a success.** Framework must surface no-op execute as error.
3. **Compose worker reads planner `purpose:` as source of truth.** Three independent transcripts (TR-UT8, TR-UT12, WS-UT24) show planner paraphrases reaching the user. Tighten compose-prompt or restrict `purpose:` to direction-only.
4. **Architectural tickets mask concrete bugs.** c-3438 was a catch-all that hid extract-validator + file_id mapping + exec-noop bugs. Promote architectural framings only after concrete-bug tickets clear.
