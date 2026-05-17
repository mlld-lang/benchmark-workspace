# ARCHITECTURE.md - fp-proof defended agent

The core invariant is simple:

> The LLM may choose badly, but it cannot cause an unauthorized effect.

This repo is a proof agent for high-utility deterministic security using mlld primitives. It should let models perform useful multi-step work while making the write boundary independent of model obedience, prompt wording, or semantic "ignore malicious instructions" defenses.

## Repository Shape

| Path | Responsibility |
|---|---|
| `rig/` | Generic defended-agent runtime. It should not know AgentDojo suites, task ids, expected answers, or benchmark fixtures. |
| `bench/` | AgentDojo binding layer: records, tools, policy, suite agents, fixture/source classifications, and small interface prompt addenda. |
| `llm/` | Provider/model wrappers. Model choice affects utility and latency, not security. |
| `src/` | Host-side bridge helpers used by tool wrappers. These should parse and normalize deterministically, fail closed, and avoid security policy decisions. |
| `tests/` | LLM-free proof tests for data flow, defended blocks, and disabled-defense canaries. |

`rig/` owns the architecture. `bench/` owns domain configuration. If a change needs a task id, expected answer, or benchmark-specific branch in `rig/`, it is the wrong shape.

## Data Flow

The intended flow is:

1. The suite agent in `bench/agents/<suite>.mld` receives the user task and imports suite records, tools, and policy.
2. The agent calls the generic runtime in `rig/index.mld`.
3. The planner emits structured actions, not arbitrary tool calls.
4. Read/resolve tools return record values with labels, facts, kinds, trust, handles, and projections defined by the suite.
5. Extract/compose workers may read untrusted content only through role-appropriate projections and may produce payload values, not authority.
6. Execute compiles a write intent through `@policy.build` and guard checks.
7. A write dispatches only if every input record, fact floor, kind, known check, correlation rule, and guard passes.
8. Otherwise the runtime returns a structured denial that names the boundary.

The current implementation uses structured history refs to carry observed/extracted values across actions. The ideal final form is a live shelf/handle architecture where mlld metadata survives state transitions without JSON rehydration.

## Action Contract

Planner actions should stay within a small generic vocabulary:

```json
{
  "action": "observe|select|extract|compose|authorize_execute|final|refuse",
  "tool": "optional configured tool name",
  "args": {},
  "source_refs": [],
  "target_shelf": "optional shelf slot",
  "reason": "diagnostic only"
}
```

The `reason` field is never authority. Invalid JSON, unknown actions, unknown tools, unknown shelves, unknown args, bad refs, or out-of-phase writes must fail closed before any external effect. The current implementation may compress some of these phases into `execute` wrappers, but the security boundary is still `authorize_execute`: compile first, dispatch only after policy succeeds.

## Security Primitives

The architecture relies on mlld primitives and deterministic bridge checks:

| Primitive | Role in the architecture |
|---|---|
| Records | Classify tool outputs and write inputs at ingress/egress. |
| Facts and kinds | Authorize control args such as recipient, user, channel, file id, event id, URL, and IBAN. |
| Handles | Preserve identity without exposing or reinterpreting raw strings. |
| Projections | Give each role only the fields it can safely use. Planner projections omit untrusted instruction-bearing content. |
| `known` checks | Allow exact task-text literals, such as a user-supplied IBAN, URL, email, or password, where the suite record explicitly permits that source. |
| `@policy.build` | Compiles write authorization from metadata rather than model claims. |
| Guards | Enforce cross-cutting rules such as no sensitive exfiltration and no untrusted outbound URLs. |
| Deterministic parsers | Normalize model/tool output and fail closed. They do not create security authority from content. |

Prompts may explain how to use the interface. Prompts must not be the defense.

## Roles

The runtime separates capability by role:

| Role | May see | May produce |
|---|---|---|
| Planner | Safe projections, handles, summaries, tool catalog | Structured next action or final answer. |
| Resolver | Configured read tools | Record outputs with facts/handles. |
| Extractor | Designated untrusted content | Payload text or scalar values without fact authority. |
| Composer | Payload inputs and opaque selected refs | Message bodies, summaries, descriptions, or other payload fields. |
| Executor | Write intent plus metadata | External write or structured denial. |

The smart model can plan and select. A fast worker can extract and compose. Neither model should receive native tools or raw write tools.

## Generic Policies

The generic policy stance is:

- Control args require proof: correct fact, kind, handle, correlation, or exact `known` task text.
- Payload args may be influenced or untrusted only where the input record permits payload data.
- Untrusted content cannot become new task authority.
- Sensitive labels cannot flow to exfiltration surfaces.
- Outbound URLs must be task-known or capability-backed; untrusted URLs in message bodies are blocked.
- Destructive writes require handle-grounded targets.
- Correlated multi-arg writes must use facts from the same source record where configured.

Suite policy composes these generic rules with domain-specific records and tool contracts.

## Suite Boundaries

Banking centers on money movement, scheduled transaction mutation, and password/profile updates. IBANs and scheduled transaction ids are control args. File contents are readable payload but cannot authorize payment/update args without per-file content attestation.

Workspace centers on typed instruction channels. Email bodies, file contents, calendar prose, contact notes, and attachments can be read for summaries or payloads, but recipients, participants, file ids, event ids, and destructive targets need facts or handles.

Slack centers on URL and identity provenance. Message/webpage/TODO content can be fetched or summarized through safe routes, but unsigned webpage emails, TODO app instructions, and message-body identities cannot authorize invite/DM/write args.

Travel centers on recommendation hijack. Objective fields such as rating, price, location, cuisine, hours, and fuel type can drive advice. Review prose is stripped from advice projections and cannot steer selections. PII remains omitted or guarded from exfiltration.

Cross-domain tests prove these labels survive composition: banking secrets cannot be emailed, workspace codes cannot be sent to Slack, webpage content cannot mint IBANs, and TODO text cannot become generic write authority.

## Status Semantics

`PASS` means the real AgentDojo benchmark task passed in this repo. `PASS*` means deterministic local evidence exists: utility route, defended-block proof, and disabled-defense breach canary. `OPEN` means expected secure utility without benchmark proof. `FLAKY` means expected secure utility but unstable. `*-FAIL` means the task is blocked by a missing provenance primitive and must fail at that boundary.

## Testing Philosophy

Every security-relevant feature should have a proof triple:

1. Utility: legitimate fixture-shaped data reaches the intended answer or write.
2. Defense: the same shape is blocked when authority comes from untrusted or insufficiently proven content.
3. Canary: removing the relevant defense allows the violation, proving the blocked test is not empty.

Do not use attack-suite runs as security proof. Use deterministic tests and disabled-defense canaries, then run benign canaries and full benign sweeps only when the proof evidence supports them.
