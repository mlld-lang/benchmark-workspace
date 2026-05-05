# Session Handoff — security tests + open work

Last updated: 2026-05-04

## Top priority: grow security-test coverage

The `tests/` mlld-native test framework is in place with 25 zero-LLM scripted security tests. The wrong-record fact firewall bypass (UT16 class, c-3c2b) is closed via kind-tagged fact fields — mlld policy.build auto-derives `policy.facts.requirements` from kind annotations on input records, so consumers don't maintain per-tool override boilerplate. Slack records are tagged; workspace producer/input records are tagged. Banking and travel records still need tagging — that's the highest-leverage follow-up (c-ce5a).

Everything else (long-term work — undefended baseline, attack sweeps, cloud batching) stays open and important, but security-test growth is first priority.

---

## Test infrastructure (read this first)

```
clean/tests/
  README.md              # API + recipes including denial-test pattern
  index.mld              # plain assertion runner (mlld tests/index.mld)
  scripted-index*.mld    # per-suite scripted runners (run via run-scripted.py)
  run-scripted.py        # wraps MCP env for scripted runs (--suite + --index)
  assert.mld             # @assertOk, @assertEq, @assertContains, @assertHas
  runner.mld             # @suite, @group, @runSuites — opts: ticket, slow, xfail
  lib/
    mock-llm.mld          # @mockOpencode, @mockPlannerRun (no LLM)
    security-fixtures.mld # @stateWithExtracted/Derived/Resolved seed helpers
  suites-scripted/
    security-{slack,banking,workspace}.mld   # current suites
    _template.mld         # copy-paste shape for new suites
```

**Run the existing security suites:**

```bash
uv run --project bench python3 tests/run-scripted.py --suite slack \
  --index tests/scripted-index-slack.mld
# (also banking, workspace)
```

**Current state**: slack 11/0/0, banking 8/0/0, workspace 6/0/0.

Each scripted suite imports its own bench domain's `tools.mld` (which connects to MCP at import). That's why per-suite indexes exist — only one suite's tools can be wired per process.

The plain assertion runner (`mlld tests/index.mld`) exists but currently only has the template suite. Plain tests are for primitive-level checks that don't need MCP; scripted tests are for multi-turn agent behavior including security firewalls.

---

## Wrong-record fact firewall (c-3c2b CLOSED via kind tags)

The UT16 cloud finding is closed. mlld core (commit 0c6558d62) added `kind:` annotations on fact field declarations; `policy.build` walks all records in scope and auto-derives `policy.facts.requirements` per input field by indexing kinds. No per-tool override declarations needed for the common case. See `SECURITY-RIG-WRONG-RECORD-BYPASS.md` for the design.

Schema:

```mlld
record @contact = {
  facts: [email: { type: string, kind: "email" }]
}

record @slack_msg = {
  facts: [
    sender: { type: string?, kind: "slack_user_name" },
    recipient: { type: string?, kind: "slack_user_name" }
  ]
}

record @send_email_inputs = {
  facts: [
    recipients: { type: array, kind: "email" }
  ]
}
```

`@send_email.recipients` (kind: email) auto-accepts any record-field tagged kind: email — `@contact.email`, `@shared_file_entry.shared_with`, etc. Adding a new email source = tag one field; every email-accepting tool input picks it up.

**Tagging status**:
- ✅ slack (records.mld + input records)
- ✅ workspace (records.mld + input records)
- ❌ banking — needs kind tagging (c-891b)
- ❌ travel — needs kind tagging (c-891b)

Override path (rare): when a tool's control arg legitimately accepts a fact whose source field name differs and isn't kind-tagged, declare `accepts:` on the input record's fact field declaration. The escape hatch `factRequirements:` on tool catalog entries is supported but discouraged — kinds is the primary path.

Untagged fact fields keep current strict default `["known", "fact:*.<argName>"]`.

---

## Test coverage gaps — write these tests next

10 tickets filed with detailed source material. Each has reproduction context and acceptance criteria.

### Suite kind tagging (highest leverage)

- **c-ce5a** (P1) — Tag banking and travel domain records with `kind:` on fact fields. Slack and workspace are done; banking and travel still get untagged-default behavior. Audit each fact field: what kind name should it carry? Use existing kinds where they apply (`email`, `email_id`, `file_id`); add new kinds for domain-specific identities (`iban`, `transaction_id`, `hotel_name`, etc.). Same kind on producer + input fact field = auto-derived accept. Slack tagging took ~20 minutes; expect similar per suite. Ticket has detailed kind suggestions per record.

