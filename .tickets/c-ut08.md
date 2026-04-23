---
id: c-ut08
status: open
deps: []
links: []
created: 2026-04-23T19:45:05Z
type: bug
priority: 1
assignee: Adam
tags: [dispatch, runtime]
---
# add_calendar_event_participants dispatch fails: mlld field undefined

UT8: add_calendar_event_participants exe dispatch fails with 'Variable add_calendar_event_participants is not executable (type: undefined)'. The tool is correctly declared in the catalog with mlld:, inputs:, labels, etc. The collection dispatch path in runtime.mld should fire (hasInputRecord, exeParamCount>1, !hasPayloadArgs all true) but either @callableEntry is false (collection key lookup fails) or the dispatch errors before reaching the exe.

Likely a StructuredValue boundary issue where the tool entry's mlld field loses its executable reference when threaded through config -> agent -> toolsCollection. Other multi-param write tools (reschedule_calendar_event, send_email) work fine — need to investigate what's different about this one.

Not a bench-level fix — this is a runtime dispatch issue.

