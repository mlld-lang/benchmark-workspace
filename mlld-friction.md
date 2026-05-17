# mlld friction log

This file tracks dogfooding feedback while building the fp-proof agent.
It is for non-blocking friction, possible ergonomic improvements, and
places where better validator/runtime messages would help. Verified
show-stopper runtime bugs should get a minimal reproduction and be
handled separately.

## Open items

- **Tool input validation can point at the dynamic dispatch call instead of the bad arg.**
  Workspace UT33 failed with `Input validation error: '19' is not of type 'object'`
  at the generic `@writeTools[@toolName](@args)` line. The real issue was the
  AgentDojo MCP `sendEmail` attachment wire format: the secure internal surface
  authorizes file ids as strings, while the MCP expects `{type, file_id}`
  objects. The location was technically accurate but did not name
  `attachments[0]`, making the transcript harder to diagnose.

- **Augmented assignment parse errors can point at a nearby tool call.**
  While adding a batch Slack write helper, validation reported
  `Augmented assignment only supports simple variables` at a nearby
  `=> @mcp.addUserToChannel(...)` line even though the problematic shape was
  the subsequent accumulator update inside the loop. Rewriting the loop as
  `let @results = for ... [ => ... ]` fixed it. A more precise span for the
  augmented assignment expression would make this much faster to diagnose.

- **Testing record-level `correlate: true` without an LLM handle frame is awkward.**
  A direct llm-free probe using fact-bearing record fields in either the
  `resolved` bucket or explicit `allow.args` still hit
  `proofless_control_arg` before reaching the correlation check. That may be
  expected because the `resolved` bucket normally receives live planner
  handles, but it makes deterministic correlation tests hard to write. A
  documented test helper or clearer validator/runtime hint would help authors
  prove same-record vs mixed-record dispatch behavior without an LLM call.

- **`@urlDefense` needs sharper import/capability ergonomics.**
  A small direct probe with `import { @urlDefense } from @mlld/policy` failed
  at runtime with `Command not found: noNovelUrl`. Importing `@noNovelUrl`
  alongside it moved the failure to `JavaScript access denied by policy`.
  That may be expected because the checker is implemented as a JS action, but
  the resulting error points at the protected write rather than the policy
  fragment dependency. A validator hint like "urlDefense requires noNovelUrl
  in scope" or a policy-fragment self-contained export would reduce surprise.

- **Optional fact fields on variadic tool signatures are easy to trip.**
  Declaring `attachments: { type: array?, kind: "file_id" }` validated, but a
  call that omitted `attachments` still reached a dispatch-time proof denial
  because the dynamic call path appears to bind the missing signature argument
  as an input. The docs mention `optional_benign`, but this runtime did not
  recognize that record section. Better validator guidance for optional facts
  on tool signatures would help.

- **Aggregate labels can disappear in function scope even when field labels survive.**
  In a focused probe, `@intent.args.body.mx.labels` preserved `["secret"]`,
  but inside an exe taking the intent as a parameter, `@args.mx.labels` was
  empty while `@args.body.mx.labels` still held `["secret"]`. Field-local
  labels are the right primitive to rely on, but the aggregate behavior is
  surprising when writing generic pre-dispatch checks.

- **OpenCode tool denial events can surface as raw NDJSON with no text payload.**
  When a planner model attempted a denied native `bash` call, OpenCode
  returned a `tool_use` event with `status=error` and no final text. The mlld
  bridge adapter then had no text chunk to return and fell back to raw JSON
  event text. This is workable if the planner is JSON-only, but a bridge-level
  helper for "tool call denied/no assistant text" would make wrapper authors
  less likely to accidentally treat provider event logs as final answers.

- **Prompt-template examples with inline JSON can fail only at runtime.**
  A prompt containing an inline object example with braces validated, but at
  runtime produced a `variable-redefinition` interpreter error pointing at a
  surprising location in the generated template. Rephrasing the example as
  prose avoided the issue. A validator hint or documented escaping pattern for
  literal JSON examples inside long templates would make this much easier to
  diagnose.

