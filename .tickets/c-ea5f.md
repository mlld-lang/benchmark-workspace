---
id: c-ea5f
status: closed
deps: []
links: [c-891b]
created: 2026-05-06T15:03:48Z
type: task
priority: 3
assignee: Adam
tags: [security, tests, workspace]
updated: 2026-05-06T21:10:44Z
---
# [WS-IT1] Add testDeleteFileAttackerIdRejected

Workspace IT1 (delete_file with attacker-fabricated file_id) has no scripted test. The defense exists structurally — `@delete_file_inputs.facts: [file_id: handle]` (records.mld:243) + `destructive:targeted` label triggers no-destroy-unknown — but no test exercises this exact attack shape. Mirror the workspace source-class-firewall pattern (e.g. testRescheduleCalendarEventExtractedIdRejected, line 191).

## Acceptance
- `testDeleteFileAttackerIdRejected` exists in tests/scripted/security-workspace.mld under group source-class-firewall
- A negative mutation entry in tests/run-mutation-coverage.py covers it
- All 4 scripted suites + invariant gate stay green
- Surfaced by spec-agentdojo-threat-model.md gap #1

