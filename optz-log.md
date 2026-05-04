# Optimization Investigation Log

## 2026-05-03

### Starting Point

Goal: identify measured speed/memory bottlenecks behind the current broad benchmark slowdown and make substantive improvements where the evidence supports a patch.

Constraints:
- Use deterministic speed/memory infrastructure where possible, especially zero-LLM replay harnesses.
- Treat `spec-perf-regression.md` as a brief, not as proof.
- Keep changes grounded in before/after measurements.
- Do not rely on heap caps as an optimization.

Current worktree at start of this pass had unrelated local changes in `src/date_shift.py`, `src/host.py`, `src/mcp_server.py`, and `src/run.py` plus several untracked files. I will avoid reverting them.

### Existing Infra

Found existing deterministic harness:
- `rig/test-harness/mock-opencode.mld`: mock `exe llm @mockOpencode` that replays scripted planner tool calls.
- `rig/test-harness/run-ut19-mock.mld`: travel UT19 replay for the c-63fe Phase B merge/cache/projection hot path.
- `scripts/repro_c63fe_mem.py`: Python wrapper that wires real AgentDojo MCP data and runs the replay through mlld SDK.

Important caveat: the existing UT19 replay is a travel/c-63fe hot-path reproducer. It is useful for framework Phase B profiling, but it is not necessarily a proxy for the current broad workspace slowdown.

### Measurements

1. Current checkout, `scripts/repro_c63fe_mem.py`, no trace, `MLLD_HEAP=12g`, `MOCK_TIMEOUT_S=900`:
   - Result: timed out at 900s.
   - Interpretation: there is framework/runtime work that can exceed the task budget without LLM provider latency. This does not yet identify the broad regression, because the fixture is known to be a worst-case travel Phase B replay.

2. Created detached worktrees for commit comparison:
   - `../clean-perf-e56` at fast-era `e56f4f37`
   - `../clean-perf-9d4` at May 1 `9d4ec43`
   - `../clean-perf-head` at current `HEAD`
   - Added untracked `.mlld-sdk -> ../mlld/sdk/python` symlink in each worktree so historical `bench/pyproject.toml` editable dependency resolves.

3. Fast-era `e56f4f37`, same UT19 replay, `MLLD_HEAP=12g`, `MOCK_TIMEOUT_S=1200`:
   - Result: timed out at 1200s.
   - Interpretation: this travel UT19 replay is not a useful proxy for the broad regression window. It was pathological even at the fast-era commit.

### Current Hypothesis

The UT19 replay can show whether the Phase B hot path is still bad, but because it is known to be bad even around the fast workspace era, I need a second fixture shaped like the current workspace timeout family. The most useful next target is a zero-LLM workspace `list_files` replay, because cloud traces show:
- Inner Python MCP `list_files` returns in tens of milliseconds.
- The expensive part is outer mlld rig session/merge/projection work.
- The task family times out under parallel pressure and barely fits solo.

### Added Workspace Replay

Added:
- `rig/test-harness/fixtures/workspace-list-files-tool-script.json`
- `rig/test-harness/run-workspace-list-files-mock.mld`
- `scripts/repro_workspace_list_files.py`

This replays the workspace UT26-shaped `resolve(list_files)` call with no planner LLM. It still uses the real workspace AgentDojo MCP data.

Current checkout measurement:
- Command: `MLLD_HEAP=12g MOCK_TIMEOUT_S=300 uv run --project bench python3 scripts/repro_workspace_list_files.py`
- Result: PASS, elapsed 38.5s.
- Output: `status=resolved`, `record_type=file_entry`, `count=26`, `records=26`.
- Note: the MLD script's internal `date +%s%3N` subtraction printed `NaN`; the Python wrapper wall clock is the reliable number.

