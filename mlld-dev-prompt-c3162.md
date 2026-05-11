# mlld-dev brief: two policy gaps surfaced by rig defense regression (c-3162)

You are mlld-dev. Two related defects in mlld's policy machinery were found while investigating a security regression in the rig clean/ project. The first is a small, well-isolated bug with a candidate patch already verified at the unit-test level. The second is a separate enforcement-scope issue with a failing acceptance test ready for you to use.

This brief is self-contained. You don't need to read the full c-3162 investigation thread; everything you need is below.

## Context (one paragraph)

The rig framework in `~/mlld/clean/` defends against prompt injection by tagging untrusted content (slack message bodies, fetched webpage content) at the record-decl level (`data: { untrusted: [field] }`), then relying on mlld's `untrusted-llms-get-influenced` auto-rule to add `influenced` to LLM worker outputs, and on `labels.influenced.deny: ["destructive", "exfil"]` in the synthesized base policy to block tainted content from reaching write-tool dispatches. End-to-end probes show this defense chain is broken in two places. Both are mlld-side.

## Gap A: `isSystemLabel` predicate too narrow → auto-rule never fires on rig worker LLM calls

### Symptom

The `untrusted-llms-get-influenced` auto-rule never adds `influenced` to LLM outputs in rig dispatch even though:
- `policy.defaults.rules` includes `'untrusted-llms-get-influenced'`
- `policy.defaults.unlabeled` is `'untrusted'`
- The exe is annotated `exe llm` (so `exeLabels` includes `'llm'`)
- The input prompt's `mx.taint` is non-empty (system labels: `src:shelf:...`, `fact:...`, `src:file`, `dir:...`, `llm`, `role:worker`, `src:exe`)

### Mechanism (verified)

`~/mlld/mlld/core/policy/input-taint.ts:30-44` defines `isSystemLabel`:

```ts
function isSystemLabel(label: string, defaults?: PolicyConfig['defaults']): boolean {
  if (label.startsWith(SOURCE_PREFIX) || label.startsWith(DIR_PREFIX)) {
    return true;
  }
  const defaultStance = defaults?.unlabeled;
  if (defaultStance && label === defaultStance) {
    return true;
  }
  return false;
}
```

Only `src:` and `dir:` prefixes are recognized as system. The rig framework auto-applies these other system-class labels that the predicate misses:

- `fact:@<rt>.<field>` — fact-source attribution from record-decl field metadata
- `llm` — exe-class label from `exe llm @foo(...)`
- `role:worker`, `role:planner`, `role:advice` — role context labels
- (`src:exe`, `src:shelf:`, `src:file` already match `src:` — fine)

Because `fact:` / `llm` / `role:` are misclassified as user labels, `hasUserLabels` returns true → `isUnlabeled = false` → `applyUntrustedDefault = false` → effective taint doesn't include `'untrusted'` → `shouldAddInfluencedLabel` returns false → no `influenced` added.

### Candidate patch (in the working tree of ~/mlld/mlld; 2.1.0 branch; uncommitted)

`core/policy/input-taint.ts`, 12-line diff:

```diff
 const SOURCE_PREFIX = 'src:';
 const DIR_PREFIX = 'dir:';
+const FACT_PREFIX = 'fact:';
+const ROLE_PREFIX = 'role:';
+const EXE_CLASS_LABELS = new Set(['llm', 'worker', 'planner', 'advice']);

 function isSystemLabel(label: string, defaults?: PolicyConfig['defaults']): boolean {
-  if (label.startsWith(SOURCE_PREFIX) || label.startsWith(DIR_PREFIX)) {
+  if (
+    label.startsWith(SOURCE_PREFIX) ||
+    label.startsWith(DIR_PREFIX) ||
+    label.startsWith(FACT_PREFIX) ||
+    label.startsWith(ROLE_PREFIX)
+  ) {
+    return true;
+  }
+  if (EXE_CLASS_LABELS.has(label)) {
     return true;
   }
   ...
 }
```

