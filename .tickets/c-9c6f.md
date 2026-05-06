---
id: c-9c6f
status: open
deps: []
links: [c-c2e7, c-2ec6]
created: 2026-05-06T00:16:35Z
type: chore
priority: 3
assignee: Adam
tags: [tests, harness]
updated: 2026-05-06T00:16:42Z
---
# Hoist @runWithState into tests/lib/mock-llm.mld

Four security suite files (security-slack.mld, security-travel.mld, security-workspace.mld, security-banking.mld) all define an identical `exe @runWithState(query, script, seedState)` inline. Hoist it to tests/lib/mock-llm.mld and re-export, then update all four suites to import it.

Watch out: mock-opencode.mld's existing @mockPlannerRun has the same closure-resolution problem with `with { session: @planner }` (we documented this when building Phase 5). If hoisting @runWithState breaks because the schema-resolution requires the call site to see @planner, leave it inline and document why instead.

Acceptance:
- @runWithState lives once in tests/lib/mock-llm.mld
- The four suites import it
- mlld validate tests/ passes
- mlld tests/index.mld + the scripted runs all stay green

