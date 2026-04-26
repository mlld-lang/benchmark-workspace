---
id: c-3c4e
status: open
deps: []
links: []
created: 2026-04-26T18:07:49Z
type: bug
priority: 2
assignee: Adam
tags: [travel, wall-timeout, over-iteration]
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