Same checkout with effects/memory tracing:
- Command shape: `MLLD_TRACE=effects MLLD_TRACE_MEMORY=1 ... scripts/repro_workspace_list_files.py`
- Result: PASS, elapsed 38.9s.
- Trace file: `/tmp/ws-list-files-1777850502/trace.jsonl`, 52 events.
- Final memory sample: RSS 1.23 GB, JS heap used 320.6 MB.
- Peak RSS: 1.23 GB at `llm.tool_result` finish for `@mockOpencode`.
- Peak JS heap used: 849.0 MB at `llm.exec.resolve_dispatch` finish for `@projectResolvedEntry`.
- First major jump: `llm.exec.resolve` finish for `@final`, +560 MB RSS and +367 MB heap. This likely includes agent/mock-opencode setup, session materialization, and imports before the first mock tool call.
- Session writes are not large by themselves: agent seed max value about 1.8 MB; total session write values about 1.87 MB.

Timeline from the trace:
- `eval.start`: 23:21:43.661
- `session.seed agent`: 23:21:58.435, about 14.8s after eval start.
- first resolver/tool work: about 23:22:01.
- repeated `normalizeResolvedValues` calls: about 23:22:01.293 to 23:22:01.862.
- large gap before `finishPlannerTool`: until 23:22:18.437, about 16.6s, likely in resolved-state update/merge/cache/projection.
- planner resolved-record projection/cache work: 23:22:20.197 to 23:22:20.960.

The hot shape is repeated mlld helper invocation churn around projection/state handling:
- `llm.exec.entry`: 4,396 events, large positive allocation churn.
- `llm.exec.resolve_lookup`: 8,792 events.
- `llm.exec.resolve_dispatch`: 5,913 events.

Next decision: compare this workspace fixture across the fast and slow commits. If it regressed in the commit window, patch the measured hot path. If it is roughly flat, this fixture is a useful microbenchmark but not the broad regression proxy.

### Change 1: Batch Planner Projection

Trace showed thousands of tiny mlld helper invocations during planner projection:
- `projectResolvedEntry` calls `recordDisplayMode`, `displayEntry`, `projectResolvedFieldValue`, `maskPreview`, and `pairsToObject` for every visible field.
- For planner-visible resolved records this projection does not need worker-side wrapper preservation; it is just the safe display surface sent back to the planner.

Patch:
- Added `@projectPlannerResolvedEntries(recordType, recordDef, entries)` in `rig/runtime.mld`.
- It batches planner display projection in one JS call.
- `@bucketEntriesForRole` and `@populatePlannerCache` use it only for `role:planner`.
- Worker projection still uses the native `@projectResolvedEntry` path.

Validation:
- Inline projection parity check for workspace `file_entry`: old one-record projection and new batched projection matched.
- Inline projection parity check for fixture `contact` using `role:planner` display keys matched.

Workspace list_files replay after patch:
- Command: `MLLD_HEAP=12g MOCK_TIMEOUT_S=300 uv run --project bench python3 scripts/repro_workspace_list_files.py`
- Result: PASS, elapsed 28.1s.
- Baseline on same checkout before patch: 38.5s.
- Improvement: 10.4s faster, about 27%.

This is a substantive single-call win, but not enough by itself to explain multi-minute cloud slowdowns. Next I need trace-after-patch and cross-commit timing to see how much hot work remains and whether this fixture tracks the regression window.

After-patch effects/memory trace:
- Command shape: `MLLD_TRACE=effects MLLD_TRACE_MEMORY=1 ... scripts/repro_workspace_list_files.py`
- Result: PASS, elapsed 28.7s.
- Trace file: `/tmp/ws-list-files-after-projection/trace.jsonl`, 52 events.
- Peak RSS: 1.12 GB at run finish, down from 1.23 GB.
- Peak JS heap used: 702 MB at a planner `llm.call` finish, down from 849 MB.

After-patch timeline:
- `eval.start`: 23:28:00.319
- `session.seed agent`: 23:28:15.356, still about 15.0s after eval start.
- `callToolWithOptionalPolicy` finishes: 23:28:17.939.
- repeated `normalizeResolvedValues` calls: 23:28:18.224 to 23:28:18.798.
- `finishPlannerTool` finishes: 23:28:26.140, about 7.3s after normalization, down from about 16.6s before patch.
- `plannerResolvedRecords` finishes: 23:28:27.429.

