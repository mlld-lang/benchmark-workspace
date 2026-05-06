# Session Handoff

Last updated: 2026-05-06 (end of bench-grind-20)

## Next session goal: continue security test buildout

Bench utility is structurally near its ceiling (~78/97 = 80.4% per STATUS.md classification). The work surface that delivers the most value now is **the security test buildout** — attack-side regressions that exercise the defenses we built but haven't yet locked behind tests.

This session (bench-grind-20) landed B7 + B8 regression tests AND a mutation-coverage harness that proves each security test actually catches its claimed defense. Read the [Mutation Coverage](#mutation-coverage-status) section below before starting new security tests — every new test should land with a registry entry.

### Current security test inventory (41 scripted + 18+2 zero-LLM/live-LLM)

| File | Tests | Coverage |
|---|---|---|
| `tests/scripted/security-travel.mld` | 10 | source-class firewall, kind-tag wrong-record-fact firewall, recommendation-hijack deterministic part |
| `tests/scripted/security-slack.mld` | 11 | source-class firewall, real-handle backing rejection, URL-promotion path |
| `tests/scripted/security-banking.mld` | 8 | source-class firewall, kind-tag firewall on payment writes |
| `tests/scripted/security-workspace.mld` | **12** (was 6, +B7×3 +B8×3 in bench-grind-20) | source-class firewall on calendar/email writes; B7 extraction-fallback poisoning; B8 'true' authorization bypass |
| `tests/suites/rig/advice-gate.mld` | 9 | advice-gate config propagation, role:advice projection, dispatch routing |
| `tests/suites/rig/classify.mld` | 9 | classifier fan-out primitive |
| `tests/suites/bench/travel-classifier-{labels,exemplars}.mld` | 20 | classifier label/exemplar shape + vocabulary |
| `bench/tests/travel-advice-gate-live.mld` | 2 | live-LLM end-to-end advice-gate (deterministic poisoned + clean state) |
| `bench/tests/travel-classifiers.mld` | live | classifier accuracy on synthetic + held-out AgentDojo labels |

### Mutation coverage status

`tests/run-mutation-coverage.py` is a meta-test that proves each security test actually catches its claimed defense. For each registered defense, the harness disables it via a one-line mutation, re-runs the affected suites, and confirms the right tests fail. Files restored via `try/finally`. See `TESTS.md` "Mutation coverage for security tests".

```bash
uv run --project bench python3 tests/run-mutation-coverage.py
```

| State | Count |
|---|---|
| Mutation-verified (in some `expected_fails`) | 30 of 41 |
| Positive controls (assert ok=true, untouched by negative mutations) | 3 |
| Unverified, needing registry extension (c-5aca) | 8 |

c-5aca tracks extending the registry. Of the 8 unverified, 5 are caught only by mlld runtime `policy.build` kind-tag firewall (need a runtime-side mutation), 2 need a 3-way combined mutation (source-class + known-task-text + policy-build), 1 is a malformed-shape rejection that needs its own mutation point.

**Discipline going forward**: every new security test ships with a mutation entry. A test added without an entry is unverified by definition.

Run scripted suites via:
```bash
uv run --project bench python3 tests/run-scripted.py --suite slack    --index tests/scripted-index-slack.mld
uv run --project bench python3 tests/run-scripted.py --suite banking  --index tests/scripted-index-banking.mld
uv run --project bench python3 tests/run-scripted.py --suite workspace --index tests/scripted-index-workspace.mld
uv run --project bench python3 tests/run-scripted.py --suite travel   --index tests/scripted-index-travel.mld
```

Expected: slack 11/0/0, banking 8/0/0, workspace 6/0/0, travel 10/0/0. Run before and after each new test lands.

### Priority-ordered work plan

The path of least resistance — independent test-writing first, architectural test classes last:

| Order | Ticket | What | Effort |
|---|---|---|---|
| ✓ | ~~c-83f3~~ | ~~B7 workspace extraction-fallback poisoning~~ — landed bench-grind-20 (3 tests, mutation-verified) | done |
| ✓ | ~~c-ae22~~ | ~~B8 workspace 'true' authorization bypass~~ — landed bench-grind-20 (3 tests, mutation-verified) | done |
| 1 | **c-5aca** | Extend mutation registry to cover the remaining 8 unverified scripted tests (3-way combined + runtime kind-firewall mutation) | 1-2 hours |
| 2 | **c-d374** | B10 get_webpage exfil:send classification + no-novel-urls. Two related defenses to test | 2-3 hours |
| 3 | **c-a720** | B5 slack recursive URL fetch (UT1 × IT3). c-c2e7 closed via state-factory pattern; use `@runWithState` like `testSelectionRefRealSlackMsgHandleRejected` | 2-3 hours |
| 4 | **c-fb58** | B6 slack instruction-channel-label not promoted (UT18 × IT3). Same harness pattern as #3 | 2-3 hours |
| 5 | **c-800d** | Correlate cross-record-mixing firewall (banking). `update_scheduled_transaction_inputs` declares `correlate: true` — test the cross-record mixture rejection | 2-3 hours |
| 6 | **c-7016** | B9 travel recommendation-hijack zero-LLM tests. **Live-LLM defense already verified 0/4 ASR on IT6.** This adds zero-LLM regression cushion: label propagation test + advice-gate denial test | 2-3 hours |
| 7 | **c-891b** | Taint-based defenses (no-untrusted-privileged, label propagation). Bigger — audit which write tools across all 4 suites get which risk classifications, build a coverage table, write tests | 1-2 days |
| 8 | **c-634c** | Typed-instruction-channel class tests (WS-UT13/UT19/SL-UT18/UT19/UT20). Different defense surface than source-class firewall. Depends on c-6479 design | 1-2 days |
| - | **c-bc1f** | Stale `@stateWithResolved` test fixture — emits non-canonical bucket shape that production `@lookupResolvedEntry` can't read. Uncovered while writing B7 tests; worked around with inline canonical seed. Audit other callers when convenient | 1-2 hours |

### Where to start (concrete first move)

1. Run `uv run --project bench python3 tests/run-mutation-coverage.py` — should report Overall: OK with 7 mutations across 4 suites. Re-baselines that nothing regressed.
2. Tackle **c-5aca**: extend the mutation registry to the remaining 8 unverified tests. Pattern is documented in `tests/run-mutation-coverage.py` MUTATIONS array — add an `edits` list for combined mutations, find the rejection point in `rig/intent.mld` or `rig/workers/`, list the test ids whose docstrings claim that defense.
3. Then **c-d374** (B10 get_webpage). Read `~/mlld/benchmarks/archive/SCIENCELOG-v2.md` lines 440-460 for the historic B5–B10 breach analyses.

### Cross-cutting verification

- **c-1bd4** — Full attack matrix spot-check + verification post-perf-fix. **Updated cost estimate: ~3,774 task-runs total (629 UT-IT pairs × 6 stock attacks); ~20 hours wall at current rate-limit budget.** Defer until the test buildout is complete; the tests catch regressions cheaply, the matrix is the headline measurement.
- **c-0eb5** — Per-task triage walk after sweeps. Lower priority than test buildout.

---

## Bench / utility state (background context)

Headline last sweep (2026-05-04): **78/97 = 80.4% utility, 0 verified breaches** (IT6 only canary; full matrix still pending).

CaMeL Claude 4 Sonnet baseline: 72/97 across the same suites.

STATUS.md is the canonical per-task classification. PASS / FLAKY / SHOULD-FAIL / BAD-EVAL / OPEN. **Only the user marks tasks FLAKY or BAD-EVAL.**

### Bench infrastructure landed in bench-grind-19

| Concern | What landed |
|---|---|
| Rate-limit pressure | `scripts/bench.sh` now defaults to 2-at-a-time batching across 5 sub-suites (workspace-a/b, banking, slack, travel). `--all-parallel` opts into legacy 4-way fan-out |
| Stagger | `--stagger 10s` default at top-level; classifier fan-out has `parallel(N, 5s)` stagger |
| Workspace splitting | Two halves of 20 tasks each (UT0–19 / UT20–39), addressable as `workspace-a` / `workspace-b` |
| Self-heal | `bench-run.yml` freshness check now refreshes `mlld-prebuilt:<ref>` first if stale, then bench-image; verifies both `clean.sha` and `mlld.sha` post-rebuild |
| Inner-worker artifact | Cloud bench now archives `/tmp/mlld-rig-inner-worker-data/opencode/` as `inner-worker-transcripts.tgz`. Visible after fetch_run.py auto-extracts to `runs/<id>/opencode-inner/` |
| Hybrid model dispatch | Confirmed working in cloud: planner=GLM-5.1 (Together AI), workers=gpt-oss-120b (Cerebras). Workers are 18% of LLM volume; planner is 82% |

### What the rate-limit investigation surfaced (do not re-discover)

- Together AI Tier 4 publishes 4500 RPM aggregate, but **GLM-5.1 per-model serving capacity** caps us at ~95 RPM combined across 4 simultaneous suites
- 4-parallel sweeps generate 5k+ HTTP 429s; tasks hit 900s wall ceiling and produce `outcome: unparseable`
- 2-at-a-time batching keeps 429s in the 15-300/suite range and tasks complete cleanly
- Multiple Together AI **API keys won't help** — limits are per-org, not per-key
- Multiple Together AI **orgs** *might* help if the bottleneck is org-level (data suggests it isn't — per-model capacity is shared globally)
- **opencode-prebuilt:dev** rebuilt 2026-05-05 18:54 PT; the user noted this version is "the patched version" (fixed an MCP-connection-drop bug, which means more calls actually go through — exposing the rate-limit ceiling that was previously masked by silent drops)
- **Cerebras gpt-oss-120b can't plan** (4/16 banking when used as planner); GLM-5.1 outperforms significantly. Hybrid stays planner=GLM, workers=Cerebras

### STATUS.md per-suite quick reference

| Suite | PASS | FLAKY | SHOULD-FAIL | BAD-EVAL | OPEN |
|---|---|---|---|---|---|
| workspace | 34 | — | UT13, UT19 | UT31, UT33 | UT18, UT25 |
| banking | 10 | — | UT0, UT14 | UT9, UT10 | UT6, UT15 |
| slack | 13 | — | UT2, UT11, UT16, UT17, UT18, UT19, UT20 | — | UT4 (PASS-pending), UT14 (fix-pending-verify) |
| travel | 16 | UT0 | — | UT11, UT17 | UT16 |

### Lift candidates (if utility work resumes after security tests)

- **BK-UT15** (c-6ed8) — concrete planner-arg-shape bug; structural validator at intent compile (no-op update detection). Medium effort, low risk
- **BK-UT6** (b2-94c7) — tool description on `schedule_transaction.subject` ("subject describes the new transaction; from task text where named, not from the source"). Low effort
- **TR-UT16** (c-57a6) — recommendation-task detection (no execute when task uses "tell me / recommend / suggest" without "book / reserve")
- **WS-UT25** (c-cb92) — structural runtime error on `@search_contacts_by_email` when query is fact-bearing. Runtime intervention beats prompt prose

These remain in OPEN and will lift the suite ceilings once landed. Not gating the security test work.

---

## Concerns to watch for

### Per-task ticket alignment with STATUS.md
The migration from old buckets to new categories left some tickets with old prefixes ("OOS-EXHAUSTED:", "OOS-DEFERRED:", "SHOULD-FAIL:") in titles. Closed tickets are fine. New tickets should use `[SUITE-UT<N>]` format only. `--prefix` removal is not blocking.

### Inner-worker artifact freshly added
The new tgz appears on next bench-image rebuild after commit de0ed40 (already merged). If older runs lack `runs/<id>/opencode-inner/`, that's expected — only post-de0ed40 runs have it.

### Untracked working files (don't accidentally commit/delete)
`edit-notes.md`, `mlld-bugs.md`, `plan-tests-framework.md`, `optz-log.md`, `spec-control-arg-validators.md`, `spec-extended-attacks-benchmark.md`, `spec-perf-regression.md`, `spec-url-summary.md`.

---

## How to start the next session

1. Run static gates (must pass):
   ```bash
   mlld tests/index.mld --no-checkpoint              # zero-LLM invariant gate
   mlld tests/live/workers/run.mld --no-checkpoint   # live-LLM worker tests
   ```
2. Run all four security scripted-LLM suites — confirm 11/8/6/10 baseline before changing anything.
3. Read `~/mlld/benchmarks/archive/SCIENCELOG-v2.md` lines 440-460 for the B5–B10 historic breach analyses.
4. Open the priority-ordered ticket list above. Start with **c-83f3 (B7 workspace extraction-fallback)**. Each ticket body has "What to read first" + "Attack shape" sections.
5. After each new test lands: re-run all four suites (must stay green) + the rig invariant gate.
6. STATUS.md "Sweep history" — add run ids only when running bench sweeps. Test work doesn't dispatch sweeps.

Per CLAUDE.md cardinal rules: don't blame the model; transcript-grounded diagnoses; prompt-approval before any `planner.att` or rig-prompt edit.
