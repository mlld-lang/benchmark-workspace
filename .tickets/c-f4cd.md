---
id: c-f4cd
status: closed
deps: []
links: []
created: 2026-04-21T16:58:28Z
type: task
priority: 1
assignee: Adam
tags: [infra, mlld-runtime]
updated: 2026-04-22T10:20:48Z
---
# MCP connection drops mid-session (opencode subprocess)

8 of 13 failing workspace tasks lose MCP connection mid-session. All subsequent tool calls return null. The model correctly identifies the connection loss but can't recover. This is in the mlld SDK's MCP subprocess lifecycle, not the benchmark code. Mitigated by parallel tool calls (more work per turn before connection dies).


## Notes

**2026-04-22T10:20:48Z** Addressed by opencode 1.4 (5-minute MCP timeout) and m-583c investigation. Remaining MCP drops are from session timeouts, not idle timer.
