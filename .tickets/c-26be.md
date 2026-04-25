---
id: c-26be
status: open
deps: []
links: []
created: 2026-04-24T23:15:28Z
type: bug
priority: 2
assignee: Adam
tags: [extract]
---
# Slack UT4 / hobbies: extract returns null visibly on resolved-msg sources

Symptom: extract from a resolved slack_msg returns 'null' to the planner even when it succeeds. Verified in transcript ses_23e9a951c (slack UT4 - post hobbies). Alice's extract returned null, Eve's returned null, Charlie's returned full attestation. On retry Eve hit extract_source_already_extracted, proving the data IS stored. Same root class as c-ad66 (already P0 ticket: 'Extract worker returns null on source-backed extraction from resolved records'). Add slack UT4 transcript as a second repro alongside the calendar-event-description case.

