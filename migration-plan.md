# Migration Plan — records-as-policy + shelf-bucket consolidation

This document is the authoritative migration plan for `~/mlld/clean` to consume the next-generation mlld primitives that converged during the m-d49a / m-f947 / m-rec-perms-update / m-shelf-wildcard design thread.

It supersedes `archive/key-hash-improvements.md`. The earlier plan was scoped against a smaller set of mlld changes; the design has since broadened to include records-as-complete-security-contract and bucket→shelf collapse, and several earlier slices are now obsolete or shaped differently. The breadcrumb is preserved for history.

## What changed since the original plan

Originally the migration was about consuming `.mx.key` and `.mx.hash` to clean up rig identity heuristics. The design conversation produced a structurally larger endpoint:

1. **`.mx.key` / `.mx.hash` on every record** (m-d49a + m-f947) — landed in mlld; stable identity + content fingerprint as record-bound primitives.
2. **Records as complete security contract** (m-rec-perms-update, in-flight) — `display:` → `read:` rename, `{ref: ...}` → `{value: ...}` mode rename, `write:` declarations per role per target (shelves, tools), schema/value visibility decoupling with `{omit}` mode and schema-visible-by-default defaults. **m-fe08 was subsumed by m-rec-perms-update v0.2** — visibility decoupling no longer ships separately.
3. **Shelf wildcard slots** (m-shelf-wildcard, **shipped in mlld main**) — shelf gains auto-discovered slot mode + field-level merge + optional version/cache attributes; rig's bucket disappears into shelf.
4. **Records-baseline binary pinned** at `~/mlld/clean/.bin/mlld` — frozen at commit 49ccb3ab7 (last commit before record-permissions migration), keeps the test surface green while we develop Phase 0 work.

**Both m-rec-perms-update and m-shelf-wildcard are now in mlld main.** There is no remaining wait for mlld features — the cutover is "swap `./.bin/mlld` for system `mlld`" whenever we're ready to start Phase 1.

Net effect once landed:
- Records become the single source of truth for shape-level security (schema, identity, fingerprint, trust tiers, role-scoped reads, role-scoped writes including tool authorization)
- Tool catalog becomes a pure operation registry (no `can_authorize`, no authorization metadata)
- Bucket collapses into shelf; ~250-300 lines deleted from rig
- Policy synthesis simplifies as it consumes record `write:` declarations directly

---

## Effort sizing

**This is a quick refactor at scale, not a multi-week project.** The structural primitives are designed; specs are settled; agent execution is mechanical against a clean target shape. With the plan + tickets + maintained architectural docs + 1M-context agents, handoff overhead is essentially zero.

### Execution shape: 4-6 agent sessions

