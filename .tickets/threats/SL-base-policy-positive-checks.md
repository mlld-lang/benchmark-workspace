---
id: SL-base-policy-positive-checks
status: open
deps: []
links: []
created: 2026-05-14T18:34:21Z
type: task
priority: 1
assignee: Adam
---
# [SL] Verify BasePolicy positive check on slack_user_name / slack_channel_name / email kinds

Verification target: analogous to banking §9 #5 for `iban`. The `kind:` annotations on `@send_direct_message_inputs.recipient`, `@invite_user_to_slack_inputs.{user, user_email}`, and `@add_user_to_channel_inputs.{user, channel}` rely on BasePolicy enforcing a positive-match check against the kind. Verify BasePolicy's new fact-kind matching grammar correctly rejects scalars without the matching kind label, not merely scalars without any fact label. From sec-slack.md §9 question 5.

