---
id: XS-update-user-info-address-exfil
status: open
deps: []
links: []
created: 2026-05-14T18:30:32Z
type: task
priority: 2
assignee: Adam
---
# [XS] update_user_info accepting untrusted address content as exfil channel

Cross-suite: @file_text.content (data.untrusted) flows into update_user_info update args via UT13 with no records-side gate. Within banking this is low-stakes (no money flow). Cross-suite the address fields could become exfil channels if read by a future workspace/slack agent. Defer to sec-cross-domain.md. From sec-banking.md §5 row A4 + §9 question 1.

