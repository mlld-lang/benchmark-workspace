# HANDOFF.md — Path to 81/97

Session breadcrumb. Forward-looking only. Read at session start. Update at end with what landed and what's next. Use `/rig` to load the framework context.

## Where we are

- **Current measured utility**: 53/97 (full benign sweep 2026-05-12 against c-bac4+c-e414+c-3162 build, BEFORE bench-side records refine migration)
- **Security verified**: 0/105 ASR on slack atk_direct + atk_important_instructions canaries (runs `25708270888`, `25708271819`)
- **Achievable ceiling**: 81/97 per `STATUS.md` (97 minus 16 hard-capped: 10 SHOULD-FAIL + 6 BAD-EVAL). FLAKY (1 task, TR UT0) is recoverable via date-arithmetic bug fix.
- **Recent commit**: `1615089` — STATUS rewrite, ticket triage, c-a6db (`?` field-optional) bench migration applied, MIGRATION-HANDOFF.md archived
- **mlld latest pushed**: `4a27abee4` — provenance/routing label split + record refine + `?` field-optional implementation

## Priority queue

### 1. Push + measure where c-a6db + new mlld actually lands

The latest cloud sweep (53/97) was against an older mlld + before the bench-side records refine migration. The c-a6db migration is applied locally; commits need pushing and a full sweep against the current build.

**Do**:
```bash
git push
scripts/bench.sh    # full 4-suite benign sweep, ~10-15min wall, ~$3-5
```

When complete, fetch results and compute **per-task set diff** against the 78/97 baseline:
- workspace UT0-19 baseline: run `25324557648`
- workspace UT20-39 baseline: `25324563037` (split came later — same run)
- banking baseline: `25324559458`
- slack baseline: `25324561113`
- travel baseline: `25324563037`

The number that matters is which tasks shift in/out of the PASS set per suite — not the aggregate count (stochastic recoveries hide regressions).

**Expected**: WS UT12 recovers (`?` field-optional unblocks `facts.requirements` for solo focus blocks — local probe confirmed). Modest gains scattered. Travel + banking likely still regressed until their refine migrations land (c-4076, c-7780).

If utility is below ~55/97: regression somewhere. Bisect before continuing.

### 2. c-4076 — travel records refine (trusted_tool_output)

`bench/domains/travel/records.mld` — add `labels: ["trusted_tool_output"]` to records that CaMeL marks as `TrustedToolSource`:

- `@hotel`, `@restaurant`, `@car_company`, `@flight_info` → add the labels declaration
- Reviews stay untrusted (`@hotel_review`, `@restaurant_review`, `@car_company_review` — already structured correctly)

Then add basePolicy rule in `rig/orchestration.mld` (`@synthesizedPolicy` path): `labels.trusted_tool_output.allow: ["fact:*"]` — values labeled trusted_tool_output satisfy fact-provenance requirements for control args at dispatch.

**Verify**:
- Zero-LLM gate clean
- Travel UT0/UT1/UT3/UT4/UT7/UT16 recover (target +4-6 tasks). These all use hotel/restaurant info as control args for `reserve_*`.
- Slack atk canaries stay 0/105 ASR (defense unchanged for slack)

CaMeL reference for which travel tools are TrustedToolSource: `~/dev/camel-prompt-injection/src/camel/pipeline_elements/agentdojo_function.py` `_TRUSTED_TRAVEL_TOOLS`.

### 3. c-7780 — banking records refine (sender=="me" user_originated)

`bench/domains/banking/records.mld` — add refine clause to `@transaction` (and likely `@scheduled_transaction`):

```mlld
record @transaction = {
  ...existing facts/data/labels...
  refine [
    sender == "me" => labels += ["user_originated"]
  ]
}
```

Add policy rule in `rig/orchestration.mld`: `labels.user_originated.allow: ["fact:*"]` so user-originated transaction fields satisfy fact-provenance for control args at dispatch.

**Verify**:
- Zero-LLM gate clean
- Banking UT3 (friend repayment), UT4 (refund), UT6 (Spotify recurring), UT11 (Apple VAT) recover. Target +3-5 tasks.
- Slack atk canaries stay 0/105 ASR

CaMeL reference: `_get_transaction_metadata` in same `agentdojo_function.py`.

### 4. mlld dep-driven `influenced` — partial done, broader work still pending

Brief at `mlld-dev-prompt-influenced-rule.md`. **mlld-dev's commit `dfa8d5c1b "Narrow influenced cascade to provenance evidence"` did the narrow half**: routing-only labels (`src:exe`, `role:worker`, `llm`) no longer trigger cascade. The broader proposal (walk dep tree based on data lineage, not code lineage) is still pending.

**Why the broader work matters for Tier 2 recovery**:

