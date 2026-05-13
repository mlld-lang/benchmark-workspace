---
id: c-97aa
status: open
deps: []
links: []
created: 2026-05-13T11:34:49Z
type: feature
priority: 2
assignee: Adam
---
# Surface specific mlld policy rule + field through rig execution_log

## Background

mlld's policy synthesis generates `policy.facts.requirements.<op>.<field>` rules from input record `facts:` declarations. When the rule fires (missing field, no proof), the error reaches rig's surface as `tool_input_validation_failed` with `issues: null` — the specific rule and field info are dropped at `interpreter/eval/exec-invocation.ts:2506` classifier.

The full error envelope from mlld DOES include `code: "POLICY_CAPABILITY_DENIED"`, `field: "<name>"`, `rule: "policy.facts.requirements.<op>.<field>"`, etc. The rig surface drops these. Result: the planner sees a generic "tool_input_validation_failed" and retries with different shapes, exhausting budget instead of giving up cleanly. The opaque error also makes debugging painful (we spent significant time to identify the actual failing rule on UT12).

## Scope

Rig-side fix:
- `rig/runtime.mld` `@toolCallError` and downstream surface (planner.mld log entry construction): preserve `code`, `field`, `rule`, `hint`, `suggestions` from mlld's error envelope through to the execution_log.
- Update execution_log schema if needed.

Optional mlld-side fix:
- `interpreter/eval/exec-invocation.ts:2506` classifier: keep the descriptive code instead of mapping to `tool_input_validation_failed`. Two options:
  - Return `code` directly (e.g., `POLICY_CAPABILITY_DENIED`)
  - Keep `error` as the high-level category but also surface `subcode` or `rule` in the returned envelope.

## Acceptance

1. WS UT12 (or any current `tool_input_validation_failed` failure) re-runs locally — the JSONL execution_log entry includes `rule`, `field`, `code`. Visible to the planner via its prompt context so it knows WHY the dispatch failed.
2. Planner stops looping on validation failures it can't fix: when the error includes a useful code/rule, planner can recognize "this fix shape won't work" and pivot or `blocked` sooner.
3. Slack canaries 0/105 ASR.

## Priority

P2 — investigation/debugging quality, not utility-blocking. Helps future failure diagnosis. Could wait until after primary records refine migration lands.

## References
- `mlld-dev-prompt-influenced-rule.md` (the brief that surfaced the rig-side surface drop)
- `~/mlld/mlld/interpreter/eval/exec-invocation.ts:2506`
- `rig/runtime.mld` `@toolCallError`
- `rig/workers/planner.mld` execution_log construction

