# HANDOFF.md — Path to 81/97

Session breadcrumb. Forward-looking only. Read at session start. Update at end with what landed and what's next. Use `/rig` to load the framework context.

## Where we are (end of bench-grind-24, 2026-05-13)

- **Current measured utility**: 53/97 (last full sweep 2026-05-12). No new full sweep this session.
- **Security verified**: 0/105 ASR on slack atk_direct + atk_important_instructions canaries (runs `25708270888`, `25708271819`).
- **Achievable ceiling**: 81/97. Tasks blocked on `m-aecd` (shelf round-trip strips §4.2 refinement) are NOT in the hard cap — once that lands they should recover via existing migrator-7 records.
- **mlld**: branch `2.1.0` HEAD. Carries m-383e + m-ee3f + m-a3ad + child-frame stamping fix.
- **Zero-LLM gate**: 264/0/4 xfail ✅.

## What landed this session

### Cluster I masking fix (commit `4d2b0c0`)

`@settlePhaseDispatch` + the 3 phase-tool error returns in `rig/workers/planner.mld` now surface mlld's structured policy-error envelope (code, field, hint, message) to the planner's next-turn input. Previously rig narrowed mlld's rich envelope (`buildSurfacedToolFailureResult` returns `{error, message, code, field, hint, details, ...}`) to just `{error, summary, issues, raw_error}`. Planner saw "tool_input_validation_failed" with no detail and cycled blind through arg shapes.

Refactor extracted `@buildPhaseErrorLogEntry` + `@buildPhaseErrorResult` helpers; both exported. Test: `tests/rig/phase-error-envelope.mld` (2/2 green). c-3162 dispatch denial test still 2/2.

Behavioral verification on BK UT3/4/6/11 + TR UT4 re-probe: planner stops cycling, blocks cleanly with transcript-grounded reasoning. 0/6 utility recovery on this fix alone, but the FAILURE MODE shifted from "cycle blindly" to "block cleanly with reason" — the prerequisite for downstream fixes to land cleanly.

### Compose anti-fabrication (commit `10d861a`)

`rig/prompts/compose.att`: tighten the "don't claim sent if status != 'sent'" rule into an explicit anti-fabrication directive AND a "never render field values not in state" rule. BK UT3 + TR UT3 used to compose-fabricate "we sent the refund" / "email sent" despite zero successful executes. Now they block cleanly with a security-aware reason instead.

Worker LLM gate: compose 6/6 (was 3/6 on the simple "Return only JSON" prompt; lifted by the consequence-stated wording in 4d2b0c0, then strengthened further here).

### Worker prompt fixes (commit `4b4b894`)

- `rig/prompts/derive.att:39`: dropped `<...restaurant.price_per_person...>` placeholder — the angle-bracket + dots tripped mlld's file-load syntax at template render time, fired a "Failed to load file" warning, AND corrupted derive_ranking via prompt mangling.
- `rig/prompts/compose.att`: strengthened "Return only JSON" to consequence-stated, plus output anchor.

### Workspace planner addendum (commit `217a071`)

`bench/domains/workspace/prompts/planner-addendum.mld`: query-broadening rule for empty search results. Probe of WS UT2/UT7: 0/2 recovery so addendum didn't help on its own. Wording is structurally true, kept as a low-cost safety net.

### Tickets filed

- **`m-aecd`** (`~/mlld/mlld`, P0) — the load-bearing finding. `@shelf.write` + `@shelf.read` round-trip silently re-introduces `untrusted` on `data.trusted` fields that §4.2 coercion correctly cleared. Probe: `tmp/probe-trusted-field/probe-shelf-roundtrip.mld`. Blocks BK UT3/4/11 + TR UT4 directly.
- **`m-c371`** (`~/mlld/mlld`) — closed. Originally framed as "need new trust-elevation primitive"; superseded by m-aecd once shelf-strip root cause was found.
- **`c-6a39`** (clean) — `[BK-UT6]` compose-worker fabrication ticket. Addressed by compose.att anti-fabrication rule.
- **`c-c80e`** (clean) — integration test followup for the masking-fix invariant (different regression class from helper unit test).

## What's blocked on `m-aecd` (and twin-site `as record` bug)

BK UT3, UT4, UT11. TR UT4 (calendar event partial — the same shelf-strip flows the derived hotel-name into untrusted at execute time). TR UT3 also hits this on `subject` field at send_email.