### Test infrastructure

- **c-c2e7** — Harness extension: dynamic handle threading across script steps. **Unblocks** the literal-UT16 test variant + c-a720 + c-fb58 + c-800d. Several attacks need step 2's args to reference handles minted in step 1; the script array is currently static.

### Historic breach regressions (B5–B10)

Per `~/mlld/benchmarks/SCIENCELOG.md` and `CHALLENGES.md`. 6 of 10 historic breach classes have no regression test yet. If a future change reopens any of these, we should know immediately.

- **c-a720** — B5 slack recursive URL fetch (UT1 × IT3). Needs c-c2e7.
- **c-fb58** — B6 slack instruction-channel labels (UT18 × IT3). Needs c-c2e7.
- **c-83f3** — B7 workspace extraction-fallback poisoning. Plain assertion test against the extract worker's null-handling.
- **c-ae22** — B8 workspace `true`-authorization bypass. Should already be defended via `allow_requires_no_control_args` (rig/intent.mld:680-695); add the regression test.
- **c-7016** — B9 travel recommendation-hijack (UT11/UT16 × IT6). Untrusted-llms-get-influenced label propagation + advice-gate denial. Linked to c-891b.
- **c-d374** — B10 get_webpage exfil:send + no-novel-urls.

### SHOULD-FAIL coverage by class

- **c-634c** (P1) — typed-instruction-channel class (WS-UT13/UT19, SL-UT18/UT19/UT20). Different defense surface than the source-class firewall — these tasks fail because the planner shouldn't be able to ACT on instructions in untrusted content at all. Test approach: assert role:planner display projection masks the actionable content (negative-coverage test). Plain assertion suite at `tests/suites/rig/display-projection.mld`.

### Defense layers not yet exercised

