---
id: c-f53d
status: closed
deps: []
links: [c-pe00]
created: 2026-04-23T02:08:06Z
type: task
priority: 1
assignee: Adam
tags: [prompts, error-messages, audit]
updated: 2026-04-23T17:17:12Z
---
# Audit all rig prompts and error messages for actionability

Review every error message the planner can receive from rig tool wrappers and every prompt section that guides model behavior. Ensure each error message:

1. States what went wrong specifically
2. Shows what the model sent vs what was expected
3. Gives a concrete example of the correct call shape
4. Does not use internal terminology (auth_bucket, source_class, policy_build) without explanation

Also review the planner prompt (rig/prompts/planner.att) for gaps where the model has no guidance — e.g. update fields, when to use selection vs resolved vs known, what the arg shapes look like for each tool type.

Files to audit:
- rig/prompts/planner.att
- rig/workers/execute.mld (plannerValidationFailure calls)
- rig/workers/resolve.mld (error returns)
- rig/workers/extract.mld (error returns)
- rig/workers/derive.mld (error returns)
- rig/intent.mld (compileScalarRef error shapes)
- rig/planner_inputs.mld (validation errors)


## Notes

**2026-04-23T17:17:11Z** Completed by the prompt/error audit session. Produced plan-prompt-error-updates.md and plan-worker-tests.md. Work broken into tickets c-pe00 through c-pe08.
