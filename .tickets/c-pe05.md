---
id: c-pe05
status: closed
deps: [c-pe01]
links: []
created: 2026-04-23T16:43:28Z
type: task
priority: 2
assignee: Adam
tags: [prompt-audit, rig]
updated: 2026-04-23T18:47:58Z
---
# Phase and runtime error message improvements

Improve medium-frequency error messages across phase dispatch and runtime.

Changes:
- wrong_phase_tool (tooling.mld): add explanation of WHY phases matter, not just how to fix
- planner_error_budget_exhausted (planner.mld): include summary of the errors that led to exhaustion
- tool_runtime_error (runtime.mld): differentiate MCP subcategories (arg format vs connection vs generic)
- extract_may_not_emit_selection_refs (extract.mld): add explanation and redirect to derive
- compose retry guard message (planner.mld): explain what compose does ('the compose worker will read your execution log and resolved data')

See plan-prompt-error-updates.md M1, M7, M8, L2, L3.

Files: rig/tooling.mld, rig/workers/planner.mld, rig/workers/extract.mld, rig/runtime.mld
Depends: c-pe01 (intent errors first — higher frequency)

Testing:
1. Rig test gate
2. Canary: slack UT8 (wrong-phase), UT7 (error budget)
3. Regression: UT9 (passing multi-phase task)

