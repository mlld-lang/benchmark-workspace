# HANDOFF.md — migrator-8 end-of-session

Session breadcrumb. Forward-looking only. Read at session start.

**For the next session: run `/migrate`.** Migration session continues on branch `policy-structured-labels-migration`. The `/migrate` skill loads three-tier separation + spike-then-test discipline; `/rig` gives general framework context but won't surface migration-specific structure.

## What this session did

Phase 0 + Phase 1 fully complete; opened the cross-cutting Phase 3 BasePolicy migration that unblocks all per-suite work. Eight commits on the migration branch.

### Phase 0 — Setup ✅

- Migration branch `policy-structured-labels-migration` created off `clean@096bcd2`.
- Five thematic commits captured the prior-session working-tree state:
  - `3737ea6` migration: infrastructure (MIGRATION-PLAN renamed, MIGRATION-TASKS, SEC-HOWTO, migrate skill, CLAUDE.md three-tier section).
  - `062285e` sec-docs: per-suite threat models + 55 threat tickets in `.tickets/threats/`.
  - `f8232ad` tickets: 46 closures + 8 moved to `.tickets/review/` + c-5f4d filed.
  - `93036ea` rig/policies: url_output URL-smuggling defense + tests lockfile.
  - `48bc93e` HANDOFF: migration session begins.

### Phase 1 — sec-doc authoring ✅

All 5 docs landed and verified per SEC-HOWTO 10-section template + 5-mark scheme:

| Doc | [T] | [-] | [?] | [!] | [ ] | Filed-tickets table |
|---|---|---|---|---|---|---|
| sec-banking | 0 | 11 | 22 | 1 | 3 | ✓ (19 BK-* tickets) |
| sec-slack | 5 | 40 | 16 | 5 | 4 | ✓ (10 SL-* tickets) |
| sec-workspace | 0 | 60 | 22 | 20 | 7 | ✓ (WS-* tickets) |
| sec-travel | 16 | 26 | 9 | 4 | 2 | ✓ (TR-* tickets — most mature) |
| sec-cross-domain | 0 | 6 | 3 | 1 | 6 | ✓ (XS-* tickets) |

55 threat tickets total in `.tickets/threats/`. No orphan marks; every uncertain mark links to a ticket inline. No coverage roll-up tables (drift surface).

### Phase 3 cross-cutting — BasePolicy schema migration (started)

Commit `31d1ace` re-authors `rig/orchestration.mld @synthesizedPolicy` against the v2.x `labels:` / `dataflow:` schema:

- Imports `@standard` + `@urlDefense` from `@mlld/policy`. `@standard` ships `labels.{rules, apply, args}` stanzas; `@urlDefense` ships `dataflow.{enrich, check}`.
- Drops the named-rule string list (no-secret-exfil, etc. — retired upstream).
- Uses new-schema `labeling: { unlabeled: "untrusted" }` keyword.
- Verified via `tmp/policy-spike/probe-policy-build-data.mld` that `@policy.build` accepts the new-schema data shape directly — no need to declare `policy @p = union(...)` at module scope (which would fail because rig overlay depends on runtime tool catalog).
- Rig overlay additively widens `labels.rules.influenced.deny` to also block destructive + exfil; preserves `trusted_tool_output` + `user_originated` `satisfies:` for fact-equivalent positive checks.

`rig/workers/advice.mld` updated to `policy @adviceGatePolicy = union(@noInfluencedAdvice)` (imported fragment).

`tests/rig/policy-build-catalog-arch.mld` test updated to assert new-schema presence: `labels.args["exfil:send"].recipient`, `labels.apply["trust:untrusted+llm"]`, `dataflow.check.length > 0`. Test passes 20/20 in isolation.

Spike probes preserved in `tmp/policy-spike/`:
- `probe-standard-import.mld` — `@standard + @urlDefense` composes cleanly.
- `probe-influenced-union.mld` — `union()` merges deny arrays additively.
- `probe-union-in-exe.mld` — proves `union()` is NOT valid as a general expression.
- `probe-policy-in-exe.mld` — proves `/policy` declarations are module-scope only.
- `probe-standard-shape.mld` — proves `@standard` is field-accessible.
- `probe-policy-build-data.mld` — proves `@policy.build` accepts data-shape basePolicy without `union()`.

Commit `5a03de1` filed ticket **c-3162-dispatch-wrap** for the surfaced gap: when the new `labels.rules.influenced.deny` correctly fires on dispatch, the throw propagates past `@dispatchExecute` because there's no wrapper around `@callToolWithPolicy`. Defense IS firing structurally; envelope shape needs the wrapper for diagnostic readability.

## Where we are

- **Branch**: `policy-structured-labels-migration` on `clean@5a03de1`.
- **mlld**: `policy-redesign` @ `f90d47e77` — runtime is the migration target.
- **Zero-LLM gate**: YELLOW — BasePolicy migration parses, 20/20 policy-build-catalog-arch tests pass, but `tests/rig/c-3162-dispatch-denial.mld` fails at module-load because dispatchExecute doesn't wrap the policy throw. Other tests may surface similar throw-vs-return shape issues.
- **Worker LLM gate**: not run this session (skipped — gate dependencies still resolving).
- **Bench utility**: 53/97 baseline from migrator-7 (2026-05-12 sweep `25710915492` et al). No new sweep this session.

