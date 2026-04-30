# Output Validators

Status: proposal / informal spec.
Scope: rig framework + bench consumer pattern.
Audience: rig maintainers, bench suite authors.
Sibling docs: `rig/PARSE_VALUE.md`, `rig/URL_PROMOTION.md`, `labels-policies-guards.md`.

## Bottom Line

Output validators are a third primitive alongside records and labels. They handle a class of correctness check that the other two structurally cannot:

- **Records** validate shape (types, presence, per-field format via post-ops). They answer *"is this scalar valid in isolation?"*
- **Labels + policies** validate flow (provenance, capability, sensitivity routing). They answer *"is it allowed for this value to reach this sink?"*
- **Validators** validate cross-value relationships between an output and one or more inputs/state. They answer *"given what we asked for and what's in state, did this output meet the contract?"*

The third question recurs across LLM workers (compose, extract, derive) and is currently handled either with imperative ad-hoc retries (the existing malformed-JSON retry in `rig/workers/compose.mld`) or with prompt rules that the model may or may not follow. Neither composes, neither generalizes, both leak into worker code.

This spec defines a small framework module — `rig/validators/` — and a configuration pattern that lets suites declare domain-specific output constraints alongside their records.

## Why This Exists

### The recurring shape

A worker (compose, extract, derive) emits a value. The value's *shape* is fine — it parses, it has the expected fields, it carries the right labels. But some non-shape property fails:

- The compose answer to *"read the content at www.X.com"* is a confirmation ("the content has been fetched") rather than the actual content.
- The compose answer drops `, France` from an address whose canonical record value contains it.
- The extract output for a recipe text returns `{ ingredient: null }` even though the source body clearly references an ingredient.
- The derive output for a "best hotel" task references an entity not present in the input set.

In every case, the output is *legal* by every shape/flow check, but *wrong* relative to what the worker was asked to produce given the inputs it was given.

### Why records can't catch this

Records validate values in isolation — type, presence, per-field format. Cross-value relational claims (*"this string must be a substring of that other field's value"*) would require either a query language inside record declarations (huge surface, kills static analyzability) or callback hooks that drag arbitrary code into record schemas (kills the static-shape contract that makes records useful).

### Why labels + policies can't catch this

Labels and policies are about data flow. They answer *"can this value, with these labels, reach this sink?"* They don't compute over content. The runtime tracks that an LLM output is `influenced` because input was `untrusted`; it does not (and cannot, in general) track *"does the output text contain a specific substring of a specific input."*

### Why prompt rules don't suffice

Prompt rules tell the model *"render the canonical state value, not the planner's paraphrase."* Models — especially smaller workers — frequently ignore this, particularly when shorter or differently-shaped outputs are more natural for their training distribution. Discipline rules in the prompt are a wish, not an enforcement mechanism. The same issue CaMeL flags about Q-LLM output: *"Q-LLM output is not considered 'clean' just because it came from an LLM."* Faithfulness to source data isn't an LLM property; it has to be checked structurally.

### The validator answer

A validator is a pure function that inspects an output against context and returns *"this output satisfies the contract"* or *"this output fails because X; here's a hint to feed back into the worker."* The runtime composes validators into guards that fire after worker LLM calls, and on failure the guard issues `=> resume` (preserving session context) with the validator's hint as a follow-up turn.

The validator never decides *what* to retry; it decides *whether* to retry and *with what feedback*. The model still does the recovery, but with a structural check between attempts.

## Where Validators Fit

```
shape          flow            relational
─────         ─────           ──────────
records       labels          validators
              + policies
```

Each is a different question, each enforced at a different boundary, each with its own primitives. Validators don't compete with records or labels; they extend the framework's correctness vocabulary in a direction the other two were never trying to cover.

The trust-boundary placement matches CaMeL's principle: don't let the model be the policy bearer for its own output.

## Design

### Validator contract

A validator is a native mlld exe with the signature:

```mlld
exe @validatorName(output, context) = [
  >> output:  the value being checked (typically a string, sometimes an object)
  >> context: anything the check needs — decision, stateSummary, expected fields, etc.
  >> Returns: { ok: bool, kind: string?, hint: string? }
  ...
  => { ok: <bool>, kind: "<kind-tag>", hint: "<retry message>" }
]
```

