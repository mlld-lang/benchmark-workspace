# HANDOFF.md — migrator-8 end-of-session

Session breadcrumb. Forward-looking only. Read at session start.

**For the next session: run `/migrate`.** Migration session continues on branch `policy-structured-labels-migration`. The `/migrate` skill loads three-tier separation + spike-then-test discipline; `/rig` gives general framework context but won't surface migration-specific structure.

## What this session did

Phase 0 + Phase 1 fully complete; opened the cross-cutting Phase 3 BasePolicy migration that unblocks all per-suite work. Commits on the migration branch: `3737ea6` infra, `062285e` sec-docs + 55 threat tickets, `f8232ad` 46 ticket closures + 8 to `.tickets/review/`, `93036ea` url_output defense, `48bc93e` + `0c69128` HANDOFFs, `31d1ace` BasePolicy migration, `5a03de1` c-3162-dispatch-wrap ticket, `0cd3d8c` MIGRATION-TASKS update.

### Phase 1 sec-doc maturity (5-mark scheme)

| Doc | [T] | [-] | [?] | [!] | [ ] |
|---|---|---|---|---|---|
| sec-banking | 0 | 11 | 22 | 1 | 3 |
| sec-slack | 5 | 40 | 16 | 5 | 4 |
| sec-workspace | 0 | 60 | 22 | 20 | 7 |
| sec-travel | 16 | 26 | 9 | 4 | 2 |
| sec-cross-domain | 0 | 6 | 3 | 1 | 6 |

55 threat tickets in `.tickets/threats/`. Every uncertain mark linked to a ticket; no coverage roll-ups.

### Phase 3 BasePolicy cross-cutting (commit `31d1ace`)

`rig/orchestration.mld @synthesizedPolicy` and `rig/workers/advice.mld` migrated to v2.x schema. Imports `@standard` + `@urlDefense` from `@mlld/policy`, produces new-schema data shape directly. Key finding from spike probes (`tmp/policy-spike/`, six probes): `@policy.build` accepts the new-schema data shape without requiring `policy @p = union(...)` at module scope — which matters because rig's overlay is runtime-dynamic. `union()` is module-scope-only; rig builds the merged data directly. Rig overlay additively widens `labels.rules.influenced.deny` (`+["destructive","exfil"]`) and preserves `trusted_tool_output` / `user_originated` `satisfies` transitional alias.

`tests/rig/policy-build-catalog-arch.mld testSynthesizedPolicyShape` re-asserts new-schema presence (`labels.args["exfil:send"].recipient`, `labels.apply["trust:untrusted+llm"]`, `dataflow.check`). Passes 20/20 isolated.

Surfaced gap → ticket **c-3162-dispatch-wrap** (commit `5a03de1`): the new `labels.rules.influenced.deny` correctly fires when influenced body flows to `exfil:send`, but the throw propagates past `@dispatchExecute` because there's no wrapper around `@callToolWithPolicy`. Defense IS firing structurally; envelope shape needs the wrapper. P0 next session.

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

Session-specific:
- `.tickets/c-3162-dispatch-wrap.md` — P0 next session
- `.tickets/threats/` — 55 sec-doc tickets (BK / SL / WS / TR / XS)
- `tmp/policy-spike/` — six probes verifying schema/union semantics

Migration references (skill loads the broader set):
- `MIGRATION-TASKS.md` — phase tracker (this is the canonical checklist)
- `MIGRATION-PLAN.md` — 8-phase plan + Phase 7 commit dispositions
- `~/mlld/mlld/MIGRATION-POLICY-REDESIGN.md` — mlld-side migration patterns + checklist
- `~/mlld/mlld/spec-label-structure.md` — v2.x value-metadata channels
- `~/mlld/mlld/spec-policy-box-urls-records-design-updates.md` — v2.x policy schema
- `sec-{banking,slack,workspace,travel,cross-domain}.md` — threat models
- `mlld-security-fundamentals.md` — current primitives (labels, factsources, records, refine, shelves, sessions)
