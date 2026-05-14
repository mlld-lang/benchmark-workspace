# HANDOFF.md — v2.x migration begins next

Session breadcrumb. Forward-looking only. Read at session start.

**For the next session: run `/migrate`.** This is a migration session, not general rig/bench work. The migrate skill (`.claude/skills/migrate/SKILL.md`) loads exactly the context you need — it's been rewritten for this cutover and includes the three-tier separation discipline, spike-then-test rhythm, and required reading list. `/rig` will give you general framework context but won't surface the migration-specific structure.

## What this session did

A diagnosis session that ended with a major architectural pivot. We started chasing per-bug fixes (m-aecd shelf re-tainting, m-9f33 §4.2-(B), m-c00b whole-object input), shipped five surgical mlld fixes, and then recognized the bug pattern as architectural — every one was the same shape: **aggregation defeats per-field sanitization**. That recognition pointed at the existing `~/mlld/mlld/spec-label-structure.md` + `~/mlld/mlld/spec-policy-box-urls-records-design-updates.md` as the proper target architecture, and the rest of the session set up the infrastructure to migrate to that target cleanly.

## Where we are

- **Current measured utility**: 53/97 (last full sweep 2026-05-12). No new full sweep this session — final canonical-6 probe was 0/6, but failure modes shifted from "cycle blindly through arg shapes" to "block cleanly with transcript-grounded reasoning." That's the right kind of progress; score recovery comes when the v2.x migration lands.
- **Security verified**: 0/105 ASR on slack `atk_direct` + `atk_important_instructions` canaries (runs `25708270888`, `25708271819`).
- **Achievable ceiling**: 81/97. Reachable post-migration; the migration's acceptance gate is ≥78/97 utility AND 0 ASR across the full 6×5 attack matrix.
- **mlld**: branch `2.1.0` HEAD carries five fixes from this session (the as-record divergence + m-aecd + m-9f33 + m-c00b + e8ff25521/034af723e). Spec-implementations live on the `policy-redesign` branch — that's the migration target.
- **Zero-LLM gate**: 266/0/4 ✅. Will need to migrate alongside records redraft.

## What landed this session

### Five rig commits (still relevant in the new architecture)

- `4d2b0c0` Cluster I masking fix — `@buildPhaseErrorLogEntry` + `@buildPhaseErrorResult` helpers in `rig/workers/planner.mld` surface mlld's structured policy-error envelope (code / field / hint / message) to the planner's next-turn input. Behavioral pivot: planner stops cycling on opaque errors, blocks cleanly with reason. Test at `tests/rig/phase-error-envelope.mld` (2/2 green).
- `4b4b894` Worker prompt fixes — derive.att file-load artifact + compose.att JSON-enforcement strengthening.
- `10d861a` Compose anti-fabrication — refuses to claim sent/created when no successful execute. Eliminates BK UT3 / TR UT3 / BK UT6 "we sent it" lying. Transitional per `c-5f4d` (closed; structural enforcement post-migration is a separate concern, not blocking).
- `fa21cb7` Cluster II planner.att nudge — teaches the planner to use derive selection_refs as control-arg ref shape, with `field` slot when needed. Structural framing, not task-shaped.
- `f168037` + `096bcd2` Banking records refine-trust + `@deriveAttestation.payload` data.trusted widening — these become unnecessary under the v2.x model (§2.4 LLM-pass invariants handle this) but stay spec-compliant; revert during migration if the new schema makes them no-ops.

### Migration plumbing (the work that teed up the next session)