Three rules:

1. **Native mlld, never JS.** Auto-unwrap at the JS boundary strips labels and factsources. Validators inspect `output` which often carries `influenced`/source metadata; that metadata must survive. Native mlld string operations (`.includes`, `.match`, `.toLowerCase`, `.length`) and iteration (`for @k, @v in @obj`) are sufficient for every validator we've identified so far.
2. **Pure function.** No side effects, no state mutation, no I/O. Inputs in, structured result out. This makes validators testable in zero-LLM unit tests and reusable across any worker.
3. **Returns an explanation, not a verdict.** When a validator fails, it returns *both* the negative result *and* the hint to feed back to the worker. The hint should quote relevant state values verbatim so the worker has the exact material to render on retry.

### Combinator

Multiple validators compose via a runner:

```mlld
exe @runOutputValidators(validators, output, context) = [
  >> Runs validators in order. Stops at first failure.
  >> Returns: { ok: bool, failed: <validator name>?, hint: <message>?, all_results: [] }
  ...
]
```

Order matters. Generic checks (length, content presence) run first; expensive or domain-specific checks run after. The runner short-circuits on first failure to keep the retry loop fast.

### Standard validators (`rig/validators/output_checks.mld`)

Initial set, all generic:

| Validator | Purpose | Failure trigger |
|---|---|---|
| `@must_contain_cited_content` | Output must include content from sources cited in `decision.sources` when the task asks for content. | `purpose` matches `\b(read|show|summarize|report|content|article)\b` AND a cited source has a string field >50 chars AND output length < 150. |
| `@must_preserve_field_values` | Output must contain a state field's verbatim value when `purpose` names that field. | `purpose` mentions a field name AND the field's value is non-empty AND that value isn't a substring of output. |
| `@must_have_min_length` | Output meets a configurable minimum. | Length below threshold. |
| `@must_be_nonempty` | Trivial precondition for compose. | Empty string. |
| `@must_match_pattern` | Format check via regex. | Pattern doesn't match. |

Each is parameterized; suites configure thresholds and per-validator options through the validator list.

### Suite extension pattern

Suites add domain-specific validators alongside their records and tools:

```
bench/domains/<suite>/
  records.mld           — data shapes
  tools.mld             — operations
  validators.mld        — output constraints  ← NEW
  prompts/
    planner-addendum.mld
```

A suite validator can reference suite records freely, since validators and records are sibling layers of domain truth:

```mlld
import { @hotel } from "./records.mld"

>> Travel-specific: a rendered address must include all parts the @hotel
>> record stores. Catches the "Paris" vs "Paris, France" surface even when
>> the planner's purpose paraphrased.
exe @must_render_full_address(output, decision, stateSummary) = [
  ...checks output text against @hotel.address field values from cited
     sources, returns { ok, kind: "field_truncation", hint }...
]

>> Travel-specific: rating values must render with one decimal place.
exe @must_render_rating_with_decimal(output, decision, stateSummary) = [
  ...
]

var @composeValidators = [
  >> Generic checks come first, suite-specific after.
  @must_contain_cited_content,
  @must_preserve_field_values,
  @must_render_full_address,
  @must_render_rating_with_decimal
]

export { @composeValidators }
```

### Worker integration

Validators are wired through the worker's existing guard pattern. The worker exposes a session, calls the LLM through a named exe (one per harness), and a `guard after` runs the validator list and either allows the result or resumes the session with the failed validator's hint.

```mlld
>> Compose-worker session
var session @composeSession = {
  decision: object?,
  stateSummary: object?,
  query: string?,
  validators: array
}

>> Per-harness LLM call (matches the planner.mld pattern)
exe @composeLlmCallStub(prompt, config) =
  @llmCall("stub", @prompt, @config) with {
    display: "role:worker",
    session: @composeSession
  }

guard after @composeRetryGuardStub for op:named:composeLlmCallStub = when [
  @mx.guard.try < 2 && @runOutputValidators(@composeSession.validators, @mx.output, @composeSession).ok == false
    => resume @runOutputValidators(@composeSession.validators, @mx.output, @composeSession).hint
  * => allow
]
```

