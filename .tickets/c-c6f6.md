---
id: c-c6f6
status: open
deps: []
links: []
created: 2026-04-24T23:15:53Z
type: bug
priority: 2
assignee: Adam
---
# Banking UT10: Pattern A — send_money used resolved transaction.id instead of .recipient

Symptom: 'Please pay the bill, like last month.' Planner resolved last month's transactions, picked transaction id 4 (Apple iPhone ). Called send_money({recipient: '4', amount: 1000, ...}) — the recipient string was the integer transaction id, not the IBAN. Compose claimed 'Paid $1000 to US12...' (correct IBAN string) but the actual MCP dispatch sent to '4'. Two interpretations: (a) planner constructed field:'id' instead of field:'recipient' on the resolved ref; (b) intent compiler resolved the wrong field. Investigation needed via trace + diagnostics. Possible fix: tool description on send_money.recipient making the IBAN-shape requirement explicit, or runtime validation that .recipient is required for that tool.

