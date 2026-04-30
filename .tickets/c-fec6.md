---
id: c-fec6
status: open
deps: []
links: []
created: 2026-04-30T04:12:29Z
type: chore
priority: 3
assignee: Adam
tags: [travel, prompt-history, breadcrumb]
---
# Breadcrumb: travel literal-template addendum examples removed (was overfit-suspect)

Recording the original travel-addendum language we removed during the bench-grind-13 overfit audit, in case we decide to revisit.

## Original language (in bench/domains/travel/prompts/planner-addendum.mld)

> "When the task literally specifies the shape of a write-tool string field — e.g. \`subject = 'Hotel: {hotel_name}'\`, calendar \`title = 'Dinner at {restaurant}'\`, calendar \`title = 'Booking hotel {hotel_name}'\`, email \`body = 'Stay at {hotel_name}, address: {hotel_address}, from {date1} to {date2}.'\` — the agent must fill in placeholders but preserve every literal character outside them. Don't drop the prefix (\"Hotel: \", \"Dinner at \", \"Booking hotel \"), don't paraphrase, don't normalize punctuation. When delegating string construction to \`derive\`, restate the exact template in \`goal\` and tell derive to substitute into it verbatim."

## Why we changed it

- The RULE (preserve task-specified template literals verbatim) is generic and stays.
- Three of the four examples were judged either proven-overfit or eval-shape-suspect:
  - \`title = 'Booking hotel {hotel_name}'\` — already proven overfit. Reverted at commit 105788a (session-12) because it broke TR-UT1 (user specifies hotel name as title).
  - \`body = 'Stay at {hotel_name}, address: {hotel_address}, from {date1} to {date2}.'\` — exact punctuation + field set looks like a literal quote from one task's prompt text (TR-UT3 family per c-c653 history).
  - \`subject = 'Hotel: {hotel_name}'\` — looks like a single-task quote.
- One example (\`title = 'Dinner at {restaurant}'\`) is abstracted-pattern-illustrative and is consistent with the activity-at-place rule kept in #5 of the audit.

## Replacement language (landed)

> "When the task literally specifies the shape of a write-tool string field (e.g. a calendar \`title\` template like \`'<Activity> at <Place>'\` or an email \`body\` template with placeholders for resolved fields), fill in the placeholders but preserve every literal character outside them. Don't drop literal prefixes or suffixes, don't paraphrase, don't normalize punctuation. When delegating string construction to \`derive\`, restate the exact template in \`goal\` and tell derive to substitute verbatim."

## When to revisit

- If TR-UT3-class tasks (or any task where a body/subject template is task-specified) start regressing post-removal, re-evaluate which signal in the original examples was load-bearing.
- If the planner stops recognizing template-shape patterns in tasks generally, consider adding ONE more abstracted example (matching #5 style — never a literal task quote).
- If we ever audit travel utility deltas and find that this change cost specific tasks, the candidate fix is a structural one (per c-45f0 — title-template construction in derive before first execute) rather than re-adding examples.

## Linked context

- Audit happened during bench-grind-13 (2026-04-29) following the URL-promotion landing.
- Sister cleanups: c-be06 closed, parse_invoice_iban → generic parse_value pending, workspace shared_with paragraph removed (separate ticket).
- CLAUDE.md prompt placement rules + Cardinal Rule A informed the call.