- **`MIGRATION-PLAN.md`** — 8-phase plan for the clean repo adopting the policy-redesign + structured-labels work. Already existed; verified current.
- **`SEC-HOWTO.md`** — authoring guide for per-suite security/threat-model docs replacing `*.threatmodel.txt`. Ten-section template. Five-mark maturity ladder (`[ ]` / `[!]` / `[?]` / `[-]` / `[T]`) with ticket-anchored uncertain marks, citation-required certain marks, tier-3 sweeps explicitly excluded from `[T]`. Suite-specific extension patterns for banking (fact-grounding), slack (URL promotion + channel-name firewall), workspace (typed-instruction-channel refusal), travel (advice gate).
- **`sec-banking.md`** — v1 draft. Needs tightening per SEC-HOWTO (drop §10/§12/§14, drop coverage roll-up, renumber, adopt 5-mark scheme). Other three suites + cross-domain doc are first task in Phase 1.
- **`MIGRATION-TASKS.md`** — temporary task tracker. Phase 0 (setup) → Phase 1 (sec-doc authoring) → Phase 2 (audit via probes) → Phase 3 (per-suite migration: banking → slack → workspace → travel) → Phase 4 (full sweep + ship). Each phase has explicit exit criteria.
- **`.claude/skills/migrate/SKILL.md`** — rewritten for v2.x cutover. Loads three-tier separation discipline, spike-then-test rhythm, per-suite exit gates, negative-discipline rules (no prompt-as-defense, no eval-shaping, no tier-bleeding fixes, etc.). Step 0 is `mlld qs` so you actually know how to write mlld before touching records.
- **`CLAUDE.md` updated** — added three-tier separation section after Cardinal Rules; replaced strict prompt-approval rule with iteration discipline + escape-hatch pattern (`USER REVIEW: {title}` P0 ticket for borderline cases).

### Ticket cleanup

- 67 → 26 open tickets. 46 closed across two passes (must-close + probably-obsoleted + agent-reviewed close batch + reframes).
- 8 tickets moved to `.tickets/review/` for individual triage: c-5041, c-debc, c-5ef9, c-3edc, c-63fe, c-a873, c-6479, c-f97d. These are real architectural primitives + active infra + migration-conditional reframes that survive the cutover but need individual reads.
- 5 tickets reframed under the new architecture: c-891b, c-6479, c-f97d, c-4564, c-634c. Titles + bodies updated to express the concern under structured-labels + policy-redesign vocabulary.

## Working-tree state (uncommitted)

```
M  CLAUDE.md                                  — three-tier section + prompt discipline rewrite
?? SEC-HOWTO.md                               — authoring guide
?? sec-banking.md                             — v1 draft
?? MIGRATION-TASKS.md                         — phase tracker
?? TICKET-REVIEW-PROMPT.md                    — prompt for the agent-driven ticket review (used; can archive)
M  .claude/skills/migrate/SKILL.md            — rewritten for v2.x cutover
?? .tickets/review/                            — 8 tickets moved here for individual review
   (plus the 46 closed tickets across two passes — all in main .tickets/)
```

Plus the 5 rig commits listed above are already committed on `main` and pushed.

**Phase 0 step 1 for the next session: commit current state, then start Phase 1 sec-doc authoring.**

## Priority queue for next session

1. **Phase 0 (Setup)** per `MIGRATION-TASKS.md`:
   - Commit the uncommitted working-tree state above.
   - Create migration branch `policy-structured-labels-migration`.
   - Verify all the specs/plan/howto/skill/tasks files are current.
2. **Phase 1 (sec-doc authoring)** — first real work:
   - Tighten `sec-banking.md` per SEC-HOWTO checklist (drop §10/§12/§14, drop roll-up, renumber, 5-mark scheme).
   - Write `sec-slack.md` from current `slack.threatmodel.txt` + code.
   - Write `sec-workspace.md`.
   - Write `sec-travel.md`.
   - Write `sec-cross-domain.md` after the four single-suite docs surface deferred items.
3. **Phase 2 (audit current state vs sec-docs)** — probe every `[-]` and `[?]` claim. Mark transitions per spike-then-test discipline. File tickets for any gaps.
4. **Phase 3 (per-suite migration)** — banking → slack → workspace → travel. Per-suite exit gate (no orphan `[?]`, attack canary 0 ASR for that suite) before next suite.
5. **Phase 4 (full sweep + ship)** — utility ≥78/97 AND 0 ASR across 6×5 matrix.

## Hard rules carried forward (from the migrate skill)

