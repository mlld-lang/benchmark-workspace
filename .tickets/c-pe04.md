---
id: c-pe04
status: closed
deps: [c-pe00]
links: []
created: 2026-04-23T16:43:18Z
type: task
priority: 1
assignee: Adam
tags: [prompt-audit, rig]
updated: 2026-04-23T18:06:26Z
---
# Planner tool descriptions and budget warnings

Rewrite rig tool descriptions from framework jargon to plain language. Improve budget warning messages with state-aware guidance.

Tool description rewrites (planner.mld tool catalog):
- resolve: 'Look up information using a read tool. Returns structured records with handles you can reference later.'
- extract: 'Read hidden content from a resolved record (like an email body or file content) and extract specific fields into a named result.'
- derive: 'Compute a result from data you already have — ranking, selection, comparison, arithmetic, or summarization. Returns a named result.'
- execute: 'Perform a write operation (send email, create event, etc.). All target values must come from prior resolves or exact task text.'
- compose: 'Write the final answer for the user and end the session.'
- blocked: 'Stop and explain why the task cannot be completed.'

Budget warning improvements:
- 50%: Include count of resolved/extracted/derived state items
- 3-remaining: Explicitly say MUST call compose or execute on next call, or blocked

See plan-prompt-error-updates.md H4 + H5.

Files: rig/workers/planner.mld (tool descriptions at line 659-701, budget warnings at line 309-312)
Depends: c-pe00

Testing:
1. Rig test gate
2. Canary: UT2 (timeout/over-resolving), UT32 (timeout)
3. Regression: UT1 (passing simple read), UT20 (passing write)
4. These are planner-facing — tested via canary tasks, not worker tests