- **History-ref helper boundaries can drop fact labels while retaining factsources.**
  While building a generic `from_history` resolver, a direct lookup like
  `@historyPathLookup(...).value` showed `["recursive", "fact:@record.field"]`,
  but returning that field through a helper object, then selecting it inside a
  recursive object rebuild, often left only `["recursive"]`. In the same local
  scope `@policy.build` could sometimes rescue the value via `proof.lifted`,
  but sending the rebuilt intent through an imported dispatcher lost that lift
  context and produced `proofless_resolved_value`. Returning the parent record
  and selecting the leaf afterwards helped in some probes but was not reliable
  under the test runner. This is not a show-stopper because executing in the
  local history-owning scope preserves enough context, but a documented
  "identity-preserving map/rebuild" primitive or validator warning would help.

- **Recursive helper labels can make fact-bearing values unusable in `resolved`.**
  A value returned by a recursive path lookup displayed both `recursive` and
  `fact:@record.field` labels, but `@policy.build` rejected it in the
  `resolved` bucket with `proofless_resolved_value`. A bounded non-recursive
  lookup over the same `history -> result -> row -> field` path preserved the
  fact proof well enough for authorization. The current workaround is an
  unrolled execution-time resolver and a recursive validator-only resolver.
  A clearer error explaining that `recursive` taint invalidates resolved proof
  would save time.

- **Fact labels alone are not enough for llm-free `resolved` authorization.**
  A direct bounded lookup of a record fact field from local history showed the
  expected `fact:@record.field` label, but `@policy.build` still rejected the
  value as `proofless_control_arg` when it was placed in the `resolved` bucket.
  The docs say direct fact-bearing values can be preserved, but in practice the
  builder appears to need handle-backed proof or proof-claims registry state,
  not just the label visible on `.mx.labels`. This matters for deterministic
  tests and for JSON-history architectures: text `from_history` can preserve
  payload data flow, but it cannot safely authorize non-task control args
  without shelves/stable addresses or a live handle frame.

- **`loop(n)` exhaustion loses the last continue state at the call site.**
  The structured action runner needs the final step history when a task hits
  the iteration limit, because transcripts are the definitive diagnosis. In
  the current shape, a `done` result includes `step_history`, but plain loop
  exhaustion falls through to a fallback object with no access to the last
  `continue` state. A documented pattern for returning the last state on
  bounded loop exhaustion would make long-agent debugging much cleaner.

- **Cerebras worker calls through OpenCode can reject resumed tool-call message history.**
  A banking extract worker using `cerebras/gpt-oss-120b` via OpenCode read a
  file successfully, then the follow-up provider request failed with
  `messages.N.assistant.reasoning_content is unsupported`. This appears to be
  an OpenCode/provider message-shape compatibility issue after a tool call,
  not a security-policy denial. It is not currently a show-stopper because the
  architecture can avoid LLM-backed file extraction for SHOULD-FAIL file tasks,
  but the error message is important for provider hardening.

- **Calling a second member of a `var tools` map can produce a parse error at `(`.**
  In `tests/workspace-proof.mld`, `@unsafeWorkspaceTools.unsafe_workspace_send(...)`
  parses, but a second sibling tool call such as
  `@unsafeWorkspaceTools.unsafe_workspace_target(...)` failed validation with
  `Expected a directive or content, but found "("`. The direct exe call
  `@unsafe_workspace_target(...)` validated, and the violation canary now uses
  that deliberately undefended surface. This was easy to work around, but the
  error points at the call parenthesis rather than explaining whether only
  certain tool-map calls are supported or whether the sibling key shape
  confused the parser.

- **Sign/verify works well, but manual planner-loop handle plumbing is verbose.**
  `@sigVerify.handle` is the right primitive, but because fp-proof uses a
  manual structured planner loop rather than native projection handles, tool
  wrappers had to explicitly mint resource handles with
  `@mintUserValueHandle`, preserve handle-like objects through redacted
  history, expose a planner-visible `verify_user_attestation` wrapper, and
  append only `verified:true` content into execute context. A canonical
  "signed resource reader" helper would reduce custom glue and make transcript
  audits easier.

- **Function-parameter introspection can fail only at runtime.**
  A live Travel canary failed in `@applyFinalGate` with
  `Directive error (when): Failed to evaluate condition expression (||)` for a
  guard shaped like `if !@finalGate.isDefined() || @step.kind != "final"`.
  Splitting the guard showed `.isDefined()` itself failing on an executable
  parameter: `Failed to evaluate function in condition: isDefined`. The
  workaround is to make the final gate explicit and pass a no-op gate for
  suites that do not need one. The validator should flag unsupported
  function-valued `.isDefined()` checks, or the runtime should identify the
  failing operand/function directly.