- **Spike-then-test before structural commits.** Every `[?]` mark in a sec-doc needs either `[-]` (citation: commit SHA + probe path) or `[T]` (tier-1 or tier-2 test). Tier-3 sweeps don't lock anything.
- **Three-tier separation** (mlld / rig / bench). Don't bridge tiers in bench; file a mlld ticket instead.
- **No prompt-as-defense.** Defense nodes in sec-doc trees must be structural.
- **No eval-shaping.** Don't read AgentDojo `utility()` / `security()` bodies. Don't lift eval examples into prompts.
- **Prompts must be minimal.** Claude has a habit of over-explaining and lifting eval examples. Don't.
- **Escape hatch** for borderline prompt changes: proceed + file `USER REVIEW: {title}` P0 ticket. See CLAUDE.md Prompt Placement Rules for the full discipline.
- **Stop-on-mlld-bug**: file `~/mlld/mlld/.tickets/m-XXXX` with probe attached, wait. Don't workaround unless small + on-target.
- **Acceptance gate is two-dimensional**: ≥78/97 utility AND 0 ASR.

## What NOT to do

- Don't run the full attack matrix until the suite-by-suite migration is complete. Per-suite canaries during migration; full matrix at ship.
- Don't pre-revert this session's bench-side commits (`f168037`, `096bcd2`). They stay until the v2.x migration verifies they're no-ops under the new model.
- Don't write a session-end document or close work without user direction. Update HANDOFF + tasks tracker; don't create new wrap-up artifacts.
- Don't approach this as a series of patches. This is one coherent cutover; the migration is the work, not a backlog of small fixes.

## Verification gates

```bash
mlld tests/index.mld --no-checkpoint              # zero-LLM, target 266/0/4
mlld tests/live/workers/run.mld --no-checkpoint   # worker LLM, target 24/24
mlld tests/rig/phase-error-envelope.mld --no-checkpoint  # masking-fidelity regression, 2/2
uv run --project bench python3 src/run.py -s <suite> -d defended -t user_task_N  # per-task probe
scripts/bench-attacks.sh single direct <suite>     # per-suite attack canary
scripts/bench.sh                                  # full benign sweep (ship gate)
scripts/bench-attacks.sh                          # full 6×5 attack matrix (ship gate)
```

## Useful pointers

- **`.claude/skills/migrate/SKILL.md`** — run `/migrate` to load it. Three-tier separation, spike-then-test, per-suite gates.
- **`MIGRATION-PLAN.md`** — 8-phase mlld-side cutover plan.
- **`MIGRATION-TASKS.md`** — temporary task tracker for this migration.
- **`SEC-HOWTO.md`** — authoring guide for per-suite security docs.
- **`sec-banking.md`** — v1 draft for the banking suite (needs tightening).
- **`CLAUDE.md`** — Cardinal Rules + three-tier separation + Prompt Placement Rules (with escape hatch).
- **`STATUS.md`** — canonical per-task bench classification + sweep history.
- **`rig/ARCHITECTURE.md`** — three-tier separation specifics + phase model.
- **`mlld-security-fundamentals.md`** — labels, policies, guards, records, refine, shelves (current model).
- **`~/mlld/mlld/spec-label-structure.md`** — v2.x value-metadata channel design.
- **`~/mlld/mlld/spec-policy-box-urls-records-design-updates.md`** — v2.x policy schema.
- **`.tickets/review/`** — 8 tickets pending individual triage against new architecture.

## Session continuity note

The architectural pivot mid-session means the working-tree state combines (a) earlier-session surgical-fix work that survives the migration and (b) later-session migration-prep that supersedes it. Both are intentional. The five rig commits already on `main` are durable; the docs in the working tree (SEC-HOWTO, sec-banking, MIGRATION-TASKS, the CLAUDE.md + migrate-skill rewrites) are the bridge to the next session.

When committing the working-tree state, group thematically:
1. CLAUDE.md + migrate SKILL.md changes — discipline + tier-separation + escape hatch
2. SEC-HOWTO.md + sec-banking.md (and archive TICKET-REVIEW-PROMPT.md if it served its purpose) — security-doc authoring infrastructure
3. MIGRATION-TASKS.md — temporary tracker

The 46 ticket closures and the `.tickets/review/` moves can land in their own commit (or fold into one of the above).
