---
id: c-e9b1
status: open
deps: [c-d172]
links: []
created: 2026-04-21T02:40:25Z
type: task
priority: 1
assignee: Adam
tags: [prompt, separation]
updated: 2026-04-21T02:40:53Z
---
# Execute prompt split: rig generic + suite addendums

rig.build accepts prompts: config for suite addendum templates. Move lines 65-66 from planner.att to bench/domains/workspace/prompts/. Per-tool knowledge stays in tool instructions: field. Depends on: planner.att rewrite.

