---
id: c-c80e
status: open
deps: []
links: []
created: 2026-05-13T22:45:29Z
type: task
priority: 3
assignee: Adam
tags: [rig, tests]
---
# [Cluster I followup] Integration test: surfaced phase error detail reaches planner's next-turn input

After 4d2b0c0 the helpers (@buildPhaseErrorLogEntry / @buildPhaseErrorResult) preserve code/field/hint/message. Unit test (tests/rig/phase-error-envelope.mld) asserts the helpers build the right envelope. What's NOT tested: that this detail actually plumbs through @appendExecutionLogEntry → execution_log file → @readExecutionLogFile → planner's compose phase input AND through the rig tool-result return path into the planner's tool_use loop.

Different regression class than the helper-unit-test: those test SHAPE. This would test PLUMBING — the detail survives the I/O round-trip and the planner-side wrapping path.

Suggested shape: a Tier 1 zero-LLM test that runs a small synthetic planner-toolctx cycle, calls a failing dispatch, then reads back from the execution log file and asserts code/field/hint present. Or a scripted-LLM test that uses the mock harness to fire one failing execute and verify the planner's next-turn prompt context contains the detail.

Not blocking. File for future regression coverage when execution log file format or read path changes.

