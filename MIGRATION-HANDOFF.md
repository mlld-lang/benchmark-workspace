# Migration Handoff

Session breadcrumb for the records-as-policy + bucket→shelf migration. Read at session start. Update at session end. For the full plan, see `migration-plan.md`. For onboarding, use `/migrate` skill.

---

## Current state (2026-05-10)

**Zero-LLM gate**: 265/0/2. **Scripted suites (post-Task #7)**: banking 10/0; slack 13/0+2xfail; workspace 14/0; travel 10/0.
**Architecture**: Stage B core landed; `state.resolved` retired; shelf is the resolved-record store via `@agent.plannerShelf`.

## Phase status

- **Phase 0 + 1 + 2 (structural)**: DONE.
- **Phase 2 closeout (bench gates)**: IN FLIGHT — see "What's next" below.
- **Phase 3**: NOT STARTED.

## What's next

1. **Benign 4-suite utility sweep MUST land first.** Per migrate skill "Bench gate ordering — benign FIRST, attacks SECOND": until utility ≥ baseline ±2 (workspace 36, banking 11, slack 13, travel 18 = 78/97), the slack security canary result is uninterpretable. ASR=0 from a non-functional agent is not a security gate.
2. **Slack security canary** — only if benign holds. `scripts/bench-attacks.sh single direct slack` + `single important_instructions slack`. Expect 0/105 each (matches historic 25466790521 + 25466791386).
3. **Phase 3** — `c-8ffd` (mixed authority) lands first as own commit; planner prompt revision next (LLM-behavior change, requires bench-sweep before/after numbers per migration-plan §3.B + explicit user approval per CLAUDE.md prompt-approval rule); remaining doc pass last (SECURITY.md, PHASES.md, EXAMPLE.mld, CLAUDE.md, STATUS.md, records-comments.txt cross-references).

## Conversion patterns (Task #7-shape work)

See `/migrate` skill "Fixture conversion patterns" for the canonical templates. Two viable shapes:

- **Pattern A** (preferred for scripted-LLM modules): `@runScriptedQuery` setup + read shelf via `@setupRun.mx.sessions.planner.agent.plannerShelf.<rt>` + drive attack via `@mockOpencode` with `seed: { agent: @setupAgent }`. No `role:worker` on test exe.
- **Pattern B** (escape hatch for synthetic content the env can't mint): `exe role:worker @testFoo()` with inline `shelf @ps from @sh ...` + `@shelf.write(@ps.<rt>, @v as record @records.<rt>)` + handle from `r_<rt>_<key>` where key is `@v.mx.address.key`.

## State shape

`{ extracted, derived, extract_sources }` — shelf is in scope via `@agent.plannerShelf`, not part of state.

## Deferred test classes (preserved in source files; not migration-blocking)

- **Cross-tool dispatch composition** in `named-state-and-collection.mld` — DEFERRED PERMANENTLY to scripted/live tier (F5 in `bench/ARCHITECTURE.md`).
- **`testCrossResolveIdentitySlackHandleDrift` + `testSelectionRefSurvivesHandleDriftSlack`** — DEFER: needs `slack_msg` content-derived `key:` declaration bench-side. Preserved in `identity-contracts.mld`.
- **`testSelectionRefRealSlackMsgHandleRejected`** (slack scripted) — same root cause as above; xfail in its own group with the deferral note.
- **`testUr23DispatchGetWebpageViaRefFetchesViaCapability`** (url-refs-b) — chained two-dispatch helper; second dispatch's shelf write may not surface in caller's read scope. Deferred with group note.

## Ticket-state discipline

When a previous handoff mentions an mlld ticket and you can't immediately verify its state, verify (read the ticket, confirm the fix commit) before your handoff lands. Closed mlld bugs do not belong in this handoff.

## Bench gate discipline (CRITICAL)

Per migrate skill "Bench gate ordering": **never dispatch attack canaries before benign utility verification.** A non-functional agent has trivially 0 ASR — not because defenses fired, but because nothing happened. Default assumption: ASR is 0 unless utility is positive. Don't bookkeep ASR=0 from a broken agent and call the security gate met.

---

## Sessions log

| Date | Session | Commit | Net |
|---|---|---|---|
| 2026-05-07 | phase-0-A invariants | `01698fa` | tests added |
| 2026-05-07 | phase-1 main | `bbf2e7d` | rename + write: |
| 2026-05-08 | stage-b-core | `c7ad4c8` | -430 lines bucket helpers |
| 2026-05-08 | migrator-2 (records audit + conversions) | `744ba93` | gate 169→194 |
| 2026-05-09 | migrator-2 (identity-contracts + writeback) | `5c229ad` | gate 194→207 |
| 2026-05-09 | migrator-2 (url-refs-b B+C) | `7578afc` | gate 207→214 |
| 2026-05-09 | migrator-2 (null-conformance suite) | `6196ed0` | gate 217→229 |
| 2026-05-09 | migrator-3 Session A (proof-chain-firewall) | `e5d3c21` | gate 229→241 |
| 2026-05-09 | migrator-3 Session A (docs + archive) | `3151e88` | doc closeout |
| 2026-05-09 | migrator-3 Session B Task #17 (mock-llm + dispatch role:worker) | `d78dc3d` | mock-llm shelf seed |
| 2026-05-09 | migrator-3 Session B (security-fixtures cleanup) | `10bfc7e` | bucket-era stripping |
| 2026-05-10 | migrator-4 Task #6 worker-dispatch conversion | `ca3e3b3` | gate 241→261 (+20 tests) |
| 2026-05-10 | migrator-4 Task #7 fixture migration | `02a45e6` | scripted suites green |
| 2026-05-10 | migrator-4 Task #8 mutation matrix re-baseline | `486d788` | mutation Overall OK |
| 2026-05-10 | migrator-4 stub removal | `7b9482d` | -50 lines deprecated stubs |
| 2026-05-10 | migrator-4 url-refs-b Group D revival | `86c389d` | gate 261→264 |
| 2026-05-10 | migrator-4 UR-19 reframe | `e5b331c` | gate 264→265 |
