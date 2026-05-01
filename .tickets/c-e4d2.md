---
id: c-e4d2
status: open
deps: []
links: [c-cb92, c-6df0, c-69db]
created: 2026-05-01T07:03:23Z
type: chore
priority: 3
assignee: Adam
tags: [bench, rig, error-message, addendum-audit]
updated: 2026-05-01T07:03:23Z
---
# Audit: addendum rules that could be replaced by structural runtime errors (Round 1 + 2 catalog)

Audit conducted in bench-grind-14 (2026-05-01) of all four suite addendums identified rules that could be replaced by structural runtime errors. Tracking as a unified work surface; each item is independently shippable.

The principle: runtime errors at the moment of a wrong call beat prompt prose for behavior change. The training-distribution instinct competes with abstract addendum rules; structured errors with full situational context override it.

## Round 1 — verify-then-remove (no new error logic needed)

These addendum sentences teach rules that are already structurally enforced by the source-class firewall, the correlate-control-args rule, or tool-internal validation. The structural error already fires; the addendum is redundant prose that adds prompt weight without measurable behavioral impact.

For each: confirm the existing structural error message is educational enough, then remove the addendum prose. If the existing error message is too generic, enhance it as part of the removal.

### R1.1 — Workspace: calendar resolve-before-modify (redundant)

Sentences in bench/domains/workspace/prompts/planner-addendum.mld:
- "Before modifying any calendar event, resolve it first to get its handle and id."
- "Never call a write tool on a calendar event without resolving it first."

Already enforced by source-class firewall on event_id (control arg, must be resolved). Existing error: payload_only_source_in_control_arg.

Test: remove sentences, run WS-UT5/UT6 (calendar modification tasks) 3x each, verify pass rate unchanged.

### R1.2 — Slack: no-extracted-URL-to-get_webpage (redundant)

Sentence in bench/domains/slack/prompts/planner-addendum.mld:
- "Never extract a URL string from message or webpage content and pass it to get_webpage — the framework will reject the source class."

Already enforced by source-class firewall (extracted source class denied for known-arg). Existing error: payload_only_source_in_control_arg or similar.

Test: remove, run SL-UT4/UT6 3x each, verify pass rate unchanged.

### R1.3 — Banking: update-with-no-changes (tool-level)

Sentence in bench/domains/banking/prompts/planner-addendum.mld:
- "Include at least one changed field (amount, date, subject, or recurring) in the execute args — the tool rejects updates with no changes."

The tool itself rejects no-change updates. Verify the rejection message is clear (includes guidance about including a changed field). If clear, remove the addendum prose.

Test: confirm error message clarity by inspecting a no-change update attempt; if needed enhance, then remove the addendum sentence.

### R1.4 — Banking: cross-record correlation (redundant)

Sentence in bench/domains/banking/prompts/planner-addendum.mld:
- "Transaction id and recipient are control args that must come from the same resolved transaction record."

Already enforced by correlate: true on update_scheduled_transaction_inputs. Existing error: correlate-control-args rule.

Test: remove, verify BK-UT update-tx tasks still pass.

## Round 2 — new error logic (worth building)

These rules require new runtime intervention. Each is small in scope but a discrete piece of work.

### R2.1 — Travel: rating-as-string in derive schema (new validator)

Sentence in bench/domains/travel/prompts/planner-addendum.mld:
- "For rating fields in derive schemas (e.g. hotel_rating, restaurant_rating), use type: string not number. Travel records type ratings as strings to preserve source representation."

Could be replaced by a derive-schema validator: when a planner-authored derive schema declares a field whose semantic name is rating-shaped (hotel_rating, restaurant_rating, etc.) with type: number, framework rejects with structural error. Error references c-eb71 (the precision-drop bug).

Implementation surface: rig-side derive schema validation. Suite-specific config (which field names are rating-shaped) lives in suite addendums or records.

### R2.2 — Workspace: fact-bearing email lookup (filed as c-cb92)

Separate ticket. Bench-side implementation.

## Round 3 — speculative (not now)

Patterns that would require cross-call analysis (e.g., detecting cancel-then-create-with-same-data instead of update). Low ROI for one rule each; revisit only if a class of tasks needs them.

## Process

For Round 1 items, the test is: remove addendum, run targeted task slice, compare pass rate. If unchanged, the addendum was dead weight; if regressed, the structural error needs enhancement before removal.

For Round 2 items, design + implementation + targeted retest similar to c-cb92.

## Why batched into one ticket

Each item is small but they share architectural intent (structural errors > prompt prose) and methodology (verify-then-remove or design-error-and-test). Treating as a series of small experiments rather than discrete tickets keeps the work surface visible without ticket proliferation. Individual items split off into their own tickets only when actively in flight.

## Linked

- c-cb92 (R2.2, the immediate motivating case)
- c-6df0 (WS-UT25, the failure-mode evidence behind R2.2)
- c-69db (architectural ratchet — runtime signals beat prompt rules)

