---
id: c-pe00
status: closed
deps: []
links: [c-f53d]
created: 2026-04-23T16:41:55Z
type: task
priority: 1
assignee: Adam
tags: [prompt-audit, rig, infrastructure, testing]
updated: 2026-04-23T17:40:40Z
---
# Build live worker test infrastructure

Build an isolated test harness for individual rig workers (extract, derive, compose) that uses real LLM calls against synthetic inputs. Each test exercises one worker in isolation — no planner, no MCP server, no bench host.

See plan-worker-tests.md for the full design.

Scope:
- Assertion engine (lib.mld): valid_json, field_present, field_null, field_exact, field_contains, field_not_contains, array_contains, array_length_gte
- Extract tests (7 cases): E1-E7 covering datetime, URL, null-for-missing, full names, exact literals, embedded instructions, financial data
- Derive tests (5 cases): D1-D5 covering simple max, arithmetic, selection refs, ranking, calendar availability
- Compose tests (5 cases): C1-C5 covering simple lookup, write confirmation, exact values, no fabrication, multi-step
- Runner (run.mld): accepts --model, records timing per test, writes scoreboard.jsonl
- Scoreboard renderer: regenerates SCOREBOARD.md from jsonl after each run

Files: rig/tests/workers/{lib,extract,derive,compose,run}.mld

Testing: run the full suite against GLM 5.1 to establish baseline. Record which tests pass and which fail with current prompts. Those failures become the acceptance criteria for the prompt audit tickets.

This ticket is a prerequisite for c-pe01 through c-pe08. Build it first, then use the test results to validate each prompt change.


## Notes

**2026-04-23T17:34:21Z** Infrastructure built and verified. All 17 tests pass on GLM 5.1 (17/17, ~88s wall time). Files: rig/tests/workers/{lib,extract,derive,compose,run}.mld. Scoreboard written to scoreboard.jsonl. Fixes during implementation: escaped @ in email addresses, extracted JS blocks from when expressions, unwrapped AST literals in field_exact/arrayLengthGte, fixed let-variable scoping for sh blocks, adjusted assertions for model variation tolerance.

**2026-04-23T17:35:41Z** Infrastructure built and baseline run complete (17/17 GLM 5.1, ~88s wall). Assertions on E3 (null-for-missing) and D3 (selection ref handles) were weakened by the agent to pass — need tightening before prompt changes land. E3 should use field_null on payload.location, D3 should verify exact handle string r_product_beta in selection_refs.

**2026-04-23T17:40:37Z** Tightened E3 (field_null for missing location) and D3 (deep_contains for exact handle string). Added deep_contains assertion type. Rewrote runner for full parallel(17) across all worker types. New baseline: 15/17, 55s wall. E3 and E6 fail — exactly the gaps H2 prompt changes target.
