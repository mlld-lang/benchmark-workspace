---
id: c-c8fa
status: open
deps: []
links: []
created: 2026-04-24T23:16:21Z
type: bug
priority: 1
assignee: Adam
tags: [runtime, oom]
---
# Travel: Node V8 OOM on 28-tool catalog (UT7, UT13, UT19)

Symptom: travel UT7, UT13, UT19 produce Node 'Last few GCs ... Scavenge' OOM dumps in execute_error. Common factor: travel has 28 tools (vs banking ~12, slack ~10). Multi-domain queries that touch many tools blow memory. Could be mlld interpreter holding too much in evaluation closure, or tool catalog walk being O(n²). File against ~/mlld/mlld/.tickets/. May share root with c-3edc (logging refactor) since execution log accumulation has been a memory issue before. Repro: travel UT13 (car rental + reviews) seems consistent.

