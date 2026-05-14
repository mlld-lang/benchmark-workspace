---
id: SL-no-email-promotion-from-untrusted
status: open
deps: []
links: []
created: 2026-05-14T18:34:04Z
type: task
priority: 2
assignee: Adam
---
# [SL] Verify no extract/derive path mints fact:email from data.untrusted content

Verification target: confirm no extract/derive path can promote `data.untrusted` content (e.g., `@webpage_content.content`) into a fact-bearing email handle. Closes Class D's 'extracted email reaches user_email arg' path under strict fact-floor on `@invite_user_to_slack_inputs.user_email: kind:email`. Structurally analogous to banking IBAN-grounding via tx records. From sec-slack.md §8 Class D.

