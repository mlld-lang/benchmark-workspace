---
id: c-ut18
status: closed
deps: []
links: []
created: 2026-04-23T20:10:34Z
type: bug
priority: 1
assignee: Adam
tags: [derive, dates, workspace]
updated: 2026-04-24T19:54:42Z
---
# UT18: relative date resolution in derive needs current datetime

REVISED: The date is actually correct — April 18, 2026 IS a Saturday the 18th, matching the _next_saturday_18 hack in date_shift.py. UT18 fails because add_calendar_event_participants can't dispatch (m-5178 collection dispatch bug), so Mark isn't added as a participant. Blocked on m-5178, not on date-shift.

