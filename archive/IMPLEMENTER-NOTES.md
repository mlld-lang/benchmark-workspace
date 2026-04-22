# Implementer Notes — Spec Hygiene Pass (Post-Questions)

Summary of changes applied after the implementer's 8-question review and follow-up hygiene feedback. All items address spec gaps surfaced by those questions; no architectural redesign.

## 1. `allow` narrowing

**Location:** `rig/INTERFACE.md`, `rig/PHASES.md`, `PLAN.md`

- Rig v2's planner-facing contract narrows `allow` to tools with no `controlArgs`.
- The lower-level `@policy.build` primitive (documented in `benchmarks/labels-policies-guards.md`) accepts broader semantics — that remains true at the policy-builder level but is not exposed to the planner.
- Suites needing unconditional authorization on a `controlArgs` tool can use `overrides.policy` with the flat form — explicit app-level escape, not planner intent.
- Rig v2 rejects a planner decision that emits `allow` on a tool with `controlArgs`.

## 2. Canonical ref grammar

**Location:** `rig/INTERFACE.md`

All non-compose phase args use **structured ref objects only**. No path strings in args.

Ref forms:

```
{ source: "resolved", record, handle, field }      // specific value (factsource-backed)
{ source: "resolved", record }                     // whole-family ref (for derive/compose inputs)
{ source: "extracted", name, field }               // extract result field
{ source: "extracted", name }                      // whole extract result
{ source: "derived", name, field }                 // derive result field
{ source: "derived", name }                        // whole derive result
{ source: "known", value }                         // user task-text literal
{ source: "selection", backing: { record, handle } } // derive-produced, rig-validated
{ source: "allow" }                                // tool-level, no controlArgs only
```

Compose `sources` additionally accepts string namespace sugar: `"resolved.*"`, `"derived.*"`, `"extracted.*"`, `"execution_log"`. **Compose-only, non-canonical.** Cannot appear in any other phase. Prefer structured refs in compose too.

## 3. `lowerSelectionRef` utility

**Location:** `rig/PHASES.md`

Selection ref lowering is implemented as a single rig utility, not phase-specific logic.

When any arg resolver encounters `{ source: "selection", backing: {...} }`, it calls `lowerSelectionRef(ref)`, which:
1. Validates the backing ref points to an instance currently in state with original proof
2. Returns the equivalent resolved ref
3. The caller's normal resolved-ref path runs on the lowered ref

Selection refs work uniformly across resolve tool args, extract source refs, derive source refs, execute control/payload args, and compose sources.

Failure mode: if lowering fails (backing instance not in state, proof lost), the utility returns an error and the phase dispatch fails cleanly.

## 4. `phase_state_file` schema and semantics

**Location:** `rig/PHASES.md`, `bench/ARCHITECTURE.md`

Both host integration files are part of the contract:
- `phase_log_file` — append-only NDJSON event stream (`planner_iteration`, `phase_start`, `phase_end`)
- `phase_state_file` — live current-phase pointer, **overwritten** (not appended) on each transition

`phase_state_file` schema:
```json
{
  "phase": "resolve",
  "phase_id": "uuid-for-this-dispatch",
  "iteration": 3,
  "worker_session_id": "..."
}
```

Write semantics:
- At `phase_start`: overwrite with full object, `worker_session_id: null` until worker returns
- When worker session ID available: overwrite with `worker_session_id` populated
- At `phase_end`: overwrite with sentinel `{ "phase": "between" }`
- At run termination: overwrite with `{ "phase": "between" }` so host never sees stale phase
- Missing or malformed file: host treats as "between"

The "between" sentinel means no phase is active. The host uses this to distinguish mid-phase MCP calls from between-phases calls.

## 5. Synthesized policy shape

**Location:** `rig/INTERFACE.md` (summary + overrides), `rig/PHASES.md` (full algorithm)

In defended mode, `@rig.build` synthesizes policy from the tool catalog. Apps do not ship `policy.mld`.

Synthesis:
```
{
  defaults: {
    rules: [
      "no-secret-exfil", "no-sensitive-exfil",
      "no-untrusted-destructive", "no-untrusted-privileged",
      "no-send-to-unknown", "no-destroy-unknown",
      "untrusted-llms-get-influenced",
      "no-novel-urls",              // when any tool has exfil:fetch risk
      "no-unknown-extraction-sources"
    ],
    unlabeled: "untrusted"
  },
  operations: {
    // Reverse-mapping from governed risk labels on the tool entry
    "exfil:send":           [tool keys with "exfil:send" label],
    "destructive:targeted": [...],
    destructive:            [tool keys with any destructive* label],
    privileged:             [...]
  },
  labels: {
    influenced: { deny: ["destructive", "exfil"] }
  },
  authorizations: {
    deny: [tool keys with can_authorize: false],
    can_authorize: {
      "role:planner": [tool keys with can_authorize != false]
    }
  }
}
```

Override semantics (via `@rig.build` config `overrides.policy`):
- Additive only — suite overrides extend, cannot weaken
- Deny lists union
- Locked rules from synthesized policy are preserved
- No suite override can disable a rig default rule