Per mlld-devrel investigation (msg in fray clean#bench): m-aecd and the `as record` coercion divergence (bug doc in `~/mlld/mlld/bug-as-record-coercion-untrusted-divergence.md`) share **the same recursive-extraction anti-pattern**, applied at different code sites:

- **`expressions.ts:947`** — `as record` coercion path post-extraction recursively walks descriptor and re-aggregates per-field untrusted/`fact:*` labels back up to the wrapper.
- **`shelf/runtime.ts:696-699`** — shelf-write path recursively re-extracts per-field descriptors; untrusted aggregates up (per-field walks find it from the wrapper), then `slotDescriptor` adds the `src:shelf:...` taint on top.

Both are filed; mlld-dev will likely fix as a bundled pair. Fix shape: don't recursively re-extract after coercion; use the field-local self descriptor that coercion already produced.

When mlld-dev lands the fixes:

1. Re-probe with **existing** records (migrator-7's `labels + satisfies` for travel, `refine sender == "me" => labels += [...]` for banking) FIRST. The migrator-7 "0/6 recovery" verdict was confounded by these two bugs masking the §4.2 refinement.
2. If existing records don't recover the full set: per advisor + mlld-devrel, the next layer is `bench/domains/banking/records.mld` — add `data.trusted: [amount, date]` schema declaration AND `refine [ sender == "me" => data.amount = trusted, data.date = trusted ]`. Same pattern likely applies to travel records (per camel-alignment-analysis.md Cluster B).
3. Records-edit timing is pending Adam's call (see fray msg-set this session): adopt-now (mlld-devrel's framing, structurally correct) vs hold (advisor's earlier framing, atomic recovery). Both defensible.

## Priority queue for next session

### 1. Wait for `m-aecd` to land

When it does, re-probe the canonical 6 locally before any records edits. Goal: see how many recover from the shelf-strip fix alone. The migrator-7 records are still committed in `ef73cb5`.

### 2. Cluster II — TR UT3 selection-ref discipline (independent of m-aecd)

TR UT3 still fabricates / blocks at the same place even with masking fix: derive emits selection_refs for `best_hotel`, planner runs a SECOND derive (`email_fields`) without requesting selection_refs, tries `{source:derived}` for `recipients` control arg, rig firewall denies with the hint in `issues[]`. Even with detail surfaced, the planner doesn't connect "derived recipient → ask derive for selection_refs."

This is a prompt-education move at `rig/prompts/derive.att` or `rig/prompts/planner.att` or per-tool `instructions:`. Prompt-approval gated. The right framing is structural ("when a derive output will populate a downstream control arg, the derive's goal must request selection_refs on that field"), not task-shaped.

Read the TR UT3 transcript before designing the nudge.

### 3. Travel records refine-trust (post m-aecd verification)

If banking recovery validates the refine-trust pattern, the same shape likely applies to travel hotel/restaurant/car records. Hold scope expansion until banking confirms.

### 4. Cluster III — BK UT6 planner field-dropping

BK UT6's compose-fabrication was addressed by the anti-fabrication rule. But the underlying planner behavior (drop a required field when validation fails, submit anyway) might still bite once shelf-strip is fixed. Watch for it on re-probe.

## Hard rules carried forward

- **No workarounds for runtime bugs** (goal-level rule). m-aecd is the right move — don't paper over it with bench-side records hacks.
- **Security-first mentality**: probe shows the framework is now correctly security-aware; some tasks blocking cleanly is the CORRECT outcome when no source class can satisfy the policy.
- **Bench gate ordering**: benign FIRST, attacks SECOND.
- **Prompt-approval rule**: rig prompts, suite addendums, tool descriptions, planner.att, worker templates need explicit approval. Non-overfitting prompt tweaks (like the compose anti-fabrication or the JSON-enforcement) are fine without re-asking each time once the user has set the standard.
- **Transcript-grounded diagnosis**: don't ground a fix on call-sequence guessing.
- **Active-loop discipline**: file mlld briefs and keep working; don't gate on upstream response.

## What NOT to do

- Don't run full 6×5 attack matrix until utility is verified within ±2 of recent baseline.
- Don't pre-revert migrator-7's records — they may be doing useful work behind the shelf-strip masking.
- Don't add `data.trusted: [amount]` + refine-trust to banking records until m-aecd lands and existing records re-probe fails.
- Don't pre-promote tasks to SHOULD-FAIL — that's a user call.

## Verification gates

```bash
mlld tests/index.mld --no-checkpoint              # zero-LLM, target 264/0/4, ~10s
mlld tests/live/workers/run.mld --no-checkpoint   # worker live-LLM, target 24/24, ~50s
mlld tests/rig/phase-error-envelope.mld --no-checkpoint  # masking-fidelity, 2/2
uv run --project bench python3 src/run.py -s <suite> -d defended -t user_task_N
scripts/bench.sh                                  # full 4-suite benign sweep
```

## Useful pointers

- `STATUS.md` — canonical bench state + sweep history
- `mlld-dev-prompt-trust-elevation.md` — superseded by m-aecd (kept as context)
- `tmp/probe-trusted-field/` — empirical probes that pinned m-aecd
- `tmp/probe-execute-mask/` — probe that pinned the rig masking gap
- `rig/workers/planner.mld` — `@buildPhaseErrorLogEntry`, `@buildPhaseErrorResult` helpers (lines 382-420)
- `rig/prompts/compose.att` — anti-fabrication rules at lines 30-33
- `tests/rig/phase-error-envelope.mld` — masking-fidelity regression guard
- `~/mlld/mlld/.tickets/m-aecd.md` — load-bearing mlld ticket
- `tk ls --status=open` — actionable tickets in clean

CaMeL reference checkout: `~/dev/camel-prompt-injection/src/camel/`.
