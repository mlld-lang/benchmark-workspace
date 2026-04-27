---
id: c-d52c
status: open
deps: []
links: [c-c79c, c-4704]
created: 2026-04-24T20:04:26Z
type: bug
priority: 1
assignee: Adam
updated: 2026-04-27T17:33:01Z
---
# WS-UT32 37 framework gate cleared (result_handles populated); now blocked downstream by c-0589 file_id arg-name


## Notes

**2026-04-27T17:29:03Z** 2026-04-27 run 25008228406 — both UT32 and UT37 still gated.
WS-UT32 (ses_23020a23dffexw6cwtRpmweEnA): file created (id 26), then 6+ share_file invocations all rejected with `Input validation error: 'file_id' is a required property`. Planner explicitly diagnosed: "the resolved id_ field (string '26') may not pass the MCP tool's integer schema validation for the file_id parameter." Tried field:"id_", field:"id" (got resolved_field_missing with available fields including id_), selection refs, derive→selection, known integer "26". All rejected at MCP boundary.
WS-UT37 (ses_230205794ffelTvtLmwgj76Dcm): identical pattern — file created (id 26), 9+ share_file attempts rejected. Plus initial extract_empty_inline_schema cost 2 iterations.
Failure mode mutated since c-0589's last note: framework field resolution works (resolved_field_missing surfaces correctly when wrong field used), but with field:"id_" intent_compile passes and MCP rejects with file_id required. Compare to c-ac6f resolution — was that fix complete for share_file or only add_calendar_event_participants?
Both gated by (a) c-0589 successor (file_id mapping) and (b) c-EXTRACT-INLINE (extract_empty_inline_schema cluster preceding the share_file work).

**2026-04-27T19:55:30Z** 2026-04-27 same root as c-0589: StructuredValue wrappers reaching MCP unflattened. file_id arrives as {type:text,data:'<id>',metadata:{...}} object instead of raw string. JSON Schema validator says 'file_id is a required property' because typed-string check fails on wrapped object. Filed cross-repo as ~/mlld/mlld/.tickets/m-6e5b. Same fix unblocks both this ticket's tasks (UT32/UT37) and c-0589 (UT8).

**2026-04-27T21:56:45Z** Same root as c-0589 (forwarded as m-41b8 in mlld). file_id has same wrapper-not-unwrapped symptom at rig/runtime.mld:1042.