The `=> resume` keeps the same model session and sends the hint as a follow-up user turn. The model has its previous output in context and can refine. This is preferred over `=> retry`, which starts a new session and loses context — the model would have to rebuild its reasoning from scratch.

### Agent configuration

`rig.build` accepts a `composeValidators` field. The default is a sensible generic list:

```mlld
var @defaultComposeValidators = [
  @must_contain_cited_content,
  @must_preserve_field_values
]
```

Suites that don't care inherit the default. Suites that do care pass their own list:

```mlld
import { @composeValidators } from "../domains/travel/validators.mld"

var @agent = @rig.build({
  ...,
  composeValidators: @composeValidators
})
```

The mechanism mirrors how suite addendums are wired (`plannerAddendum`, `deriveAddendum`, etc.) — same pattern bench authors already learn for prompts, applied to validators.

## Usage

### Suite developer: adding a domain check

1. Identify the failure mode. Read transcripts of failing tasks; find the relational property the output should satisfy but doesn't. Confirm the property is generic across a *class* of tasks in the suite, not specific to one benchmark task (Cardinal Rule A).
2. Write a native mlld validator exe in `bench/domains/<suite>/validators.mld`. Follow the contract: `(output, context) → { ok, kind, hint }`.
3. Add the validator to the suite's exported list (typically appended after generic validators).
4. Test the validator in isolation: zero-LLM input/output cases that exercise the check.
5. Live-canary against the failing task class. Acceptance threshold per CLAUDE.md (≥4/5 PASS for the targeted task; no regressions on adjacent tasks).

### Rig maintainer: adding a generic validator

1. Confirm the property is *truly* generic — applies regardless of suite. *"output must include content cited"* is generic; *"address must end with a country name"* is suite-specific.
2. Add to `rig/validators/output_checks.mld`. Document the failure trigger and the hint it produces.
3. Add zero-LLM tests in `rig/tests/index.mld` (suggested prefix: `OV-N`).
4. Update the default validator list if the new validator should be on by default for all suites.
5. Document the addition in this spec's "Standard validators" table.

### Rig maintainer: adding validators to a new worker

Currently scoped to the compose worker. To extend to extract/derive:

1. Add `extractValidators` / `deriveValidators` to `rig.build` config with sensible defaults.
2. Add `extractSession` / `deriveSession` if not already present.
3. Wrap the worker's `@llmCall` in three harness-specific exes (stub/opencode/claude) that bind to the session.
4. Add three `guard after` blocks that call `@runOutputValidators` and `=> resume` on failure.
5. Document new generic validators specific to that worker (e.g., `@extract_must_have_nonempty_fields_when_source_has_tokens`).

The pattern is the same; it just gets repeated per worker. If a fourth worker needs validators, consider whether the per-worker boilerplate has earned promotion to a syntax-level affordance.

## Testing

Validators are pure functions over plain inputs, so they are testable without LLM calls.

### Zero-LLM unit tests (in `rig/tests/index.mld`)

For each validator, cover:
- **Triggering case**: an output that violates the check; assert `ok == false` and the `hint` quotes the relevant state value.
- **Healthy case**: a correct output for the same context; assert `ok == true`.
- **Boundary cases**: edge thresholds (length just above/below, empty inputs, missing context fields).

For the combinator, cover:
- **Short-circuit**: first failing validator's hint propagates; later validators don't run.
- **All-pass**: empty-failure result.
- **Empty validator list**: trivially passes.

### Integration tests

A representative end-to-end test seeds a synthetic state and decision, runs `@dispatchCompose` with a stub harness, and asserts that:
- A "good" stub response is allowed through without retry.
- A "bad" stub response triggers retry, the retry receives the hint, and a corrected stub response is allowed.

### Live canaries

Each new generic or suite-specific validator is canaried against the task class it targets:
- Acceptance: ≥4/5 PASS on representative failing tasks.
- Regression check: no decline on currently-passing tasks in the same suite.

## Failure Modes and Edge Cases

### False positives

Validators are heuristic when applied to LLM outputs. False positives cost an extra LLM call (the unnecessary retry).

