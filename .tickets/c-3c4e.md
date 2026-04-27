---
id: c-3c4e
status: closed
deps: []
links: []
created: 2026-04-26T18:07:49Z
type: bug
priority: 2
assignee: Adam
tags: [travel, wall-timeout, over-iteration]
updated: 2026-04-26T20:49:24Z
---
# [TR-UT19] hits 900s wall with 22 calls — multi-domain task still over-iterates

**Run 24962959633:** TR-UT19 hit 900s wall with 22 tool calls. The only task to wall-timeout this sweep (others completed within budget).

UT19 task: "2-day London + 3-day Paris trip; recommend top-rated car rental in each city". Multi-domain, complex.

Even with parallel resolve_batch dramatically reducing per-batch wall, the planner made 22 separate tool calls. Each call has GLM-5.1 planner thinking time (~25-40s) + the tool execution time. 22 calls × 30s/call avg ≈ 660s of just planner thinking.

## Possible patterns

1. **Re-resolves:** planner re-resolves the same data multiple times (happened in UT6 too)
2. **Validation errors causing retries:** earlier batches failed with `control_ref_backing_missing` etc., requiring retry with different arg shape
3. **Multi-stage gathering not consolidated:** planner does separate batches per city instead of one fan-out

## Investigation

Pull UT19 transcript: count distinct tools, look for retries with different arg shapes, identify what forced 22 calls.

## Fix candidates

1. **Planner.att rule:** "If a tool fails with control_ref_backing_missing or similar arg-shape errors, you may retry once with a different shape, but if it fails again, accept partial state and proceed."
2. **resolve_batch failure handling:** if a batch fails partially (some specs error), DON'T silently drop — surface which specs failed so the planner can retry only those rather than re-issuing the whole batch.
3. **Tool description tightening:** the recurring `control_ref_backing_missing` errors come from arg shape confusion. Better tool descriptions could prevent retries.

## Connection

c-d590 (singular hotel_name vs plural) is exactly this pattern — caused UT12 to over-batch trying different shapes. Same fix family.

## Discovered in

Sweep 24962959633 — only 900s timeout in the sweep, indicating remaining edge case.


## Notes

**2026-04-26T20:49:24Z** ## 2026-04-26 — Substantially mitigated by c-5a24 + c-eda4 (session bench-grind-9)

UT19 wall-time went from 622s/42 iters/22 MCPs (baseline 24962959633) → 156s/34 iters/16 MCPs (post-c-5a24 run 24964974666). Then post-c-eda4 in local canary: reaches compose with full €4,260 answer table (limited only by c-63fe MCP disconnect on remote).

The over-iteration was being caused primarily by:
1. **c-5a24 field clobber** — planner re-resolved entries because previously-resolved fields had been wiped. FIXED.
2. **c-eda4 batch state clobber** — planner re-resolved entire record families because parallel-batch settle wiped them. FIXED.

Both pieces eliminated. UT19 still shows over-fanning to non-required record types (resolves restaurants/hotels for a cars+restaurants task) but that's planner-quality not framework — already addressed by c-5a24-induced state stickiness.

## Status reduction

Downgrading from "structural over-iteration" to "edge case where planner over-fans, capped by c-63fe on remote". Recommend:
- Wait for c-63fe to land before re-evaluating UT19 specifically.
- If after c-63fe fix UT19 still over-iterates, file targeted ticket for the over-fanning (suite addendum: "for cars-only or restaurants-only tasks, don't pre-emptively resolve other families").

Closing as superseded by c-5a24 + c-eda4. New ticket should be filed if measurable over-iteration recurs after c-63fe lands.