## Priority queue for next session

1. **c-3162-dispatch-wrap** (filed this session) — wrap `@callToolWithPolicy` in `@dispatchExecute` with `when [denied => ...]` arm so policy throws surface as `{ ok: false, stage: "dispatch_policy", failure: { ... } }`. Unblocks c-3162-dispatch-denial test and similar shape across suites. P0 — closest path to green gate.

2. **Sweep remaining zero-LLM test breakages.** Run `mlld tests/index.mld --no-checkpoint` and triage each failing suite. Most likely classes:
   - Throw-vs-return shape (same family as c-3162-dispatch-wrap).
   - Records using retired `when:` shape that needs `refine [...]` per MIGRATION-POLICY-REDESIGN.md §"Record refine".
   - Tests asserting old basePolicy shape (`defaults.rules`, `operations:`) — re-author to new schema.

3. **Phase 3.a tools punch list (banking)** — once gate is green, walk `bench/domains/banking/tools.mld` against `sec-banking.md §3`. Likely no major changes; confirm.

4. **Phase 3.b records redraft (banking)** — `bench/domains/banking/records.mld` against `sec-banking.md §4`. Apply v2.x `refine [...]` shape, verify `facts:` / `data.trusted:` / `data.untrusted:` declarations match the threat model. Spike each declaration in `tmp/records-banking/`.

5. **Phase 3.d test lockdown (banking)** — promote `[?]` marks in sec-banking §5/§8 to `[T]` where feasible via tier-1 (`tests/rig/`) or tier-2 (`tests/scripted/security-banking.mld`) tests. Don't promote against tier-3 sweep evidence.

6. **Suite exit gate (banking)** — zero-LLM green, worker LLM green, local probe of UT0/UT3/UT4/UT6/UT11, attack canary `scripts/bench-attacks.sh single direct banking` at 0 ASR. Then move to slack → workspace → travel.

7. **Per-suite continuation** — slack/workspace/travel follow banking's pattern. Travel is most mature (16 [T] marks); banking + workspace need the most records-side work.

8. **Phase 4 ship gate** — full benign sweep (≥78/97 utility), full 6×5 attack matrix (0 ASR), Phase 7 whack-a-mole reconciliation per MIGRATION-PLAN. Archive `*.threatmodel.txt`, `*.taskdata.txt`, `MIGRATION-PLAN.md`, `MIGRATION-TASKS.md` to `archive/`.

## What NOT to do

- Don't merge back to main until gate is green AND attack canaries verified. The branch IS the migration container.
- Don't pre-revert this session's bench-side overlay commits (`f168037`, `096bcd2` on main, plus the satisfies declarations now in orchestration.mld). They stay until v2.x verifies they're structurally redundant.
- Don't workaround retired-syntax errors by avoiding the affected code path. The errors are the migration's punch list — answer each with a migration, file a ticket, or both.
- Don't add task-id-specific or evaluator-shaped behavior anywhere (Cardinal Rule A + Prompt Placement Rules in CLAUDE.md).
- Don't write summary documents at session end. Update HANDOFF + MIGRATION-TASKS; don't create new wrap-up artifacts.

## Verification gates

```bash
mlld tests/index.mld --no-checkpoint              # zero-LLM gate (currently YELLOW)
mlld tests/live/workers/run.mld --no-checkpoint   # worker LLM (not run this session)
mlld tests/rig/policy-build-catalog-arch.mld --no-checkpoint  # 20/20 ✓ this session
mlld tests/rig/c-3162-dispatch-denial.mld --no-checkpoint     # FAIL — c-3162-dispatch-wrap

uv run --project bench python3 src/run.py -s banking -d defended -t user_task_3 user_task_4 user_task_6 user_task_11 -p 4
scripts/bench-attacks.sh single direct banking
```

## Useful pointers

- `.claude/skills/migrate/SKILL.md` — `/migrate` skill, three-tier separation + spike-then-test
- `MIGRATION-PLAN.md` — 8-phase mlld-side cutover plan
- `MIGRATION-TASKS.md` — phase tracker (this session marked Phase 0 + Phase 1 complete)
- `SEC-HOWTO.md` — authoring guide for sec-*.md
- `sec-{banking,slack,workspace,travel,cross-domain}.md` — threat models (all 5 landed)
- `~/mlld/mlld/MIGRATION-POLICY-REDESIGN.md` — mlld-side migration patterns + checklist
- `~/mlld/mlld/spec-label-structure.md` — v2.x value-metadata channels
- `~/mlld/mlld/spec-policy-box-urls-records-design-updates.md` — v2.x policy schema
- `tmp/policy-spike/` — six probes verifying schema/union semantics
- `.tickets/c-3162-dispatch-wrap.md` — filed this session, P0
- `.tickets/threats/` — 55 sec-doc tickets (BK / SL / WS / TR / XS)
- `STATUS.md` — bench results (53/97 measured, ceiling 81/97)
- `rig/ARCHITECTURE.md` — three-tier separation specifics
- `mlld-security-fundamentals.md` — current security model narrative (labels, factsources, records, refine, shelves, sessions)
- `DEBUG.md` — investigation methodology
