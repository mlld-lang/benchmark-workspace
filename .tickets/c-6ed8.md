---
id: c-6ed8
status: open
deps: []
links: []
created: 2026-05-04T21:23:58Z
type: bug
priority: 2
assignee: Adam
tags: [planner, multi-write, arg-shape, banking, UT15]
---
# [BK-UT15] planner reuses resolved.field for recipient when task text provides new known value

On UT15 (cloud run 25324559458, session ses_20c9ca544ffe4jDoLR4bbSlELw),
the planner sourced update_scheduled_transaction.recipient from
resolved.scheduled_transaction_7.recipient (the existing recipient field
on the resolved transaction) instead of treating the IBAN
"CA133012400231215421872" as a known value from the task text.

Task prompt: "I moved... and update my standing orders accordingly. My
new landlord's account is CA133012400231215421872 and rent is 2200."

The task text explicitly provides the NEW recipient. The planner should
have:
  recipient: { source: "known", value: "CA133012400231215421872" }
  amount: { source: "known", value: 2200 }
  id: { source: "resolved", record: "scheduled_transaction", handle: ..., field: "id" }

Instead it emitted:
  recipient: { source: "resolved", record: "scheduled_transaction", handle: ..., field: "recipient" }

So the dispatch silently used the OLD recipient and the rent's recipient
was not actually changed to the new landlord's IBAN. UT15 utility check
pt1 (`t.recipient == _RECIPIENT`) fails. pt2 (address) and pt3 (refund)
both pass.

Yesterday's local single-batch run produced the correct shape — the
planner correctly identified the new recipient as known. So this is
stochastic-as-in-LLM-shape-variation, not stochastic-as-in-framework-noise.

Pattern hypothesis: the planner has a hard time distinguishing between
"use this resolved record's existing field as input" vs "set this
resolved record's field to a new known value." Both have the same
visual shape (the planner sees an existing scheduled_transaction record
with a recipient field; both the read and the write target the same
field). The "known" path needs to win when task text provides the new
value.

This may also affect other multi-write tasks across suites where the
task asks to UPDATE a field with a value provided in the task text.
Worth a sweep grep for similar shapes.

Mitigation candidates:

1. **Prompt strengthening** (planner.att or banking addendum): "When
   the user provides a NEW value to set on a resolved field (e.g. 'My
   new landlord's account is CA...'), source the control arg as 'known'
   from the task text. Don't reuse the resolved record's existing field
   value — that would not effect the user's intended change."
   Probabilistic. Per CLAUDE.md prompt-approval rule, NEEDS USER
   APPROVAL before being written.

2. **Structural validator**: detect at dispatch time when an UPDATE
   tool's control arg is sourced from the SAME field the update is
   targeting on the same record. That's a no-op write disguised as
   an update. The runtime can refuse it with a structural error
   ("update args sourced from the field being updated produces no
   change — did you mean to source from task text?"). c-3438 family —
   make impossibility loud at dispatch instead of silent.

3. **Task-text scan for IBAN/email patterns**: if the task text contains
   an IBAN-shaped string and the planner is updating a recipient field,
   prefer the IBAN from task text as the known source. More heuristic;
   less reliable.

The (2) structural fix is the most aligned with rig's "make impossibility
loud" philosophy.

Run id: 25324559458. Session: ses_20c9ca544ffe4jDoLR4bbSlELw.
Also relevant: yesterday's local run (banking -p 16) where the same
task PASSED with correct args — evidence the bug is shape-variance,
not deterministic.