Spike (2026-05-13): a clean module-scope var picks up `src:file`/`dir:*` labels after passing through `@resolveRefValue` — labels from the FILE THE RESOLVER CODE LIVES IN (rig/workers/*.mld, rig/intent.mld). For banking arithmetic tasks (BK UT3/4/6/11), user-trusted inputs go through derive worker → derive output picks up `src:file: rig/workers/derive.mld` → cascade fires → influenced → `labels.influenced.deny: ["exfil"]` blocks send_money.

The brief's proposal would address: distinguish "value came from file as data" vs "value passed through code in a file as routing." mlld currently treats both as provenance.

**Action**: Ping mlld-dev to clarify scope:

> The c-3162 over-fire fix addressed the immediate symptom. The broader proposal in `mlld-dev-prompt-influenced-rule.md` is still needed for Tier 2 utility recovery — bench tasks where derive worker output picks up `src:file: rig/workers/derive.mld` from code path even on User-trusted inputs trigger cascade and block legitimate flows. Is the rig-side fix in scope (strip code-path provenance before LLM dispatch), or is the broader mlld proposal still in-scope?

Repro: `/tmp/probe-c3162-clean.mld` — plain string → `@resolveRefValue` → taint includes rig source-file path. Or just observe the c-3162 clean test still XFAIL.

Don't block on this for #2/#3; Tier 1 work is independent.

### 5. Cluster I — `search_calendar_events.args.query` schema bug

Workspace UT2, UT7 fail because the schema for `search_calendar_events.query` arg rejects both structured ref AND bare string forms (mutual-exclusion bug). Agent loops trying both shapes, gives up.

**Investigate**:
- Probe `@search_calendar_events_inputs` decl in `bench/domains/workspace/records.mld`
- Test what shape mlld accepts for the `query` arg at dispatch (`source: "known"` vs raw string)
- Either fix the schema, or file mlld-side ticket if mlld is wrong

**Verify**: WS UT7 (dental check-up reschedule) recovers — once the agent can search for the existing event, the resolved event_id + shelf-derived participants work for reschedule_calendar_event (shelf-driven trust propagation is already wired).

### 6. Reader-set propagation (c-dee1) — DEFER until after Tier 1 lands

Workspace UT15/UT18/UT20/UT21 (calendar event creation from emails). Wait until Tier 1 + Tier 2 land and re-measure — some may recover via dep-driven `influenced` (Tier 2) alone if email content traces to User-trusted task text. If they still fail after Tier 1+2: design pass on per-instance reader sets via record refine + label-flow rule.

## Hard rules carried forward

- **Security-first mentality**: promise security holds, NOT utility. When a fix surfaces hidden defense regressions, surfaced failures are findings not regressions to paper over. Re-baseline utility against properly-enforced defenses.
- **Bench gate ordering**: benign FIRST, attacks SECOND. ASR=0 from a broken agent is meaningless.
- **Baseline-attribution discipline**: cite explicit baseline run id, verify JSONL, run per-task set diff (not just count).
- **2-at-a-time sub-suite concurrency** on cloud: non-negotiable. Use `scripts/bench.sh` (auto-paces) and `scripts/bench-attacks.sh` (per-attack shape map).
- **Prompt-approval rule**: every prompt change (rig prompts, suite addendums, tool descriptions, planner.att, worker templates) needs explicit user approval before being written.
- **No model blame**: GLM 5.1 has hit 80%+ on these suites before; framework/prompt/runtime are the variables.

## What NOT to do

- **Don't run full 6×5 attack matrix** until utility is verified within ±2 of recent baseline. ASR=0 from a partially-recovered agent is structurally meaningless. Slack canary pair is sufficient ASR signal during iteration.
- **Don't relax records or weaken policy rules to make tasks pass.** The 17 hard-cap tasks are deliberate. Argue for reclassification only with transcript-grounded evidence; only the user marks FLAKY or BAD-EVAL.
- **Don't bundle prompt changes with semantic changes** in the same commit.
- **Don't write a session-end document or close work** without user direction. Session boundaries are the user's call.
- **Don't punt mlld-side findings to the handoff and stop.** File `cd ~/mlld/mlld && tk add ...` and keep working. mlld-dev typically responds same-turn.

## Verification gates

```bash
mlld tests/index.mld --no-checkpoint              # zero-LLM, target 263+/0/X, ~10s
mlld tests/live/workers/run.mld --no-checkpoint   # worker live-LLM, target derive 7/7, ~50s, ~$0.05
uv run --project bench python3 src/run.py -s <suite> -d defended -t user_task_N  # single-task local probe, $0.05-0.25
scripts/bench.sh                                  # full 4-suite benign sweep, ~10-15min, ~$3-5
scripts/bench-attacks.sh single direct slack      # slack atk_direct canary, ~35min, ~$2
scripts/bench-attacks.sh single important_instructions slack  # second canary
```

Per-task set diff template (replace `<run-id>` and `<suite>`):
```bash
NEW=$(find runs/<new-run-id> -name "defended.jsonl" | head -1)
OLD=runs/<baseline-run-id>/results/bench/results/.../defended.jsonl
echo "Now PASS: "
jq -r 'select(.utility == true) | .task_id' "$NEW" | sort -V
echo "Was PASS: "
jq -r 'select(.utility == true) | .task_id' "$OLD" | sort -V
```

## Useful pointers

- `STATUS.md` — canonical bench state, per-task classifications, recovery path table
- `RECORD-REFINE-MIGRATION.md` — current refine grammar (`labels:`, `refine [...]`, `@input` qualifier, `?` field-optional)
- `camel-alignment-analysis.md` — CaMeL trust model comparison + alignment plan
- `mlld-dev-prompt-field-optional.md` — `?` field-optional brief (mlld-side landed; bench-side applied in `1615089`)
- `mlld-dev-prompt-influenced-rule.md` — original dep-driven influenced brief (partial done via `dfa8d5c1b`)
- `mlld-dev-prompt-influenced-rule-followup.md` — followup ping: code-path provenance vs data-path provenance scope question (awaiting mlld-dev reply)
- `mlld-security-fundamentals.md` — security model narrative
- `bench/domains/<suite>/records.mld` — current record decls
- `rig/orchestration.mld` `@synthesizedPolicy` — where to add new label allow-rules
- `tk ls --status=open` — actionable tickets; Tier 1 starts with c-4076 and c-7780

CaMeL reference checkout: `~/dev/camel-prompt-injection/src/camel/`. Specifically `pipeline_elements/agentdojo_function.py` for per-tool source assignments, `pipeline_elements/security_policies/<suite>.py` for per-tool policy logic, `capabilities/` for trust/readers semantics.
