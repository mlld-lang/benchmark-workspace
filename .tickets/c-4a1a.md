---
id: c-4a1a
status: open
deps: []
links: []
created: 2026-05-05T14:06:55Z
type: task
priority: 2
assignee: Adam
tags: [rig, planner-signal, probe-grounded]
---
# Extract/derive null_fields + rehearse blocked_extract_fields signals

**Probe-grounded** (tmp/probe-banking-date-extracted/probe.mld). Witty-comet UT2 transcript showed the planner spending 2 iterations bouncing off a 'blocked_args: [date]' rehearse where the underlying cause was its own extract returning effective_date=null (file said 'increased by 100' with no date). The planner reasoned 'date is a payload arg but might require a specific source class' — wrong inference; the issue was sparse extract output.

## Landed in this ticket

**(D) null_fields on extract + derive results.** Both worker result objects now carry `null_fields: [...]` listing schema-declared fields the worker did not fill. Computed via @nullFields in rig/runtime.mld parallel to @previewFields. Surfaces at the moment the data shape is determined, before any rehearse call.

**(A) blocked_extract_fields on rehearse result.** When rehearse blocks because compileArgRef hits extracted_field_missing or derived_field_missing on a referenced field, the rehearse return now carries `blocked_extract_fields: [{arg, source, name, field}]` alongside blocked_args. The planner can disambiguate 'wrong source class' vs 'extract didn't fill this field' without bouncing.

## Files touched

- rig/runtime.mld — @nullFields helper (parallel to @previewFields), exported
- rig/workers/extract.mld — null_fields added to both result paths (tool-fetch + source-backed) and to state writes
- rig/workers/derive.mld — null_fields added to result + state writes
- rig/workers/planner.mld — @blockedFieldHints helper; blocked_extract_fields added to plannerRehearse result; @planner_tool_result schema extended; blockedFieldHints exported
- rig/tests/index.mld — 10 invariant tests (NF-1..5 for nullFields, BFH-1..5 for blockedFieldHints)
- tmp/probe-banking-date-extracted/probe.mld — reusable probe demonstrating the rehearse signal end-to-end

## Verification

- Invariant gate: 210/211 (was 200, +10 new), xfail unchanged
- Worker LLM tests: 24/24 unchanged
- Security suites: slack 11, banking 8, workspace 6, travel 10 — all green
- Probe demonstrates blocked_extract_fields surfaces correctly with full {arg,source,name,field} hint when extract entry has null at requested field

## Pending

- Planner.att prompt note explaining null_fields + blocked_extract_fields. Drafted, awaiting user approval per the prompt-approval rule.
- A targeted bench-grind UT2 run after prompt approval to verify the planner reads the new signal and skips the null-extract pivot loop.

## Why this matters

The witty-comet UT2 trace showed the planner reaching the right outcome eventually (drop date, retry) but burning 2 iterations on a guess that wasn't supported by the available signal. With these two signals the planner has unambiguous structural data: 'this field of your extract is null' surfaces directly. Same family as c-cb92 / c-e4d2 (replace addendum prose with structural runtime errors).


## Notes

**2026-05-05T14:18:39Z** Landed and verified.
- @nullFields helper in rig/runtime.mld + exported
- extract result + state writes carry null_fields (both modes)
- derive result + state writes carry null_fields
- @blockedFieldHints helper in rig/workers/planner.mld + exported
- plannerRehearse result carries blocked_extract_fields
- @planner_tool_result schema extended for null_fields + blocked_extract_fields
- planner.att updated: 1 sentence under preview_fields paragraph + 1 bullet under rehearse return shape
- 10 zero-LLM invariant tests (NF-1..5 + BFH-1..5) — all pass
- probe tmp/probe-banking-date-extracted/probe.mld reproduces the rehearse signal end-to-end with full {arg,source,name,field} hint

Effect: banking UT2 3/3 PASS local post-prompt (was 1/2 pre-prompt). Worker LLM tests 24/24 on rerun. Cloud sweep verification next.