**Mitigations:**
- Predicates use conservative thresholds (e.g. `length < 150` for "brief" rather than `< 200`).
- Triggers gate on multiple conditions (e.g., brief-confirmation requires *both* the verb-keyword match in `purpose` *and* substantial cited content *and* short output).
- Retry budget is one extra call per worker invocation. False positives degrade cost, not correctness.

### False negatives

A validator may fail to catch a genuine issue. The retry doesn't fire and the bad output ships.

**Mitigations:**
- Validators are additive; new ones can be appended as bug classes are identified.
- Existing validators can have their predicates tightened.
- The runtime is unchanged either way; no rollback on validator changes.

### Validator authoring mistakes

A validator that always fires triggers infinite retry until the budget exhausts. The session resumes with the same hint repeatedly; the model converges or the retry budget caps it.

**Mitigations:**
- Retry budget is hard (`@mx.guard.try < N`); after the cap, the result is allowed through regardless. No infinite loops.
- Zero-LLM unit tests catch always-failing validators on synthetic healthy inputs.
- Validators that consistently fail in production are visible in the LLM call log and surface in standard transcript reads.

### Cost amplification

A worker that hits the retry budget on every call doubles its LLM spend.

**Mitigations:**
- Validators are designed for the *exception* case, not the common case. If a validator fires on >20% of healthy tasks in production, its predicate is too aggressive and should be tightened.
- Live canary acceptance includes regression-on-passing-tasks; a validator that costs widespread retries shows up as latency or budget warnings.

## Anti-Patterns

### What NOT to use validators for

- **Schema validation.** Use records.
- **Data flow / capability checks.** Use labels and policies.
- **Substituting for prompt clarity.** Validators are a backstop for cases where prompts can't reach. They aren't the place to dump every "the model should..." rule. Prompt clarity is upstream; validators are the safety net.
- **Per-task fixes.** A validator's predicate must apply to a *class* of tasks. Per-task overfitting is forbidden by Cardinal Rule A. If a check only justifies one benchmark task, it doesn't ship.
- **Cross-suite leak.** A travel-specific validator goes in `bench/domains/travel/validators.mld`. It does not reach into rig.

### What NOT to put in JS

The validator body. Native mlld preserves provenance metadata that JS auto-unwrap erases. The metadata may not matter for a specific validator's predicate, but it stays consistent and the boundary stays predictable. JS is reserved for the cases mlld genuinely cannot express (complex regex with lookbehind, bigint math, calls to external libraries) — which is essentially never for an output validator.

## Open Questions

1. **Should the runtime expose `validate:` config directly on `exe ... with { ... }`?** Right now validators wire through guards in worker code. If multiple workers in different files repeat the pattern, syntax sugar (`exe ... with { validators: [@v1, @v2], on_validation_fail: "resume" }`) becomes attractive. Defer until at least three workers use validators in production.
2. **Should validators have a "severity" field?** A `severity: "warn" | "block" | "retry"` axis would let validators distinguish "bad enough to retry" from "advisory; emit a warning but allow." Defer until concrete need.
3. **Should there be a built-in "all generic validators" macro that suites mix in?** `[...@defaultComposeValidators, @suiteValidator]` works but is verbose. A `@withDefaults([@suiteValidator])` helper might be ergonomic. Defer until the verbosity becomes a real complaint.
4. **Should the combinator return *all* failures rather than short-circuit?** Short-circuit is cheaper but loses information when multiple things are wrong. Defer until a debugging session demands the multi-result shape.

## Future Directions

- **Apply to extract and derive workers.** The pattern is uniform; each worker that emits an LLM-shaped output can have its own validator list. Likely first concrete need: a `@derive_must_reference_inputs` to catch derive workers hallucinating values not in the source set.
- **Bench-side OOS thresholds.** A suite validator that consistently fires on a known-stochastic task could itself emit a structured result that bench scoring uses to tag the failure as "validator-rejected" rather than "compose-malformed." More informative than a flat utility=false.
- **Promote to language-level syntax.** If the pattern carries across enough workers and domains, propose a `validators:` config on `exe` declarations in mlld. The runtime model is then identical to what's documented here; only the surface changes.

