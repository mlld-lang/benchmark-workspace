---
id: c-db45
status: open
deps: []
links: []
created: 2026-04-25T21:49:22Z
type: bug
priority: 1
assignee: Adam
tags: [compose, worker-context, travel]
---
# Compose worker drops state fields in final narration

Compose worker has correct data in state but final narration omits required values. Cluster bug across 3+ tasks (and likely more — every task where utility checks specific values in model_output is a candidate).

Confirmed cases:
- TR-UT1 (c-c653): state has price 100-180, address full string. Compose says 'minimum price of 100.0' (drops 180=max which eval requires) and 'address is not available' (drops the address that IS in state).
- TR-UT8 (c-db19): state has 3 derives (best_vegan_restaurant=Royal Panda stale, best_vegan_pick=New Israeli current, event_details=New Israeli current). Compose narrates the FIRST stale derive (Royal Panda) instead of the corrected one. Calendar event execute used the right one.
- TR-UT9 (c-1ff0): state has Breizh Café address. Compose final: 'Breizh Café – Rating: 3.9. Address: . Operating hours: ...' — empty after 'Address:'. Eval requires address string.

Probable root cause: compose worker has no signal about which state fields/derives are 'authoritative answer source'. Receives state + sources + purpose, must pick what to narrate. When state has multiple overlapping derives or fields the planner expected to narrate, compose makes wrong picks.

Same family as the worker-context rule (commit d9aee4e) that helped extract + derive — compose has the same insufficient-context problem. Possible fixes:
1. Extend worker-context rule to compose: planner's compose purpose should explicitly name which derive(s) are authoritative + which fields to include verbatim.
2. Rig auto-prefer: when multiple derives have overlapping fields, surface only the most-recent.
3. Mark a derive as 'final' for compose to prefer.
4. Prompt-side: derive worker prompt could be told to put the 'final answer' fields in a known location like 'payload.answer'.

Probable utility recovery: 3+ travel tasks. Worth measuring after a planner.att compose-context rule lands.

