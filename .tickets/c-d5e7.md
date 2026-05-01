---
id: c-d5e7
status: closed
deps: []
links: []
created: 2026-04-26T20:49:10Z
type: bug
priority: 3
assignee: Adam
tags: [travel, derive, worker, regression-watch]
updated: 2026-05-01T08:59:27Z
---
# [Travel UT8] Watch: derive_empty_response on vegan-restaurant task

## Symptom

Run 24966154043 (image adc2e7f, post-c-eda4): UT8 ran 9 MCP calls, resolved restaurants + dietary restrictions + ratings + prices + addresses cleanly. Then derive call returned `derive_empty_response` (worker LLM produced empty content). Planner retried 1-2x, all returned same empty response, eventually unparseable terminal.

## Status

UNCLEAR if real bug or stochastic. Was True in:
- 24962959633 baseline
- 24964974666 c-5a24 sweep
- Local canary post-c-eda4 (not specifically run, but no pattern reason it would have changed)

Failed in:
- 24966154043 c-eda4 remote sweep

The c-eda4 fix only touched batch state-merge. UT8 ran a single resolve (no batch) then a multi-spec resolve_batch (which c-eda4 affected). The MCP server might have been distressed (c-63fe-adjacent — many other tasks in this run hit MCP errors).

## What to watch for

- If UT8 fails again with derive_empty_response → real bug
- If only fails on c-63fe-heavy remote runs → c-63fe-adjacent (worker LLM disconnected)
- If always fails locally → derive worker prompt or input shape issue

## Investigation if it recurs

1. Pull transcript: was the derive worker session log empty, or did it return something the host parsed as empty?
2. Check derive worker test (`rig/tests/workers/run.mld` derive_simple_max etc.) — does it cover the vegan-style schema?
3. Check whether large dietary_restrictions strings in resolved.restaurant trigger context overflow.

## Discovered in

Session bench-grind-9 — full transcript scan of failing remote tasks.


## Notes

**2026-05-01T08:59:27Z** Closing 2026-05-01. TR-UT8 verified passing in bench-grind-14; derive_empty_response watch no longer needed.