## Anti-Goals

- This is **not** a replacement for prompt clarity. Validators are a backstop, not the primary correctness mechanism.
- This is **not** a path for re-introducing strong worker-output policy enforcement that records or labels can't already provide. Validators check *what the worker produced*, not *what the worker is permitted to do*.
- This is **not** a way to bake benchmark-specific answers into the agent. Per-task overfitting is forbidden; predicates apply to classes of tasks or they don't ship.

## References

- `rig/PARSE_VALUE.md` — sibling design doc; analogous pattern (bounded transform with audit trail) but for `extract`-class output, not output validation.
- `rig/URL_PROMOTION.md` — sibling design doc; capability scoping for a specific transform.
- `labels-policies-guards.md` — security model narrative; explains why guards are the right dispatch surface.
- `CLAUDE.md` Cardinal Rule A — overfitting prohibition; applies to validator predicates.
- `~/mlld/benchmarks/camel-security.md` (project notes) — the architectural insight that a Q-LLM's output shouldn't be assumed clean. Validators operationalize that for a worker-output context.
- `rig/workers/planner.mld` — concrete `=> resume` usage in the existing compose-retry-when-no-terminal guards. Validators reuse the same pattern.

## Status / Next Steps

### What shipped

1. **`rig/validators/output_checks.mld`** — generic validators (`@must_contain_cited_content`, `@must_preserve_field_values`), the `@runOutputValidators` combinator, the `@composeOutputText` JSON-extraction helper, and `@defaultComposeValidators` default list.
2. **`rig/tests/index.mld`** — 9 zero-LLM unit tests under `validators/OV-N` covering: brief-confirmation triggering and skipping, field-divergence triggering and skipping, combinator short-circuit and all-pass and empty-list, JSON-text extraction. All passing in the invariant gate.

### What deferred

The compose-worker integration (`rig/session.mld @composeSession` + per-harness wrappers + guards) was prototyped and verified mechanically (guards fire, `=> resume` sends hints, model receives them) but reverted from the working tree because:

- The first live consumer was UT0 / UT12, and the worker model (GLM-5.1) doesn't render meaningfully more content even with a directive hint pinning the canonical state value. The retry fires, the model rewrites, the eval still rejects. **Validator infrastructure works; the targeted cases are model-capability-limited.**
- Adding the compose-side machinery before there's a consumer that benefits adds per-compose-call overhead (one validator chain) for no measured utility win.

The compose integration design is recorded above — if a future case (or a stronger compose model) calls for it, the wiring is documented.

### Lessons learned during the prototype (worth recording)

1. **Function-call predicates inside a guard's `when` arm need a 0-arg wrapper exe to evaluate reliably.** Inline complex expressions like `@composeRetryDecision(@output, @composeSession.foo, @composeSession.bar, ...).needsRetry` did not trigger retries even when the equivalent logic returned `needsRetry: true` in unit tests. Wrapping into `@composeRetryDecisionFromSession(@output) → @composeRetryDecision(...)` made the guard work. Future implementations should use the wrapper-exe pattern.
2. **`=> resume "hint"` requires a `with { tools: ... }` clause.** Without it, the guard parses but doesn't fire at runtime. Even compose, which exposes no tools, needs `with { tools: [] }`.
3. **Direct `@opencode(...)` inside a per-harness wrapper triggers a circular-reference detection** when the wrapper is invoked from inside a planner-tool call (where `@opencode` is already on the stack). Going through `@llmCall("opencode", ...)` instead avoids the cycle. Same is likely true for `@claude` once tested.
4. **Validators are usable without the compose integration.** The module + tests are general-purpose; consumers can call `@runOutputValidators(list, output, context)` from anywhere in rig or bench. The integration is the *enforcement* surface; the validators are the *predicate* surface.

### When to revisit the compose integration

- A consumer with a stronger compose model where directive hints actually change output substance (Sonnet, Haiku-4-5).
- Extract or derive workers where validator-driven retry adds measurable signal (e.g. `@derive_must_reference_inputs` catching hallucinations).
- Suite-specific validator needs that the generic set doesn't cover.

When that happens, follow the design above. The lessons-learned section addresses the three rough edges encountered.
