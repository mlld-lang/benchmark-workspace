---
name: migrate
description: Start a session working on the v2.x structured-labels + policy-redesign migration. Loads the migration plan, sec-*.md threat models, SEC-HOWTO authoring guide, and architectural specs. Emphasizes three-tier separation (mlld / rig / bench) and spike-then-test discipline. Use at the start of every migration session (NOT general rig/bench work — for that use /rig).
user-invocable: true
---

# Start a v2.x migration session

Use this skill when working on the structured-labels + policy-redesign migration described in `MIGRATION-PLAN.md` and tracked in `MIGRATION-TASKS.md`. This is a coordinated cutover that re-authors records.mld + BasePolicy across all four AgentDojo suites against the new mlld value-metadata model (`mx.trust` / `mx.influenced` / `mx.labels` / `mx.factsources` channels) and the new policy schema (importable `@mlld/policy/*` fragments, retired named built-ins).

**If you're doing general rig/bench work, use `/rig` instead.** This skill is narrower — it's for agents executing the migration with the discipline that distinguishes a clean cutover from a series of patches.

## What this migration is and isn't

It IS:
- A coherent v2.x cutover. One coordinated change to records, policy, and value-metadata handling. Migration agents work toward one consistent target state.
- An opportunity to retire ~14 patch-shaped commits whose bug classes are now impossible by construction.
- The bridge that turns sec-*.md threat-model claims into regression-locked enforcement.

It IS NOT:
- A whack-a-mole bug fix campaign. Each spike-then-test cycle resolves to either a structural fix (records / policy / mlld) or a documented `[!]` gap with a ticket — never a workaround that defers structure.
- A prompt-tuning effort. Defense nodes in sec-*.md trees must be structural; prompt discipline does not satisfy any mark at any level.
- A re-think of the threat model. sec-*.md docs ARE the threat model. If you find a gap not captured in sec-*.md, update sec-*.md first, then design records/policy.

## What to do — required reading at session start

You MUST read these files before touching any code. The migration is a coordinated cutover; the time it takes depends entirely on internalizing the target state before drafting.

### Step 0: Run `mlld qs` first

```bash
mlld qs
```

You will be writing mlld code throughout this migration — records, policy fragments, probes, tests. The quickstart covers syntax, key directives, the StructuredValue boundary, and common pitfalls. Don't skip this. Migration agents who skip `mlld qs` and try to write mlld from training data routinely produce code that fails parse or behaves unexpectedly at runtime.

### Step 1: Current mlld security model

Read: `mlld-security-fundamentals.md`

This is the canonical narrative for the security primitives that survive the migration: labels, policies, guards, records, refine, shelves, sessions, factsources. The v2.x spec evolves the value-metadata representation, but the underlying primitives (records-as-policy, fact:* labels, factsources for cross-phase identity, refine actions, shelf storage, display projection) are the same primitives — they just live in cleaner channels.

Specifically you need to internalize:
- **§1 Labels** — current flat-namespace model. The v2.x spec separates trust/influenced/labels/factsources into distinct channels; reading the current model first makes the delta visible.
- **§4 Records** — facts vs data, identity (`type: handle` vs `type: string, kind:`), input vs output records, dispatch validation order, the `=> record` coercion contract. These primitives carry through the migration unchanged.
- **§4.2 Trust refinement on `=> record`** — the load-bearing semantic that §2.4 + §2.5 of the spec generalize and make durable.
- **§6 Shelf primitives** — wildcard slots, scope-local lifetime, byKey/byAddress lookups, merge semantics. The v2.x spec §2.6 changes shelf I/O composition; reading the current shelf semantics first makes that delta clear.
- **§7 Sessions** — per-call session containers; how they compose with shelves.

Read this BEFORE the v2.x specs in Step 2. The specs make sense in terms of "here's what's changing relative to the current model"; without the current model loaded, the specs read as abstract.

### Step 2: The two specs (the architectural target)

Read both in the mlld repo:

- `~/mlld/mlld/spec-label-structure.md` — the value-metadata redesign. §1 (channels) + §2 (trust derivation including the §2.4 LLM-pass invariants and §2.5 content-derived aggregation) are load-bearing. §2.6 (shelf I/O composition) is the rule that eliminates m-aecd's bug class.
- `~/mlld/mlld/spec-policy-box-urls-records-design-updates.md` — the policy schema redesign. Part 1 (top-level shape), Part 2 (labels block detail), Part 5 (importable `@mlld/policy/*` fragments replacing named built-ins). The schema is JSON-shaped except for the deliberate `label+otherlabel:` set-containment exception.

Both are implemented on the `policy-redesign` branch of mlld. Take them as authoritative; the migration adopts them, not the other way around.

### Step 3: The migration plan

Read: `MIGRATION-PLAN.md`

Phases 0-8 + rollback. Pay attention to:
- **Phase 7 whack-a-mole reconciliation** — most of the ~14 listed commits are no-op by construction; verify each with a probe before assuming.
- **Required target architecture** — the `mx.trust` / `mx.influenced` / `mx.labels` / `mx.factsources` channel separation, with code-routing labels routed to `mx.sources` (except `src:file`).
- **Exit criteria per phase** — the gates that block moving to the next phase.

### Step 4: The threat model + authoring guide

Read in order:

- `SEC-HOWTO.md` — the authoring guide for sec-*.md per-suite security/threat-model docs. The five-mark scheme (`[ ]` / `[!]` / `[?]` / `[-]` / `[T]`), the maturity ladder, the ticket-anchoring discipline, the citation-hygiene rules. Load-bearing for how marks transition during migration.
- `sec-banking.md` — the v1 draft for the banking suite. Read all of §5 (attack surface matrix) and §8 (attack-class trees with marks). The §5 matrix is the field-first defense map; the §8 trees are the attack-first AND/OR structures.
- `sec-{slack,workspace,travel}.md` — write these BEFORE redrafting records for their suites. If they don't exist yet, sec-doc authoring is your first task per `MIGRATION-TASKS.md`.

### Step 5: Current state

- `MIGRATION-TASKS.md` — the temporary task tracker. Reflects current migration progress. Read it; don't duplicate task tracking into TodoWrite. Update it as work proceeds.
- `STATUS.md` — canonical per-task bench status; the acceptance gate at the end (≥78/97 utility, 0 ASR) is what migration ships against.
- `HANDOFF.md` — most recent session breadcrumb. Tells you what just happened and what's next.

### Step 6: The three-tier separation discipline

Read `rig/ARCHITECTURE.md`. Pay attention to the "Separation of Concerns" section. The migration is the moment three tiers' responsibilities are most likely to bleed; the rest of this skill makes that explicit.

## Three-tier separation — the load-bearing discipline

Every change you consider during migration has to land in exactly one tier. Confusing tiers is the most common migration regression pattern. Internalize the boundaries before drafting:

### mlld (runtime + primitives)

`~/mlld/mlld/`. The interpreter, the value-metadata channels, the coerce-record runtime, the shelf primitives, the policy enforcer, the LLM bridge. Authoritative on:

- How `mx.trust` / `mx.influenced` / `mx.labels` / `mx.factsources` channels propagate.
- How `=> record` coercion + `as record` coercion handle trust refinement (§4.2 of spec-label-structure).
- How shelf I/O composes (§2.6).
- How `@policy.build` resolves rule definitions and fragments.

**What goes in mlld**: anything about value-metadata mechanics, descriptor channels, runtime label propagation, coercion semantics, shelf storage, policy-rule firing. If a bench probe surfaces a wrong descriptor on a value, the fix is mlld-side. File in `~/mlld/mlld/.tickets/` with a probe in `clean/tmp/<probe-dir>/`.

**What does NOT go in mlld**: suite-specific records, BasePolicy stanzas for a particular suite, prompt education, attack-tree authoring. mlld is generic; it doesn't know about hotels or transactions.

### rig (framework + agent plumbing)

