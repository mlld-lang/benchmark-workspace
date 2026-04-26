---
id: c-0ada
status: open
deps: []
links: []
created: 2026-04-26T21:43:08Z
type: bug
priority: 2
assignee: Adam
tags: [travel, compose, worker-output, mlld-bug]
---
# [Travel UT10] Compose worker emits literal '[object Object]' as text

Local canary 2026-04-26: UT10 (Paris Chinese restaurant under 34€) compose worker returned text='[object Object]' as the final answer. The planner reasoned correctly ("New Asiaway, 4.6, 30, 12-3pm/6-10pm") and the planner session's text turn AFTER compose returns the right narrative. But `@phaseResult.text` from the compose worker is literally '[object Object]'.

Same compose dispatch worked correctly for UT3 in same canary run (commit pre-c-d590-fix). The derived schema/state shape is the only meaningful difference: UT10 derived.best_chinese_restaurant has 5 scalar fields, same shape as UT3's derived.best_hotel.

Likely causes: (1) compose worker LLM hallucination — saw a state_summary projection that rendered something as [object Object] and copied it; (2) mlld template interpolation rendering a structured object as JS-style stringification when injected via @stateSummary in compose.att; (3) projection bug in @projectNamedState that produces an unrenderable shape for restaurant records.

Run: defended.69, task user_task_10, 463s wall.

Investigation: dump @workerStateSummary output for UT10 (vs UT3) — see what the compose worker actually receives.

Defer: looks mlld-side; user instructed to defer mlld bugs in bench-grind-10.

