---
id: c-ut8r
status: closed
deps: []
links: []
created: 2026-04-23T20:09:44Z
type: bug
priority: 0
assignee: Adam
tags: [dispatch, handle, metadata-loss]
updated: 2026-04-24T19:54:42Z
---
# Fix @normalizeResolvedValues handle metadata loss

Rig fix landed: @normalizeResolvedValues uses direct field access instead of @nativeRecordFieldValue. Spike passes, invariant gate 98/0. Bench still fails because of m-5178 (collection dispatch for multi-param all-facts tools). The rig fix is correct but insufficient — m-5178 blocks the tool dispatch itself.

