---
id: c-dee1
status: open
deps: []
links: []
created: 2026-05-13T11:34:08Z
type: feature
priority: 2
assignee: Adam
---
# Reader-set propagation primitive for messaging/calendar records

## Background

Per `camel-alignment-analysis.md`, CaMeL's policy callbacks use **per-instance reader sets** as the unit of "who can read this value." Each output record carries a readers set as metadata, derived from the source:

- `Email.readers = {sender, recipients, cc, bcc}`
- `Message.readers = {recipient}`
- `CalendarEvent.readers = {participants}` (organizer-as-user is User-trusted)
- `CloudDriveFile.readers = file.shared_with.keys()`

Policies enforce `can_readers_read_value(destination_readers, value)`: the destination's readers must include any readers attached to the value being sent. This is more granular than `data.trusted/untrusted` — it tracks *which entities* can read this value as a property of the value.

Our model approximates via role-based projection (`read: { role:worker: [...], role:planner: [...] }`) which is role-coarse, not entity-grained.

## Affected tasks (likely recoverable)

- WS UT15 (family reunion event from emails): emails have specific readers; event participants should inherit. CaMeL allows.
- WS UT18 (hiking trip with Mark): Mark named in task text (User-trusted); details from email (sender + recipients have readers covering Mark).
- WS UT20/UT21: similar shape — calendar event from email content.

## Design questions to resolve

1. **Per-instance reader sets on records** — should records support a `readers:` declaration that's POPULATED at coercion from another field? E.g., for `@email_msg`, `readers:` = union of sender + recipients + cc + bcc fields. Refine clauses might handle this.

2. **Reader-flow rule** — analogous to `labels.influenced.deny: ["exfil"]`, a `readers.<...>.flow` check at dispatch: "for write tools with `exfil:send` target, the destination arg's reader set must cover any readers attached to other args."

3. **mlld vs rig boundary** — readers as a label class (mlld policy rule) vs as a record metadata field (rig consumes via refine)? Probably the latter; refine sets per-instance readers, policy honors them via a new rule.

## Acceptance

1. Records carry per-instance reader sets via refine.
2. Policy rule honors reader-set propagation: write-tool destination readers must cover value readers.
3. WS UT15/UT18 (and similar): agent succeeds when email participants/sender cover the calendar participants.
4. Defense holds: untrusted source (file/webpage with no clear readers) → defaults to empty readers → write tools deny (matches current SHOULD-FAIL behavior).
5. Slack canaries stay 0/105 ASR.

## Dependencies

- Records refine landing (done).
- mlld dep-driven influenced (`mlld-dev-prompt-influenced-rule.md`).

## Estimated impact

2-4 workspace tasks (UT15, UT18, possibly UT20/UT21).

## Priority

Medium — design work, not immediate. After records refine migration + `?` field-optional + dep-driven influenced land, re-measure to confirm whether this is still the blocker on these tasks. Some may recover via dep-driven influenced alone (if email content is user-task-text-referenced, deps trace to User).

## References
- `camel-alignment-analysis.md` "CaMeL's reader-set propagation for messaging records"
- CaMeL ref: `~/dev/camel-prompt-injection/src/camel/pipeline_elements/agentdojo_function.py` `_get_email_metadata`, `_get_calendar_event_metadata`, etc.
- CaMeL ref: `~/dev/camel-prompt-injection/src/camel/capabilities/readers.py`, `utils.py:can_readers_read_value`
- `bench/domains/workspace/records.mld` — current `@email_msg`, `@calendar_event` shapes

