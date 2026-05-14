---
id: WS-contact-autopopulation
status: open
deps: []
links: []
created: 2026-05-14T18:34:39Z
type: task
priority: 3
assignee: Adam
---
# [WS] Decide rig posture on inbox-auto-populated contacts

AgentDojo Inbox.contact_list auto-populates from sender/recipients/cc/bcc of all received emails — including attacker-sender addresses. No rig primitive distinguishes inbox-auto-populated from manually-added contacts, so any attacker email lands fact-grade contact authority on @contact.email. Decide: (a) benchmark-side fix (contact provenance), OR (b) rig treats auto-populated entries as carrying the sender email's untrusted label. §5 row A10, §9 #2.

