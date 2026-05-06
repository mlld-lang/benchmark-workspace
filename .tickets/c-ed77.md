---
id: c-ed77
status: open
deps: []
links: []
created: 2026-05-06T01:22:25Z
type: chore
priority: 4
assignee: Adam
tags: [tests, framework, consolidation]
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

