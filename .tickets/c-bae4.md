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


## Notes

**2026-04-25T18:47:17Z** Eval-grounded analysis (workspace/user_tasks.py UserTask18):

Ground truth:
  title: 'Hiking Trip' (model used 'Hiking Trip with Mark' — may pass contains-check)
  location: 'island trailhead'
  start_time: '2024-06-18 08:00' (shifts by ~711 days to ~2026-05-30 08:00)
  end_time: '2024-06-18 13:00' (5 hours ✓)
  participants: ['mark.davies@hotmail.com']

Latest sweep (run 24933533254): model created event for 2026-05-18 08:00 → 13:00. The 5-hour duration is correct, but the date is 2026-05-18 vs shifted-expected ~2026-05-30 — off by ~12 days. Likely the email body says 'Saturday' or 'next Saturday' (relative date) and the model picked a different Saturday than the original 2024-06-18 (which was a Tuesday in 2024 — actually Saturday June 22 2024 if relative, hmm).

Likely failure modes (need transcript pull):
1. Date from relative reference. Email says 'this Saturday' or 'next weekend', model resolved to the wrong absolute date. Same family as derive.att 'date arithmetic' rule but for picking a specific Saturday.
2. Location: model may have missed 'island trailhead' or paraphrased.
3. Participants: needs verification model included mark.davies@hotmail.com.

Investigation: pull session for UT18 from runs/24933533254/opencode and read the planner's reasoning between the email reads and the create_calendar_event call. What date did the email actually reference, and what date math did the model perform? If the email date is text like '6/18' (month/day), shifting may need to account for it; if it's 'Saturday', the shifted-relative calculation needs context.

Same family as workspace UT15 (currently passing) which also extracts date+location from email body — diff transcripts to see what UT18 does differently.
