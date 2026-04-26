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


## Notes

**2026-04-26T22:04:21Z** **2026-04-26T22:00:00Z bench-grind-10**: Investigated via spike (`/tmp/clean-bgrind10/coerce_spike.mld`). Two-layer issue:

1. **LLM schema violation**: compose worker returned `{"text": {nested object}}` instead of `{"text": "<string>"}`. The compose prompt says `{"text": "<final answer>"}` but GLM 5.1 occasionally inlines structured fields under text instead of rendering them as a single string.

2. **mlld validate: demote artifact**: `record @composeAttestation = { data: [text: string], validate: "demote" }` — when the parsed `text` field is an object, demote coerces it via JS `String(obj)`, producing the literal string "[object Object]". After demote, `@typeof(@text) == "string"` so the existing typeof-based malformed check doesn't fire.

**Fix shipped (rig/workers/compose.mld)**: added one explicit check `if @text == "[object Object]" [ => true ]` to `@isComposeMalformed`. The retry path then fires with the existing "your previous output was malformed" prompt, giving the worker a second chance with explicit feedback. This catches the demote artifact cleanly without overfitting (the literal "[object Object]" string is a deterministic sentinel of the schema-violation→demote chain).

Verified spike-side. Will see if UT10 stabilizes in the next sweep.

This is NOT a mlld bug per se — `validate: "demote"` correctly demotes a type mismatch by attempting String coercion. The bug is in the LLM not following the JSON schema. The detection-and-retry shape is the appropriate fix layer.
