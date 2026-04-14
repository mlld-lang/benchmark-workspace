# Rig Architecture

Rig is a mlld framework for defended capability-oriented agents. This document describes the separation of concerns and the discipline that keeps the system general.

## Why This Exists

LLM agents that call tools are vulnerable to prompt injection. You cannot stop an LLM from being tricked. You can stop the consequences from manifesting. Rig enforces runtime constraints on what tool calls can do, derived from developer-declared records and operation metadata, regardless of what the LLM decides.

## The Core Separation

Rig has a strict split between two kinds of work:

**Write-side (static, security-critical)** — tool invocations that change state. These must pass through developer-declared operation contracts. Control args need proof-bearing values. Payload args may come from user literals, extracted content, or derived values. The framework enforces these mechanically at dispatch time.

**Read-side (dynamic, general)** — resolving entities, extracting typed data from tainted content, deriving answers over typed inputs. These do not authorize side effects directly. Extract and derive produce typed results, but those results are not proof-bearing unless explicitly promoted via a validated mechanism.

Conflating these is the source of brittleness. Static contracts for writes. Dynamic shapes for read-side data production.

## The Phase Model

A task runs through phases. The planner picks which phase to dispatch next based on task state and the execution log.

- **resolve** — obtain authoritative records/handles/proofs from read tools or verified task literals. Produces proof-bearing values.
- **extract** — coerce bounded tainted content (an email body, a file, a webpage) into typed data against a schema. Produces typed-but-not-proof-bearing values.
- **derive** — compute rankings, comparisons, arithmetic, selections, summaries over already-typed inputs (resolved records, extracted payloads, other derived values). Produces typed-but-not-proof-bearing values.
- **execute** — perform one concrete write under compiled per-step authorization. Single tool invocation. No shelf scope. Compiled policy applied at dispatch.
- **compose** — render the final user-facing answer from typed state. No tools. Presentation, not reasoning.
- **blocked** — explicit halt when the task is genuinely impossible or requires clarification.

**Not in scope for v2:** an advice phase for recommendation-hijack defense. Recommendation tasks run through the normal derive → compose path. Derive operates on resolved data, which is not influenced by tainted content. Tasks where influenced content leaks past this and corrupts the recommendation are accepted as v2 misses. The advice gate pattern will be revisited once the rest of the architecture is settled.

Each phase does exactly its job. Compose does not do derivation. Execute does not do reasoning. The planner does not do tainted-content handling.

## The Source Class Vocabulary

Every value referenced in planner intent carries an explicit source class. This is the same vocabulary the authorization buckets use:

- **`resolved`** — proof-bearing value backed by authoritative state. Comes from a resolve phase (read tool result coerced through a record with `=> record`) or from verified task-text literals (user said this email, it matches `known`). Carries factsource metadata. Eligible for control-arg proof.
- **`known`** — user-typed literal from task text. Rig verifies the value appears in the query. Eligible for control-arg proof via task-text verification.
- **`extracted`** — typed value produced by extract phase from tainted content. Typed but not proof-bearing. Payload-only for writes.
- **`derived`** — typed value produced by derive phase from typed inputs. Typed but not proof-bearing. Payload-only for writes unless promoted via a validated selection ref.
- **`allow`** — tool-level unconstrained authorization. Only permitted on tools with no control args.

The planner cannot "upgrade" an extracted or derived value into resolved proof by relabeling the source class. Rig validates source class against the provenance stored with the value.

## The Clean Planner Invariant

The planner is a long-running planner LLM session that coordinates work. It never sees raw tainted content. It sees:
- records projected through `role:planner` display (fact fields as handles, data fields omitted or masked)
- extract and derive results (typed schemas; scalars are payload-only; selection refs point back to resolved instances)
- execution log attestations (status, handles, counts — no worker prose)

The planner emits typed intent: resolve a record family, extract from a source, derive a shape from typed inputs, execute an operation with typed args, compose a final answer. It does not author rig internals (slot names, contract registry paths, auth buckets).

This invariant is load-bearing. If the planner sees tainted content, prompt injection reaches the authorization layer. If the planner authors rig internals, framework mistakes look like task mistakes.

## The Separation of Concerns

**App code declares domain truth:**
- **records** — what values are (facts vs data), how they project (display modes), how they're identified (keys), how they persist
- **tools** — what operations exist, which are read vs write, control args, payload args, risk labels, static payload records for writes

That's the whole app-to-rig contract. Two files per suite. No shelf authoring. No policy wiring. No contract catalogs for derivation.

