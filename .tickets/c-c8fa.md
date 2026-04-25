---
id: c-c8fa
status: closed
deps: []
links: []
created: 2026-04-24T23:16:21Z
type: bug
priority: 1
assignee: Adam
tags: [runtime, oom]
updated: 2026-04-25T15:28:56Z
---
# Travel: Node V8 OOM on 28-tool catalog (UT7, UT13, UT19)

Symptom: travel UT7, UT13, UT19 produce Node 'Last few GCs ... Scavenge' OOM dumps in execute_error. Common factor: travel has 28 tools (vs banking ~12, slack ~10). Multi-domain queries that touch many tools blow memory. Could be mlld interpreter holding too much in evaluation closure, or tool catalog walk being O(n²). File against ~/mlld/mlld/.tickets/. May share root with c-3edc (logging refactor) since execution log accumulation has been a memory issue before. Repro: travel UT13 (car rental + reviews) seems consistent.


## Superseded by c-63fe (2026-04-25)

The "Node V8 OOM on 28-tool catalog" framing turned out to be
incomplete. After per-task tool routing reduced travel's catalog
visible to ~5 tools per task, runner-level OOMs (exit 137) still
happened until shape was bumped to 16x32, and even then 100+ MCP
"Not connected" cascades fire in a 32x64 -p 20 run.

The OOM was MCP-server level (per-task lifecycle), not tool-catalog
size. The full scope is in c-63fe with the run matrix and surviving
hypotheses.

### Status
Closing as superseded. Travel measurement still blocked on c-63fe.
