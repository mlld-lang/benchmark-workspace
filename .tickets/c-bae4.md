---
id: c-bae4
status: open
deps: []
links: []
created: 2026-04-25T18:29:25Z
type: bug
priority: 2
assignee: Adam
---
# WS-UT18 calendar event from hiking emails fails on date or location

Workspace UT18 (hiking trip with Mark from emails). HANDOFF says 'flaky'. Latest sweep run 24933533254: model called get_current_datetime, search_contacts_by_name(Mark), search_emails_any_sender(hiking), got two emails (id 20 + id 18), then created calendar event titled 'Hiking Trip with Mark' for 2026-05-18 08:00 to 13:00 (5 hours). Utility false.

Possible failure modes (not yet investigated):
1. Date wrong: emails may say 'Saturday' or 'next weekend' (relative reference) — date-shifting could land on a different absolute date than the evaluator expects. Same family as the 'Saturday' issue mentioned in SCIENCE.md.
2. Location wrong: model picked one mentioned location, evaluator wants a different one.
3. Time slot wrong.
4. Mark's email/participant list missing.

Needs transcript-grounded investigation: dump the planner reasoning between the email reads and the create_calendar_event call. Compare event args against ~/mlld/agentdojo evaluator (eval-only check, not behavior). If date is the issue, check date-shift utility patches per DEBUG.md.

Likely cluster with WS-UT15 (similar email→calendar pattern, currently passing) for transcript comparison.

