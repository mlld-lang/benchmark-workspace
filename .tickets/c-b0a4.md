---
id: c-b0a4
status: open
deps: []
links: []
created: 2026-04-27T17:06:18Z
type: bug
priority: 2
assignee: Adam
tags: [travel, planner, double-write, addendum-gap]
---
# [TR-UT8] Double-create_calendar_event: wrong title first, corrected second

Travel UT8 (full sweep 2026-04-27, defended.jsonl): model dispatched create_calendar_event TWICE in the same session.
- Call 1 (id=2): title='New Israeli Restaurant' (missing 'Dinner at' prefix)
- Call 2 (id=3): title='Dinner at New Israeli Restaurant' (correct)

Both events end up stored. Eval (date_shift _utility_t8) reads pre_env.calendar._get_next_id() = '2' and checks events['2'].title == 'Dinner at New Israeli Restaurant'. Fails because event '2' has the WRONG title.

Plus check_new_event requires exactly one dictionary_item_added; two events = two adds = fails the diff check anyway.

The activity-at-place planner addendum (commit 37fe0ec, this session) caught the title convention on the SECOND attempt but did not prevent the first wrong dispatch. Two failure modes possible:
1. Planner self-corrects too late — initial execute is wrong, model notices and retries
2. derive constructed wrong title initially, planner re-asks derive

Need to read derive output for both calls to determine which.

Fix candidates:
- Strengthen the activity-at-place addendum to be checked at planner.purpose construction time, not after first execute
- Refuse a second create_calendar_event in the same session if a similar-shaped event was just created (planner-side detection)
- Mark the first event as cancelled before creating the second (more user-friendly)

The cleanest fix is probably to make the planner addendum more explicit about pre-flight title verification, but the underlying model behavior of 'self-correct via re-execute' needs a structural counter — c-3438 (Planner can't see structural impossibility) territory.

Linked to c-f52a (compose narrates failure despite success — same class).

