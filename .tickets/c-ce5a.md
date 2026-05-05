---
id: c-ce5a
status: open
deps: []
links: [c-3c2b, c-7016, c-891b]
created: 2026-05-05T06:13:36Z
type: task
priority: 1
assignee: Adam
tags: [security, kind-tags, banking, travel, bench-records]
updated: 2026-05-05T06:13:40Z
---
# Bench domain: tag banking + travel record fact fields with kind:

Slack and workspace bench domain records are now tagged with `kind:` annotations (commit f11d084). Banking and travel are not. Without kind tags, those suites' fact fields fall back to mlld's strict `fact:*.<argName>` default — which over-blocks legitimate cross-record flows where the input arg name differs from the source field name (e.g. `send_money.recipient` ← `@iban_value.value`).

## What to read first

1. `SECURITY-RIG-WRONG-RECORD-BYPASS.md` — the kind-tag firewall design from mlld-dev
2. `bench/domains/slack/records.mld` — slack tagged producer + input records (reference example)
3. `bench/domains/workspace/records.mld` — workspace tagged records (reference example, more complex)
4. `bench/domains/banking/records.mld` — needs tagging
5. `bench/domains/travel/records.mld` — needs tagging
6. mlld commit 0c6558d62 "Add fact kind tags for record policy requirements" — the core implementation

## Pattern to follow

Replace bare type declarations:
```mlld
record @contact = {
  facts: [email: string]
}
```

With object-form including kind:
```mlld
record @contact = {
  facts: [email: { type: string, kind: "email" }]
}
```

Both producers (records returned by read tools) AND input records (write tool input schemas) tag fields with the same kind names. mlld walks records in scope at policy.build, builds kind→`fact:@<rec>.<field>` index, derives accepts per input fact field automatically.

## Banking kinds (suggested)

- `@transaction.id`: kind "transaction_id"
- `@transaction.sender` / `.recipient`: kind "iban"
- `@scheduled_transaction.id`: kind "scheduled_transaction_id" (or share with @transaction; depends on whether they're interchangeable as control args)
- `@scheduled_transaction.sender` / `.recipient`: kind "iban"
- `@iban_value.value`: kind "iban"
- `@user_account.{first_name,last_name}`: probably skip (not control args anywhere)
- `@file_text.file_path`: kind "banking_file_path"

Inputs:
- `@send_money_inputs.recipient`: kind "iban"
- `@schedule_transaction_inputs.recipient`: kind "iban"
- `@update_scheduled_transaction_inputs.{id, recipient}`: kinds "scheduled_transaction_id", "iban"

Audit each tool's actual flow before committing — these are suggestions, not gospel.

## Travel kinds (suggested — verify against actual records)

- `@hotel.name`: kind "hotel_name"
- `@restaurant.name`: kind "restaurant_name"
- `@car_rental_company.name`: kind "car_rental_name"
- `@flight.id`: kind "flight_id" or similar
- `@calendar_evt.id_`: kind "calendar_event_id" (matches workspace)
- `@calendar_evt.participants`: kind "email" (matches workspace)
- `@user.email`: kind "email"

Inputs vary per write tool — audit `bench/domains/travel/records.mld` for the input record set.

## Acceptance

1. All banking + travel record + input record fact fields tagged with appropriate kinds.
2. Existing security suites for banking remain green (currently 8/0/0). Add new tests if there are kind-derivable cases worth locking.
3. Travel security suite created (currently doesn't exist) with at least the recommendation-hijack test from c-7016 once the kinds are in place.
4. Run a banking sweep + travel sweep to confirm no utility regression. Strict defaults can over-block; if a sweep regresses, the fix is more kinds (or an `accepts:` override on a specific input field).

## Why this matters

Without kind tagging, banking and travel write tools' fact fields default to `fact:*.<argName>` — which doesn't match any real producer record's fact (different field names). Real flows go through compileExecuteIntent which produces the wrapped intent shape, and policy.build accepts those (mlld handles wrapped values specially). But selection-ref attacks on the wrong record would slip through if the kinds aren't aligned.

Slack tagging took ~20 minutes. Banking is similar size; travel may be larger (more record types).

## Linked

- c-3c2b (closed) — the wrong-record-bypass firewall design
- c-7016 — travel recommendation-hijack tests; benefits from this work

