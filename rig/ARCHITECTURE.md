# Rig Architecture

Rig is a mlld framework for defended capability-oriented agents. This document describes the separation of concerns and the discipline that keeps the system general. Phase mechanics, lifecycle files, and policy synthesis details live in `PHASES.md` — this doc is the why, not the how.

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
- **resolve_batch** — parallel-safe fan-out of multiple resolves in one planner turn (introduced for travel; eliminates serialized cascade latency on multi-domain lookups).
- **extract** — coerce bounded tainted content (an email body, a file, a webpage) into typed data against a schema. Produces typed-but-not-proof-bearing values.
- **derive** — compute rankings, comparisons, arithmetic, selections, summaries over already-typed inputs (resolved records, extracted payloads, other derived values). Produces typed-but-not-proof-bearing values.
- **rehearse** — pre-execute structural check: the planner proposes an execute decision and rig validates source classes, control-arg proof, and policy *without* dispatching the tool. Used to catch infeasible operations early and surface a structured hint to the planner.
- **execute** — perform one concrete write under compiled per-step authorization. Single tool invocation. No shelf scope. Compiled policy applied at dispatch.
- **compose** — render the final user-facing answer from typed state. No tools. Presentation, not reasoning.
- **advice** — alternate compose path for recommendation/advice queries, gated by a task-entry classifier. Uses `role:advice` display projection that structurally strips `data.untrusted` fields before any LLM call sees state, plus a `no-influenced-advice` policy rule that catches anything that slips through. Falls back to a fact-only answer if any input still carries `influenced` taint.
- **blocked** — explicit halt when the task is genuinely impossible or requires clarification.

Each phase does exactly its job. Compose does not do derivation. Execute does not do reasoning. The planner does not do tainted-content handling. See `PHASES.md` for the dispatch contract and the host-integration files each phase emits.

## The Source Class Vocabulary

Every value referenced in planner intent carries an explicit source class. This is the same vocabulary the authorization buckets use:

- **`resolved`** — proof-bearing value backed by authoritative state. Comes from a resolve phase (read tool result coerced through a record with `=> record`) or from verified task-text literals (user said this email, it matches `known`). Carries factsource metadata. Eligible for control-arg proof.
- **`resolved_family`** — projection across the resolved set of a record type (e.g. all resolved hotels' names). Family expansion is rig-validated; each expanded entry inherits its source instance's proof. Used by derive when reasoning over the full resolved population of a kind.
- **`known`** — user-typed literal from task text. Rig verifies the value appears in the query. Eligible for control-arg proof via task-text verification.
- **`selection`** — rig-minted ref pointing back to a specific resolved instance that survived a derive. The only bridge from derive output into control-arg proof. Cannot be planner-authored; rig validates that the ref resolves to an instance in the derive input set and carries through that instance's original factsource proof.
- **`extracted`** — typed value produced by extract phase from tainted content. Typed but not proof-bearing. Payload-only for writes.
- **`derived`** — typed value produced by derive phase from typed inputs. Typed but not proof-bearing. Payload-only for writes unless promoted via a validated `selection` ref.
- **`allow`** — tool-level unconstrained authorization. Only permitted on tools with no control args.

The planner cannot "upgrade" an extracted or derived value into resolved proof by relabeling the source class. Rig validates source class against the provenance stored with the value. The full whitelist lives at `planner_inputs.mld`.

## The Clean Planner Invariant

The planner is a long-running planner LLM session that coordinates work. It never sees raw tainted content. It sees:
- records projected through `role:planner` display (fact fields as handles, data fields omitted or masked)
- extract and derive results (typed schemas; scalars are payload-only; selection refs point back to resolved instances)
- execution log attestations (status, handles, counts — no worker prose)

The planner emits typed intent: resolve a record family, extract from a source, derive a shape from typed inputs, execute an operation with typed args, compose a final answer. It does not author rig internals (slot names, contract registry paths, auth buckets).

This invariant is load-bearing. If the planner sees tainted content, prompt injection reaches the authorization layer. If the planner authors rig internals, framework mistakes look like task mistakes.

## The Separation of Concerns

**App code declares domain truth:**
- **records** — what values are (facts vs data), how they project (display modes for planner / worker / advice), how they're identified (keys), how they persist
- **tools** — what operations exist, which are read vs write, control args, payload args, risk labels, static payload records for writes, per-tool `instructions:` guidance

That's the core app-to-rig contract. A suite may also supply: per-worker prompt addendums (planner / extract / derive / compose), classifiers for task-entry routing, and a bridge module for adapter coercions at the MCP boundary. None of these are required for a working agent — they're opt-in surface for suites that need them.

**Rig owns the mechanics:**
- planner-facing tool wrappers and worker dispatch (resolve, resolve_batch, extract, derive, rehearse, execute, compose, advice, blocked)
- state storage (derived from record declarations)
- display projection at LLM boundaries (`role:planner`, `role:worker`, `role:advice`)
- handle exposure and resolution
- compiled authorization via `@policy.build`
- source class validation and ref lowering (including resolved_family expansion and selection ref minting)
- selection ref validation (the only derive → control-arg bridge)
- parallel classifier fan-out at task entry (`@rig.classify`) and `toolFilter` / `adviceMode` consumption
- URL promotion: tainted URL extraction, private URL capabilities, output URL validation
- output validators (forbidden-pattern checks on terminal compose output)
- lifecycle event emission to the host (phase log, phase state, LLM call log, execution log — see `PHASES.md`)
- prompt generation for each worker (including op docs from tool metadata)

App developers should never need to know how any of this works to ship a working defended agent. Suites contribute domain truth and optional addendums; rig owns mechanics.

## Extract vs Derive: Why Both

Extract and derive look similar from outside — both produce typed output. They are not interchangeable.

**Extract reads tainted content.** An email body, a file, a webpage contains free-text that has to be turned into structured fields (a task list, calendar-event inputs, an address change). The input is data with `untrusted` labels. Extract coerces through a schema — either the write tool's `inputs` record (for write preparation) or an inline planner-declared schema (rare). The output carries extracted provenance.

**Derive reads already-typed values.** Resolved records, extracted payloads, other derived values, sometimes task literals. No tainted free-text. Derive computes: ranking, comparison, arithmetic, selection. The output carries derived provenance.

They sit at different points in the security model. Extract crosses the tainted/typed boundary. Derive operates within the typed layer. Collapsing them would lose a meaningful distinction.

What rig does change relative to v1: extract no longer depends on a suite-specific standalone contract catalog. The schema for extract comes from either the write tool's `inputs` record (for write preparation) or an inline planner-declared schema (for the rare cases where extract is producing typed data for reasoning rather than writing).

## Derive and the Control-Arg Firewall

Extract and derive results are typed but not proof-bearing. A derived email address is not eligible for a `send_email.recipient` control arg even if it happens to equal a known address.

The only bridge from extract/derive outputs into control-arg proof is a **selection ref**: a ref that points back to an already-resolved instance. **Selection refs can only be produced by derive, not by extract.** Extract reads tainted content; allowing extract to mint selection refs would create a laundering path where injected content could "select" an arbitrary resolved instance. Derive operates on typed inputs, so selecting among them is selection among already-proven values.

If derive selects among resolved hotels, it returns a selection ref identifying the winner as an existing resolved record. Rig validates the ref (it must resolve to an instance that was in the derive input set and carries original factsource proof), then carries through the original proof at the execute boundary.

Selection refs are rig-validated — they cannot be planner-authored as plain resolved refs. This closes the laundering path.

Raw extracted or derived scalars cannot reach control args under any circumstance.

## The Advice Gate

Recommendation/advice queries are the canonical recommendation-hijack target: an attacker plants a "best hotel" pitch in an untrusted review field, and a naive compose surfaces it. Rig handles this with a task-entry classifier plus a separate worker:

1. The suite agent runs an advice classifier (via `@rig.classify`) that decides whether the query is asking for a recommendation. Classification result threads into `adviceMode: true` on `@rig.run`.
2. When `adviceMode` is set, terminal compose routes to the **advice worker** (`workers/advice.mld`) instead of the standard compose worker.
3. The advice worker projects state through `role:advice`, which structurally strips `data.untrusted` fields (e.g. hotel `review_blob`). Untrusted prose never reaches the LLM.
4. A module-scope `no-influenced-advice` policy rule denies any advice-labeled exe whose inputs still carry the `influenced` taint label after projection. If the rule fires, the gate falls back to a fact-only answer over resolved-records only.

The defense is structural at layer 3 (display projection) and policy-enforced at layer 4 (authorization). Prompt discipline is not the defense.

## URL Promotion

Tainted URLs are dual-purpose: they may name a resource the user wants fetched (`get_webpage_via_ref`), or they may carry exfiltration payloads. Rig handles them as a separate primitive:

- A `find_referenced_urls` rigTransform pulls URLs out of typed state and exposes them as refs the planner can call by index, never by literal value.
- A private `get_webpage_via_ref` capability resolves the ref through rig and returns content into a tainted record.
- Output validators (`validators/output_checks.mld`) and the `url_output` policy (`policies/url_output.mld`) check terminal compose output for novel URLs that did not originate in the input space.

This keeps the planner from authoring URLs it constructed from untrusted text, and prevents tainted URLs from reaching outbound exfil channels in compose output.

## What Rig Does Not Do

- Rig does not weaken write-side security to make reads easier.
- Rig does not let extract or derive authorize writes directly.
- Rig does not let the planner guess source class from string matching.
- Rig does not let the planner relabel a derived value as resolved.
- Rig does not host suite-specific state or contracts.
- Rig does not solve task-reasoning failures by adding rules to its own (generic) prompts. Per-suite reasoning conventions belong in suite addendums or per-tool `instructions:` — see CLAUDE.md "Prompt Placement Rules" for the layering.

When you find yourself wanting to bend these rules, the answer is almost always: add a general primitive, not a task-shaped workaround.

## The Discipline

When a new task fails, ask:
1. Is a rig invariant broken? Fix rig.
2. Is the domain under-declared (records/tools don't express the task's truth)? Improve records/tools.
3. Is this an extract or derive miss? Route through the correct phase.
4. Is this a concrete handoff bug (wrong arg carry, lowercased username)? Fix the bug.
5. Is this a domain-reasoning gap that holds across a class of tasks in this suite? Add a suite addendum at the smallest worker scope that catches it.

The wrong moves are:
- add a task-shaped contract to the suite
- add a task-shaped rule to the planner prompt
- add a task-shaped guard to the orchestrator
- add a workaround to rig for a domain quirk

If the abstraction name sounds like the benchmark answer, it's overfitting.

## Layered Defenses

Rig composes the mlld security primitives into six layers. Each catches what the others miss:

1. **Taint tracking** — contaminated data can't flow into sensitive operations.
2. **Fact-based proof** — authorization-critical values must come from authoritative sources.
3. **Display projections** (`role:planner`, `role:worker`, `role:advice`) — the LLM can't exfiltrate or be influenced by what it can't see.
4. **Authorization** — the planner constrains which tools and values the worker can use via compiled per-step policy.
5. **Typed state with source class firewall** — derived and extracted values cannot promote into proof-bearing state without a validated selection ref.
6. **URL promotion + output validation** — tainted URLs only reach tools through rig-minted refs; terminal output is checked for novel URL exfil.

An attack that gets past one layer hits the next.

## Role context across authorize-then-submit flows

Post-m-rec-perms-update, rig's write-tool dispatch path activates two role contexts in sequence:

- **Outer exe is `role:worker`** — the role that performs the side effect. The MCP submit happens here, and the input record's `write.role:worker.tools.submit` permission is checked against the active role at that moment.
- **Inner exe is `role:planner`** — invoked from inside the worker exe to do the authorization compile (`@policy.build`). The planner role is activated briefly; `@policy.build` checks the input record's `write.role:planner.tools.authorize` permission AND the value-attestation/source-class proofs for the planner-supplied args.

The canonical example is `rig/workers/execute.mld`:

```mlld
exe role:planner @compileForDispatch(...) = [
  let @built = @policy.build(...)   >> planner-side authorize check
  => { ok: ..., built: @built, ... }
]

exe role:worker @dispatchExecute(...) = [
  let @prep = @compileForDispatch(...)   >> role transitions to planner
  ...                                     >> role transitions back to worker
  let @raw = @callToolWithPolicy(...)    >> submit happens under role:worker
  ...
]
```

**Both gates fire — defense in depth.** `@policy.build` certifies that the planner's intent matches the tool's input record schema and the planner has authorize permission. The runtime's `write.role:worker.tools.submit` check certifies that the active role at submit time has explicit submit permission. An attacker that bypasses one still hits the other.

**Don't simplify either role annotation.** Reverting `@dispatchExecute` to `role:planner` regresses the migration: post-cutover, `policy.build` would still pass (planner has authorize) but the submit would fail (`WRITE_DENIED_NO_ROLE: activeRole=role:planner, declaredRoles=role:worker`). Reverting `@compileForDispatch` to `role:worker` would skip the planner-side intent verification; the submit would succeed but planner-side proofs wouldn't be re-validated.

**Call-site role assertion does NOT activate the write context.** `@call(...) with { read: "role:worker" }` only affects projection, not write authorization. The active role for write enforcement is the EXE's declared role, period. (Verified by parse probe; error: `WRITE_DENIED_NO_ROLE` persists with `activeRole: role:planner` despite `with { read: "role:worker" }`.)

**Test scaffold inherits the production role structure.** Tests of write-dispatch paths need `exe role:worker @testFoo()` outer; tests of `@policy.build` invariants need `exe role:planner @testBar()` outer. Tests that mix both (e.g., build-and-dispatch in one logical flow) split into two role-scoped exes. The pattern catches in test runs as `WRITE_DENIED_NO_ACTIVE_ROLE` (module scope) or `WRITE_DENIED_NO_ROLE: activeRole=role:planner` (planner-outer test invoking a worker-side dispatch).

This pattern generalizes for any future authorize-then-submit flow rig adds. As of Phase 1, only `@dispatchExecute` follows it; resolve and extract phases call read-side tools whose input records don't trigger write enforcement.

## The AgentDojo MCP Bridge

Rig ships a Python MCP server (`rig/agentdojo-mcp/`) that exposes AgentDojo's per-task fixtures as MCP tools and persists post-run env state. It lives under rig because it's part of the rig/host integration contract, not a per-suite concern. Suites use it via `import tools from mcp "tools"` in their `tools.mld`. The server handles state coercion, fixture loading, and env-state writeback for AgentDojo's evaluator. A legacy `clean/src/mcp_server.py` exists as a fallback path; new work targets the rig-hosted server.

## Defended vs Undefended

Rig defaults to defended. Setting `defense: "undefended"` on `@rig.run` skips:
- compiled per-step authorization (`@policy.build` + policy-bearing dispatch)
- the synthesized base policy

What still runs in undefended mode:
- display projection at LLM boundaries (`role:planner` / `role:worker` / `role:advice`)
- source-class validation on planner refs
- selection ref minting and validation
- taint label propagation

Undefended is a measurement mode for ablation comparisons, not a "raw mlld" mode. If you need to disable display projection or source-class checks for an experiment, do it explicitly per-experiment — don't read undefended as "everything off."

## Harness Agnosticism

The planner and workers are LLM calls. The specific LLM backend is pluggable (Claude, opencode, open-model). Rig does not assume a specific provider. Prompts, display projection, and session tracking work with any harness that supports the minimal protocol (structured input, structured output, session ID).

## References

- mlld primitives: `~/mlld/mlld/spec-thin-arrow-llm-return.md`, `~/mlld/mlld/spec-display-labels-and-handle-accessors.md`, `~/mlld/mlld/spec-agent-authorization-permissions.md`
- Security narrative: `clean/labels-policies-guards.md`
- Phase / lifecycle / policy contract: `PHASES.md`
- Security invariants: `SECURITY.md`
- Advice gate: `ADVICE_GATE.md`
- URL promotion: `URL_PROMOTION.md`
- Typed instruction channel (deferred design): `TYPED_INSTRUCTION_CHANNEL.md`
