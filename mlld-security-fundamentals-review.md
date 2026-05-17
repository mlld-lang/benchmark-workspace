# mlld-security-fundamentals.md review notes

These notes are based on rebuilding the AgentDojo proof agent in this repo and comparing the result against the older `clean` rig. The fundamentals document is strong as a runtime/security reference. The main opportunity is to add a shorter agent-builder path and make several hard-won benchmark lessons more explicit.

## Suggested changes

### Add a "defended agent quick path"

The document is deep enough to be correct, but a new agent builder needs a 1-2 page path before the full reference:

1. Model every downstream write control arg as a record `facts:` field.
2. Put instruction-bearing content in `data.untrusted:`.
3. Give planner/read roles projections that omit untrusted prose.
4. Put exact user-task literals in `known`, never values merely discovered in payload.
5. Put resolved record values in `resolved`, never copied strings.
6. Run `@policy.build` inside `role:planner`.
7. Dispatch the write inside `role:worker`.
8. Prefer `records_require_tool_approval_per_role: true` for defended agents.
9. Write a proof triple: utility, defended block, disabled-defense canary.

### Promote strict submit-role guidance

The doc explains `records_require_tool_approval_per_role`, but it currently reads like an optional advanced mode. For defended agents, the safer default should be:

- records declare both `write.role:planner.tools.authorize` and `write.role:worker.tools.submit`;
- policy sets `records_require_tool_approval_per_role: true`;
- the dispatcher has an outer `role:worker` submit helper and an inner `role:planner` `@policy.build` helper.

This should be documented as the canonical planner-worker pattern. The current proof agent now uses this shape.

### Make `known` more obviously narrow

The most common mistake is treating `known` as "the model knows this" or "a worker found this". It should be restated aggressively:

- `known` means exact user-task text, from an uninfluenced source.
- Values copied from email/file/message/webpage content are not `known`.
- Array values require every security-critical element to be task-grounded or proven.
- If a value was found by a tool, prefer a fact-bearing `resolved` value or deny.

### Add a benchmark-grade proof section

The fundamentals doc should define the test bar used here:

- utility test proves legal data can flow;
- defense test proves the unsafe path is blocked at the intended primitive;
- canary test proves the same violation succeeds when that primitive is removed.

This should include the SHOULD-FAIL nuance: a task is not healthy merely because it fails. It must fail due to policy, guard, projection, write grant, fact proof, exact-known, correlation, or another named primitive.

### Add transcript-first debugging guidance

The runtime sections mention tracing, but defended-agent debugging needs an operational rule:

- read the agent transcript before hypothesizing;
- policy/build denials, missing proof, wrong refs, and arbitrary planner failure look identical in the final score;
- a structural refusal must be transcript-cited before it is counted.

This belongs near the tracing section and should point to the expected evidence fields: `policy_denied`, `security_denied`, `known_not_in_task`, `proofless_control_arg`, `history_ref_denied`, guard denial code, and record/write denial codes.

### Document URL capability as a first-class pattern

The Slack suite showed that URL provenance deserves a standard recipe:

- direct URL fetch is allowed only for task-known URLs;
- URLs discovered inside messages/files/webpages should become opaque refs;
- raw payload URLs should not be planner-visible reusable authority;
- destination URLs for writes need task-known or signed/app-origin provenance;
- outbound payload URLs should be blocked by policy/guard unless intentionally allowed.

This currently requires local helper code. It would be useful to present the desired mlld-native shape even if the primitive is still evolving.

### Separate reference depth from field modeling rules

The record sections are correct, but the load-bearing modeling rule should be repeated in every relevant section:

> If a value may ever become a write control arg, model it as a fact at ingress. If it is instruction-bearing content, model it as untrusted data. Do not try to recover authority later from a derived string.

That one rule explains most AgentDojo passes and most SHOULD-FAIL ceilings.

### Call out JS/Python interop as a benchmark risk

The interop section is good. Add a short warning specific to agents:

- JS helpers may normalize, rank, and aggregate;
- JS helpers must not recreate security authority;
- do not parse record metadata in JS to decide authorization;
- after JSON serialization, assume proof is gone unless the runtime explicitly preserves it.

This would have saved several proof-bridge detours.

### Clarify display projection vs advice

The influenced-advice defense is easier to understand if the doc separates:

- preventing unsafe writes after seeing untrusted text;
- preventing recommendations/advice from being biased by untrusted review prose.

The latter is not just a write-control problem. The cleanest pattern is role-specific projection plus an `advice` gate or objective-only records. The fundamentals doc should include both patterns.

### Add a "do not build a phase framework first" note

The successful proof agent came from building records, policy, and tests first, then letting the agent loop stay small. The fundamentals doc can explicitly warn that mlld primitives are the framework; don't make the model learn a large custom provenance grammar unless a smaller records/policy shape has failed.
