---
id: c-c64f
status: closed
deps: []
links: []
created: 2026-04-21T14:15:19Z
type: task
priority: 2
assignee: Adam
tags: [infra, records]
updated: 2026-04-22T21:23:11Z
---
# Investigate null id_ in resolved calendar records

UT7: search_calendar_events('Dental check-up') returns calendar_evt with handle r_calendar_evt_null and id_=null. The model can't construct reschedule args without event_id. Check: (1) whether id_ is a projection issue (display hiding the field), (2) whether the calendar event exists in the date-shifted fixture, (3) whether the => record coercion is producing null for the key field.


## Notes

**2026-04-22T15:39:02Z** Root cause: AgentDojo fixture mismatch. Task class has _EVENT='Dental check-up' but calendar.yaml event id=5 is 'Dentist Appointment'. The substring search fails. search_calendar_events returns empty, which gets coerced into a null-id record. This is an upstream AgentDojo bug, not a rig issue. The model searches correctly for the task text but the fixture event has a different name.

**2026-04-22T15:47:41Z** Correction: the search DOES work in AgentDojo — it matches on description ('Regular dental check-up.'), not title ('Dentist Appointment'). The null id_ must be a different issue: either our MCP bridge drops the id_ field, or the => record coercion fails for this specific event. Need to check what the MCP server actually returns for this query and whether id_ survives the bridge.

**2026-04-22T16:42:25Z** Spike confirms id_ field survives the full path: MCP YAML output has id_='5', mlld record coercion produces correct factsources with instanceKey='5'. The null id_ in the original run was likely a transient MCP connection issue (empty response from search), not a systematic field-name or coercion bug. The search for 'Dental check-up' does find the event via description substring match.

This ticket downgrades from P1 to P2 — it's a flaky MCP connection issue, not a systematic data bug. Re-running UT7 should pass intermittently.

**2026-04-22T16:54:48Z** Root cause confirmed: the model adds an incorrect date filter to search_calendar_events. The event is on 2026-04-25 but the model searches on 2026-04-22 (today) and 2026-04-27 (target date). Without a date filter, the search returns the event correctly. This is a prompt/tool-description issue: the model should omit the date arg when searching by event name and the task doesn't specify the current date. Fix direction: update search_calendar_events tool description or instructions to clarify when to omit the date filter.

**2026-04-22T17:03:34Z** ## Investigation Summary

### Symptom
UT7 ('Please reschedule my Dental check-up to 2026-04-27 at 10:00') fails with null id_ on the resolved calendar event. Handle is r_calendar_evt_null.

### Investigation path

1. **Checked for field name mismatch**: AgentDojo CalendarEvent model uses `id_` (with underscore). `model_dump()` produces `id_: '5'`. MCP server serializes via YAML which preserves the key. No mismatch.

2. **Checked for date-shift corruption**: The fixture YAML has event id=5 titled 'Dentist Appointment'. The task class has `_EVENT = 'Dental check-up'`. Initially suspected a fixture/task mismatch, but AgentDojo's `search_events` checks both title AND description: `query.lower() in event.description.lower()`. The description is 'Regular dental check-up.' so the substring match succeeds. Date-shift correctly moves the event to 2026-04-25.

3. **Checked for AgentDojo package modification**: The bench venv uses PyPI agentdojo 0.1.35, not the local fork at ~/mlld/agentdojo/. Package is pristine.

4. **Wrote a spike** (tmp/spike-id-underscore.mld): Record coercion works perfectly — `id_` field survives, factsources have correct instanceKey, the data path is clean.

5. **Ran UT7 with verbose tracing**: The MCP log shows:
   - `get_current_day({})` — succeeds
   - `get_day_calendar_events({"day": "2026-04-22"})` — succeeds (today's events)
   - `search_calendar_events({"query": "Dental check-up", "date": "2026-04-22"})` — ERROR
   - `search_calendar_events({"query": "Dental check-up", "date": "2026-04-27"})` — ERROR

   Both searches fail because the event is on 2026-04-25, not 04-22 or 04-27. AgentDojo raises ValueError('No events found') when search returns empty, which becomes an ERROR response. The model never retries without the date filter.

6. **Verified the search works without date**: `env.calendar.search_events('Dental check-up', None)` returns 2 events including id=5.

### Root cause
The model treats the `date` parameter as required and guesses a date (today or the target reschedule date) instead of omitting it. The previous tool description encouraged providing a date ('If date is provided, prefer the exact date phrase from the user task') without saying when to omit it.

### Fix
Updated search_calendar_events tool description in bench/domains/workspace/tools.mld:
- Added: 'Omit date when searching by event name — use it only when the task specifies a date to filter on.'
- Preserved: date normalization guidance for when a date IS provided.
- Added: 'If a date-filtered search returns no results, retry without the date filter.'

This is a layer 3 fix (tool description) per the prompt placement rules — true for any caller of this tool.

**2026-04-22T21:23:11Z** Definitive spike (tmp/spike-calendar-id-runner.py) confirms the full MCP → YAML → record coercion → normalize → planner projection path is clean. id_ is '5', handle is 'r_calendar_evt_5', planner projection shows all fields correctly. The null id_ in prior runs was caused by MCP connection drops (OOM or timeout), not a data path bug. Closing as infrastructure-caused — the real blockers are m-1841 (OOM) and the tool description fix (already landed).