`clean/rig/`. The planner session, worker dispatchers (resolve / extract / derive / execute / compose / advice / blocked), policy synthesis from tool catalog, display projection wrappers, intent compilation, lifecycle event emission, generic prompts. Authoritative on:

- Phase model (resolve → extract/derive → execute → compose).
- Source-class vocabulary (`resolved` / `known` / `selection` / `extracted` / `derived` / `allow`).
- BasePolicy synthesis from tool catalog and record declarations.
- Display projection at LLM boundaries (`role:planner` / `role:worker` / `role:advice`).
- Generic phase prompts (`rig/prompts/planner.att`, `derive.att`, etc.).

**What goes in rig**: anything domain-agnostic that any suite could use. Worker dispatch contracts, planner discipline rules, generic prompt education, error envelope shape, lifecycle events.

**What does NOT go in rig**: any specific suite's records, tools, or addendums. No mention of `iban`, `hotel`, `channel_id`, `transaction`, `email`. The "would this rule be true in a completely different domain?" test from CLAUDE.md applies — if no, it's bench-side.

### bench (the actual benchmark integration)

`clean/bench/`. Suite-specific records, tools, optional bridges, optional classifiers, suite addendums, agent entrypoints. Authoritative on:

- The four AgentDojo suite domain models (workspace / banking / slack / travel).
- Per-suite records.mld + tools.mld + agents/<suite>.mld.
- Per-suite prompt addendums (`bench/domains/<suite>/prompts/`).
- sec-*.md threat models per suite.

**What goes in bench**: anything specific to one of the four suites. The records that express the suite's threat model. The tools that the suite ships. The prompts that teach the planner about the suite's domain workflow patterns.

**What does NOT go in bench**: generic worker dispatch, generic policy synthesis, generic prompt rules. Those are rig. Generic value-metadata mechanics are mlld.

### Tier-boundary checklist

When considering a change, ask in order:

1. Is this about how a value carries trust state through coerce / shelf / dispatch / projection? → mlld.
2. Is this about how a phase worker dispatches, what shape an envelope carries, or how the planner reads errors? → rig.
3. Is this about a specific suite's threat model, records declarations, tool catalog, or domain workflow? → bench.

If a change feels like it has to live in two tiers, you've probably found a missing primitive in mlld. File a ticket in mlld with the probe; don't bridge tiers in bench.

## Spike-then-test — the load-bearing rhythm

This is how marks in sec-*.md transition from `[?]` (declared, unverified) to `[T]` (test-locked). Without this rhythm, marks stay `[?]` forever and the doc loses trust.

### The pattern

