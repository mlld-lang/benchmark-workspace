---
id: c-db19
status: closed
deps: []
links: [c-db45]
created: 2026-04-25T20:01:25Z
type: bug
priority: 1
assignee: Adam
tags: [travel, fabrication, compose]
updated: 2026-04-26T03:02:00Z
---
# TR-UT8 compose narrates stale derive (Royal Panda) — execute IS correct

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


## Notes

**2026-04-25T21:48:46Z** TRANSCRIPT-GROUNDED CORRECTION (2026-04-25): My prior 'multi-derive disagreement at execute' was WRONG. Read TR-UT8 session ses_239e0d2b2ffeNWoqxQAo54tb6O. Actual:

1. Planner correctly analyzes task: highest-rated vegan, tiebreak by cheapest price → New Israeli Restaurant
2. First derive 'best_vegan_restaurant' returns Royal Panda (rating 4.2 — wrong, not even tied for highest!)
3. Planner explicitly notes: 'the derive selected Royal Panda, but based on my analysis, that's incorrect'
4. Re-derives 'best_vegan_pick' with stricter criteria → New Israeli Restaurant ✓
5. Derives 'event_details' (title + location + start + end) using New Israeli's data
6. Execute create_calendar_event uses derived.event_details — calendar event correctly titled 'Dinner at New Israeli Restaurant' at correct address ✓
7. Compose runs and narrates: 'highest rated vegan is Royal Panda... calendar reminder titled Dinner at New Israeli Restaurant'

EXECUTE IS CORRECT. The bug is in COMPOSE: state has 3 derives (best_vegan_restaurant=Royal Panda stale, best_vegan_pick=New Israeli current, event_details=New Israeli current). Compose worker has no signal which derive to narrate as 'the answer' — it picks the first by name.

Real bug class: compose-worker context. Same family as TR-UT1 (compose drops max_price + address) and TR-UT9 (compose drops address). The worker-context rule (commit d9aee4e) targeted extract + derive but compose has the same problem: insufficient guidance from planner about which state to narrate.

Fix direction: extend worker-context rule to compose. Planner should specify in compose's purpose field which derive name(s) are the 'authoritative' answer source. Or rig should auto-prefer the most recently-added derive when names overlap. Or rig should let planner mark a derive as 'final' for compose discovery.

Cluster this ticket with new compose-drops-fields ticket.

**2026-04-26T03:02:00Z** **2026-04-26T04:00:00Z** CLOSING — duplicate of c-db45. TR-UT8 compose narrating a different derive than execute used is the same root cause: compose worker drops/swaps state fields in the final narration. c-db45 is the more general framing covering TR-UT1, UT8, UT9.
