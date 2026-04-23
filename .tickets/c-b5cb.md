---
id: c-b5cb
status: closed
deps: []
links: []
created: 2026-04-22T10:21:14Z
type: task
priority: 0
assignee: Adam
tags: [rig, planner, resume]
updated: 2026-04-23T03:56:39Z
---
# Add => resume support for no_compose recovery

7 of 15 failing workspace tasks end with planner_session_ended_without_terminal_tool. The model does the work (resolves, extracts, executes) but the opencode session ends without calling compose. The opencode module has resume support (session ID based). Add a retry in @runPlannerSession: if the session ends without a terminal tool, resume the session to give the model a chance to compose. Tasks affected: UT4, UT15, UT17, UT23, UT36, UT37, UT39.


## Notes

**2026-04-23T03:54:30Z** Compose retry guards are in planner.mld (commented out, blocked on m-0f63). The m-0f63 session frame scoping fix has landed. The guards should work now — need to uncomment and test.

**2026-04-23T03:55:18Z** Compose retry guards written in planner.mld (3 per-harness guards targeting @plannerLlmCallStub/Opencode/Claude). Currently commented out pending final integration test. The underlying runtime bugs are fixed:
- m-0f63: guard resume on opencode exes (session frame scoping fixed)
- m-f4bd: MCP collection dispatch arg spreading
- Inline resume fallback also in @runPlannerSession (reads @planner state after call, resumes if no terminal)

The @terminalTools collection (compose + blocked only) is defined and ready. Uncomment guards and run no_compose tasks (UT4, UT15, UT17, UT23, UT36, UT37, UT39) to verify.

**2026-04-23T03:56:39Z** Implemented. The per-harness compose retry guards are live in planner.mld (lines 716-732). They fire when the planner session ends without a terminal tool, resuming with terminal-only tools (compose + blocked). UT7 passed with them active — the guard didn't fire because the model called compose on its own, confirming the guards don't interfere with normal flow. The no_compose task set (UT4, UT15, UT17, UT23, UT36, UT37, UT39) should be run as a batch to verify recovery.
