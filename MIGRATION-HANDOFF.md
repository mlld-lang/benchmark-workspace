# Migration Handoff

Session breadcrumb for the records-as-policy + bucket→shelf migration. Read at session start. Update at session end. For the full plan, see `migration-plan.md`. For onboarding, use `/migrate` skill.

---

## Current state (2026-05-10)

**Gates**: zero-LLM 265/0/2; scripted suites all green (banking 10/0, slack 13/0+2xfail, workspace 14/0, travel 10/0); mutation matrix Overall OK. **Bench utility 69/97** (vs 78/97 baseline; Δ-9 classified per STATUS.md "Sweep history": migration-attributable Δ-5 split between c-bac4 + c-e414, plus pre-existing defense gaps and stochastic noise). **Migration is structurally complete**; Phase 2 closes after c-bac4 + c-e414 + benign re-sweep.

## Phase 2 close — next session scope

1. **c-bac4** — complete `state.capabilities.url_refs → typed shelf` migration (Phase 2.A leftover per migration-plan §2.A). Affects ~3-4 slack utility tasks (UT1, UT6, UT15) + confounds UT20 SHOULD-FAIL signal. Closes the deferred `testUr23DispatchGetWebpageViaRefFetchesViaCapability`.
2. **c-e414** — slack UT12 channel-name projection regression. Possibly migration-related; investigate alongside c-bac4.
3. **Benign re-sweep** targeting utility ≥ 76/97. **Slack security canary** (direct + important_instructions) to verify url_ref fix didn't open ASR holes. If utility ≥ 76 and canary stays 0 ASR: declare Phase 2 closed.

## Phase 3 scope (do not start until Phase 2 closes)

- **c-8ffd** mixed-authority cleanup — own commit.
- **Planner prompt revision** per migration-plan §3.B — REQUIRES explicit user approval in-session before any prompt edit. Bring proposed wording diff, get approval, land with bench-sweep before/after numbers in commit message.
- **Doc pass** — mechanical bucket→shelf vocabulary updates across `rig/SECURITY.md`, `rig/PHASES.md`, `rig/EXAMPLE.mld`, `clean/CLAUDE.md`, `STATUS.md` headline, `bench/domains/*/records-comments.txt`.

## Post-migration

When Phase 3 lands: `git mv MIGRATION-HANDOFF.md archive/`. `/migrate` skill stays on disk but goes dormant (not invoked at session start); future sessions use `/rig` with STATUS.md as canonical state. **Two `/migrate` learnings to promote into `.claude/skills/rig/SKILL.md` before dormancy** (Phase 3 closer handles): (a) bench gate ordering rule (benign first, attacks second; ASR=0 from broken agent is meaningless), (b) HARD RULE that session-end requires explicit user direction + the no-fixed-bug-history handoff discipline.

## Sessions log

| Date | Commit | Net |
|---|---|---|
| 2026-05-07 | `01698fa` `bbf2e7d` `f58ddad` | Phase 0.A invariants + Phase 0.B baselines + Phase 1 cutover |
| 2026-05-08 | `c7ad4c8` `485bb88` `744ba93` | Stage B core (-430 lines bucket helpers) + scaffolding + records audit |
| 2026-05-09 | `5c229ad` `7578afc` `6196ed0` `e5d3c21` `3151e88` `d78dc3d` `10bfc7e` | identity-contracts, url-refs B+C, null-conformance, proof-chain-firewall, docs, mock-llm shelf seed, bucket-era stripping |
| 2026-05-10 | `ca3e3b3` Task #6 worker-dispatch (gate +20) | |
| 2026-05-10 | `02a45e6` Task #7 fixture migration | |
| 2026-05-10 | `486d788` Task #8 mutation matrix re-baseline | |
| 2026-05-10 | `7b9482d` deprecated stub removal | |
| 2026-05-10 | `86c389d` `e5b331c` url-refs Group D + UR-19 reframe (gate +4) | |
| 2026-05-10 | `10d28de` rename @planner&lt;Phase&gt; → @&lt;phase&gt;Worker | |
| 2026-05-10 | `135d874` strip tools.submit (m-1b99 anticipation) | |
| 2026-05-10 | `3b8599f` tests/rig strict-mode opt-ins (m-1b99 follow-up) | |
| 2026-05-10 | `29fd430` STATUS.md 2026-05-10 sweep classifications | |
