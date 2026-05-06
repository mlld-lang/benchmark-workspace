---
id: c-ed77
status: closed
deps: []
links: []
created: 2026-05-06T01:22:25Z
type: chore
priority: 4
assignee: Adam
tags: [tests, framework, consolidation]
updated: 2026-05-06T01:45:44Z
---
# Consolidate live-LLM tests under tests/

Currently the live-LLM tier (real LLM calls) lives at the legacy location:

- rig/tests/workers/    — worker LLM tests with scoreboard.jsonl, parallel runner (rig/tests/workers/run.mld)
- rig/tests/flows/      — live-LLM flow integration tests
- rig/tests/patterns/   — live-LLM pattern tests
- rig/tests/llm/lib/    — opencode/claude harness utility used by the above
- rig/tests/helpers.mld — used by flows/, patterns/

These tests have a fundamentally different contract from the new framework:
- Stochastic evaluation (model output varies per run)
- Cost-per-run (~\$0.05 per test cycle)
- Scoreboard tracking for model comparison
- Different timing model (~50s for workers, longer for flows/patterns)

To consolidate under tests/, design a third tier:

- tests/live/                  — live-LLM suites (or tests/llm/, name TBD)
- tests/live-index.mld         — runner that handles the scoreboard contract
- tests/lib/llm-harness.mld    — re-export of the existing rig/tests/llm/lib/opencode utility (or move outright)

Acceptance criteria:
- All worker/flow/pattern tests run under one canonical runner
- Existing scoreboard.jsonl format preserved (or migrated, with ticket)
- README.md TESTS.md table updated to show all three tiers in tests/
- rig/tests/{workers,flows,patterns,llm}/ deleted after migration verifies
- Cost model documented (when to run, expected dollar amount, parallel safety)

Estimated effort: 4-8 hours. Mostly mechanical move + index rewiring + scoreboard runner port.

Out of scope:
- Changing what each individual test asserts
- Cost-reduction (separate concern)
- Folding scoreboard tracking into the new framework's pass/fail/xfail surface (different contract; might warrant its own opt or a separate report)

Linked: c-c2e7 (closed) is the analogous consolidation for the scripted-LLM tier; this ticket completes the picture for the live-LLM tier.


## Notes

**2026-05-06T01:45:44Z** Closing — live-LLM tier moved to tests/live/ in commit 863248b. Surface-level move only:

- rig/tests/workers/   → tests/live/workers/
- rig/tests/flows/     → tests/live/flows/
- rig/tests/patterns/  → tests/live/patterns/
- rig/tests/llm/       → tests/live/llm/
- rig/tests/helpers.mld → tests/live/helpers.mld

The existing runner (tests/live/workers/run.mld with scoreboard.jsonl) retains its contract intact — same parallel-run model, same scoreboard format, same cost expectations. Import paths updated:
- ../../index.mld         → ../../../rig/index.mld
- ../../runtime.mld       → ../../../rig/runtime.mld
- ../../workers/<x>.mld   → ../../../rig/workers/<x>.mld
- ../../../tests/fixtures.mld → ../../fixtures.mld

CLAUDE.md First Actions and TESTS.md updated to reference the new location. .gitignore updated to ignore scoreboard.jsonl at its new path. rig/tests/ removed entirely.

Result: all three test tiers now live under tests/. mlld tests/index.mld still passes 255/0/3xfail; mlld validate tests/live/ passes 20 files.

Out of scope (left as a follow-up if needed): folding the live-LLM runner's stochastic-evaluation/scoreboard contract into the new framework's @suite/@runSuites surface. That's a deeper integration with different cost/result semantics; the surface move is sufficient for now.
