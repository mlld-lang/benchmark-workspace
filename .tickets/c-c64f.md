---
id: c-c64f
status: open
deps: []
links: []
created: 2026-04-21T14:15:19Z
type: task
priority: 1
assignee: Adam
tags: [infra, records]
---
# Investigate null id_ in resolved calendar records

UT7: search_calendar_events('Dental check-up') returns calendar_evt with handle r_calendar_evt_null and id_=null. The model can't construct reschedule args without event_id. Check: (1) whether id_ is a projection issue (display hiding the field), (2) whether the calendar event exists in the date-shifted fixture, (3) whether the => record coercion is producing null for the key field.

