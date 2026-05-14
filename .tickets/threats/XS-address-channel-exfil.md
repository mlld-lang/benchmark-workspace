---
id: XS-address-channel-exfil
status: open
deps: []
links: []
created: 2026-05-14T18:35:02Z
type: task
priority: 3
assignee: Adam
---
# [XS] Cross-suite: workspace contact emails / recipients as exfil channel

@contact.email and @email_msg.recipients fact fields could become exfil channels if a future cross-suite agent reads them through workspace tools then forwards them via slack/banking. Distinct from XS-update-user-info-address-exfil (banking address content). Decision deferred to sec-cross-domain.md. From sec-workspace.md §9 #8.

