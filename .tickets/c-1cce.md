---
id: c-1cce
status: closed
deps: []
links: []
created: 2026-04-23T02:07:37Z
type: bug
priority: 0
assignee: Adam
tags: [execute, dispatch, update]
updated: 2026-04-23T03:20:33Z
---
# Update fields not reaching preparedArgs in execute dispatch

reschedule_calendar_event fails with no_update_fields even when the intent compiler produces correct compiled_args containing new_start_time and new_end_time. The spike (tmp/spike-reschedule-intent.mld) proves intent compilation works — compiled_args has all three fields. But in live bench runs, @hasNonNullFieldValue(@preparedArgs, @updateFields) returns false every time, across 5 attempts with known, derived, and selection sources.

The values compile into @compiled.compiled_args but don't survive into @preparedArgs. The path is: @payloadPairs iterates @payloadArgs checking @compiled.compiled_args[@argName].isDefined() → @payloadValues → @mergeArgSources → @preparedArgs. Something in this chain drops the update fields in the session context that doesn't happen in standalone spikes. May be related to structured value wrapper behavior across session callback boundaries.


## Notes

**2026-04-23T02:22:32Z** Root cause found: the no_update_fields error comes from @policy.build (the mlld runtime), NOT from rig's @hasNonNullFieldValue check. The error has phase: 'build'. The runtime's policy builder enforces updateArgs validation on the authorization intent, but payload args (new_start_time, new_end_time) aren't in the authorization intent — they're just data. The runtime shouldn't check for them in the authorization. This is a runtime bug in @policy.build's updateArgs validation.

**2026-04-23T03:00:10Z** ## Investigation summary (2026-04-22)

### What we know

1. **The error is from @policy.build, not from rig's @hasNonNullFieldValue check.** The execution log shows `phase: 'build'` on the no_update_fields issue. @policy.build rejects before rig's own update check at execute.mld:91 ever runs.

2. **Intent compilation is correct.** Spike at tmp/spike-reschedule-intent.mld proves `@compileExecuteIntent` produces correct `compiled_args: { event_id: '5', new_start_time: '2026-04-27 10:00', new_end_time: '2026-04-27 11:00' }` for all source types (known, derived, selection).

3. **The policy_intent (flat form) only contains control args.** `@flatPolicyIntent` in intent.mld builds from entries where `auth_bucket != 'allow'`. Payload known values had no `auth_bucket` set (intent.mld line 561), so they're excluded from the flat intent. Result: `policy_intent = { reschedule_calendar_event: { event_id: { eq: '5', attestations: [...] } } }` — no update fields.

4. **@policy.build needs to SEE the update fields to pass updateArgs validation.** The GPT/mlld dev confirmed: the runtime checks rawArgs in authorization-compiler.ts:1775 BEFORE stripping payload args. Flat form with update fields as bare values works: `{ reschedule_calendar_event: { event_id: {...}, new_start_time: '2026-04-27 10:00' } }` returns valid:true with the update field in strippedArgs.

5. **Bucketed form also works** per the mlld dev's tests.

### What we tried

1. **Added auth_bucket: 'known' to payload known values in intent.mld** — This put the values in the known authorization bucket, but also put ALL payload known values into @flatPolicyIntent for every tool, breaking tests for non-update tools (execute-worker-known-control-arg-policy, execute-worker-collection-input-record-policy). Reverted.

2. **Merging update fields into @policyIntent in execute.mld** — Added update field values as bare entries in the flat policy intent before calling @policy.build. The approach is:
   - Build @baseIntent as before (flat form with only control args)
   - If updateFields.length > 0, merge compiled_args values for update fields into the operation's entry
   - Pass the merged intent to @policy.build

   This passes the gate at 90/2. The 2 failing tests (execute-worker-known-control-arg-policy, execute-worker-collection-input-record-policy) appear to be from OTHER changes in the working tree (the state optimization removed @appendExecutionLog from runtime.mld, breaking imports in workers that still reference it). NOT from the update field fix itself.

### Current state of the code

The fix is in execute.mld lines 98-110 (in the working tree):
```
let @baseIntent = when [
  @controlArgs.length == 0 && !@compiled.policy_intent[@operationName].isDefined() => { allow: [@operationName] }
  @compiled.policy_intent[@operationName].isDefined() => @compiled.policy_intent
  * => { allow: [@operationName] }
]
let @policyIntent = when [
  @updateFields.length == 0 => @baseIntent
  * => [
    let @updatePairs = for @fieldName in @updateFields when @compiled.compiled_args[@fieldName].isDefined() => {
      key: @fieldName,
      value: @compiled.compiled_args[@fieldName]
    }
    if @updatePairs.length == 0 [ => @baseIntent ]
    let @baseArgs = @baseIntent[@operationName] ?? {}
    let @mergedArgs = @mergeArgSources([@baseArgs, @pairsToObject(@updatePairs)])
    => { [@operationName]: @mergedArgs }
  ]
]
```

This requires importing @replaceObjectField from runtime.mld (though the current version uses @mergeArgSources + @pairsToObject instead).

### Remaining work

1. **Resolve the 2 test failures** — these are likely from the state optimization (removing @appendExecutionLog from runtime.mld) conflicting with test imports, not from the update field fix. Need to either commit the state optimization first or isolate the update field fix.

2. **Handle derived source for update fields** — The current fix works for `known` source values. For `derived` values, `@compiled.compiled_args` should have the resolved value. Needs verification in a live run.

3. **Run UT7 with the fix** — Verify reschedule_calendar_event succeeds end-to-end.

### Key files
- rig/workers/execute.mld — the dispatch path where @policyIntent is built
- rig/intent.mld — @compileExecuteIntent, @flatPolicyIntent, @compileScalarRef
- tmp/spike-reschedule-intent.mld — standalone spike proving intent compilation works
- tmp/spike-live-dispatch.mld — live MCP spike proving the full resolve path works

### Related tickets
- m-b71c: runtime ticket (closed by mlld dev — runtime is correct, rig needs to pass update fields)
- c-f337: improve no_update_fields error message
- c-f53d: audit all rig prompts and error messages

**2026-04-23T03:20:33Z** FIXED. UT7 passes. The fix was in intent.mld: @flatPolicyIntent now includes declared update fields from @toolUpdateArgs, and @policyIntentValue handles null attestations correctly. No execute.mld changes needed.
