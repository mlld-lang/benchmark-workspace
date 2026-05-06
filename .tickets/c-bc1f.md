---
id: c-bc1f
status: open
deps: []
links: [c-83f3, c-5aca, c-ae22]
created: 2026-05-06T05:29:43Z
type: task
priority: 3
assignee: Adam
tags: [tests, fixtures]
updated: 2026-05-06T05:52:22Z
---
# Stale @stateWithResolved fixture: produces non-canonical resolved bucket

tests/lib/security-fixtures.mld @stateWithResolved produces a bucket with shape {version, by_handle} but production @lookupResolvedEntry (rig/intent.mld:265) requires the canonical {_rig_bucket: "resolved_index_v1", order, by_handle, version, planner_cache} shape via @isResolvedIndexBucket. Direct resolved-ref lookups against fixture-seeded state therefore fail with resolved_handle_not_found.

Discovered while writing c-83f3 B7 tests — worked around with a local b7CalendarSeed helper inlining the canonical shape (tests/scripted/security-workspace.mld). Other callers may be passing for the wrong reason: tests/scripted/security-slack.mld:347 (testSelectionRefBackingWithoutIdentityRejected) uses it for a selection-ref test that asserts ok:false — could be passing via "resolved_handle_not_found" instead of the intended "selection_backing_missing without identity_field" path. Worth auditing.

Fix: update @stateWithResolved (and @stateResolvedAndExtracted) in tests/lib/security-fixtures.mld to emit the canonical _rig_bucket: resolved_index_v1 envelope, including order, planner_cache stub, and per-entry identity_field/identity_value/field_values matching what @normalizeResolvedValues writes (rig/runtime.mld:287). Then re-verify the slack/travel/banking selection-ref tests still assert what they intend — they may surface real test-quality issues.

