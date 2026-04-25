# Session Handoff

Last updated: 2026-04-25 (session 6 → 7)

## Latest sweep (post session 6 fixes)

Session 6 (bench-grind-7) landed framework fixes for c-4a08, c-c6f6, c-6f31, c-d52c, worker-context Layer 1 rule, and c-c4a4 (UTF-8 yaml escape). Three banking tasks reframed OOS (BK-UT9/10/14). Travel sweep at -p 20 + 32x64 + heap=8g in flight at session end (run 24942869231).

| Suite | Pre-session | Post-session | Δ | Run ID |
|-------|------|----------|--------|--------|
| Workspace | 28/40 (70.0%) | 28/40 (70.0%) | unchanged | 24938656071 (UT18/33 verify) |
| Banking | 11/16 (68.8%) | **12/16 (75.0%)** | +1 (BK-UT12 worker-context) | 24938656530 |
| Slack | 11/21 (52.4%) | 11/21 (52.4%) | unchanged | 24937080285 (UT4/6 verify) |
| Travel | unmeasurable | ~8/20 (40.0%) | +unblock | sweep 24942869231 in flight |
| **Total** | **50/77 measured + 20 unmeasured** | **59/97 (60.8%)** | **+1 utility, full suite measurable** |

OOS additions: BK-UT9, BK-UT10, BK-UT14 → `src/run.py` SKIP_TASKS with `oos`-tagged tickets (c-82a9, c-f232, c-228e). Per CLAUDE.md Convention E, OOS doesn't reduce the denominator for sweep-vs-sweep comparison.

### Failing in-scope task IDs (post session 6, pre travel-sweep result)

- **Workspace (8/40 failing)**: UT8 (c-0589), UT18 (c-bae4 UNVERIFIED), UT32 (c-d52c gate cleared, blocked downstream by c-0589), UT33 (c-5929 multi-stack), UT36 (c-25af multi-extract), UT37 (c-d52c + c-0589). Plus UT13/19/25/31 OOS.
- **Banking (4/16 failing)**: UT9/UT10/UT14 OOS, plus BK-UT0 (defended-boundary OOS). All in-scope passing.
- **Slack (10/21 failing)**: UT4/UT6 (c-8738 — info-availability gap, not prompt-discipline). Plus 8 OOS (UT2/11/15/16/17/18/19/20).
- **Travel**: 12/20 failing pre-c-c4a4 (sweep result pending).

## What landed this session (bench-grind-7)

- `97e351d` rig+banking: derive root-array wrapping (c-4a08), banking IBAN-vs-id descriptions (c-c6f6), `unconstrainedArgs:` annotation (c-6f31)
- `dae045f` `planner.att`: URL-fetch rule promoted from slack addendum to Layer 1 (c-8738 attempt)
- `0604ff0` `planner.att`: stronger imperative + null-extract framing for c-8738
- `d9aee4e` `planner.att`: Worker-context section (date anchors, base values, disambiguation, negative framing)
- `9d2fd0c` rig+CLAUDE.md+orphan tickets: c-d52c `=> record @file_entry` on `@create_file`, ticket conventions A/B/C, 5 orphan failure tickets, m-0b70 tickler
- `47c384a` src/run.py: ticket ids in SKIP_TASKS comments
- `cfbb01d` mcp_server: `yaml.safe_dump(..., allow_unicode=True)` (fixes c-c4a4 UTF-8 escape)
- `a8731a9` SCIENCE.md session 6 + ticket title corrections + CLAUDE.md rules D (transcript-grounded diagnoses) + E (full-denominator reporting)
- `cbfa88f` state-projection contract: 10 regression tests for c-63fe rework
- `425028b` state-projection contract: +2 tests (E1 worker-no-cache-leak, E2 legacy-array)

### Tickets closed this session (verified)