**Rig owns the mechanics:**
- phase loop and worker dispatch
- state storage (derived from record declarations)
- display projection at LLM boundaries
- handle exposure and resolution
- compiled authorization via `@policy.build`
- source class validation and ref lowering
- selection ref validation (the only derive/extract → control-arg bridge)
- phase lifecycle emission to the host
- prompt generation for each worker (including op docs from tool metadata)

App developers should never need to know how any of this works to ship a working defended agent.

## Extract vs Derive: Why Both

Extract and derive look similar from outside — both produce typed output. They are not interchangeable.

**Extract reads tainted content.** An email body, a file, a webpage contains free-text that has to be turned into structured fields (a task list, a calendar event payload, an address change). The input is data with `untrusted` labels. Extract coerces through a schema — either the write tool's `payloadRecord` (for write-preparation extract) or an inline planner-declared schema (rare). The output carries extracted provenance.

**Derive reads already-typed values.** Resolved records, extracted payloads, other derived values, sometimes task literals. No tainted free-text. Derive computes: ranking, comparison, arithmetic, selection. The output carries derived provenance.

They sit at different points in the security model. Extract crosses the tainted/typed boundary. Derive operates within the typed layer. Collapsing them would lose a meaningful distinction.

What rig v2 does change: extract no longer depends on a suite-specific standalone contract catalog. The schema for extract comes from either the write tool's `payloadRecord` (for write preparation) or an inline planner-declared schema (for the rare cases where extract is producing typed data for reasoning rather than writing). See spike 41 for the proof that `payloadRecord` is enough schema authority.

## Derive and the Control-Arg Firewall

Extract and derive results are typed but not proof-bearing. A derived email address is not eligible for a `send_email.recipient` control arg even if it happens to equal a known address.

The only bridge from extract/derive outputs into control-arg proof is a **selection ref**: a ref that points back to an already-resolved instance. **Selection refs can only be produced by derive, not by extract** (spike 42). Extract reads tainted content; allowing extract to mint selection refs would create a laundering path where injected content could "select" an arbitrary resolved instance. Derive operates on typed inputs, so selecting among them is selection among already-proven values.

If derive selects among resolved hotels, it returns a selection ref identifying the winner as an existing resolved record. Rig validates the ref (it must resolve to an instance that was in the derive input set and carries original factsource proof), then carries through the original proof at the execute boundary.

Selection refs are rig-validated — they cannot be planner-authored as plain resolved refs. This closes the laundering path.

Raw extracted or derived scalars cannot reach control args under any circumstance.

## What Rig Does Not Do

- Rig does not weaken write-side security to make reads easier.
- Rig does not let extract or derive authorize writes directly.
- Rig does not let the planner guess source class from string matching.
- Rig does not let the planner relabel a derived value as resolved.
- Rig does not solve task-reasoning failures by adding prompt discipline.
- Rig does not host suite-specific state or contracts.

When you find yourself wanting to bend these rules, the answer is almost always: add a general primitive, not a task-shaped workaround.

## The Discipline

When a new task fails, ask:
1. Is a rig invariant broken? Fix rig.
2. Is the domain under-declared (records/tools don't express the task's truth)? Improve records/tools.
3. Is this an extract or derive miss? Route through the correct phase.
4. Is this a concrete handoff bug (wrong arg carry, lowercased username)? Fix the bug.

The wrong moves are:
- add a task-shaped contract to the suite
- add a task-shaped rule to the planner prompt
- add a task-shaped guard to the orchestrator
- add a workaround to rig for a domain quirk

If the abstraction name sounds like the benchmark answer, it's overfitting.

## Layered Defenses

Rig composes the mlld security primitives into five layers. Each catches what the others miss:

1. **Taint tracking** — contaminated data can't flow into sensitive operations.
2. **Fact-based proof** — authorization-critical values must come from authoritative sources.
3. **Display projections** — the LLM can't exfiltrate what it can't see.
4. **Authorization** — the planner constrains which tools and values the worker can use via compiled per-step policy.
5. **Typed state with source class firewall** — derived and extracted values cannot promote into proof-bearing state without a validated selection ref.

An attack that gets past one layer hits the next.

## Harness Agnosticism

The planner and workers are LLM calls. The specific LLM backend is pluggable (Claude, opencode, open-model). Rig does not assume a specific provider. Prompts, display projection, and session tracking work with any harness that supports the minimal protocol (structured input, structured output, session ID).

## References

- mlld primitives: `~/mlld/mlld/spec-thin-arrow-llm-return.md`, `~/mlld/mlld/spec-display-labels-and-handle-accessors.md`, `~/mlld/mlld/spec-agent-authorization-permissions.md`
- Security narrative: `~/mlld/benchmarks/labels-policies-guards.md`
- De-risking spikes: see `~/mlld/clean/SPIKES.md`
