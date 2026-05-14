---
id: WS-attachment-label-prop
status: open
deps: []
links: []
created: 2026-05-14T18:34:34Z
type: task
priority: 2
assignee: Adam
---
# [WS-UT-13, WS-UT-33] Verify file-source labels propagate through attachments array references at send_email dispatch

@email_msg.attachments is data.untrusted on source; @send_email_inputs.attachments is data.trusted (handle-grounded). Verify file-source labels propagate through array refs into send-time dispatch so a secret-labeled file cannot be attached without no-secret-exfil firing. §5 row A9, §8 Class B, §9 #1.

