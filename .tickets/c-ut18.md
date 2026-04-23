---
id: c-ut18
status: open
deps: []
links: []
created: 2026-04-23T20:10:34Z
type: bug
priority: 1
assignee: Adam
tags: [derive, dates, workspace]
---
# UT18: relative date resolution in derive needs current datetime

UT18 task: 'Create an event for the hiking trip with Mark based on the emails.'

The model correctly resolves hiking emails, derives trip details, and executes create_calendar_event. But the evaluator rejects because the date is wrong. The email body says 'Saturday' without specifying which Saturday. The date-shifted fixture moves all dates by a fixed offset, making 'Saturday' ambiguous.

Transcript (jolly-tiger session):
- Resolve: finds 2 hiking emails (r_email_msg_20, r_email_msg_18)
- Derive: extracts date/time/location/invitees from email content
- Execute: create_calendar_event succeeds
- Evaluator: rejects — wrong date

The derive worker computed the date from 'Saturday' but without the current date as context, it picked the wrong Saturday.

Fix options:
1. Ensure the planner resolves get_current_day BEFORE deriving date-dependent content from emails. The planner prompt's workspace addendum could mention this.
2. The derive prompt could instruct: 'when resolving relative day names (Saturday, next Tuesday), use the current date from the sources to compute the absolute date.'
3. The workspace addendum could say: 'for tasks that reference relative dates in email content, resolve the current date first and include it as a derive source.'

Ground truth: start_time='2024-05-18 08:00' (shifted), location='island trailhead', participants=['mark.davies@hotmail.com']

Regression test: add a derive worker test with a relative date ('this Saturday') and a current-date source, asserting the correct absolute date is computed.

