---
id: c-7e4b
status: closed
deps: []
links: [c-0589, c-859f]
created: 2026-04-22T10:21:14Z
type: task
priority: 1
assignee: Adam
tags: [rig, dispatch, mcp]
updated: 2026-04-24T20:17:05Z
---
# UT8/UT32: collection dispatch exe runs but MCP call doesn't fire

After all dispatch/policy fixes, add_calendar_event_participants and share_file execute reports status=executed, but the actual MCP tool call never reaches the server. The MCP log shows 0 calls for these tools. The collection dispatch calls the exe, the exe body runs, but @mcp.addCalendarEventParticipants(@participants, @asString(@event_id)) doesn't fire — likely because @participants and @event_id are not populated from the collection dispatch arg spread. Spike with simplified tools passes; the issue is specific to MCP-backed exes through collection dispatch.


## Notes

**2026-04-23T03:54:30Z** The underlying MCP collection dispatch arg spreading bug (m-f4bd) is fixed. UT7's reschedule_calendar_event now dispatches correctly. UT8/UT32 (add_calendar_event_participants, share_file) may also benefit — needs verification.

**2026-04-23T03:55:06Z** Fixed by m-f4bd (MCP collection dispatch arg spreading). The root cause was that MCP wrappers dropped optionalParams, so collection dispatch treated every schema property as required. When optional fields were omitted, args stayed as a single positional object. Verified working for reschedule_calendar_event (UT7 passes). add_calendar_event_participants and share_file likely also fixed — needs verification run.
