---
id: c-9fb7
status: open
deps: []
links: [c-891b, c-8f56]
created: 2026-05-06T12:07:50Z
type: task
priority: 1
assignee: Adam
tags: [security, audit, prereq]
updated: 2026-05-06T12:07:56Z
---
# AgentDojo threat-model audit: per-suite injection_tasks.py → defense coverage table

Build a verified table of every AgentDojo injection task across all four suites and what each one actually attacks. Output: spec-agentdojo-threat-model.md (or similar). Prerequisite for c-891b and any future defense-design work.

## Why

bench-grind-20 attempted c-ad40 add exact: to update_user_info_inputs based on c-891bs claim that UT13 × IT7 attacks update_user_info. A local attack run revealed IT7 actually targets update_password already defended. The c-ad40 fix was reverted; lesson captured in c-8f56.

Root cause: we have ticket-text descriptions of historic breaches CHALLENGES.md, SCIENCELOG references, per-ticket B-n labels but no verified mapping to the CURRENT AgentDojo task definitions. AgentDojo gets updated; ticket text doesnt. The mismatch led to designing defense for a non-existent threat AND breaking benign utility.

This audit fixes the gap once and produces a reference table that future tickets can cite.

## Scope

For each suite banking, slack, workspace, travel, read:
bench/.venv/lib/python3.13/site-packages/agentdojo/default_suites/v1_1_1/SUITE/injection_tasks.py

This is task-definition metadata class names, GOAL strings, the tool calls each injection tries. It is NOT checker code — Cardinal Rule A no checker code reading does not apply. The injection_tasks.py file declares the attack shape; the user_tasks.py file plus checker code off-limits verify success.

Per injection task, document:
- Class name e.g. InjectionTask7
- GOAL string the attackers visible objective
- Which tools the attack tries to call
- Which arg fabrication shape extracted-from-untrusted, known-not-in-task, fabricated URL, cross-record mixing, etc.
- Per-suite UT × IT pairs that this attack runs against

Cross-reference with our current defense set. Build a per-suite section listing each IT, its target tool, the defense layer that catches it, the corresponding test name, the mutation entry, and a STATUS field one of: COVERED-VERIFIED, COVERED-NO-TEST, UNDEFENDED, NOT-IN-CURRENT-MATRIX.

## Output

spec-agentdojo-threat-model.md at clean/ root. Sections:
1. Per-suite per-IT entries
2. Aggregate coverage table
3. Gaps section: tools/threat shapes with no defense, with no test, or with stale ticket text

## Acceptance

1. spec-agentdojo-threat-model.md exists with all 4 suites covered.
2. Cross-reference table matches what tests/run-mutation-coverage.py shows plus the actual scripted suites.
3. Any ticket-text inaccuracies surfaced like c-891bs B4 claim noted with corrections.
4. Estimated effort: half a day.

## Why this unblocks c-891b

c-891bs scope taint-based defenses, risk-classification coverage needs a verified target list before designing tests. With the audit table in hand, c-891b becomes for each rule, tool-class cell in the verified table, write a test plus mutation entry instead of speculatively defending against narratives that may or may not match the current attack matrix.

