---
id: c-eeb6
status: closed
deps: []
links: [c-pe02, c-ad66, c-32db]
created: 2026-04-23T04:36:01Z
type: bug
priority: 0
assignee: Adam
tags: [extract, worker, null-response]
updated: 2026-04-25T03:44:31Z
---
# Source-backed extract returns null for calendar event descriptions

UT4, UT39, and likely other tasks: when the model calls extract with a resolved calendar_evt source and an inline schema asking for 'description' or 'title', the extract returns null. The model says: 'The extract returned null for all three. This could mean the description field is empty or the extract didn't find a description.'

The model then tries inline JSON schemas which get rejected with extract_empty_inline_schema. It doesn't know to use derive instead, which DOES work for extracting hidden content from resolved records.

Two problems:
1. Source-backed extract with inline schemas returns null instead of the content — may be a worker LLM issue or a schema validation issue
2. The model doesn't know that derive is the right tool for reasoning over hidden content in resolved records — extract is for tool-backed fetches or schema-coerced payloads

Tasks affected: UT4 (calendar descriptions), UT39 (email body content — first derive attempt returned null)

From UT4 transcript: model correctly resolved 3 events, tried 6 extract calls (all null or error), never tried derive, session ended without composing.


## Notes

**2026-04-25T03:44:31Z** Fixed alongside c-ad66. Same root cause: rig coercer was lenient on degenerate worker output. With the @coerceExtractAttestation hardening + dispatcher's @attestation == null check, the planner now sees extract_empty_response when the worker LLM emits a null/missing/empty payload or empty/null raw. UT4 calendar-description case will get an actionable error instead of silent null preview_fields.