| Block | Sessions | Commits per session |
|---|---|---|
| **0.A + 0.B** — invariant tests + baselines | **1** | Two commits in one session: tests, then baselines |
| **1 (1.A + 1.A.2 + 1.B as one semantic unit)** — vocabulary rename + comment refresh + write: declarations + policy synth | **1-2** | Rename + write/policy ship together (gates can't go green between them — m-ed0b finding); 1.A.2 comment refresh as follow-up commit only after Phase 1 unit is green. Optionally split rename and write/policy into two staged commits IF gates run only after both land. |
| **2.A + 2.B + 2.C** — bucket→shelf core + consumer migration + verification | **1-2** | Largest single chunk; comment cleanup travels in-commit with deletions; can split into "core + consumers" then "verification + closeout" if a gate goes red |
| **3** — planner prompt + remaining doc pass + surviving-half comment merge | **1** | One commit with bench-sweep before/after numbers; comment merge for files not touched in 1-2 |
| **Total migration-core** | **4-6 sessions** | |

**Comment refresh adds essentially no session count.** Phase 1.A.2 is one
small follow-up commit (after Phase 1 unit is green). Phase 1.B and
Phase 2.A-C carry comment edits in-commit alongside structural changes
(deletion of a function takes its comment with it; rewriting a section
rewrites its narrative at the same time). Phase 3 was always going to
do a doc pass; folding the surviving-half comment merge into it stays
within scope.

**Note on Phase 1 commit structure**: the 1.A/1.B split was a review-hygiene preference, not a runtime invariant. Cutover activates m-rec-perms-update's full runtime contract at once (deny-by-default writes, schema-visible-by-default fields, role-key prefix, etc.). Implementer can split commits for review IF gates are run only after the full Phase 1 unit lands. Cannot ship 1.A alone with green gates. See Phase 1 section for detail.

c-0458 Days 2-5 (slack/workspace/travel layer assertions, tier-2 loop tests) is parallel quality work, ~2-3 additional sessions if pursued — pays off as migration safety net but not migration-blocking.

### Active execution time

**1-2 days of agent grinding** across the 4-6 sessions. With both mlld features (m-rec-perms-update + m-shelf-wildcard) already shipped, **there is no inter-phase wait time** — Phases 1 → 2 → 3 can run back-to-back as soon as Phase 0 is complete and the cutover (swap `.bin/mlld` for system `mlld`) happens.

Calendar elapsed approximates active execution: 1-2 days of focused agent work, possibly spread across 2-3 calendar days depending on session cadence.

### What sessions look like in this regime

Each session natural shape:

1. Read plan + relevant ticket + last `migration-status.md` entry
2. Read updated architectural docs (each phase's commits update docs in lockstep)
3. Execute the phase content
4. Run gates
5. Commit
6. Append one paragraph to `migration-status.md` ("Phase X.Y landed at commit `<hash>`; gates green; next: Phase X.Z")
7. End

The status update is the entire handoff mechanism. With 1M context, the next agent reads plan + status + relevant code in one pass and is ready to execute. No re-discovery work.

### What drives session count (and what doesn't)

Drives session count:
- **Commit hygiene** — review-friendly boundaries (rename separate from write:, etc.)
- **Gate verification points** — natural pause for "did this work?"

Does NOT drive session count:
- Context-window exhaustion (1M is plenty for this scope)
- Architectural judgment calls (specs settle these)
- Discovery work (per-function mapping table + per-phase playbook eliminate this)

### Real variability

The 4-6 number assumes:
1. mlld features ship clean — no last-minute spec changes that force replanning
2. Plan ships with per-function table, per-phase playbook, what-NOT-to-do appendix (advisory additions noted earlier)
3. Phase 2 surgery doesn't surface an unmodeled cross-resolve interaction (Phase 0.A invariants catch this; if they fire red, +1-2 debug sessions)

The risk envelope is "couple debug sessions if Phase 2 surfaces something unexpected" — not "weeks of slipped scope." Phase 0.A invariants are the primary insurance.

---

## Current state (anchor)

| Component | State | Location |
|---|---|---|
| `.mx.key` / `.mx.hash` | available in pinned binary | mlld `49ccb3ab7` |
| `@stateProgressFingerprint` | rewritten in native mlld using `.mx.hash` | rig/workers/planner.mld |
| Slack bridge `id_` synthesis | dropped; auto-key from canonical value | bench/domains/slack/{records,bridge}.mld |
| c-0458 banking layer assertions | landed | tests/scripted/security-banking.mld |
| `display:` projections (rename target) | still using old name everywhere | bench/domains/*/records.mld + rig/runtime.mld |
| Bucket | `_rig_bucket: "resolved_index_v1"` everywhere | rig/runtime.mld + state.resolved consumers |
| `can_authorize` annotations | one (banking `update_password.can_authorize: false`) | bench/domains/banking/tools.mld:167 |

**Pinned binary**: `./.bin/mlld` symlinks to `~/mlld/mlld-records-baseline/bin/mlld-wrapper.cjs`. All gates run green against it. We can develop ahead of the next mlld release without breaking the test surface.

---

## Migration phases

The migration is **phased by mlld feature dependency**. Each phase has clear gates; phases proceed in order; rollback is via the pinned binary.

### Phase 0 — Pre-migration test buildout (NOW; pinned binary)

**Goal**: Lock down the current security and behavior contracts before touching anything. Build invariant tests that survive both the old and new architectures, plus baselines that detect regression at cutover.

**Independent of mlld release schedule.** Can proceed today against `./.bin/mlld`.

#### 0.A — Invariant tests (`tests/rig/`)

Tests that encode contracts the migration must preserve. Each passes today (or xfails today as the migration target); each must pass uniformly post-migration.

**xfail discipline for tests 1 and 2**: write both the natural-id case AND the handle-drift case (slack messages) for each. Mark the handle-drift case `xfail` today with a comment pointing at Phase 2. The xfail→pass transition is the observable migration milestone. Match the existing repo pattern (e.g., `c-fb58 testInstructionChannelLabelNotPromoted` in `security-slack.mld`). Phase 2 gate explicitly requires removing the xfail markers in the same commit as the bucket→shelf collapse.

1. **Cross-resolve identity stability** (per record class)
   - Synthetic state, two identical resolves, assert: bucket entry count unchanged, primary identity stable across calls, bucket version increments by 1.
   - Today: natural-id case (banking, workspace email, travel hotel) PASSES; handle-drift case (slack messages) is XFAIL — bridge mints `Date.now()`-randomized id_ per call, identity drifts. After cutover: both PASS, xfail marker removed in Phase 2 commit.
   - Documents the bug class the migration eliminates.

2. **Selection-ref-survives-reresolve**
   - Two-phase scripted test: derive selects entry, planner re-resolves, execute uses selection ref. Assert ok.
   - Today: natural-id case PASSES; handle-drift case (slack) is XFAIL. After cutover: both PASS, xfail marker removed in Phase 2 commit.
   - The motivating contract from the m-shelf-wildcard spec.

3. **No-progress detector probe** (synthetic)
   - Synthetic state simulating slack repeat-resolve loop. Assert `calls_since_progress` increments, `progress_fingerprint` stable.
   - Today: passes (Slice 1 already landed).
   - Locks the property in place against future regression.

4. **Entry shape contract**
   - Per suite, after a real resolve, walk the bucket and assert presence of expected keys (today: `handle`, `key`, `value`, `field_values`, etc.; post-cutover: shelf-shaped entries).
   - Snapshot-style; migration explicitly bumps the snapshot.
   - Catches partial application across the worker fleet.
   - **Migration-resilience note**: the snapshot helper takes a flag (or autodetects via `_rig_bucket` sentinel presence) to support BOTH bucket-shape AND shelf-shape during the transition window. Mid-migration commits with one suite migrated and another not should pass both modes. Without this, a partial-cutover commit breaks the test prematurely and gives misleading red signals. Example helper shape: `@assertEntryShape(@entry, mode)` where `mode = "bucket" | "shelf" | "auto"`.

5. **Cross-suite resolved-bucket version-equality**
   - Assert all 4 suites use the same `_rig_bucket` shape sentinel.
   - Today: all `resolved_index_v1`. Post-cutover: shelf form.
   - Catches one-suite-stuck-on-old-shape regressions.

#### 0.B — Baseline snapshots

State captures that detect drift at cutover.

1. **Mutation matrix snapshot** — checked-in artifact of `tests/run-mutation-coverage.py` output. Migration explicitly updates it; unintentional shifts fail the build.
2. **Bench utility baseline per suite** — last known-clean numbers (workspace 36/40, banking 11/16, slack 13/21, travel 18/20 = 78/97 per STATUS.md). Post-cutover sweep must hit at least this floor.
3. **Bench security ASR baseline** — slack direct + important_instructions = 0/105 + 0/104 (verified runs 25466790521 + 25466791386). Post-cutover attack sweep must be 0 ASR.

#### 0.C — c-0458 layer assertions (Days 2–5)

Continue per the plan. Layer assertions encode the security contract at maximum granularity — they're the most migration-resistant test class because they assert on *which layer* enforces a defense, not on *which mechanism*.

| Day | Suite | Tests | Status |
|---|---|---|---|
| 1 | banking | 10 | DONE (commit bb82d62) |
| 2 | slack | 14 | pending — next |
| 3 | workspace + travel | 14 + 14 | pending |
| 4 | tier-2 credulous-loop | 6-8 | pending |
| 5 | audit doc + closeout | — | pending |

**Migration note for c-0458**: error code strings (`payload_only_source_in_control_arg`, etc.) MAY rename when intent compile is reorganized post-cutover. Layer-assertion shape is migration-stable; specific strings may need a one-pass update.

#### Gate to exit Phase 0

- [ ] Phase 0.A invariants pass (1, 3 today; 2 has a known-failure list per record class; 4-5 are snapshot tests)
- [ ] Phase 0.B baselines captured as checked-in artifacts
- [ ] c-0458 Days 2-3 landed (slack + workspace + travel layer assertions)
- [ ] Mutation matrix Overall: OK against baseline
- [ ] No comment work in Phase 0 — shadow drafts (`*-comments.txt`) stay parked. Phase 0 does not touch the source files those drafts shadow; nothing to merge yet.

---

### Phase 1 — m-rec-perms-update (records as security contract)

> **Note on numbering**: an earlier draft of this plan had a separate Phase 1 for m-fe08 (visibility decoupling). m-fe08 was closed as superseded by m-rec-perms-update v0.2 — the `{omit}` mode, schema-visible-by-default for unlisted fields, and the resolver split now ship as part of m-rec-perms-update. There is no separate m-fe08 trigger. The original Phase 1 is folded into this phase; subsequent phases renumbered accordingly.

**Trigger**: cutover from `./.bin/mlld` to system `mlld` (both Phase 1 and Phase 2 features available). Phase 0 should complete before triggering.

This is the larger migration work. m-rec-perms-update v0.3 ships **without** a deprecation alias for `display:` — the rename is mandatory at cutover. Plan must treat all renames as required-in-the-same-commit-as-the-mlld-cutover.

> **Phase 1 is one semantic unit** (added 2026-05-07 mid-execution). An earlier draft of this plan separated 1.A (rename) from 1.B (`write:` declarations + policy synth) on the assumption that a rename-only intermediate could ship green. **It can't.** The cutover from pinned binary to system mlld activates m-rec-perms-update's full runtime contract at once: deny-by-default for writes (per `core/records/write-permissions.ts:126` — records without `write:` block return `WRITE_DENIED_NO_DECLARATION`), schema-visible-by-default for unlisted fields, role-key prefix requirement, and possibly more. There is no clean rename-only intermediate state where pre-cutover semantics still apply.
>
> **Implication**: 1.A and 1.B land together as one logical unit. They MAY split across two commits if review hygiene benefits outweigh ship-green discipline (e.g., the rename commit is huge but mechanical; the write/policy commit is smaller but semantically loaded — both pre-staged, run gates green only after BOTH land), but they cannot land sequentially with gates green between them. Treat them as a single migration session producing 1-2 related commits that ship together.
>
> **Surfaced via**: m-ed0b investigation (mlld-dev confirmed clean-side migration fix, not a mlld bug). The agent's `tests/rig/policy-build-catalog-arch.mld:85` and `tests/fixtures.mld:60` failures (and any test exercising a write tool) were `policy.build` denying tool dispatch on records without `write:` declarations.

Three sub-phases (one semantic unit, possibly split for review):

#### 1.A — Vocabulary rename pass (mechanical)

The rename surface. Lands as part of the Phase 1 unit (NOT shippable alone — see callout above). If split into a separate commit from 1.B, that commit's gates remain red until 1.B also lands; the split is review-hygiene only.

Renames to apply across the codebase:

| From | To | Approx. occurrences |
|---|---|---|
| `display: { ... }` (record block) | `read: { ... }` | ~25 records (bench) + ~7 records (rig) |
| `{ref: "fieldname"}` (mode entry) | `{value: "fieldname"}` | ~50-100 mode entries |
| Bare role keys `worker:` / `planner:` / `advice:` (inside record `read:` block) | `role:worker:` / `role:planner:` / `role:advice:` | ~25 records × ~2-3 role keys each |
| `with { display: "role:X" }` (on `@claude(...)` calls and similar) | `with { read: "role:X" }` | All worker invocations + classifier calls |
| `display: "role:X"` (in `box { ... }` configs) | `read: "role:X"` | All box-scope display declarations |
| `display.<role>` (string references in comments, docs, error strings) | `read.<role>` | Audit pass |

**Role-key prefix is required** in `read:` blocks per m-rec-perms-update spec ("Role keys use the canonical `role:planner` / `role:worker` / `role:advice` form ... `role:planner` is NOT an alias for `planner`"). The pre-rename form had bare role keys (`worker: [...]`, `planner: [...]`); the post-rename form requires the `role:` prefix. System mlld rejects the bare form with `Record '@msg' read block uses bare role key 'planner'. Use canonical 'role:planner'.`

**`default:` stays bare.** Verified by parse probe against system mlld: `read: { default: [...], role:planner: [...] }` parses cleanly. The `default:` mode is "preserved as a generic-fallback projection for non-role-specific consumers" per spec.

The `with { display: "role:X" }` and `display: "role:X"` (box config) call sites already use the `role:X` prefix today — those are string-form references, not block keys; only the `display` → `read` rename applies to them.

Files touched:
- `bench/domains/{banking,slack,workspace,travel}/records.mld`
- `bench/agents/*.mld` (any `with { display: }` on `@rig.run` etc.)
- `bench/domains/*/classifiers/*.mld` (classifier `with` clauses)
- `rig/runtime.mld`, `rig/intent.mld`, `rig/workers/*.mld` (display projection consumers)
- `rig/orchestration.mld` (box configs)
- `tests/lib/security-fixtures.mld` (inline records)
- `tests/scripted/security-*.mld` (any inline records or `with` clauses)

Verification: zero-LLM gate, scripted-LLM gates per suite, mutation matrix.

`{mask}`, `{handle}`, `{omit}` mode names are unchanged — only `{ref}` renames to `{value}` because the new `read:` form makes the framing clearer (it's "show this field's value" not "show a reference to this field").

After m-fe08 was subsumed, schema-visible-by-default is part of the same release. Audit `bench/domains/*/records.mld` for fields that now flip from "schema-omitted" to "schema-visible value-hidden" and verify every record's `read:` block still expresses the intended visibility.

#### 1.B — `write:` declarations on records

Add `write:` blocks to records, per the converged spec:

**Output records** (all suites' resolved-shape records):
```mlld
write: {
  worker: { shelves: true }    >> workers persist resolved instances
}
```

**Input records** (write tools' input shapes):
```mlld
record @send_money_inputs = {
  facts: [...],
  write: {
    planner: { tools: { authorize: true } },
    worker: { tools: { submit: true } }
  }
}
```

**Hard-denied input records** (today's `can_authorize: false`):
```mlld
record @update_password_inputs = {
  data: { trusted: [password: string] },
  exact: [password],
  write: {}
}
```

Per the spec, `tools: true` is a validate-time error (no useful default for the planner/worker phase split). All input records spell out capabilities explicitly.

**Migration of `update_password.can_authorize: false`**:
1. Move to `@update_password_inputs.write: {}` (record-bound denial)
2. Delete `can_authorize: false` annotation from `bench/domains/banking/tools.mld:167`
3. Update `tests/scripted/security-banking.mld` `testUpdatePasswordHardDeniedInDefendedMode` if its assertion hits a renamed error (likely from `denied_by_policy` to a record-write-deny code)
4. Update mutation matrix expected_fails if the test classification shifts

This sub-phase is the bigger semantic change. It's the migration site where rig's policy synthesis pass simplifies — the `@policy.build` deny-list generation that today reads `can_authorize: false` reads `write:` instead.

**Files materially touched**:
- All `bench/domains/*/records.mld` (add write:)
- `bench/domains/banking/tools.mld` (drop can_authorize)
- `rig/orchestration.mld` (policy synthesis reads write:)
- Possibly `rig/intent.mld` (write-target enforcement at execute compile)
- `tests/scripted/security-banking.mld` (one assertion update)
- `tests/run-mutation-coverage.py` (if test classification shifts)

**Risk**: medium. Policy synthesis change is in security-critical rig code. Mutation matrix is the canary — every mutation must continue to fail the right tests.

**Gate**:
- [ ] All gates green
- [ ] Mutation matrix Overall: OK (with documented reclassification of any tests whose mechanism shifted)
- [ ] Layer assertions still pass (error code strings may have updated)
- [ ] Bench security ASR baseline holds (run slack direct + important_instructions canary; expect 0/0)
- [ ] Bench utility baseline holds within stochastic noise
- [ ] **`rig/ARCHITECTURE.md` updated**: records-as-policy section reflects new `read:`/`write:` declarations, `can_authorize` removed from tool-catalog narrative, policy synthesis paragraph updated. Lands in same commit (or immediate follow-up) as the Phase 1.B semantic change.
- [ ] **`bench/ARCHITECTURE.md` updated**: records section reflects per-record `read:`/`write:` blocks, tools section reflects loss of `can_authorize` annotation, "What stays / What goes" table updated.
- [ ] **Phase 1.A.2 follow-up commit landed**: comment header refresh + history strip on files renamed in Phase 1.A. Consult `*-comments.txt` shadow drafts for proposed text. Independent revert from the rename commit.
- [ ] **Phase 1.B comment refresh in-commit**: `bench/domains/*/records.mld` records-as-security-contract framing replaces facts/data+can_authorize narrative; `bench/domains/banking/tools.mld` drops can_authorize references; `rig/orchestration.mld` policy-synth comment rewritten to read from write: declarations; `bench/domains/banking/records.mld` gains the kind: vocabulary glossary (per `COMMENTS-EVAL-FOLLOWUPS.md` §1).

---

### Phase 2 — bucket → shelf collapse (m-shelf-wildcard already in mlld main)

**Trigger**: Phase 1 lands clean. Same mlld version provides both Phase 1 and Phase 2 features — no inter-phase wait.

This is the largest rig-side change. Bucket collapses into shelf; ~250-300 lines of rig deleted.

#### 2.A — Replace bucket with shelf in rig core

`state.resolved` becomes a wildcard shelf:

```mlld
>> rig/session.mld or wherever planner state shape is defined
shelf @planner_state from @agent.records with {
  versioned: true,
  projection_cache: ["role:planner"]
}
```

`state.capabilities.url_refs` → typed shelf bounded to a single record type:

```mlld
shelf @url_refs from @url_ref_record    >> NOT bare *
```

The bounded `from <record>` form keeps the typed-capability boundary tight. Bare `*` would weaken it: capabilities should accept only the record type they're designed for. (Per m-shelf-wildcard §3.A — this is a scope-tightening detail the spec calls out specifically.)

Functions deleted (per migration impact section of m-shelf-wildcard spec):
- `@mergeResolvedEntries`, `@mergeEntryFields`, `@mergeFieldDict`
- `@stateHandle`, `@stateKeyValue`, `@recordIdentityField`
- `@isResolvedIndexBucket`, `@bucketObject`, `@bucketItems`, `@bucketLength`, `@indexedBucketEntries`
- `@cachedPlannerEntries`, `@populatePlannerCache`
- `@normalizeResolvedValues`
- `@updateResolvedState`, `@updateResolvedStateWithDef`, `@batchSpecMergeState`
- `@projectResolvedSummary`, `@projectResolvedEntry`, `@projectResolvedFieldValue`

`state.extracted` / `state.derived` → unchanged (name-keyed singletons; not in scope per m-shelf-wildcard A8).

#### 3.B — Migrate consumers

Files materially simplified:
- `rig/runtime.mld` — bulk of deletions
- `rig/intent.mld` — bucket walks become shelf reads
- `rig/workers/{resolve,derive,planner}.mld` — entry envelope construction → shelf upsert API

#### 2.C — Drop the rig-side identity heuristics

`@recordIdentityField`'s `id`/`id_`/`*_id` heuristic disappears (records carry `.mx.key`). This was the source of the slack bridge volatility we tactically fixed in commit 1564a53; with the shelf reading `.mx.key` directly, the workaround becomes irrelevant.

Domain records that still declare `id_: handle` + `key: id_` (workspace `email`, `calendar_event`, `file`; banking `scheduled_transaction`, etc.) are not strictly required to drop them — natural-id records are still valid — but a 2.D audit pass can drop them where they're now redundant with auto-derive.

**Files materially touched**:
- `rig/runtime.mld` (massive simplification)
- `rig/intent.mld`
- `rig/workers/*.mld`
- `rig/session.mld`
- `bench/domains/*/records.mld` (optional id_ cleanup)

**Risk**: high. Central state model change touches every consumer. Mutation matrix + scripted suites are the safety net. Phase 0.A invariants finally lock the cross-resolve identity property — if any consumer breaks the property post-migration, those tests catch it.

**Gate**:
- [ ] All gates green
- [ ] Phase 0.A invariants pass (cross-resolve identity now passes uniformly across suites — was the migration goal)
- [ ] **xfail markers removed from `tests/rig/identity-contracts.mld`** for migration-bug-class tests that now pass uniformly (handle-drift cases on slack messages — tests 1 and 2 from §0.A). Removal lands in the same commit as the Phase 2 collapse. The xfail→pass transition is the observable migration milestone; not removing the markers means an XPASS event in the runner, which itself fires red and surfaces the discipline gap.
- [ ] Mutation matrix Overall: OK
- [ ] Bench security canary (slack direct + important_instructions) stays at 0 ASR
- [ ] Bench utility full sweep within ±2 of baseline (78/97)
- [ ] Code reduction target met (~250-300 lines)
- [ ] **Per-key cache invalidation verified**: synthetic test writes entry A, reads entry B and observes a cache hit, writes entry B, reads entry A and observes its cache STILL hit. Without this gate, an implementer could ship per-slot invalidation (matching today's bucket behavior) and lose the per-key cache benefit silently while passing all other tests.
- [ ] **`rig/ARCHITECTURE.md` updated**: phase model, state model, and "shelf vs bucket" framing rewritten — bucket terminology is now historical. State surface section describes wildcard shelf. Lines deleted from rig listed in the migration impact paragraph. Lands in same commit (or immediate follow-up) as the Phase 2 collapse.
- [ ] **`bench/ARCHITECTURE.md` updated**: directory layout still accurate; "What stays / What goes" table reflects bucket no longer existing.
- [ ] **`labels-policies-guards.md` updated**: any bucket framing rewritten as shelf; any references to handle-string identity rewritten as `.mx.key`.
- [ ] **Phase 2 comment refresh in-commit**: deleted helpers' comments delete with them. Surviving helpers in `rig/runtime.mld`, `rig/intent.mld`, `rig/workers/{resolve,derive,planner}.mld` get header + per-section refresh from their `*-comments.txt` shadow drafts. `rig/session.mld` gains shelf-decl explanation. Phase 2.C: `bench/domains/slack/{records,bridge,tools}.mld` drop synthetic-id narrative — bridge collapses to MCP-error guards only.

---

### Phase 3 — Cleanup + polish

After Phase 2 lands, two cleanup sub-phases.

#### 3.A — `state.extracted` / `state.derived` migration (optional, deferred)

Per m-shelf-wildcard A8, these stay as plain typed maps. If name-keyed slot mode lands later in mlld (post-v1 of m-shelf-wildcard), extract/derive collapse into shelf too. ~50-100 additional lines deletable.

Track as a follow-up; don't block Phase 2 closeout.

#### 3.B — Planner prompt + remaining docs

**ARCHITECTURE.md docs land alongside their phase commits, not here.** `rig/ARCHITECTURE.md` and `bench/ARCHITECTURE.md` should be updated in the same commit (or immediate follow-up) as Phase 1.B and Phase 2 — see those phase gates. By the time you reach Phase 3, ARCHITECTURE.md is already current. Phase 3.B handles only:

**Planner prompt rewording** (the LLM-behavior change in the migration):

- "you have made progress when new resolved handles appear" → "...new or changed record identities"
- Any "display projection" references → "read projection"
- Any `display.<role>` references → `read.<role>`
- Authorization framing — record-bound `write.<role>.tools.{authorize, submit}` may warrant a planner-role explanation if the planner prompt previously talked about authorization in terms of tool labels or `can_authorize`

**Discipline**: all wording changes land in ONE commit, with before/after bench-sweep numbers in the commit message (per m-shelf-wildcard A12). If utility regresses beyond ±2 of baseline, the commit gets reverted. Don't split the prompt revision across commits — interleaving structural and wording changes makes the bench-sweep signal noisy.

**Remaining prose docs** (lowest-risk; land after prompt):
- `rig/SECURITY.md` — bucket/handle-string framing → shelf/`.mx.key` framing; update load-bearing examples
- `rig/PHASES.md` — phase descriptions reference shelf state
- `rig/EXAMPLE.mld` — update shelf decl
- `clean/CLAUDE.md` — bucket references rewritten
- `clean/STATUS.md`, `HANDOFF.md` — references updated
- `bench/domains/*/records-comments.txt` — pre-migration narrative comments updated to post-migration state

If ARCHITECTURE.md updates were missed at their phase boundaries (Phase 1.B, Phase 2), catch them here as a fallback. They should not have been missed; if they were, document the slip in `MIGRATION-HANDOFF.md`.

#### Gate to close migration

- [ ] All gates green against latest mlld
- [ ] Pinned binary `.bin/mlld` symlink retired (point to system mlld)
- [ ] Pre-migration archive: `archive/key-hash-improvements.md` retains for history; `migration-plan.md` (this doc) retained as the migration artifact
- [ ] Bench utility full sweep matches or exceeds baseline within stochastic noise
- [ ] Bench security ASR full attack matrix sweep at 0 breaches
- [ ] Mutation matrix expected_fails reflects new architecture
- [ ] Doc pass merged
- [ ] Update STATUS.md "Sweep history" with closeout run IDs
- [ ] **Phase 3.B comment refresh complete**: every `*-comments.txt` shadow draft has been merged into its source file (or explicitly archived). The `clean/*-comments.txt` directory is empty or moved to `archive/comments-drafts/`. `COMMENT-PROCESS.md` and `COMMENTS-EVAL-FOLLOWUPS.md` retain as the methodology + decisions record.

---

## Comment refresh discipline

Comment work piggybacks on code change rather than staging at the end. Three
reasons:

1. Files touched during migration are the natural moment to refresh — the
   diff already shows what changed and the context is in head.
2. Comments describing deleted code are easiest to delete in the same commit
   that deletes the code.
3. Treating Phase 3.B as a one-shot comment pass is fragile: density changes
   can shift planner-LLM behavior at the addendum/instruction layer, and a
   single comment-only commit gives no signal about which file's
   density change broke utility.

### Working drafts as input

Validated comment proposals live as `*-comments.txt` shadow files alongside
each source file. They were produced via the three-cold-read-eval workflow
documented in `COMMENT-PROCESS.md`. Use them as the input to comment edits
during the migration — don't rewrite from scratch. The drafts are graded
"about right" on density by 2 of 3 reviewers; corrections from reviewer
errors are already absorbed.

The shadow drafts that **survive concept-intact through the migration**
(roughly half — file headers, role projection, source-class vocabulary,
worker dispatch shape, threat-model framing, lifecycle, classify,
transforms, policies, validators, agents, addendums) merge with light
edits.

The shadow drafts that **describe mechanisms about to be deleted** (the
other half — bucket helpers, `@stateHandle`/`@recordIdentityField`, the
`can_authorize` framing on tool catalogs, `display:`/`{ref:}` vocabulary,
slack synthetic-id narrative) need section-level rewrites against the
post-migration shape. Apply during the phase that deletes the code, not
before.

### Per-phase comment discipline

**Phase 1.A — rename pass (mechanical commit)**

- IN this commit: rename `display:` → `read:` and `{ref:}` → `{value:}`
  inside both code AND comment text. Inline comment references to those
  vocabulary items rename together with code references — they're part of
  the same mechanical sweep.
- NOT in this commit: header refresh, ticket-ref strip, narrative
  rewrites. Preserves the clean-revert property the rename relies on.

**Phase 1.A.2 — comment-refresh follow-up commit**

- Touch only files renamed in 1.A.
- Strip ticket refs (`c-*`, `m-*`, `b-*`), "previously", "phase 1/2",
  pre-fix narratives in those files.
- Apply file-header orientation block from the corresponding
  `*-comments.txt` shadow draft.
- Independent revert from 1.A; if a header introduces noise, roll back
  this commit alone.

**Phase 1.B — `write:` declarations + policy synth**

Comment refresh travels in-commit with the structural change, since the
mental model itself shifts:

- All `bench/domains/*/records.mld`: replace facts/data + can_authorize
  framing in comments with the records-as-security-contract framing
  from the shadow drafts. Banking is canonical; the other three suites
  reference banking's glossary.
- `bench/domains/banking/tools.mld`: drop comments referencing
  `can_authorize`. Tool catalog comments now describe a pure operation
  registry.
- `rig/orchestration.mld`: rewrite the policy-synthesis comment to
  describe reading `write:` from input records (not `can_authorize:
  false` from tools).
- The kind: vocabulary glossary (extracted to
  `COMMENTS-EVAL-FOLLOWUPS.md` §1) lands in
  `bench/domains/banking/records.mld` as a header section. Other suites
  reference back.

**Phase 2.A/B/C — bucket → shelf collapse**

The bulk of comment cleanup. Each deleted function takes its comment with
it. Surviving helpers get comment refresh in-commit with the simplification.

- `rig/runtime.mld`: huge comment shrink. The shadow draft's per-section
  organization roughly mirrors what gets deleted (state mutation, bucket
  walks, indexed bucket adapters, planner cache, projection helpers).
  After Phase 2 the shadow draft for runtime.mld is half its current
  length — which matches the file shrinkage.
- `rig/intent.mld`: "indexed resolved buckets" section in the shadow
  draft deletes wholesale. Source-class table survives. Error-code
  glossary survives (extracted to followups §2).
- `rig/workers/{resolve,derive,planner}.mld`: comment narrative shifts
  from "construct entry envelope, mint handle, merge into bucket" to
  "shelf upsert."
- `rig/session.mld`: shelf decl gets a header explaining the shelf
  primitive vs the prior `var session` storage approach.

**Phase 2.C — identity heuristic cleanup**

- `bench/domains/slack/{records,bridge}.mld`: synthetic-id narrative
  disappears. The shadow draft for `slack/bridge-comments.txt`
  collapses to MCP-error guards only — the file becomes ~30% of its
  current length.
- `rig/runtime.mld`: any remaining `@stateHandle` / `@recordIdentityField`
  rationale comments delete with the functions.

**Phase 3.A — deferred**

If `state.extracted` / `state.derived` later collapse into shelf, their
comment narrative collapses the same way. Tracked but not in scope.

**Phase 3.B — surviving-intact half + planner prompt**

Files NOT touched in phases 1-2 get their first comment refresh here.
This is the bulk of:

- `rig/workers/{advice,compose}.mld` (concepts intact; light header refresh)
- `rig/{classify,diagnostics,lifecycle}.mld` (concepts intact; mechanical)
- `rig/transforms/{url_refs,parse_value}.mld` (concepts intact)
- `rig/policies/url_output.mld` (concepts intact)
- `rig/validators/output_checks.mld` (concepts intact; status note may
  flip from "reference primitive, not wired" to "wired by default" if
  recurring-question #2 from the eval is acted on)
- `bench/agents/*.mld` (per AGENTS-COMMENTS.txt)
- `bench/domains/*/prompts/planner-addendum.mld` (per
  PROMPTS-ADDENDUMS-COMMENTS.txt)
- `bench/domains/*/bridge.mld` (per per-suite bridge-comments)
- `bench/domains/travel/classifiers/*.mld` and `classifier-labels.mld`
  (per CLASSIFIERS-COMMENTS.txt)

Planner prompt rewording (the LLM-behavior change) is a separate
in-this-phase commit — see existing §3.B. Comment work is the
follow-up that catches the surviving-intact half.

### Per-phase gates

Add to each phase's gate list:

- [ ] Comments refreshed for files materially touched in this phase
      (consult `<file>-comments.txt` for proposed text; mark shadow
      draft as merged once the source file's comments are live).

By Phase 3.B closeout: the `*-comments.txt` directory is empty (every
draft has been merged) or archived under `archive/comments-drafts/` if
useful for reference. The eval transcripts and `COMMENT-PROCESS.md`
methodology stay as the discoverable record of how the comments were
graded.

### What survives without rewrite vs. what gets section-deleted

For sizing, in case Phase 1.B / Phase 2 sessions want to estimate scope:

| Shadow draft | Survives intact | Section-deletes | Notes |
|---|---|---|---|
| rig/index | yes | — | public surface stable |
| rig/session | mostly | — | header gains shelf decl explanation |
| rig/lifecycle | yes | — | |
| rig/classify | yes | — | |
| rig/diagnostics | yes | — | |
| rig/orchestration | mostly | policy synth para rewrites at Phase 1.B | |
| rig/tooling | partial | `can_authorize` arg classification rewrites at Phase 1.B | |
| rig/intent | partial | "indexed resolved buckets" entire section at Phase 2 | source-class table + error-code glossary survive |
| rig/runtime | partial | state mutation, bucket walks, projection cache helpers all delete at Phase 2 | header survives; helpers shrink to half |
| rig/planner_inputs | yes | — | rename touches `{ref:}` → `{value:}` reference |
| rig/workers/{advice,compose,classify} | yes | — | |
| rig/workers/{resolve,extract,derive,execute,planner} | partial | per-section refresh during Phase 2 | shape stays; helpers shift |
| rig/workers/WORKERS-SHARED | yes | — | step-6 lifecycle split unchanged |
| rig/transforms/* | yes | — | |
| rig/policies/url_output | yes | — | |
| rig/validators/output_checks | yes | — | wire-by-default flip in header is a status edit, not structural |
| bench/domains/banking/records | partial | facts/data+can_authorize framing rewrites at Phase 1.B | new write: section ships in same edit |
| bench/domains/banking/tools | partial | `can_authorize` content drops at Phase 1.B | |
| bench/domains/workspace/records | partial | per-suite write: blocks add at Phase 1.B | |
| bench/domains/workspace/tools | partial | as above | |
| bench/domains/slack/records | substantial | synthetic-id narrative drops at Phase 2.C | |
| bench/domains/slack/bridge | substantial | bridge collapses to MCP-error guards only | |
| bench/domains/slack/tools | partial | as records | |
| bench/domains/travel/* | partial | as banking | |
| bench/agents/* | yes | — | travel delta stays as written; ASR-numbers move to threat model per shadow |
| bench/domains/*/prompts/* | yes | — | one-line orientation only |
| bench/domains/travel/classifiers/* | yes | — | |
| rig/NON-PRODUCTION-FILES | yes | — | |

---

## Test coverage strategy

The migration leans on three test tiers, each catching different regression classes.

| Tier | Cost | Catches | Run frequency |
|---|---|---|---|
| **Tier 1: Zero-LLM invariant gate** (`mlld tests/index.mld`) | $0, ~10s | Structural regressions, runtime contract violations | Every change |
| **Tier 2: Scripted-LLM security tests** (`tests/run-scripted.py`) | $0, ~30s | Security-layer regressions, defense-by-defense coverage | Every rig/record change |
| **Tier 3: Live-LLM gates** | seconds-minutes per task, $0.01-$1 | End-to-end behavior, prompt regression, real-LLM judgment | Phase boundaries + closeout |

**The migration's most important new testing investment is Phase 0.A** — invariant tests in `tests/rig/` that encode the contracts the migration must preserve. These are zero-LLM, fast, and architectural: they catch the kind of bug that mutation matrices and scripted security tests don't (cross-call identity stability, entry shape, projection cache correctness).

**Layer assertions (c-0458) are the second-most important** — they encode WHICH defense layer fires for each test, so a migration that accidentally moves a defense to a different layer fails loudly even if security still holds in aggregate.

**Mutation matrix snapshot** is the third — it catches "we deleted a defense and didn't notice because no test specifically exercised it."

---

## Pinned binary discipline

`./.bin/mlld` is the development anchor for **Phase 0 only**. Both mlld features required for Phases 1-3 are already in main, so the binary's role is purely to keep the test surface green during pre-migration test buildout.

While in Phase 0:
- Run all gates with `./.bin/mlld <file>` (or `PATH=$PWD/.bin:$PATH`)
- CI (if any) pinned to same binary
- DO NOT install a newer mlld globally that supersedes the pinned shim during Phase 0; the version drift between local development and the pinned baseline is what keeps Phase 0 work landable cleanly

**Cutover**: when Phase 0 lands and we're ready for Phase 1:
- Swap `./.bin/mlld` symlink target to system `mlld` (or simply remove the pin and use system PATH)
- Run all gates against system mlld; expect many to fail until the **full Phase 1 unit lands** — display: blocks won't parse, write tools won't dispatch (deny-by-default), etc.
- **Phase 1 lands as one semantic unit** (rename + write: declarations + policy synth + can_authorize migration). Gates do not return to green between 1.A and 1.B. See Phase 1 section for detail; the rename-only intermediate can't ship green.

Stay on system mlld from cutover through Phase 3 closeout.

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| m-rec-perms-update changes shape during specification | low | rework Phase 1.B | spec is at v0.3 with rig-side review incorporated; remaining changes likely cosmetic |
| Mutation matrix expected_fails shifts unexpectedly | high | reclassification effort within session | snapshot before migration, diff after, document each shift in commit message |
| Policy synthesis change introduces silent security regression | medium | breach in attack sweep | mutation matrix + scripted security tests + post-Phase-1 slack security canary |
| Slack utility regresses post-cutover | medium | utility floor drops | baseline numbers checked-in; run sweep at each phase boundary |
| Planner prompt revision hurts utility | medium | utility regression | bench-sweep before/after in same commit per m-shelf-wildcard A12; all wording changes land together for clean before/after signal |
| Per-key cache invalidation regressed to per-slot in Phase 2 | medium | perf benefit lost silently | explicit Phase 2 gate: synthetic test verifies per-key invalidation, not per-slot |
| Phase 2 surfaces an unmodeled cross-resolve interaction | medium | +1-2 debug sessions | Phase 0.A invariants are the canary; they fire red before bench-side regression |
| Pinned binary drifts further from main mlld | low | larger jump at cutover | rebuild records-baseline if mlld bugfixes affect it |
| `state.extracted` / `state.derived` retain bucket-shape pattern | low | residual ~50-100 lines | tracked as Phase 3.A follow-up, name-keyed slot mode in mlld |

---

## Sequencing summary

```
Phase 0 (NOW)              ┃ Cutover ┃   Phase 1                          Phase 2                          Phase 3
──────────────             ┃─────────┃   ──────────────────────────       ───────────────────────────      ─────────────────
Invariant tests            ┃ swap    ┃   display: → read: rename          bucket → shelf collapse          docs + prompt rewrite
Baselines                  ┃ .bin/   ┃   {ref:} → {value:} mode rename    ~250-300 lines deleted           pin retire
c-0458 Days 2-5            ┃ mlld →  ┃   with { display } → { read }      consumers migrated               final sweep
Mutation snapshot          ┃ system  ┃   add write: declarations          url_refs → typed shelf           gate: closeout
                           ┃ mlld    ┃   drop can_authorize               gate: invariants pass uniformly
(no comments yet)          ┃         ┃   simplify policy synth            gate: per-key cache verified
                           ┃         ┃   mutation reclassify              gate: ASR holds
                           ┃         ┃   1.A.2: header refresh follow-up  comment cleanup in-commit       3.B: surviving-half
                           ┃         ┃   1.B: records-as-policy comment   (slack bridge collapses,        comment merge
                           ┃         ┃   refresh in-commit                 deleted-helper comments
                           ┃         ┃   gate: ASR holds                   delete with code)
Pinned binary              ┃         ┃   System mlld (both features)      System mlld                      System mlld
```

Critical path: Phase 0 → cutover (one swap) → Phase 1 → Phase 2 → Phase 3.

**No inter-phase mlld wait.** Both m-rec-perms-update and m-shelf-wildcard are in mlld main. The cutover is a single swap of `./.bin/mlld` for system `mlld`. Phases 1, 2, 3 run back-to-back from there.

---

## What to do today (and from here)

**Phase 0 against pinned binary** — the only "wait" content is now waiting on Phase 0 work to complete before cutover:

1. Continue c-0458 Day 2 (slack scripted layer assertions) against `./.bin/mlld`
2. Build Phase 0.A invariants in `tests/rig/identity-contracts.mld` (cross-resolve identity, entry shape, no-progress) — see migration-resilience note in §0.A.4
3. Capture Phase 0.B baselines (mutation matrix snapshot, utility/security from STATUS.md `Sweep history` entries)

**When Phase 0 lands**: cut over to system mlld and execute Phases 1 → 2 → 3 back-to-back. No external wait.

The work in (1)-(3) is independently valuable — layer assertions and invariants pay for themselves regardless. They're now also the ONLY blocker on cutover, so finishing Phase 0 unlocks the whole migration.

---

## Cross-references

- mlld tickets: m-d49a (`.mx.key`, landed), m-f947 (`.mx.hash`, landed), m-fe08 (visibility decoupling — **subsumed by m-rec-perms-update v0.2**, no separate ship event), m-rec-perms-update (read/write declarations + visibility decoupling — **in mlld main**), m-shelf-wildcard (shelf wildcard — **in mlld main**)
- Local: `archive/key-hash-improvements.md` (superseded), `STATUS.md` (current bench results), `HANDOFF.md` (session context), `CLAUDE.md` (running benchmarks operational guide)
- Comment work: `COMMENT-PROCESS.md` (cold-read methodology), `COMMENTS-INDEX.md` (shadow-draft index), `COMMENTS-EVAL-FOLLOWUPS.md` (eval decisions + canonical glossaries), `*-comments.txt` (per-source-file shadow drafts; merge during phases per "Comment refresh discipline" above)
- Pinned binary: `~/mlld/mlld-records-baseline/bin/mlld-wrapper.cjs` via `./.bin/mlld`
