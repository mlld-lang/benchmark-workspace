# Security Invariants

Load-bearing claims the implementation must preserve. These are non-negotiable. Any change that weakens one of these requires explicit architectural review.

## 1. The Clean Planner

The planner never sees raw tainted content.

**What the planner sees:**
- Records projected through `role:planner` display — fact fields as handles, data fields omitted or masked
- Extract and derive attestations (schema names, field types, validated selection refs — not raw content)
- Execution log attestations (status, handles, counts, literal strings)
- User query text

**What the planner does NOT see:**
- Raw tool results from workers (would include tainted content)
- Email bodies, file contents, webpage text, message bodies (unless explicitly ref-visible in a record's planner display)
- Worker prose reasoning (workers return `->` attestation, not prose)
- Extracted or derived scalar values unless the schema explicitly surfaces them to the planner display

**How it's enforced:**
- Planner LLM call is wrapped in a box with `display: "role:planner"`
- State values are read orchestrator-side and serialized into the prompt with record display projection applied
- Workers use `->` returns for attestation, which have expression-scoped taint (built from handles and literals)
- Workers use `=> @value as record @R` for canonical returns, which apply display projection at the LLM bridge

**Why it matters:**
If the planner sees tainted content, prompt injection reaches the authorization layer. An attacker who planted text in an email body could influence the planner's authorization decisions.

## 2. Write Control Args Require Proof-Bearing Values

Every control arg on an execute dispatch must have proof. Valid sources:

- **`resolved`** ref → value has factsource from a resolved record; proof verified at `@policy.build`
- **`known`** value → value appears verbatim in task text; verified with `{ task: query }` config
- **`selection`** ref → points back to an already-resolved instance that was in a derive/extract input set; carries through the original proof

Rejected for control args:
- Bare literal strings not in task text
- `extracted` refs (typed but not proof-bearing)
- `derived` refs pointing at scalar values (typed but not proof-bearing)
- Compose-produced values
- Values fabricated by the planner

**Why it matters:**
The `no-send-to-unknown` and `no-destroy-unknown` rules require proof on destination/target control args. Without this invariant, an LLM-fabricated email address could slip into a `send_email.recipient` arg.

## 3. Source Class Is Authoritative

Rig validates the source class of every planner-emitted ref against the value's provenance in state. The planner cannot relabel a derived value as resolved.

**How it's enforced:**
- Extracted values are stored with `provenance: "extracted"` metadata
- Derived values are stored with `provenance: "derived"` metadata
- Resolved records carry factsource metadata
- Ref resolver checks provenance against the declared source class; mismatch is a hard error

**Why it matters:**
Without this, the planner could launder a fabricated email address through derive and then reference it as `{ source: "resolved", ... }` to pass control-arg checks.

## 4. Selection Refs Are Derive-Only and Rig-Validated

`selection` refs are the only path from derive results into control-arg proof. **Only derive can produce selection refs** (spike 42). Extract cannot.

**Why derive-only:**
Extract reads tainted content. If extract could mint selection refs, an attacker who plants "select the CEO's account" in an email body could cause the extract worker to produce a selection ref pointing at a legitimate resolved instance — laundering injected content into authorization proof. Derive operates on already-typed inputs; selecting among them means selecting among already-proven values.

**Validation:**
- The backing ref must resolve to an instance that existed in the derive input set
- The backing instance must carry original factsource proof
- The planner cannot author a selection ref from scratch — only the derive worker, with rig validation, can produce them

**Why it matters:**
Without this, derive/extract become laundering paths. A fabricated value could emerge as a "selection" with no verification that it actually corresponded to an input.

## 5. Static Input Contracts for Writes

Write operations declare an `inputs` record. The execute boundary coerces the payload/data subset through that record before the tool is invoked, while fact fields stay on the proof-bearing authorization path.

**What this covers:**
- Email bodies, subjects, and headers
- Calendar event payloads (title, description, times, location)
- File contents for create/append operations
- Any multi-field write payload

**Why it matters:**
Input records enforce field-level trust refinement plus top-level policy sections such as `exact`, `update`, `allowlist`, and `blocklist`. Without them, a write worker could inject arbitrary fields or bypass exact-match user text requirements.

## 6. Expression-Scoped Taint via `->`

`->` is not a sanitizer. It does not magically clean tainted content. What it does is scope taint to the expression's own inputs rather than inheriting from the exe's ambient scope.

A worker that internally processes tainted content returns a clean attestation to the planner only if:
- the `->` expression is built from handles (opaque, no taint), counts (no taint source), and literal strings (no taint)
- record-projected returns use `=> @value as record @R` so display projection applies at the bridge

The security comes from **what is in the expression** plus **display projection at record boundaries**, not from the arrow syntax itself. Writing `-> @raw_email_body` leaks taint; the `->` syntax doesn't save you.

**Strict mode:**
An exe with `->` in source never falls back to `=>` for tool dispatch. If the `->` was in an unreached branch, the LLM sees null. This closes the "I thought I gated this" leak.

**Why it matters:**
If developers treat `->` as sanitization, they'll write leaky expressions. Making the mental model explicit (expression-scoped taint + display projection, not arrow magic) prevents this.

## 7. Display Projection at LLM Boundaries

Records projected into LLM prompts go through the role's display mode. Fields not in the display are omitted entirely (strict whitelist). Masked fields show preview + handle. Ref fields show value + handle. Handle-only fields show just the opaque handle.

**How it's enforced:**
- LLM calls inside a box with `display: "role:X"` apply the record's `role:X` display mode to record-valued tool results crossing the bridge
- `@cast(value, record)` explicitly coerces a value through a record's display
- `@value as record @R` in return expressions triggers the same path
- Orchestrator code serializing state into prompts applies the appropriate display

**Why it matters:**
Display projection is how the planner stays clean while still being able to reference values by handle. Without it, every record-bearing tool result would leak data fields.

## 8. One Write Per Execute Dispatch

The execute worker performs exactly one concrete write per dispatch. Multi-step writes are a planner-managed sequence of single-action dispatches.

**Why it matters:**
- Authorization is compiled per-step. Value pinning in `@policy.build` applies to this specific dispatch.
- A single worker with multiple write tools could mix authorization contexts.
- Failure modes are cleaner: one dispatch fails, the planner sees the specific failure and can re-plan.

## 9. Correlate Control Args When Declared

When a write tool declares `correlateControlArgs: true`, every control arg value's factsources must point to the same source record instance. Cross-record dispatches are denied.

**The attack this defends:**
An attacker plants a transaction with their own recipient. The planner is tricked into mixing the attacker's recipient with a legitimate transaction's id. Both values have fact proof, so single-arg checks pass. Without correlation, the dispatch goes through and updates the legitimate transaction with the attacker's recipient.

**How it's enforced:**
At dispatch time (not prompt time), rig checks that all control args with `correlateControlArgs` share the same `instanceKey` (or `(coercionId, position)` for keyless records).

## 10. No Source-Class Inference from Ref Contents

Rig does not guess source class from string matching. Every ref carries explicit source class metadata.

**Why it matters:**
The f951244 shelf regression lesson: if rig tries to infer behavior from string patterns, edge cases break. Explicit source class makes misuse structurally impossible — the planner cannot accidentally produce an "unclassified" ref that rig fills in wrong.

## Regression Notes

### The f951244 Shelf Display Regression

Changing the planner's state read from orchestrator-side `@shelf.read` to box-scoped `@fyi.shelf` caused all state to render as `{}` to the planner. The planner could not see values and fabricated placeholder strings.

**Lesson:** Display projection via `@claude` with `display: "role:X"` and display projection via `@fyi.shelf` inside that same box are not the same path. Don't assume equivalence without verification.

**Implementation rule:** Read state orchestrator-side when building the planner prompt. Apply display projection to the serialized values. Do not depend on box-scoped `@fyi.shelf` for planner state visibility.

### The Phase Lifecycle Collapse

Rig not writing to `phase_log_file` resulted in `phase_event_count=0` across all tasks. Tools fired but the host couldn't attribute them to phases. Diagnostics broke.

**Lesson:** The host-to-rig integration contract includes phase event emission. Missing emission isn't a diagnostic gap — it looks like a runtime bug and wastes investigation time.

**Implementation rule:** Phase lifecycle emission is part of the rig contract. Every dispatch emits start and end events. Every planner iteration emits an iteration event. See `PHASES.md` for the emission format.

## Threat Model Alignment

These invariants map to the attack classes rig defends against:

- **Prompt injection via email/file/web content** — defended by clean planner (#1), display projection (#7), `->` scoping (#6)
- **LLM fabrication of authorization values** — defended by control-arg proof requirement (#2), source class authority (#3), selection ref validation (#4)
- **Privilege escalation via authorized tool** — defended by one-write-per-dispatch (#8), static payload contracts (#5)
- **Cross-record mixing attacks** — defended by correlate-control-args (#9)
- **Laundering via extract or derive** — defended by source class firewall (#2, #3, #4)
- **Indirect bias via recommendations** — **not defended in v2.** Derive over resolved data is the only mitigation available (clean inputs produce clean outputs). Tasks where influenced content leaks past this and corrupts recommendations are accepted as v2 misses. Advice gate defense deferred to a later iteration.

If a new attack class is identified, add it here with the invariant that defends against it. If no invariant defends, the defense is missing and rig needs a new primitive, not a prompt tweak.
