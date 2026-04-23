---
id: c-ut8r
status: open
deps: []
links: []
created: 2026-04-23T20:09:44Z
type: bug
priority: 0
assignee: Adam
tags: [dispatch, handle, metadata-loss]
---
# Fix @normalizeResolvedValues handle metadata loss

UT8: add_calendar_event_participants dispatch fails because @normalizeResolvedValues strips handle-bearing metadata from fact fields.

Root cause (confirmed by GPT5.4 spike at tmp/spike-ut8-handle-loss.mld):
- rig/runtime.mld:252 uses @nativeRecordFieldValue to populate identity_value and field_values
- @nativeRecordFieldValue prefers mx.data[field] / data[field] over direct field access
- For live record-coerced values, this strips the proof-bearing StructuredValue wrapper
- The value '24' survives but loses its handle metadata
- Collection dispatch validates the strict input record and rejects event_id because it's no longer handle-bearing

Fix: In @normalizeResolvedValues, use direct field access (which preserves the live wrapper) for identity_value and field_values. Do NOT change @nativeRecordFieldValue globally — it's also used in planner-summary paths and checkpoint-restored cases (rig/tests/index.mld:1633) that depend on the plain-data preference.

Regression test: add a structural test to rig/tests/index.mld that creates a multi-param no-payload tool with event_id:handle, normalizes through @normalizeResolvedValues, and asserts dispatch succeeds. The spike at tmp/spike-ut8-handle-loss.mld is the template.

Files: rig/runtime.mld (@normalizeResolvedValues), rig/tests/index.mld (regression test)

Testing:
1. Run spike: mlld tmp/spike-ut8-handle-loss.mld --no-checkpoint
2. Rig test gate: mlld rig/tests/index.mld --no-checkpoint
3. Canary: uv run --project bench python3 src/run.py -s workspace -d defended -t user_task_8