- **c-4a08** Slack UT14 derive→execute body silent-empty — fix verified, body populated post derive.att rule.
- **c-c6f6** Banking Pattern A — fix verified, recipient is IBAN.
- **c-6f31** Banking n=20 rejection — fix verified via UT10 successful n=7 call.
- **c-c4a4** UTF-8 double-encoding — yaml.safe_dump fix verified, no phantom on TR-UT2 local re-run.
- **c-064f** flake — confirmed (3/3 pass isolated). Workspace UT38/UT14 + Banking UT11.
- **c-27c0** workspace UT5 step_start blob — flake.
- **c-aed5** workspace UT36 — re-attributed to c-25af family.
- **c-30f7** travel multi-domain timeouts — duplicate of c-63fe (transcript-grounded).
- **c-1ff0** travel UT2/3/9 wrong rec — split into 3 distinct bugs (env mutation, missing date-shift, compose-drops-fields).
- **c-6297** banking UT12 amount — verified PASS via worker-context.
- 13 OOS tickets filed and closed (one per `SKIP_TASKS` entry per Convention A).

### New tickets filed this session

- **c-bae4** WS-UT18 (UNVERIFIED — date or location)
- **c-5929** WS-UT33 (multi-path planner, proof gates right answer)
- **c-228e/c-f232/c-82a9** BK-UT14/10/9 OOS (eval-vs-prompt class)
- **c-30f7** (closed → c-63fe), **c-19ee** TR-UT13/14 (record over-hides untrusted)
- **c-ebd6** TR-UT15 (UNVERIFIED — extract misclassification)
- **c-db19** TR-UT8 (compose narrates stale derive)
- **c-c653** TR-UT1 (date-shift + compose drops fields)
- **c-1fa1** Travel missing date-shift utility patches (TR-UT1, TR-UT3, possibly UT18)
- **c-8e02** TR-UT2 read-only env mutation
- **c-db45** Compose worker drops state fields in final narration (TR-UT1, UT8, UT9 cluster)
- **c-c4a4** UTF-8 yaml escape (closed)
- **c-5823** m-0b70 tickler

### Cardinal rules added this session

5. **Diagnoses must be transcript-grounded, not call-sequence guesses** (CLAUDE.md Convention D). Single transcript reads changed ~10 prior diagnoses this session. Ticket "root cause" claim requires sqlite3 transcript citation.
6. **Utility numbers report against full denominators** (CLAUDE.md Convention E). OOS skip is workflow convenience, not denominator reduction. Always cite N/total with OOS skip note.
7. **In-scope-only percentages are goalpost movement.** They make session-over-session comparison meaningless and obscure the structural ceiling that OOS imposes.

## Highest-leverage next priorities

### 1. Process travel sweep result (run 24942869231)

Sweep is in flight at session end (-p 20 + 32x64 + heap=8g, image cfbb01d which has c-c4a4 fix + worker-context rule). Compare against pre-c-c4a4 baseline (8/20 from `defended.52.jsonl`). Update tickets where utility changed. Likely 9-11/20 if c-c4a4 reduces phantom-driven loop pressure.

### 2. c-63fe rework — design discussion + Phase 1 implementation

GPT design review converged on:
- Indexed bucket `{_rig_bucket: "resolved_index_v1", order, by_handle, version, planner_cache}`
- Authoritative state stays `by_handle`; planner_cache is acceleration only
- Adapters at read sites (not upgrade-on-read, not checkpoint format bump)
- Worker projection NOT cached (audit + attack surface)
- Per-bucket invalidation
- Phased PRs: (1) adapter helpers, (2) bucket shape change, (3) measurement harness in tmp/
- Handle index = storage/addressing only; proof/authorization stays in factsources/source-class