Remaining hot areas:
- Agent/session setup before the mock LLM call remains about 15s and dominates this fixture.
- The state settlement path is still about 7s.
- `normalizeResolvedValues` still generates many small calls, but it is under 1s here.

### Change 2: Reduce Agent Build Catalog Work

Added a build-only harness:
- `rig/test-harness/run-workspace-build-agent.mld`
- `scripts/repro_workspace_build_agent.py`

Baseline build-only timing:
- Command: `MLLD_HEAP=12g MOCK_TIMEOUT_S=300 uv run --project bench python3 scripts/repro_workspace_build_agent.py`
- Result: PASS, elapsed 12.3s.
- Effects trace showed only six memory events; verbose trace showed imports completed around 1.7s, then about 10s elapsed before evaluation finish. That points at untraced ordinary mlld work inside `rig.build` / `validateConfig`.

Patches:
- Stopped eagerly materializing `routedTools` in `validateConfig`. Current dispatch/docs helpers already prefer direct filtering from the flat `agent.tools` catalog and only use `routedTools` as a fallback.
- Added `@synthesizedPolicyParts` in `rig/tooling.mld` to batch metadata-only policy operations/authorization synthesis in JS.
- Added `@validateToolCatalogFast` in `rig/tooling.mld` to batch catalog validation in JS.

Build-only timing after build-path patches:
- 12.3s baseline → about 10.0s.
- Defended and `BUILD_DEFENSE=none` are now essentially identical, so remaining build cost is likely imported tool-capsule materialization rather than policy generation.

Workspace list_files replay after all patches:
- 38.5s baseline → 28.1s after projection patch → 21.4s after build-path patches.
- Final traced run: 21.3s, peak RSS 754.5 MB, peak JS heap 337.6 MB.
- Initial traced baseline was 38.9s, peak RSS 1.23 GB, peak JS heap 849 MB.

The final trace still shows about 13.3s before the tool result finishes, so there is more possible work in import/build/tool-capsule materialization. But the local microbenchmark is now about 44% faster and uses substantially less memory.

### Change 3: Guard No-Op Lifecycle Writes

`finishPlannerTool` calls lifecycle file helpers even when `phaseLogFile`, `phaseStateFile`, and `llmCallLogFile` are null. The old helpers checked for empty paths inside shell bodies, so a no-op could still spawn a shell. I split those helpers into mlld guards plus raw shell writers so null/empty paths return before subprocess execution.

Measurement:
- Workspace list_files after this patch: 21.7s.
- Prior all-patches run: 21.4s.

Conclusion: this is a correctness/overhead cleanup for no-op lifecycle writes, but not a meaningful win on the workspace replay. The remaining local cost is elsewhere.

### Validation

- `MLLD_HEAP=12g mlld rig/tests/index.mld --stdout --allow-absolute --max-output-lines 120`
  - Result: 192 pass / 1 fail.
  - The one failure is the existing `xfail/c-bd28/UH-1-selection-ref-tolerates-unicode-dash-variant` expected-failure case.
  - Re-ran after the lifecycle guard patch with the same result.
- `MLLD_HEAP=12g mlld bench/tests/workspace-tools.mld --stdout --allow-absolute --max-output-lines 80`
  - Result: 5 pass / 1 fail.
  - Failure is `workspace-thin-agent`, a source-text assertion expecting `routedTools: @routeToolCatalog(@tools)` in `bench/agents/workspace.mld`; the current agent file does not contain that text.
- `MLLD_HEAP=12g mlld bench/tests/catalog-migration.mld --stdout --allow-absolute --max-output-lines 80`
  - Result: 6 pass / 4 fail.
  - Failures are source-text migration assertions for travel date normalization and banking/slack/travel runtime-clean checks. They appear unrelated to these runtime patches.

### Workspace Replay Across Commits

Copied the new workspace replay fixture into the comparison worktrees and timed it without the projection patch:

| Commit | Timing |
| --- | ---: |
| `e56f4f37` fast-era | 51.4s |
| `9d4ec43` May 1 | 54.2s |
| clean current `7bf5283` | 37.4s |
| current worktree + batch projection patch | 28.1s |
| current worktree + all patches | 21.4s |

Conclusion: this workspace `list_files` replay is not the broad regression reproducer. It improved from the fast-era commits to current HEAD, then improved again with the projection patch. It is still a good microbenchmark because it exercises a real expensive path without LLM latency, but it does not explain why full cloud workspace/slack/travel got slower.

### UT19 Follow-Up: Resolved Family Hot Path

The UT19 replay should not be discarded just because the full run times out. Profiling partial runs makes the slow path concrete:
- Batch A only: 46.0s before the targeted planner-handle projection change.
- Batch A only after `@projectPlannerResolvedHandles`: 41.5s, about 10% faster.
- Batch A+B still times out at 300s.
- Verbose Batch A+B trace shows the timeout is dominated by native `rig/intent.mld` resolved-family expansion: `@compileScalarRefWithMeta`, `@resolveControlRefValue`, `@lookupResolvedEntry`, `@valueField`, `@name`, and loop/if frames repeatedly allocate while expanding the same `resolved_family` buckets.

I briefly prototyped an application-level JS fast path in `intent.mld` to batch `resolved_family` arg compilation. That is preserved, but not imported, at `rig/intent.resolved-family-fastpath.experimental.mld`. The active direction is to use this as a comparison point while optimizing the native mlld runtime/interpreter path instead of moving provenance logic into JS.

### Native Runtime Pass: UT19 Batch A

I switched from app-level `intent.mld` changes to runtime profiling with Node CPU profiles against the zero-LLM UT19 harness.

Baseline for this pass:
- Batch A only (`UT19_MAX_STEPS=1`, no runtime trace): last recorded local runs were 43.4s and 41.8s.
- Batch A+B (`UT19_MAX_STEPS=2`, no runtime trace): timed out at 300s.

Runtime patches in `~/mlld/mlld`:
- `interpreter/eval/exec-invocation.ts`: do not call `hasExeLabel('llm')` or emit verbose LLM exec memory trace samples when runtime memory tracing is disabled.
- `interpreter/eval/exec-invocation.ts`: cache deserialized captured module env maps back onto the object that supplied them, not only onto `.internal`.
- `interpreter/eval/import/variable-importer/executable/CapturedModuleEnvKeychain.ts`: replace the per-object accessor property used by `sealCapturedModuleEnv` with a non-enumerable writable data property. This preserves `Object.keys` / JSON hiding but avoids installing getter/setter closures across many executable internals.
- `core/security/url-provenance.ts`: skip URL regex scanning when a string does not contain `://`.
- `interpreter/eval/exec/builtins.ts`: use Sets for builtin method lookup.
- `interpreter/eval/exec-invocation.ts`: skip command-name variable lookup for object builtin dispatches like `.isDefined()`.
- `interpreter/hooks/guard-post-orchestrator.ts`: add a cheap after-guard precheck so execs with no possible after-guard skip output/input guard materialization.

Measured results:
- After trace-gating only: 41.8s.
- After captured-env cache + URL precheck: 40.0s, then 39.0s.
- After captured-env seal data-slot change: 33.1s, then 33.2s.
- After builtin lookup change: 33.0s, no meaningful additional movement on Batch A.
- After after-guard precheck: 28.2s, then 29.5s.

Net Batch A result:
- About 43.4s -> 28-30s, roughly 32-35% faster on the zero-LLM replay.
- CPU profile before the seal change had `sealCapturedModuleEnv` and `rehydrateNestedCapturedModuleScope` dominating import/setup time.
- CPU profile after the seal change moved the residual setup cost toward post-guard materialization; the after-guard precheck removed a large share of that no-op path.