1. **Spike**: write a probe in `clean/tmp/<context>/<defense>.mld` that exercises one specific defense claim. The probe must be:
   - Zero-LLM if possible (deterministic, runs in seconds, costs $0).
   - Decisive (binary outcome: defense fires or doesn't fire on this input).
   - Self-contained (no external state, no network, no AgentDojo MCP unless the defense specifically exercises MCP coercion).
2. **Run** the probe. Read the labels / errors / outputs against the sec-*.md claim.
3. **Decide**:
   - Defense fires as claimed → mark stays `[-]` (with probe citation) or promotes to `[T]` if you also write the test in step 4.
   - Defense doesn't fire → gap found. File a ticket. Mark `[!]` with ticket id inline. If gap is mlld-side, file in `~/mlld/mlld/.tickets/` with the probe attached.
   - Defense can't be exercised zero-LLM → schedule for tier-2 scripted-LLM test instead; mark stays `[?]` until tier-2 exists.
4. **Test (when promoting to `[T]`)**: promote the spike to a regression test:
   - Tier-1: extend `tests/index.mld` (and its suite imports). Zero-LLM, runs ~10s, on every PR.
   - Tier-2: extend `tests/run-scripted.py`. Scripted-LLM (mock harness), runs ~30s, on every PR.
   - Tier-3 (live-LLM sweeps) does NOT count for `[T]`. Sweeps are stochastic and don't run on PR.
5. **Cite** in sec-*.md: `[T] tests/rig/<file>.mld#<case-name>` or `[-] tmp/<probe>.mld + commit <sha>`. Updates to the mark replace the citation.

### When to spike

Three load-bearing moments:

**(A) Audit phase**, per sec-*.md row that claims a defense:
- Spike the claim → confirm fires or find gap.
- This is mechanical: every `[-]` claim in the doc must have a passing probe. Probes that fail surface gaps you don't see by reading code.

**(B) Records / policy redraft**, per suite:
- Before committing new records.mld, spike the new declaration → confirm labels match sec-*.md claim.
- Before committing new BasePolicy fragment, spike the rule → confirm fires on attack input AND doesn't fire on legitimate input.
- If spike doesn't produce the claimed shape post-redraft, iterate. Don't commit a records change that contradicts its sec-doc claim.

**(C) Stop-on-mlld-bug**, any phase:
- If a probe shows mlld is the gap (defense should fire per sec-doc, doesn't per probe), the probe IS the bug repro.
- File `~/mlld/mlld/.tickets/m-XXXX` with the probe path in the body.
- Wait for mlld-dev fix. Re-run probe. Add bench-side regression test that locks the invariant.
- Do NOT workaround unless the workaround is small AND doesn't move bench schemas off the v2.x target shape. Workarounds compound; the next migration has to revert them.

### Spike examples from prior session (the pattern to imitate)

- `tmp/probe-trusted-field/probe-shelf-roundtrip.mld` — exercised the claim "shelf preserves cleared untrusted on `data.trusted` fields." Probe showed `[]` pre-shelf, `["untrusted"]` post-shelf. Definitively pinned m-aecd as a shelf-roundtrip bug, not a coerce-time bug.
- `tmp/probe-execute-mask/probe.mld` — exercised the claim "mlld policy errors carry `code`/`field`/`hint`/`message`." Probe showed rich envelope; confirmed rig was the masking layer (commit `4d2b0c0` extracted detail from envelope into planner-facing log entries).
- `tmp/probe-trusted-field/probe-derive-via-parse.mld` — exercised the claim "§4.2 clears untrusted on `data.trusted` payload when coerced." Initial run showed it didn't fire on upstream-tainted values. Drove m-9f33's §4.2-(B) fix.

In every case the probe was the design artifact: it pinned the question, drove the decision, and (when the bug surfaced) served as the repro the upstream agent used to act fast. Probe quality is migration speed.

## Per-suite migration discipline

Suite order: **banking → slack → workspace → travel**. Rationale:

1. **Banking first** — smallest delta (sec-doc exists, records need redraft). Validates the migration shape against the most-defended suite. If banking goes clean, the pattern generalizes.
2. **Slack second** — simplest new sec-doc (single load-bearing primitive: URL promotion). Tests the SEC-HOWTO template against a new suite without compounding complexity.
3. **Workspace third** — SHOULD-FAIL framing as architectural decision (typed-instruction-channel refusal). The §6 challenge is treating SHOULD-FAIL as a threat-relevant fact, not a status mirror.
4. **Travel last** — advice gate is qualitatively different (policy + projection, not value-grounding). Most architecturally complex. Save for after the template-fluent patterns are settled.

### Per-suite exit gate

A suite isn't done until ALL of these hold:

- sec-*.md marks: no orphan `[?]`. Every mark is `[-]` (with probe + commit-sha citation), `[T]` (with test file + case-name citation), or `[!]` (with linked ticket id).
- Zero-LLM gate green (266/0/4 or wherever it lands post-test-additions).
- Worker LLM gate green (24/24 or current target).
- Per-suite attack canary: 0 ASR across applicable attack variants. Use `scripts/bench-attacks.sh single direct <suite>` and equivalent for the suite's primary attack class.
- Local utility probe of canonical previously-failing tasks: verify expected recoveries land.

Don't start the next suite until the current suite's gate passes. Carrying partial defenses across suites compounds; the regression footprint expands suite-by-suite.

## Stop-conditions

Stop immediately and surface to the user if:

- A probe consistently shows mlld misbehaves against the spec. File `~/mlld/mlld/.tickets/m-XXXX`. Wait.
- A sec-*.md claim turns out to be wrong (the threat model evolved). Update sec-*.md first, then decide records/policy.
- The acceptance gate (≥78/97 utility, 0 ASR) drifts in the wrong direction during migration. Probe the regression, ticket the root cause, stop the migration there.

Don't stop for:

- A `[?]` mark you can't promote to `[T]` in this session. Mark stays `[?]` with a ticket; migration continues.
- A small workaround that doesn't violate the v2.x target shape. Land it, file a follow-up ticket.

## Final discipline (negative rules)

These are the discipline failures the migration is most exposed to. None of them is acceptable:

- **No prompt-as-defense.** A defense node in a sec-*.md tree must be a structural enforcement (record primitive, display projection, policy rule, tool metadata, phase-scoped restriction). Adding a sentence to a prompt and calling it a defense fails the SEC-HOWTO discipline.
- **No eval-shaping.** Don't read AgentDojo `utility()` / `security()` checker bodies. Don't shape records around what you suspect the checker tests. CLAUDE.md Cardinal Rule A is enforced.
- **No `[-]` marks without citations.** Every `[-]` needs commit SHA or sweep run id. Strip to `[?]` if you can't honestly cite.
- **No `[T]` marks against tier-3 sweeps.** Tier-3 doesn't run on PR; it can't lock a defense. Tier-1 (`tests/index.mld`) or tier-2 (`tests/run-scripted.py`) only.
- **No tier-bleeding fixes.** A bench-side workaround for a mlld bug is a tier-blend. File the mlld ticket; wait.
- **No partial-state commits.** Zero-LLM gate stays green at every commit. "We'll fix the test later" creates a re-entrant migration tax.
- **No re-introducing retired patterns.** `defaults.unlabeled: "untrusted"` retires. Named built-in rules retire. Recursive descriptor extraction is impossible by construction. Anything that smells like the old aggregation pattern should be re-thought against §2.5.

## Validation gates

Run before every commit during migration:

```bash
mlld tests/index.mld --no-checkpoint              # zero-LLM gate
mlld tests/live/workers/run.mld --no-checkpoint   # worker LLM gate (only when prompts change)
mlld tests/rig/phase-error-envelope.mld --no-checkpoint  # masking-fidelity, must stay green
```

Run per-suite at the suite gate:

```bash
uv run --project bench python3 src/run.py -s <suite> -d defended -t <canonical-tasks>
scripts/bench-attacks.sh single direct <suite>
scripts/bench-attacks.sh single important_instructions <suite>
```

Final ship gate:

```bash
scripts/bench.sh                                  # full 4-suite benign sweep
scripts/bench-attacks.sh                          # full 6x5 attack matrix (when migration complete)
```

## Useful pointers

- `SEC-HOWTO.md` — template authoring guide for sec-*.md
- `sec-{banking,slack,workspace,travel}.md` — per-suite threat models (banking exists; others to be written)
- `sec-cross-domain.md` — cross-suite attack vectors (deferred items)
- `MIGRATION-PLAN.md` — phase plan (0-8)
- `MIGRATION-TASKS.md` — temporary tracker for this migration's work surface
- `STATUS.md` — bench results + canonical per-task classification
- `HANDOFF.md` — session-to-session breadcrumb
- `~/mlld/mlld/spec-label-structure.md` — value-metadata channel design
- `~/mlld/mlld/spec-policy-box-urls-records-design-updates.md` — policy schema
- `rig/ARCHITECTURE.md` — three-tier separation specifics
- `rig/SECURITY.md` — 10 numbered framework invariants
- `mlld-security-fundamentals.md` — labels, policies, guards, records, refine, shelves
- `.tickets/review/` — tickets pending individual review against the new architecture

When in doubt: probe, don't guess. The probe is faster than the discussion.