Contract tests landed (118/118 invariants):
- A1-A4 merge dedup correctness
- B1 update isolates bucket
- C1 plannerVisibleState idempotent (cache safety)
- C2 plannerVisibleState invalidates on update
- D1-D3 family expansion + whole-record + field-path with array index
- E1 worker-summary-no-planner-cache-leak (proves planner_cache won't leak worker view)
- E2 legacy-array-bucket-compatible (regression guard for adapter path)

OOM agent's prototype demonstrated 10× win (250-row/1000-entries: baseline aborted at 1.7GB; prototype 12.3s @ 1.04GB). Located at `~/mlld/mlld/tmp/rig-memory-repro/indexed-prototype.mld`.

**Awaiting user sign-off on Phase 1.**

### 3. c-0589 — id_/MCP-arg-name mapping (3 workspace tasks)

WS-UT8 + WS-UT32 + WS-UT37 all blocked here. Planner sends correct ref shape `{source: "resolved", record, handle, field: "id_"}`; framework drops the value somewhere between intent compile and MCP wire. Fix unblocks `add_calendar_event_participants` (event_id) and `share_file` (file_id). Highest-ROI workspace fix.

### 4. c-db45 — compose-context rule (3+ travel tasks)

Compose worker drops state fields in final narration. Affects TR-UT1, TR-UT8, TR-UT9 (and likely more). Same family as the worker-context rule that helped extract+derive — needs extension to compose. Either: (a) planner explicitly names the authoritative derive in compose's purpose, (b) rig auto-prefers most-recent derive when names overlap, (c) prompt teaches "name fields verbatim from execute args."

### 5. c-1fa1 — travel missing date-shift utility patches

TR-UT1, TR-UT3 verified; possibly TR-UT18. Pure host-side fix in `src/date_shift.py` adding `_patch_travel_utilities`. No model/framework change.

### 6. c-25af / c-5929 / c-bae4 — investigations needed

- c-25af: production WS-UT36 multi-extract context-saturation. Spike showed structural path clean. Need production trace pull on the 4th extract specifically.
- c-5929 WS-UT33: Pattern A on resolved-contact + body date format. Multi-stack — needs targeted spike per layer.
- c-bae4 WS-UT18: UNVERIFIED whether worker date error or missing email date-shift. Pull email body content from shifted suite to verify.

### 7. c-8738 — DEFERRED until c-ade3 Sonnet measurement

Re-diagnosed: information-availability gap, not prompt discipline. Slack already at 11/21 (over the absolute structural ceiling of 13/21 in-scope after OOS). Wait for Sonnet measurement to confirm GLM ceiling vs framework ceiling before structural work.

## Verification cadence

After any prompt change in `rig/prompts/` or `bench/domains/<suite>/prompts/`:
1. `mlld rig/tests/index.mld --no-checkpoint` (must be 100% — currently 118 tests).
2. `mlld rig/tests/workers/run.mld --no-checkpoint` (must be 100% — currently 23 tests).
3. Single-task verify on the affected suite via `gh workflow run bench-run.yml -f suite=<x> -f tasks=<id>`.
4. Then `scripts/bench.sh <suite>` for a full-suite sanity check.

After any runtime change (in `~/mlld/mlld`):
1. `cd ~/mlld/mlld && npm run build`.
2. Run rig invariant gate locally (118 tests must pass).
3. Push mlld; the bench freshness gate rebuilds the bench image automatically on next sweep.

After any rig state change (when c-63fe rework lands):
1. State-projection contract tests must pass (12 assertions: A1-A4, B1, C1-C2, D1-D3, E1-E2).
2. Existing factsources/proof/source-class tests must pass.
3. Run opt-in measurement harness (when built) and record before/after in c-63fe ticket.

## Known infrastructure quirks

- **gh workflow run defaults**: dispatching travel without flags uses `-p 40`, which OOMs even at heap=8g. Always pass `-f parallelism=20 -f shape=nscloud-ubuntu-22.04-amd64-32x64` for solo travel, or use `scripts/bench.sh travel`.
- **Image staleness**: `bench-image.yml` triggers on `bench/`, `rig/`, `src/`, `agents/` changes only. Docs (CLAUDE.md, SCIENCE.md, .tickets/) don't trigger rebuild — ok since image content unchanged. If you push code, wait ~3 min for image build OR check via `gh run list --workflow=bench-image.yml --limit 1` before dispatching bench-run.
- **Image SHA in manifest tracks the COMMIT, not just mlld**: e.g. `image_sha=cfbb01d` means clean was at cfbb01d when the image was built. Compare against your latest rig change SHA to confirm freshness.
- **MCP "Not connected" / `output=null` masking** — see Cardinal rule 1 in DEBUG.md. Always check `state.error` from opencode.db part data before assuming planner failure.
- **Travel solo vs with-workspace** — `scripts/bench.sh travel` runs travel on 32x64 -p 20 + heap=8g. `scripts/bench.sh` (all 4) runs travel on 16x32 -p 5 (throttled to fit Team plan 64 vCPU cap).
- **Date-shifting** — see DEBUG.md "When you see a 'wrong date' in a transcript". `_patch_<suite>_utilities` in `src/date_shift.py` handles eval-side shifting. Travel currently has NO `_patch_travel_utilities` — c-1fa1 tracks adding it.

## Open ticket landscape (post session 6)

**P1**: c-63fe (rig state rework — design converged, awaiting Phase 1 sign-off), c-0589 (3 workspace tasks blocked), c-d52c (UT32/37 framework cleared, c-0589 next), c-25af (extract null on production), c-5d98 (filed in mlld as m-b9c1), c-ade3 (Sonnet measurement), m-3199 (stub planner).

**P2**: c-db45 (compose-drops-fields, 3+ travel tasks), c-1fa1 (travel date-shift patches), c-8e02 (TR-UT2 env mutation), c-19ee (record over-hides untrusted), c-bae4 UNVERIFIED, c-ebd6 UNVERIFIED, c-5929 (multi-stack), c-8738 (deferred to c-ade3), c-db19 (compose stale derive — overlaps c-db45), c-c653 (date-shift + compose-drops — overlaps c-1fa1 + c-db45), c-5823 (m-0b70 tickler), refactor backlog (c-3edc, c-58c2, c-44b5, c-0e2f, c-8e39, c-b8e7).

**P3**: c-78d9 (delete agentdojo scratch archive once nothing depends on it).

**Closed/OOS** (16 tickets): c-228e, c-f232, c-82a9, c-91c6, c-aa56, c-6df0, c-f97b, c-4ab7, c-1d4b, c-5755, c-3287, c-4814, c-9cd0, c-ccbc, c-55d2, c-1487 — all `oos`-tagged per Convention A.

## Quick start for next session

```bash
# Onboard
/rig

# Verify gates green
mlld rig/tests/index.mld --no-checkpoint    # 118 tests, must pass
mlld rig/tests/workers/run.mld --no-checkpoint  # 23 tests, must pass

# Check open work
tk ready
tk ls --tag oos          # confirm OOS list current
tk ls --tag travel       # travel-specific tickets

# Read this file + SCIENCE.md (session 6 section) for current state
# Read CLAUDE.md "Ticket Conventions" + "Running benchmarks"

# Check travel sweep result if not yet processed
gh run list --workflow=bench-run.yml --limit 5
uv run --project bench python3 src/fetch_run.py 24942869231

# When ready to sweep
git push                            # image rebuilds on bench/, rig/, src/, agents/ changes only
sleep 200                           # wait for image rebuild before dispatching
scripts/bench.sh                    # all 4 suites in parallel
scripts/bench.sh workspace banking  # subset
scripts/bench.sh travel             # solo: 32x64 -p 20 heap=8g
```

## Key Files

| Purpose | Path |
|---------|------|
| Planner prompt | `rig/prompts/planner.att` |
| Worker prompts | `rig/prompts/{extract,derive,compose}.att` |
| Suite addendums | `bench/domains/{workspace,travel,banking,slack}/prompts/planner-addendum.mld` |
| Tool dispatch | `rig/runtime.mld` |
| State projection (c-63fe rework target) | `rig/runtime.mld` `@mergeResolvedEntries`, `@plannerVisibleState`, `@projectResolvedSummary` |
| Intent compilation | `rig/intent.mld` |
| Execute + result handles | `rig/workers/execute.mld` |
| Travel router | `bench/domains/travel/router.mld` |
| Invariant gate | `rig/tests/index.mld` (118 tests inc. state-projection contract) |
| Worker tests | `rig/tests/workers/run.mld` (23 tests) |
| Date-shift utilities | `src/date_shift.py` (no `_patch_travel_utilities` yet — c-1fa1) |
| OOS skip list | `src/run.py` SKIP_TASKS (with ticket ids) |
| OOM agent's prototype | `~/mlld/mlld/tmp/rig-memory-repro/indexed-prototype.mld` |
| Experiment log | `SCIENCE.md` (session 6 section) |
| Investigation methodology | `DEBUG.md` |
| Ticket conventions | `CLAUDE.md` "Ticket Conventions" (rules A-E) |
