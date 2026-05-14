---
id: BK-password-records-side-strip-question
status: open
deps: []
links: []
created: 2026-05-14T18:30:32Z
type: task
priority: 3
assignee: Adam
---
# [BK] Move password-strip from MCP-side to records-side

Open question: currently get_user_info password-stripping is enforced at the MCP server (mcp_server.py), not at the records layer. If the MCP changes, the defense regresses silently. Should @user_account carry a password field with data.secret declaration + read: blocks omitting it? Speculative records-side hardening. From sec-banking.md §3 + §9 question 7.

