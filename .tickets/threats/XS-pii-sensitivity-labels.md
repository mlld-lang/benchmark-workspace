---
id: XS-pii-sensitivity-labels
status: open
deps: []
links: []
created: 2026-05-14T18:34:37Z
type: task
priority: 3
assignee: Adam
---
# [XS] Add secret/sensitive labels to PII fields on @user_info (cross-suite)

Add secret / sensitive labels to @user_info passport_number, bank_account_number, credit_card_number fields. Currently data.trusted with no sensitivity label; defense relies on read: projection omission across all roles. Adding labels would enable a no-secret-exfil / no-sensitive-exfil rule firing independently of projection — a second structural layer. Cross-suite concern: banking and slack have similar PII candidates on their user-info records. Decision shape: does the second structural layer warrant the addition, given display omission already holds? From sec-travel.md §8 Class D + §9 question 1; cross-references banking @user_account password handling.

