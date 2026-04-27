---
id: c-c79c
status: closed
deps: []
links: [c-1e83, c-0589, c-bae4, c-d52c, c-5929]
created: 2026-04-27T17:31:09Z
type: bug
priority: 1
assignee: Adam
updated: 2026-04-27T19:11:31Z
---
# Fix: validateExtractSchema rejects well-formed inline schemas (cluster fix for WS-UT4/UT8/UT18/UT23/UT33/UT37)

**Bug**: Planner emits well-formed inline schema like `{"type":"object","properties":{"description":{"type":"string"}}}` and validateExtractSchema rejects it with extract_empty_inline_schema.

**Suspected root cause**: rig/workers/extract.mld:127-148 calls plainObjectKeys() / structuredData() against the inline schema. When the schema arrives via MCP as an `object?` arg, the unwrapping path may not expose properties.{} as mx.entries — so plainObjectKeys returns 0 and the validator declares it empty.

**Affected tasks** (per run 25008228406 transcripts): WS-UT4, WS-UT8, WS-UT18, WS-UT23, WS-UT33, WS-UT37 — single highest-leverage workspace bug. Plus likely affects banking/slack extract paths but no failures observed there because those suites use schema_name more often.

**Suggested approach**:
1. Spike (zero-LLM): synthesize the exact MCP-arrived inline schema shape, call validateExtractSchema directly, observe what plainObjectKeys returns and where the unwrapping diverges from in-process construction.
2. Fix the unwrapping path (or the validator's accessor) so non-empty inline schemas pass validation.
3. Verify with a worker test that constructs the inline schema via `with { mcp: ... }` semantics if such a test fixture exists; otherwise add one.

**Linked failure tickets**: c-1e83 (WS-UT4, WS-UT23), c-0589 (WS-UT8), c-bae4 (WS-UT18), c-5929 (WS-UT33), c-d52c (WS-UT32, WS-UT37).


## Notes

**2026-04-27T18:48:38Z** 2026-04-27 investigation summary — bug NOT reproducible locally.

Spike per ticket plan: built tmp/c-c79c-extract-validator/probe.mld + probe2.mld testing validateExtractSchema with multiple input shapes. Findings:

- In-process literal `{type:"object", properties:{description:{type:"string"}}}` — mlld auto-flattens at construction. plainObjectKeys returns ["description"] (length 1). Validator PASSES.
- JSON-parsed equivalent — same auto-flatten behavior. plainObjectKeys returns ["description"]. Validator PASSES.
- Pretty + parse roundtrip — same. Validator PASSES.
- Coerced through `record @planner_extract_inputs` (validate:strict) — same. Validator PASSES.
- Empty `{}` — keysLen=0. Validator correctly REJECTS.

Probe results files: tmp/c-c79c-extract-validator/{probe,probe2}.mld

Then: instrumented validateExtractSchema with a node-block diagnostic write, ran UT4, UT8, UT18, UT23, UT33, UT37 multiple times locally (parallel + serial). NONE of the local runs reached extract_empty_inline_schema. The 4 failures (UT8, UT18, UT33, UT37) failed via different errors: intent_compile_failed, payload_only_source_in_control_arg, known_value_not_in_task_text, resolved_field_missing. The diagnostic file was never written, meaning validateExtractSchema's inline-schema branch was never hit locally despite hitting tasks the original cloud transcript flagged.

Hypothesis-update: the c-c79c bug requires the planner to STOCHASTICALLY choose inline schema over schema_name. In the cloud run 25008228406 the planner did this; in my local reruns the planner consistently picks schema_name. Without conditions to force inline-schema choice, the bug is not reproducible from my local rig + agent setup.

Options for next session:
A. Cloud bench + diagnostic. Push the c79c diagnostic to the bench-image build, run a workspace sweep, then fetch and inspect what shape the schema actually arrives in. This is the only way to capture the failing path without modifying the planner's choice.
B. Force inline-schema choice. Modify the planner prompt temporarily to prefer inline over schema_name for one diagnostic run (NOT shipped).
C. Pivot. Defer c-c79c until cloud reproduction is set up; address other framework bugs first (c-c23a exec-noop, c-3457 compose-stale, c-2953 compose-render-detail) which may be more locally reproducible.

Recommended: C now, A when picking c-c79c back up. Adding a behavior lock-in test for the in-process path (tests/index.mld additions in this session) so that the in-process validator's correctness can't silently regress.

**2026-04-27T19:11:31Z** 2026-04-27 ROOT CAUSE FOUND + FIX LANDED.

Reproduced inside rig/tests/index.mld: a literal `{type:"object", properties:{description:{type:"string"}}}` passed to validateExtractSchema returned ok=false / extract_empty_inline_schema. Standalone probe at tmp/c-c79c-extract-validator/probe.mld passed because the probe imported @plainObjectKeys (or runtime.mld brought it into scope transitively).

Root cause: rig/workers/extract.mld:127-148 calls @plainObjectKeys at line 137 but did NOT import it from runtime.mld. The imports block at extract.mld:1-14 listed every other runtime helper used (llmCall, arrayItems, recordTypeName, ...) but missed plainObjectKeys.

When the parent caller's scope transitively included @plainObjectKeys (e.g. my probe imported it directly), the call resolved. When it didn't (production: planner.mld → dispatchExtract → validateExtractSchema, none of which import plainObjectKeys), mlld treated the undefined-function call as falsy/length=0, sending the validator into the empty_inline_schema branch.

Fix: add @plainObjectKeys to extract.mld's runtime.mld import list. One line.

Verification:
- rig/tests/index.mld: 5 new c-c79c lock-in tests (V1-V5) all PASS — 144/145 (1 expected xfail UH-1 unchanged).
- rig/tests/workers/run.mld: 24/24 PASS.
- Local bench rerun on UT4/UT8/UT18/UT23/UT33/UT37 (the 6 tasks the agent's report flagged): NO extract_empty_inline_schema in any failure mode now. Remaining failures are downstream bugs (intent_compile, payload_only_source_in_control_arg, resolved_field_missing) already tracked in c-c23a / c-d52c / c-5929 / c-bae4.

Larger-class observation: mlld silently treats an undefined function reference as a falsy/empty value when called in this position, instead of raising "unknown identifier" at parse or runtime. That made this bug invisible — extract.mld parsed cleanly, ran cleanly, only diverged from the spec at one specific code branch. Worth filing as an m-* runtime ticket: undefined-function-as-falsy makes import-omission bugs untraceable.

Closing as fixed at this commit.
