---
id: WS-influenced-rule-verify
status: open
deps: []
links: [BK-influenced-prop-verify, TR-influenced-prop-verify]
created: 2026-05-14T18:34:30Z
type: task
priority: 1
assignee: Adam
updated: 2026-05-14T19:07:48Z
---
# [WS] Verify labels.influenced.deny propagates via mx.influenced channel post-records-as-policy

Verify #influenced-deny-exfil rule (labels.influenced.deny: [destructive, exfil]) survives the records-as-policy migration via the new mx.influenced channel. Closes A1/A2 typed-instruction-channel laundering through influenced fields. §8 Class A.

