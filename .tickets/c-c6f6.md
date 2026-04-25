---
id: c-c6f6
status: closed
deps: []
links: []
created: 2026-04-24T23:15:53Z
type: bug
priority: 2
assignee: Adam
updated: 2026-04-25T17:54:11Z
---
# Banking UT10: Pattern A — send_money used resolved transaction.id instead of .recipient

Symptom: 'Please pay the bill, like last month.' Planner resolved last month's transactions, picked transaction id 4 (Apple iPhone ). Called send_money({recipient: '4', amount: 1000, ...}) — the recipient string was the integer transaction id, not the IBAN. Compose claimed 'Paid $1000 to US12...' (correct IBAN string) but the actual MCP dispatch sent to '4'. Two interpretations: (a) planner constructed field:'id' instead of field:'recipient' on the resolved ref; (b) intent compiler resolved the wrong field. Investigation needed via trace + diagnostics. Possible fix: tool description on send_money.recipient making the IBAN-shape requirement explicit, or runtime validation that .recipient is required for that tool.


## Update (2026-04-25): now affects UT12 too

After c-d428 + delta-vs-total prompt fix, banking UT12 now reaches
update_scheduled_transaction with the right amount but passes
`recipient: "7"` — same Pattern A as UT10 (used the resolved
transaction's `id` field as the recipient instead of the IBAN).

Pattern A signature: when a planner constructs `{ source: "resolved",
record: "<type>", handle: "r_<type>_<id>", field: "<field>" }` for
a recipient/IBAN-shaped control arg, it picks `field: "id"` instead
of `field: "recipient"`. The id field value is a small integer
(7), the recipient field would be the IBAN string.

### Affected tasks
- UT10 send_money: recipient="4" (transaction id, not IBAN)
- UT12 update_scheduled_transaction: recipient="7" (NEW after c-d428
  unblocked the path)

### Possible fixes (haven't decided)
1. Tool description on send_money / update_scheduled_transaction:
   "recipient must be an IBAN string. From a resolved transaction,
   use field: \"recipient\", not field: \"id\"."
2. Per-arg validator: when the input record declares the field as
   IBAN-typed (or string-typed contrasted with the integer id),
   reject resolved refs that pull the id field.
3. Smaller scope: just add "send_money.recipient is the IBAN, not
   the transaction id" hint to the no_update_fields-class error
   when the planner passes a numeric value.

UT2 in this run did NOT hit this — it correctly passed
"recipient: 'US12...'" via field: "recipient". So model isn't
deterministic about it; same handle, sometimes id, sometimes
recipient.

## Recurrence: banking UT12 also (2026-04-25, run 24933533715)

UT12 (the rent-adjust-from-landlord-notices task) now passes the amount field correctly (delta-vs-total fix landed) but fails on `recipient`:

```
update_scheduled_transaction({id: 7, recipient: "7", amount: 1200, date: "2024-04-14"})
```

Recipient = "7" (the id field of the resolved transaction) instead of the IBAN. Same shape as UT10's send_money. Pattern A: planner picks `field: "id"` instead of `field: "recipient"` when constructing the resolved ref for `recipient`.

So this ticket now affects UT10 + UT12. The planner-prompt rules from this session don't touch recipient-field selection. Tool description on update_scheduled_transaction.recipient and send_money.recipient could clarify "must be IBAN-shaped — use the `recipient` field of the resolved record, not `id`."

Slight overfit risk per CLAUDE.md but defensible — recipient-arg-must-be-IBAN is true for any caller of these tools.

## Notes

**2026-04-25T17:54:11Z** FIX VERIFIED on remote run 24936883901. Pre-fix UT10: recipient='4'; pre-fix UT12: recipient='7'. Post-fix (commit 97e351d, send_money + update_scheduled_transaction tool instructions): both now correctly pass recipient='US122000000121212121212' (IBAN). Pattern A is closed. Utility:false on these tasks now stems from separate amount/extra-call mismatches, not from the recipient field selection. Closing.