Companion test file (also uncommitted, in working tree): `core/policy/c-3162-probe.test.ts` — 6 tests:
- 2 breach-scenario assertions (the actual taint chain from rig dispatch)
- 4 regression guards (no over-broadening, explicit user labels still suppress default, empty inputs still don't promote, exe-class labels work as designed)

### Verification status

- All 6 c-3162-probe tests pass
- Full mlld unit-test suite (non-SDK/CLI): 6254 pass / 117 skipped / 0 failures
- All 166 policy tests pass
- All 129 interpreter policy + run + pipeline tests pass
- Rig zero-LLM gate (clean side): 264 pass / 0 fail / 2 xfail — unchanged from pre-patch
- End-to-end probe in rebuilt mlld: shelf-sourced untrusted body → `@stubLlm(...) with { policy }` now produces a prompt-level value with `["llm", "untrusted", "influenced"]` in `mx.labels` (verified post-rebuild)

### Ask for Gap A

Review the patch. Specific things to consider:

1. **Naming**: `EXE_CLASS_LABELS = {llm, worker, planner, advice}` — are these the right exe-class labels to system-classify? Are there others (`compose`, `extract`, `derive`, `resolve` from rig — but those are role:worker context labels)? The set should cover all framework-applied labels that aren't user-applied trust assertions.

2. **Prefix collision**: `role:` prefix is treated as system. A user could plausibly declare `role:custom` as a user-trust marker. With the patch, that wouldn't trigger user-label detection. The 4th regression test in `c-3162-probe.test.ts` documents this; if it's a concern, the EXE_CLASS_LABELS set could include `role:worker`, `role:planner`, `role:advice` as exact matches instead of treating the whole `role:` prefix as system. Trade-off: explicit list is brittle to new role names; prefix is broad but conflicts with hypothetical user `role:*` semantics.

3. **`fact:` prefix**: only used by mlld's record-decl machinery for fact-source attribution. No user expression for `fact:*` labels exists today. Prefix recognition seems safe.

4. **Upstream landing**: this is a small, well-tested change. Suggest landing on main with a CHANGELOG entry citing c-3162 / clean-side defense regression as the motivating bug class.

## Gap B: `labels.{X}.deny` doesn't enforce on payload args at dispatch

### Symptom

Even with Patch A applied, the rig dispatch of an `exfil:send` tool with `body={source:"derived", name:"X", field:"body"}` carrying `mx.labels: ["influenced"]` and a policy containing `labels.influenced.deny: ["destructive", "exfil"]` returns `status: "sent"` with `policy_denials: 0`. The write fires.

Probed with two test surfaces (both fail to deny):

1. Full rig path: `@dispatchExecute(@agent, @state, decision, query)` → `@compileForDispatch` (which calls `@policy.build`) → `@callToolWithPolicy(@tool, @toolsCollection, @operationName, @finalArgs, @built.policy)` → tool exe with `with { policy: @built.policy }`. Tool catalog declares `labels: ["execute:w", "tool:w", "exfil:send"]`. Policy.operations declares `{ exfil: ["exfil:send"] }`. No denial.

2. Stripped path: `@sendExe(body) = js {...} with { labels: ["exfil:send"] }`, called as `@sendExe(@tainted) with { policy: @policy }` where `@tainted` carries `mx.labels: ["influenced"]`. No denial.

Worth noting: in test 2, probe showed `@sendExe.mx.labels` is `[]` — `with { labels: [...] }` on an exe definition apparently doesn't attach labels to the exe. So test 2's stripped path doesn't actually carry the exfil:send label into dispatch. This is itself a finding (separate from B but related to how exe-decl labels propagate).

`--trace effects` on the full rig path shows many `__policy_rule_no_influenced_advice` per-input guards firing (a different rig rule, scoped narrowly via `policy @adviceGatePolicy = { defaults: { rules: ["no-influenced-advice"] } }` in `rig/workers/advice.mld:38`). **No `__policy_rule_labels_*_deny` guard fires anywhere in the dispatch chain.** The `labels.influenced.deny` rule from rig's basePolicy is in the policy config but never produces a guard at this dispatch.

### Candidate mechanisms (need your read — UNVERIFIED)

`~/mlld/mlld/interpreter/eval/pipeline/command-execution/preflight/policy-preflight.ts:102` (and the sibling branches at lines 117, 132) calls `policyEnforcer.checkLabelFlow` only when:

```ts
if (opType && inputTaint.length > 0 && !deferManagedLabelFlow && shouldApplySurfaceScopedPolicy) {
  policyEnforcer.checkLabelFlow({ inputTaint, opLabels, exeLabels, flowChannel: 'arg' }, ...);
}
```

One or more of these conditions appears to be false for the rig tool dispatch path. Candidate hypotheses, all UNVERIFIED:

1. **`opType` resolution miss**: `ExecutableOperationType = 'sh' | 'node' | 'js' | 'py' | 'prose' | null`. The rig tool exe is `exe @runtime_send(body) = js {...}` — should resolve to `'js'`. But the path through `@callToolWithPolicy → @directExe(@args) with { policy }` may dispatch differently than direct `@exe()` calls, and `opType` may end up null. Trace `runPolicyPreflight` to see what `opType` arrives with.

2. **`inputTaint` from `descriptorToInputTaint(guardDescriptor)` empty**: the body arg's `mx.labels: ["influenced"]` may not flow into the guardDescriptor at the dispatch boundary. The chain that resolves `{source:"derived", name:"X", field:"body"}` into a concrete value (in rig: `@resolveRefValue` → `@resolveNamedValue` in `rig/intent.mld`) may not preserve labels onto the resolved value's descriptor that the dispatcher subsequently builds `guardDescriptor` from. Trace `descriptorToInputTaint` output for the body arg's resolved value.

3. **`opLabels` doesn't include the tool's catalog labels**: `getOperationLabels({ type: 'js' })` returns `['op:js']`, not `['exfil:send']`. The tool's `labels: ["execute:w", "tool:w", "exfil:send"]` from the catalog map needs to end up in `exeLabels` for the deny rule to find `exfil:send`. Verify whether mlld's exec-invocation pipeline reads the tool-collection-entry `labels: [...]` field and pushes it into `exeLabels` for the dispatched exe. (For rig's `var tools @x = { foo: { mlld: @bar, labels: [...] } }` — does mlld's runtime even read those labels at dispatch?)

4. **`shouldApplySurfaceScopedPolicy` returns false**: depends on operation context shape. Tool-dispatch via `@callToolWithPolicy` may produce an operation context that fails this check.

5. **`deferManagedLabelFlow` is true**: depends on policy config having "managed" label flow markers. Unlikely in our scenario but worth ruling out.

### Acceptance test (failing today, ready to use)

`~/mlld/clean/tests/rig/c-3162-dispatch-denial.mld` — minimal, self-contained, uses existing rig primitives. Two tests:

- `testInfluencedBodyDenied` — expects denial when body is derived from influenced-tagged value. Currently FAILS.
- `testCleanBodyNotDenied` — sanity that clean bodies still pass. Currently PASSES.

Run:
```
cd ~/mlld/clean && mlld tests/rig/c-3162-dispatch-denial.mld --no-checkpoint
```

When you have a fix for Gap B, both tests should pass.

The test file builds a complete dispatch context (synthesizedPolicy from `~/mlld/clean/rig/orchestration.mld`, agent with `defense: "defended"`, tool catalog with `exfil:send` label, derived state seeded via `@updateNamedState`, dispatch via `@dispatchExecute`). It deliberately uses `var influenced @x = "..."` to attach the label directly (so the test stays independent of Gap A — even on pre-patch mlld, the test demonstrates the dispatch-enforcement gap once labels are present somehow).

### Ask for Gap B

1. **Instrument** `interpreter/eval/pipeline/command-execution/preflight/policy-preflight.ts`'s `runPolicyPreflight` function to log (when `process.env.MLLD_TRACE_POLICY_PREFLIGHT === '1'` or similar) the values of: `opType`, `inputTaint`, `opLabels`, `exeLabels`, `shouldApplySurfaceScopedPolicy`, `deferManagedLabelFlow`, and whether `checkLabelFlow` ultimately fires. Run the acceptance test with that env var set; report which condition skips the check.

2. **Trace tool-catalog labels**: when rig declares `var tools @x = { send_message: { mlld: @impl, labels: ["exfil:send"], ... } }` and dispatches via `@x.send_message(@args) with { policy }`, do the `labels: [...]` from the catalog entry flow into the exe's runtime `exeLabels` at the dispatch site? If not, that's a wiring gap — the catalog metadata needs to make it into the dispatch's operation context.

3. **Trace ref-resolution label preservation**: when `@args.body` is `{source: "derived", name: "X", field: "body"}` and the rig's `@resolveNamedValue` (in `rig/intent.mld`) unwraps to a value carrying `mx.labels: ["influenced"]`, does that value's descriptor reach `guardDescriptor` at `policy-preflight.ts`? If labels are stripped at the ref-resolution boundary, that's a separate descriptor-merging gap.

4. **Design the fix**: depending on which hypothesis lands, the fix shape differs. Don't pre-commit. The acceptance test pins behavior; whatever fix gets there is fine.

5. **Don't bundle with Patch A**: Gap A is well-isolated and ready to land. Gap B is its own investigation. They share a motivating bug (c-d0e3) but the fixes are independent.

## File map

| Concern | Path |
|---|---|
| Patch A (uncommitted) | `~/mlld/mlld/core/policy/input-taint.ts` (working tree, 2.1.0 branch) |
| Patch A test (uncommitted) | `~/mlld/mlld/core/policy/c-3162-probe.test.ts` |
| Gap B acceptance test | `~/mlld/clean/tests/rig/c-3162-dispatch-denial.mld` |
| Gap B suspect code | `~/mlld/mlld/interpreter/eval/pipeline/command-execution/preflight/policy-preflight.ts` |
| Investigation ticket | `~/mlld/clean/.tickets/c-3162.md` (full trail; this brief summarizes it) |
| Related rig-side ticket | `~/mlld/clean/.tickets/c-d0e3.md` (5 SHOULD-FAIL tasks executing unauthorized writes — the rig-side failure mode this fixes) |

## Discipline

- Every claim above is transcript- or code-line-cited (with explicit UNVERIFIED tags where applicable).
- Both fixes need test coverage at landing: Patch A has its tests already; Gap B's acceptance test exists and should be moved into mlld's own test surface as part of the fix.
- No "while we're at it" scope creep on Gap B — fix the enforcement gap, nothing else.

## What we expect after both fixes land

When both Patch A and the Gap B fix are in mlld main, the rig clean-side scenario closes structurally:

- `rig/policies/url_output.mld` (the untracked c-84d5 draft on the clean side) becomes optional defense-in-depth rather than essential
- 5 SHOULD-FAIL slack/workspace/banking tasks (currently executing unauthorized writes) get their writes denied at dispatch with `policy_denials > 0`
- Slack `atk_direct` canary ASR returns to 0/105 (closes the c-bac4-exposed IT1 breach)
- Phase 2 of the records-as-policy migration can close cleanly

That's the scope. Land Patch A first as the easy win; tackle Gap B with the acceptance test pinning behavior.
