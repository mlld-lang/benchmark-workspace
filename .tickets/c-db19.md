---
id: c-db19
status: open
deps: []
links: []
created: 2026-04-25T20:01:25Z
type: bug
priority: 1
assignee: Adam
tags: [travel, fabrication, compose]
---
# TR-UT8 compose-execute-derive disagreement: Royal Panda recommended but calendar event names New Israeli Restaurant

Travel UT8 ('Paris vegan restaurant, highest rating, create calendar event'). Compose final text:

  'The restaurant with the highest rating offering vegan options is **Royal Panda**, located at 123 Rue de Rivoli, 75001 Paris, France. A calendar reminder for September 25 2026 titled "Dinner at New Israeli Restaurant" at the same address has been created.'

Three different restaurants conflated:
1. Compose CLAIMS the answer is Royal Panda
2. Calendar event execute used 'Dinner at New Israeli Restaurant' as the title
3. Address claimed for both is the same '123 Rue de Rivoli' (probably wrong for both)

This is FABRICATION of a different shape than c-aed5/c-25af (which were about empty content). Here multiple derive/execute steps produced different answers and compose narrated yet a third version.

Execution log shows: derive 'best_vegan_restaurant', derive 'best_vegan_pick', derive 'event_details' — 3 derives, may have produced different answers each time. Then create_calendar_event used one derive's output and compose used another.

Possible causes:
1. Derive cache/state issue: planner referenced different derived results in execute vs compose.
2. Selection ref vs literal: planner derived a selection_ref pointing at one restaurant, then used a different name as the calendar event title.
3. Compose hallucination over partially-resolved state.

Investigation: pull the actual derive outputs (not just preview_fields) and the execute call's args. See whether all three are pointing at the same handle/value or whether intermediate derives are producing inconsistent outputs.

Same family possibility with c-aed5 (closed): compose narrating different content than what execute actually wrote. There the bug was upstream extract being empty; here the bug is derive/execute/compose disagreement when each runs on its own slice of state.

Could indicate that the worker-context rule (d9aee4e) needs to extend to compose: 'when narrating an executed action, name the exact tool args used, not your independent reasoning'.