Still unresolved:
- Batch A+B still times out at 300s after these runtime patches.
- That means the broader runtime overhead is materially improved, but the pathological second-step resolved-family/control-ref path is still dominated by native `rig/intent.mld` helper expansion (`@valueField`, `@name`, `@lookupResolvedEntry`, `@resolveControlRefValue`, `@compileScalarRefWithMeta`) and needs another focused pass.

Post-patch Batch A+B trace:
- Command shape: `MLLD_TRACE=verbose MLLD_TRACE_MEMORY=1 MLLD_HEAP=12g MOCK_TIMEOUT_S=120 UT19_MAX_STEPS=2 ... scripts/repro_c63fe_mem.py`
- Result: timeout at 120s, trace file `/tmp/ut19-step2-post-runtime/trace.jsonl`.
- 4,477 events from `2026-05-04T02:36:01.985Z` to `2026-05-04T02:38:01.842Z`.
- Top counts remain:
  - `@normalizeResolvedValues` 998
  - `@batchSpecMergeState` 508
  - `@pairsToObject` 420
  - `@callTool` 252
  - `rig/intent.mld` frames 217
  - `@valueField` in `intent.mld` 129
  - `@name` 100
  - `@refSource` 79
  - `@compileScalarRefWithMeta` 74
  - `@resolveControlRefValue` 40
  - `@lookupResolvedEntry` 32
- Top positive heap churn still sits in `rig/intent.mld`: file-level `intent.mld` +7.5GB cumulative positive heap, `@valueField` +4.8GB, `@name` +3.1GB, `@compileScalarRefWithMeta` +2.8GB.

Validation after runtime patches:
- `MLLD_HEAP=12g mlld rig/tests/index.mld --stdout --allow-absolute --max-output-lines 120`
- Result: 192 pass / 1 fail.
- The one failure is still the existing `xfail/c-bd28/UH-1-selection-ref-tolerates-unicode-dash-variant`.

### Correction: Node Fast Paths Are Diagnostic Only

Adam pushed back that the goal is to find the mlld runtime slowdown, not to rewrite hot rig helpers in Node. That is correct. I removed the active application-level Node fast paths from the rig route:

- Removed active planner projection Node helpers from `rig/runtime.mld` / `rig/workers/planner.mld`.
- Removed active policy/catalog Node helpers from `rig/tooling.mld` / `rig/orchestration.mld`.
- Kept `rig/intent.resolved-family-fastpath.experimental.mld` as an explicit diagnostic/control artifact only.

After this correction, the zero-LLM timings are worse than the earlier app-fastpath numbers, but they are the right baseline for investigating mlld itself:

| Native route case | Time |
| --- | ---: |
| build only (`UT19_MAX_STEPS=0`) | 9.5s |
| A[0] | 14.9s |
| A[0-1] | 21.6s |
| A[0-2] | 28.2s |
| A[all] | 74.1s |

This shows the slow path is real native mlld work. There are no LLM calls in this harness; it is local MCP + mlld evaluation.

### Native Runtime Pass: Descriptor / Captured-Env Churn

CPU profile for native A[0-2] (`/tmp/mlld-cpu-a-0-2-native-1777866708`) showed:

- `mergeDescriptors`: 5.2s self
- `sealCapturedModuleEnv`: 2.8s self
- `toolArrayKey`: 2.6s self
- GC: 2.2s self
- recursive URL extraction: about 1.3s self

The important stacks were:

- `getVariable -> getVariable -> ... -> recordSecurityDescriptor -> mergeDescriptors`
- `rehydrateNestedCapturedModuleScope -> sealCapturedModuleEnv`
- descriptor intern keys repeatedly rebuilding tool provenance keys

Runtime patches:

- Added parent-scope variable lookup that does not recursively record security descriptors in every parent environment. The child lookup still records the found variable descriptor once in the requesting environment.
- Added no-op fast return to `recordSecurityDescriptor` for empty descriptors and identical descriptor objects.
- Made `sealCapturedModuleEnv` return immediately when the non-enumerable captured env slot already contains the same map, and avoid redundant WeakMap writes for sealed data slots.
- Added reference-checked `mx -> SecurityDescriptor` caches in both `core/types/variable/VarMxHelpers.ts` and `interpreter/utils/structured-value.ts`; cache hits require the same labels/taint/sources/urls/tools/policy references, and `updateVarMxFromDescriptor` clears the core cache.