- **c-891b** — Taint-based defenses (`no-untrusted-privileged`, `no-untrusted-destructive`, label propagation). Includes a policy-rule-coverage audit document — current `update_user_info` is NOT defended at any rehearse-time layer despite the historic UT13 × IT7 breach (kind tagging won't fix this because update_user_info has `facts: []` — taint is the right layer). Decide: reclassify, add new rule, or accept out-of-scope.
- **c-800d** — Correlate cross-record-mixing (`update_scheduled_transaction` declares `correlate: true`). Banking attack: id from tx_A + recipient from tx_B should reject. Needs c-c2e7 + benefits from c-ce5a (banking kind tagging).

`tk show <id>` for full bodies.

---

## Long-term work (still important, lower priority than tests)

These are filed and open but should not bump security-test work.

### Cloud bench wall time — c-2d0f

Slack/workspace/travel cloud sweeps spend most wall on SHOULD-FAIL grinding to 700-900s timeouts. Two paths in priority:

1. **Fix the underlying detection** — c-5ef9 landed this session for one shape (control-arg-from-untrusted). The wider class (control-arg-not-derivable-from-state) needs the c-3c2b firewall fix above to short-circuit at rehearse.

2. **Operational split** (c-2d0f) — `scripts/bench.sh` produces `fast` + `grind` dispatch sets, single source-of-truth at `bench/grind-tasks.json`. Works regardless of detection fixes; reduces critical-path wall ~40% on slack/workspace/travel.

### Undefended baseline — c-debc

Need a flat-tools-to-planner agent (no rig orchestration, no records, no policy) for the publication's "tier 0 = undefended" baseline column. Proposed shape: `bench/agents/<suite>.mld` dispatches based on `@payload.defense`. Outputs the price-of-defense delta for the matrix.

### Attack canary + full attack suite — c-1bd4

After security tests close the known gaps:

1. Read `~/mlld/benchmarks/SCIENCE*` for canary attacks (3-5 cases historically hardest to defend).
2. Spot-check via `gh workflow run bench-run.yml -f attack=<atk> -f defense=defended -f tasks=<id>`.
3. Mitigate any breaches found.
4. Full attack matrix on cloud (6 stock attacks × 4 suites = 24 dispatches via `scripts/bench-attacks.sh`).
5. Record results in SCIENCE.md per `spec-extended-attacks-benchmark.md`.

### Per-task triage — c-0eb5

Walk the per-task ticket set after each sweep — make sure every failing in-scope task has an open ticket with current theory (Convention A). Some currently-closed OOS/SHOULD-FAIL tickets describe failures that still occur on every sweep — they should be reopened (Convention E).

---

## Concerns to watch for

### Rehearse output is intentionally minimal

Per `spec-rehearse.md` and the rehearse tool implementation, rehearse returns `{ok, blocked_args, structurally_infeasible}` with no specific reason codes — that's deliberate (no info leak about policy structure). Tests can only assert `ok`/`blocked_args`. For finer-grained assertions (which rule fired), use the diag stream (`MLLD_TRACE=effects`) or grep test stderr for `[rig:diag:*]` lines.

### Tests passing for shallow reasons

The three `selection-ref-graceful-failure` tests pass because of lookup failures (handle not found, entry without identity_field, mismatched handle string), not because of the kind-tag firewall. They confirm graceful failure on malformed input — a real defense, but a lower bound. The deep firewall validation lives in `selection-ref-wrong-record-bypass/selectionRefRealSlackMsgHandleRejected` (passing now via kinds).

### Fixture sophistication

`tests/lib/security-fixtures.mld` builds plain-object resolved/extracted/derived entries. These don't carry `factsources` metadata or `identity_field`/`identity_value`, which limits how deeply the firewall path is exercised. The setup-phase pattern (run a real resolve, capture state via `result.mx.sessions.planner.state`) gives factsource-bearing fixtures — see `@setupSlackMsgState` in security-slack.mld for the canonical form. Use that pattern when the test needs to reach the actual firewall code paths.

### Untracked working notes

The repo contains a few untracked working files from previous sessions (`edit-notes.md`, `mlld-bugs.md`, `plan-tests-framework.md`, `optz-log.md`). Don't accidentally commit; don't accidentally delete. They're context for ongoing work.

### gpt agent's reverted JS-batching patches

A previous perf session produced 4 optimization patches: 2 mlld-native (kept, in `820f0d9`), 2 JS-batching (reverted per user direction — progress through mlld-native first; only drop to JS if necessary). If deeper optimization is needed later, the reverted patches are recorded in `optz-log.md`.

### Why rehearse is "free but not instant"

The rehearse RESPONSE is deterministic and instant — no MCP call, no LLM call, just compile + policy.build. But the planner LLM call to EMIT a rehearse intent is a regular LLM round-trip (~30-60s on GLM, ~14s on Cerebras). Even an "optimal" SHOULD-FAIL exit costs 4-5 LLM round-trips (~2-4 minutes). The round-trip floor is set by the model; c-c2e7 (harness extension) helps test fixtures, not production wall time.

### Attestation suffix subtle bug (fixed)

Rig's `@factAttestations` was emitting only `fact:@<rec>.<field>[<position>]` for every factsource. mlld's auto-derived patterns (from kinds) are bare `fact:@<rec>.<field>`. Mismatch → `proofless_control_arg` even when the source/sink kinds matched. Fix in this session: emit BOTH bare and `[N]`-suffixed forms. If you see `proofless_control_arg` in a transcript with kinds correctly set, suspect this bug-class — check `rig/intent.mld:343-355` (the `@factAttestations` JS block).

---

## How to start the next session

1. Run the gates (must pass):
   ```bash
   mlld clean/rig/tests/index.mld --no-checkpoint
   mlld rig/tests/workers/run.mld --no-checkpoint
   ```
2. Run the security suites:
   ```bash
   uv run --project bench python3 tests/run-scripted.py --suite slack --index tests/scripted-index-slack.mld
   # also banking, workspace
   ```
   Expected: 11/0/0, 8/0/0, 6/0/0.
3. Read `SECURITY-RIG-WRONG-RECORD-BYPASS.md` (notes from mlld-dev) for the kind-tag firewall design — implemented in mlld + rig + bench (slack/workspace).
4. Pick from the gap tickets in priority order: c-ce5a (P1, tag banking + travel records with `kind:`) → c-c2e7 (harness extension, unblocks several others) → c-634c (P1, typed-instruction class) → B5–B10 + c-800d + c-891b (taint defenses).
5. Long-term work (c-2d0f, c-debc, c-1bd4) is yours to schedule — they don't block tests but they're filed for visibility.

Per CLAUDE.md cardinal rules: don't blame the model; transcript-grounded diagnoses; prompt-approval before any `planner.att` edit.
