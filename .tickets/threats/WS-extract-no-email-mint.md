---
id: WS-extract-no-email-mint
status: closed
deps: []
links: []
created: 2026-05-14T18:34:54Z
type: task
priority: 1
assignee: Adam
updated: 2026-05-14T23:08:31Z
---
# [WS] Verify no extract path mints kind:email factsource on extracted scalars

Verify selection refs from extract phase only point at a resolved @contact or @email_msg field — no extract path mints a kind:email factsource on an extracted scalar. Closes worker-laundering extract→fact path for A1/A10. §8 Class B.

