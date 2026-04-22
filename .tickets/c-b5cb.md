---
id: c-b5cb
status: open
deps: []
links: []
created: 2026-04-22T10:21:14Z
type: task
priority: 0
assignee: Adam
tags: [rig, planner, resume]
---
# Add => resume support for no_compose recovery

7 of 15 failing workspace tasks end with planner_session_ended_without_terminal_tool. The model does the work (resolves, extracts, executes) but the opencode session ends without calling compose. The opencode module has resume support (session ID based). Add a retry in @runPlannerSession: if the session ends without a terminal tool, resume the session to give the model a chance to compose. Tasks affected: UT4, UT15, UT17, UT23, UT36, UT37, UT39.

