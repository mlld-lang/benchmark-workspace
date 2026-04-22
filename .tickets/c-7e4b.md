---
id: c-7e4b
status: open
deps: []
links: []
created: 2026-04-22T10:21:14Z
type: task
priority: 1
assignee: Adam
tags: [rig, dispatch, mcp]
---
# UT8/UT32: collection dispatch exe runs but MCP call doesn't fire

After all dispatch/policy fixes, add_calendar_event_participants and share_file execute reports status=executed, but the actual MCP tool call never reaches the server. The MCP log shows 0 calls for these tools. The collection dispatch calls the exe, the exe body runs, but @mcp.addCalendarEventParticipants(@participants, @asString(@event_id)) doesn't fire — likely because @participants and @event_id are not populated from the collection dispatch arg spread. Spike with simplified tools passes; the issue is specific to MCP-backed exes through collection dispatch.