`no-influenced-advice` is **not** synthesized. Advice phase is out of v2 scope.

## 6. State substrate

**Location:** `rig/PHASES.md`, confirmed in `ARCHITECTURE.md`

Rig is implemented on the existing mlld shelf primitives. Shelf preserves factsources across I/O and has battle-tested proof preservation.

What changes: apps don't author shelf declarations. Rig generates layout internally:
- Each record in the catalog → internal shelf slot typed by that record (collection type)
- Extract and derive results → internal slots keyed by planner-provided name
- Planner box has read scope on the full internal shelf
- Worker boxes get phase-scoped write access

Record-level proof preservation works automatically through shelf I/O.

## 7. Multi-recipient and array-typed args

**Location:** `bench/INTERFACE.md`, `bench/ARCHITECTURE.md`

Tool signature determines the shape. Payload record field type **must match the tool exe signature exactly**.

Example payload record (now corrected in the ARCHITECTURE.md schematic):
```mlld
record @email_payload = {
  facts: [],
  data: [recipients: array, subject: string, body: string, cc: array, bcc: array]
}
```

Dispatch rules:
- Array-typed control args: rig checks proof **per element**. Every element needs its own resolved/known/selection ref.
- Array-typed payload args: `@cast` validates each element against field element type.

Planner usage patterns (task-level, not framework-level):
- Identical message to multiple recipients: single execute with `recipients: ["a", "b"]`
- Personalized per recipient: one execute per recipient with single-element array

## 8. Advice phase explicitly out of v2 scope

**Location:** `rig/ARCHITECTURE.md`, `rig/PHASES.md`, `rig/SECURITY.md`, `bench/ARCHITECTURE.md`, `PLAN.md`

Explicit scope decision:
- No advice phase in v2
- No `@debiasedEval` helper
- No `no-influenced-advice` rule
- Recommendation-class tasks run normal `derive → compose` (derive on resolved data is not influenced)
- Recommendation-hijack attack tasks are accepted misses for v2
- Spike 38 retained as reference for future work

Build plan is now 9 steps (was 10): Step 7 is "first benchmark suite (workspace)," advice step removed.

## 9. Test taxonomy (first-class, not a spike)

**Location:** `PLAN.md` + new `clean/rig/CLAUDE.md`

Three test kinds:

1. **Invariant tests** — `rig/tests/index.mld` (mlld convention for entry point). Zero-LLM deterministic assertions on individual primitives. <1s. Runs on every change. Modeled on v1 spike 34 integration smoke.
2. **Flow tests** — `rig/tests/flows/<phase>.mld`. Stub LLM, per-phase end-to-end. Run at each implementation step.
3. **Benchmark runs** — `bench/...`. Real LLM, real evaluation. Run at Step 7+.

Minimum invariant coverage required:
- `@policy.build` accepts synthesized policy
- Tool collection round-trips through runtime parameter binding
- `.mx.params`, `.mx.controlArgs`, `.mx.factsources` accessible on exes
- Cross-module exe `.mx.labels` round-trip
- `@toolDocs` renders control-arg annotations correctly
- Thin-arrow strict mode doesn't leak tool-slot value
- Selection ref lowering returns expected resolved ref
- Provenance firewall: `{ source: "derived", ... }` in control-arg position rejected at compile
- `allow` on a tool with controlArgs rejected at planner intent validation
- Source class mismatch: extracted value referenced as `resolved` is rejected
- Per-element proof check: array control arg with one missing element is rejected

CLAUDE.md in `clean/rig/` carries forward the v1 discipline: "first action: run the invariant tests" — scoped to v2 as `rig/tests/index.mld`.

## 10. Planner session explicitly out of scope

**Location:** `PLAN.md` (Deferred From v2 Scope)

Persistent planner context is the supported mechanism. Session corruption terminates the run cleanly. No mid-run recovery, no reconstruction machinery. State richness is verified by benchmark success, not by a corruption-recovery design requirement.

If session management becomes a real issue in production, solve it then with evidence.

## 11. Timeshifting (added by user)

**Location:** `bench/ARCHITECTURE.md`, `PLAN.md`

Host-level concern. V2 bench host must preserve v1's date-shift behavior (`date_shift.py`, `get_shifted_suite(...)`) so AgentDojo suites load relative to the current day rather than the original fixture reference date. Not a rig concern, not an agent concern. Required for benchmark parity with prior runs.

## Doc drift fix (post-review)

`bench/ARCHITECTURE.md` schematic for `@email_payload` was using scalar types; now corrected to match `bench/INTERFACE.md` (recipients, cc, bcc as arrays). Internal consistency restored.

---

All items above are in the specs. No conversational clarification required. Implementation can proceed against:
- `~/mlld/clean/rig/ARCHITECTURE.md`, `INTERFACE.md`, `PHASES.md`, `SECURITY.md`, `EXAMPLE.mld`, `CLAUDE.md`
- `~/mlld/clean/bench/ARCHITECTURE.md`, `INTERFACE.md`
- `~/mlld/clean/PLAN.md`, `SPIKES.md`