Measurements after the parent-lookup/captured-env patch:

| Native route case | Before | After |
| --- | ---: | ---: |
| A[0-2] | 28.2s | 19.7s |
| A[all] | 74.1s | 47.7s |
| B[4] dispatch stop | 68.9s after removing app fastpaths | not rerun before mx cache |
| B[4] merge stop | 87.6s after removing app fastpaths | not rerun before mx cache |

Post-patch CPU profile (`/tmp/mlld-cpu-a-0-2-post-1777867124`) showed `sealCapturedModuleEnv` dropped from 2.8s self to 0.17s self. Remaining top costs were descriptor merging/interning and recursive URL extraction.

Measurements after the `mx` descriptor cache:

| Native route case | Before mx cache | After mx cache |
| --- | ---: | ---: |
| A[0-2] | 19.7s | 17.6s |
| A[all] | 47.7s | 45.6s |
| B[4] dispatch stop | 68.9s | 64.1s |
| B[4] merge stop | 87.6s | 78.1s |

Current native-route improvement from the corrected baseline:

- A[0-2]: 28.2s -> 17.6s, about 38% faster.
- A[all]: 74.1s -> 45.6s, about 38% faster.
- B[4] merge stop: 87.6s -> 78.1s from the post-correction baseline; still too slow.

Remaining bottleneck:

- Phase B resolved-family/control-ref dispatch and native state merge still dominate. B[4] dispatch is 64.1s and B[4] merge is 78.1s, so the merge itself adds about 14s on top of dispatch for this narrow case.
- The post-patch profile still points at `extractDescriptorInternal`, `mergeDescriptors`, tool provenance keying, guard-input materialization, and recursive URL extraction.

### Native Runtime Pass: B-Specific Cleanup

I tried three B-specific runtime cleanups:

- Reuse already-materialized guard variables inside `guardPreHook` instead of materializing structured guard inputs a second time.
- Move user-hook error-bucket creation until after matching user hooks are found.
- Add a URL text prefilter that returns early only when a string has neither `:` nor `.`. This is compatible with current `scheme://` URLs and future `website.com`-style scheme-less domains.

I also tried broadening the simple field-access fast path to preserve-context reads. That failed focused tests:

- It broke a rig-style structured arg rebuild test.
- It bypassed schema-invalid after-guard behavior.

That field-access broadening was reverted. Do not revive it without a narrower provenance-preserving design.

Validation after the surviving B-specific cleanups:

- `npx vitest run core/security/url-provenance.test.ts interpreter/utils/field-access.test.ts interpreter/eval/exec-invocation.structured.test.ts tests/interpreter/hooks/guard-post-hook.test.ts --reporter=dot`
  - 120 tests passed.
- `npm run build`
  - passed.

Measurements:

| Native route case | Corrected baseline | After descriptor/captured-env/mx cache | After B cleanup |
| --- | ---: | ---: | ---: |
| A[all] | 74.1s | 45.6s | 38.8s |
| B[4] dispatch stop | 68.9s | 64.1s | 54.1s |
| B[4] merge stop | 87.6s | 78.1s | 67.3s |

Current B-specific improvement:

- B[4] dispatch stop: 68.9s -> 54.1s, about 21% faster.
- B[4] merge stop: 87.6s -> 67.3s, about 23% faster.

Interpreting the 54s/67s B numbers:

- These B fixtures are cumulative: build + full Batch A + one selected Batch B tool.
- Current A[all] is 38.8s, so B[4] dispatch adds roughly 15s beyond A.
- Current B[4] merge stop is 67.3s, so native merge adds roughly another 13s beyond B dispatch.

What remains on B:

- The merge phase still adds about 13s over dispatch for B[4].
- The larger B slices are still expected to be pathological until we attack recursive descriptor extraction / state-merge field reads more directly.
- A safe next target is a B[4] post-cleanup CPU profile and then a narrower optimization for descriptor extraction on descriptor-free plain objects. The broader field-access shortcut was too blunt.

### MCP / LLM Split for B[4]

I preserved the MCP JSONL for the current B[4] merge-stop run to verify whether the 68s number is actually local MCP or hidden worker LLM time.

Result:

- Wall time: 68.5s.
- MCP entries: 7.
- MCP tool elapsed sum: 3.2ms.
- MCP dispatch sum: 1.0ms.
- MCP format sum: 0.9ms.
- MCP save sum: 0.0ms.
- Logged tools:
  - `get_all_hotels_in_city` x2
  - `get_all_restaurants_in_city` x2
  - `get_all_car_rental_companies_in_city` x2
  - `get_car_price_per_day` x1

Interpretation:

- These B split timings are not MCP-tool-execution time. The local MCP calls are effectively negligible for this travel case.
- They are not LLM worker time either. `@mockOpencode` is declared `exe llm` only to get real session binding semantics, but its body replays `config.toolScript` and directly invokes planner tool exes. No provider call is made.
- The current B fixtures run only the two `resolve_batch` steps. They do not run the later fixture `derive` or `compose` steps where real rig runs can invoke worker LLMs.
- Therefore the 50-70s remaining time is mlld runtime/interpreter overhead around state, security/provenance, guards, field access, descriptor extraction/merge, URL provenance, and session/result materialization.

### Security / Provenance Architecture Pass

The next profiles showed the remaining slowdown was not one single regex or MCP call. It was descriptor/provenance representation churn:

- B[4] merge profile before this pass: `evaluateExecInvocationInternal` 30.6s inclusive, `prepareExecGuardInputs` 10.9s, `mergeResolvedArgValueDescriptors` 7.7s, `materializeGuardInput` 7.6s, `mergeDescriptors` 20.0s self, `toolArrayKey` 11.8s self, `descriptorInternKey` 6.2s self.
- Full-B profile after the first descriptor fixes still had `mergeToolArrays` 21.7s self and `freezeToolArray` 3.3s self.
- After preserving normalized descriptor identities, `freezeToolArray` dropped to 0.09s and `varMxToSecurityDescriptor` dropped from 5.1s inclusive to 0.7s inclusive.
- After aligning tool provenance with the audit boundary, `mergeToolArrays` dropped from 10.4s self to 0.4s self.

Runtime changes made in this pass:

- `core/types/security.ts`
  - Avoids constructing descriptor intern keys when the tool provenance key is already guaranteed to exceed the intern key limit.
  - Adds ordered descriptor-pair merge caching and makes multi-descriptor merges fold through that cache.
  - Adds normalized tool-array metadata so repeated auditRef subset checks do not rescan the same arrays.
  - Adds tool-array pair merge caching for different descriptors that carry the same tool histories.
  - Avoids copying auditRef Sets when caching normalized tool-array metadata.
- `core/types/variable/VarMxHelpers.ts`
  - Preserves normalized descriptor arrays when creating/updating `mx` instead of cloning labels/sources/urls/tools back into fresh arrays.
  - Keeps the reference-checked `mx -> SecurityDescriptor` cache useful across more paths.
- `interpreter/utils/structured-value.ts`
  - Preserves normalized descriptor arrays on structured values.
  - Avoids cloning tool arrays when converting structured `mx` back into descriptors.
  - Avoids redundant URL scans when structured text is already available, and avoids re-walking `data` when lazy text materializes.
- `interpreter/eval/exec-invocation.ts`
  - Only attaches tool provenance when the call also has an audit boundary: top-level executable calls or surfaced tool calls. Nested pure helper exes no longer add unique `tools` provenance entries with no matching audit event.
  - Skips tool-input validation argument construction when no input schema exists.

Measurements on the zero-LLM UT19 harness:

