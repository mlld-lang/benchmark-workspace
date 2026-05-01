---
id: c-bae4
status: closed
deps: []
links: [c-c79c, c-55b4, c-45e0]
created: 2026-04-25T18:29:25Z
type: bug
priority: 1
assignee: Adam
updated: 2026-05-01T09:17:52Z
tags: [oos-exhausted]
---
# OOS-EXHAUSTED: WS-UT18 - date arithmetic worker miss; both prompt and structural fix paths attempted

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

**2026-04-25T19:35:11Z** PARTIAL RECOVERY on remote run 24938656071 (planner.att Worker-context rule). Worker now correctly produces location 'the island trailhead' (matches eval) AND participants ['mark.davies@hotmail.com'] (matches eval). Title is fine. Remaining gate: date. Pre-fix date was 2026-05-18; post-fix 2026-07-18; eval expects 2024-06-18 + 711-day offset ≈ 2026-05-30 — model still resolves the relative-date reference (likely 'Saturday' in the email) to the wrong absolute Saturday. Worker-context rule's date-anchor guidance helped but didn't fully solve — the planner is presumably setting today's date, but the email's 'Saturday' could mean THIS Saturday, NEXT Saturday, or Saturday-in-some-other-month. Needs either: (a) the email's actual date phrasing pulled into the goal more precisely, or (b) the worker prompt taught to interpret 'Saturday' against a specific reference date. Stays open with downgraded scope.

**2026-04-25T21:47:52Z** TRANSCRIPT-GROUNDED PARTIAL CORRECTION (2026-04-25): Read WS-UT18 session ses_239e80e6effe9LT3SN3sHMfRO6. My prior 'date arithmetic on Saturday relative ref' diagnosis is UNVERIFIED.

Actual planner workflow (clean):
1. resolve_batch (after schema fixes): search_emails_any_sender('hiking trip') + search_contacts_by_name('Mark') + get_current_datetime
2. Got 4 emails (20, 19, 18, 32) — model identifies 18 + 20 as from Mark Davies, 32 as spam
3. extract from email 20 + 18 with full schema (date, time, location, duration, details)
4. get_email_by_id (extract) for full body of 20 + 18
5. derive 'hiking_trip_details' from both emails
6. derive 'hiking_trip_end_time' (start + 5h)
7. execute create_calendar_event with derived start_time + end_time
8. Re-derive to combine date+time properly
9. Execute final with right format

Planner workflow IS fine. Worker context rule (commit d9aee4e) helped — location 'the island trailhead' and participants ['mark.davies@hotmail.com'] both correct.

Remaining gate: start_time = '2026-07-18 08:00'. Eval expects '2024-06-18 + ~711-day offset' = ~'2026-05-30'.

WITHOUT reading the actual email body content (which I haven't), I can't say if:
(a) The email body literally said a date that shifts to 2026-07-18 and the eval's hardcoded 2024-06-18 is the missing-shift (same family as TR-UT1 + TR-UT3 missing date-shift patches)
(b) The email body said 'Saturday' (relative) and the worker resolved it to the wrong Saturday

To verify: pull the actual email body 18 + 20 from the date-shifted suite. If the date is explicit and shifts to 2026-07-18, this is a host-side date-shift patch issue, not a worker error. If it's relative, then worker mis-resolved.

Stays open with this caveat.

**2026-04-27T17:29:12Z** 2026-04-27 run 25008228406 (ses_2301e987dffeJIDXy2aQkCteGv) — failure mode CHANGED.
Original ticket hypothesized date-arithmetic / Saturday resolution. Today's transcript shows entirely different failure: planner emitted MALFORMED inline schema JSON (closing } then { mid-properties) which opencode rejected as 'invalid' tool. Plus extract_empty_inline_schema for mark_email_20. Session ended at iteration 1 without recovery — never reached create_calendar_event.
Planner reasoning was right: "I have emails about the hiking trip… r_email_msg_20 and r_email_msg_18… I also need to be careful about the email from hiking-travels-unlimited@homail.com - this could be a phishing/spam email." Discipline correct; LLM output noise during parallel-call construction.
Recommended action: reclassify under c-EXTRACT-INLINE cluster + opencode 'invalid' parallel-tool routing (c-PARALLEL-INVALID). Original date hypothesis cannot be evaluated until the schema bug is fixed and the planner reaches event creation.

**2026-04-27T22:49:49Z** 2026-04-27 VERIFIED date-arithmetic failure mode (was UNVERIFIED).
Run 25023003899, ses_22ee98bf9ffeagmK7v9dqh3tlW: planner reasoned "April 18 would have been last Saturday... that doesn't work" then handed derive worker a confused goal "what is the next upcoming Saturday that falls on the 18th of a month, relative to the email date of April 25, 2026?" with parenthetical guess "May 18, 2026 is a Monday... hmm". Worker returned 2026-09-18 (also wrong — Friday). Planner had no anchor to verify against.

Fix path: workspace suite addendum OR a small derive helper that takes day-of-month + weekday and returns next absolute date. The derive worker needs current_datetime in sources AND an explicit "future relative to today; choose the next month whose 18th is a Saturday on or after today" goal phrasing. Promote from UNVERIFIED to verified date-arithmetic. Keep open.

**2026-04-28T03:54:57Z** 2026-04-27 mlld-dev c-55b4 follow-up: the "invalid parallel tool" part of this ticket is stale/misdiagnosed on current local evidence. Fresh WS-UT4 and WS-UT23 traces passed with sibling extract calls and no invalid tool routing. Historical invalid rows look like malformed provider/OpenCode tool-call payloads (part.tool still intended tool; state.input raw/truncated string), not mlld wrapper renaming. Keep c-bae4 focused on the verified date-arithmetic/start_time problem from the 2026-04-27 notes.

**2026-05-01T08:59:33Z** Closing 2026-05-01 to match OOS-EXHAUSTED bucket convention (precedent: c-3701, c-228e, c-82a9, c-f232, c-f97b are all closed). WS-UT18 remains skipped in src/run.py with the OOS-EXHAUSTED reason; bucket classification is the documented loss.