| Case | Corrected native baseline | Before this pass | Current |
| --- | ---: | ---: | ---: |
| A[all] | 74.1s | 38.8s | 11.1s |
| B[4] merge stop | 87.6s | 67.3s | 12.9s |
| B[all] merge stop | timed out at 300s | 104.3s | 29.0s |

Stepwise full-B merge-stop results:

| Change | Time |
| --- | ---: |
| Corrected native route | timed out at 300s |
| Descriptor key limit skip + pair merge cache + validation gate | 104.3s |
| Preserve structured descriptor/tool-array identity | 75.9s |
| Tool-array merge cache | 51.9s |
| Preserve variable metadata descriptor/tool-array identity | 46.4s |
| Attach tool provenance only at audit boundaries | 30.0s |
| Avoid duplicate structured URL extraction | 29.0s |

Interpretation:

- The biggest issue was not that security/provenance exists. It was that the runtime represented provenance as eager, repeatedly copied arrays on every value, and it treated nested helper calls like audited tools.
- The `tools` history was especially expensive because every nested helper call got a unique auditRef, so merges could not dedupe and descriptor histories grew across pure mlld helper expansion.
- Attaching `tools` provenance only when an audit event can exist is both faster and more coherent: a descriptor should not point at auditRefs that were never written.
- The remaining 29s is now a different problem shape. Tool provenance merging is no longer dominant. The latest current-state profile before the URL tweak (`/tmp/mlld-cpu-b-all-merge-auditboundary-1777871782/CPU.20260503.221623.75687.0.001.cpuprofile`) showed the next targets as guard input materialization, recursive descriptor extraction, URL extraction during structured materialization, and captured-scope rehydration.

Likely next targets:

- Cache recursive descriptor extraction for immutable/structured values with explicit invalidation/versioning. `extractDescriptorInternal` is still high inclusive time, but much of that is recursive double-counting, so this needs counters or focused instrumentation before patching.
- Reduce guard input materialization. The current profile still shows `prepareExecGuardInputs` and `materializeGuardInput` as meaningful inclusive costs; we should avoid creating full Variables unless a matching guard actually needs them.
- Continue reducing structured URL extraction. The duplicate text/data scan is fixed, but URL provenance still walks large object/text values. The next safe version is boundary-only extraction or object-level URL caches for immutable structured values.
- Revisit captured-scope rehydration. `rehydrateNestedCapturedModuleScope` is no longer the top offender, but still appears around 6.5s inclusive in the profiled full-B path.

### Regression Fix Follow-Up

After the first optimization commit, the full suite exposed four security/metadata regressions:

- Condition descriptors from `if`/`when` tests were isolated in child condition environments and not recorded back to the parent.
- Imported block-style `llm` wrappers could return an imported scalar variable object instead of the scalar text after LLM result metadata wrapping.
- Nested exe calls inside an exe block could be assigned to locals and then omitted from the block's local security descriptor when the block returned an unrelated literal.
- A first attempt to normalize block returns fixed the imported scalar case but was too broad: direct `.mx` access on a returned let-bound variable lost the variable wrapper.

Runtime fixes:

- `interpreter/eval/when/condition-evaluator.ts` now records the child condition environment's local descriptor back into the parent.
- `interpreter/eval/exe/block-execution.ts` records descriptors from let/augmented assignments into the block environment, so nested tool/helper effects are folded into the invocation result without adding auditless nested tool provenance.
- `interpreter/eval/exe-return.ts` unwraps non-executable return variables when they do not need metadata-preserving variable wrappers.
- `interpreter/eval/exec-invocation.ts` unwraps non-executable variable results before LLM metadata wrapping, keeping ordinary block returns available for post-invocation field access like `.mx`.

Verification:

- Full mlld suite: `npx vitest run --reporter=dot` -> 569 files passed, 7 skipped; 6688 tests passed, 131 skipped.
- Build: `npm run build` passed.
- Zero-LLM UT19 B[all] merge-stop sanity: reported 29.3s, wall 30.8s. This is in the same band as the 29.0s post-optimization result, so the semantic fixes did not materially undo the performance gain.
