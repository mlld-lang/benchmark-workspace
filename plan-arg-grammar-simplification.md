# Plan: Arg Grammar Simplification (mint_user_literal + role-aware compilation)

Status: Draft. Owner: migrator-10 thread (2026-05-15). Supersedes: the unrevised mint integration work in `rig/mint.mld` + `rig/orchestration.mld` + `rig/workers/resolve.mld` + `rig/tooling.mld` (see §"What reverts" below).

## Why

Mid-migration discovery: the current planner-emitted value/ref grammar is over-complex relative to what the framework actually needs for security. Specifically:

- 9 source-class ref shapes (`{source: "known", value: ...}`, `{source: "resolved", ...}`, etc.). The system still needs multiple ref kinds — literals, resolved/state refs, selection refs, extracted/derived payload refs, minted user-literal refs — but the planner is forced to wrap *every* arg in a source-class envelope even when no firewall check fires (payload fields, read/filter args). That wrapping is ceremony, not structural defense.
- Payload fields (`data.untrusted: [body, subject, ...]`) require source-class wrapping that the firewall never reads — pure grammar ceremony.
- Read tool args (`query`, `city`, `date`) are filter parameters but treated identically to write tool authority args (`recipients`, `file_id`) — different threat models, same wrapping.
- The `known` source class is already retired in mlld (m-5686 gates its formal removal on rig migration); it persists in rig today as a substring check + label name with no other structural backing.
- User-task literals destined for write-authority control args are the load-bearing case where structural verification matters. Today they go through the same `{source: "known", value: ...}` shape that read filter args use, despite needing fundamentally stronger guarantees.

Result: planner emissions are noisy, repetitive, and the LLM frequently confuses similar-looking source-class shapes. The records-as-policy migration target (records own the contract) is the right opportunity to consolidate.

## Architectural target

**Keep phases. Simplify values. Make payloads ordinary JSON. Make proof-bearing authority values explicit handles. Use `mint_user_literal` as the user-task-literal proof tool.**

**Load-bearing invariant**: *Bare values are allowed only where record/tool metadata says proof is not needed. Authority-bearing write fields still require handles/proof. User-task literals get that proof through `mint_user_literal`.*

| Arg role | Determined by | Bare values OK? | Examples |
|---|---|---|---|
| Read/filter | Tool has `read:r` / `resolve:r` label AND input record doesn't mark the arg as proof-requiring | Bare OR structured ref accepted; compiler resolves refs as today, bare values pass through | `search_emails(query: "Sarah")`, `get_hotels(city: "Paris")` |
| Read/filter with explicit task-literal policy | Tool/input record declares the arg as task-literal-required (e.g. URL fetch tools) | Bare values verified against task text via input-policy metadata; structured refs resolved | `get_webpage(url: "<task-text URL>")` (declared via input-record metadata, NOT via planner-emitted source class) |
| Write payload | Tool has `execute:w` AND arg is in input record's `data:` block | Yes | `body: "Hello"`, `subject: "FYI"`, `amount: 100`, `description: "..."` |
| Write authority | Tool has `execute:w` AND arg is in input record's `facts:` block | **No** — requires resolved handle, validated selection ref, or minted user-literal ref | `recipients: <ref>`, `file_id: <ref>`, `event_id: <ref>` |
| Bare write-authority literal | (illegal shape) | **Reject** — error: `bare_literal_in_authority_arg` with hint: "call `mint_user_literal` first" | — |

The categorization combines two signals already in the system:
- Tool phase labels (`read:r` / `resolve:r` / `execute:w`) — already in tool catalog entries.
- Input record field classification (`facts:` vs `data.trusted:` vs `data.untrusted:`) — already in input records.
- Per-arg proof-required metadata on the input record (NEW — replaces planner-emitted `{source: "known"}` as the trigger for task-literal verification of read filter args that need it, e.g. URL fetch).

The framework just doesn't read them together for arg shape decisions today.

## Two-tier separation

This plan lives across **rig** (the framework) and **bench** (per-suite consumers). It does NOT touch mlld; per-field check actions + mintUserValueHandle + label primitives already shipped (m-7d15, m-f4f5, m-31b5, m-5828, m-8e37).

## Critical context for a fresh session

These two decisions are load-bearing and the most likely sources of regression if a fresh session doesn't internalize them. Re-litigating them wastes session time; the user already adjudicated.

**1. `mint_user_literal` is a planner-provider tool (in `@plannerTools`), NOT a suite tool with rigTransform/auto-injection.**

The first draft of mint integration (this session, commit `3c0636d`) routed mint through `rigTransform` + auto-injection into every suite's catalog via `agent.rigInternalTools`. That pattern is **wrong** for this use case — suite tools are only callable via `resolve(...)` / `execute(...)`, which forces the planner into the ugly `resolve({tool: "mint_user_literal", args: {value: {source: "known", value: "..."}}, purpose: "..."})` shape the simplification is meant to eliminate.

The correct pattern: mint is a sibling of `resolve` / `extract` / `derive` / `execute` in `@plannerTools` (defined in `rig/workers/planner.mld` ~line 1177). The planner emits `mint_user_literal({value: "..."})` as a top-level action; the worker runs at planner-provider tier.

Phase D explicitly reverts the rigTransform/auto-injection scaffolding. Don't accidentally re-introduce it.

**2. Option (a) planner-visible mint, NOT option (b) silent auto-mint.**

The user adjudicated this twice in this session:
- "I think the right approach is to give the planner the tool so that if they attempt to mint something that is NOT literally in the user message, they get an error."
- "definitely the convention is to wrap mintUserLiteral so we can validate the proper shape."

A fresh session might be tempted by option (b) — "rig auto-mints when a bare literal hits a fact field; no explicit tool call." This is simpler-looking but wrong: it produces opaque rehearse rejections instead of a structured tool error the planner can read and react to. GPT5.5 also suggested option (b) and was overruled.

If a fresh session sees the simpler-looking shape and is tempted: re-read this section. The structured tool-error path is the point.

## Landmines from prior sessions

Concrete gotchas not in any spec or doc. Each cost real session time when first hit — save the next session from re-discovering.

| Landmine | Symptom | Workaround / correct approach |
|---|---|---|
| `var tools` collection spread (`{ ...A, ...B }`) | `Invalid string length` OOM during eager walk of tool-catalog metadata | Don't merge via spread. Use sibling fields on the agent (e.g. `agent.rigInternalTools` next to `agent.tools`) and check both at lookup time. Or: keep mint as a planner-provider tool entirely (this plan's approach) so the suite tools collection isn't touched at all. |
| Agent shelf field name | Code expecting `@agent.shelf.user_value` fails silently | Field is `@agent.plannerShelf`. Verify before writing. |
| Session-scoped vars not readable from `role:worker` exes | `@planner.query` returns `null` inside a worker dispatcher | Workers don't have planner session in scope. Query must be passed as a parameter. The dispatch path already threads `query` through `dispatchResolve(agent, state, decision, query)` etc. |
| `var session @planner` is module-scope only | Parse error inside an exe body | Session declarations live at module top. Activation happens via `with { session: @planner, seed: {...} }` at the call site, not at exe declaration. |
| Reserved mlld variables | `Cannot create variable '@X': name is already reserved` | Reserved set: `@root`, `@base`, `@now`, `@input`, `@payload`, `@state`, `@debug`, `@keychain`, `@fm`, `@mx`, `@p`. Don't shadow. |
| `data.untrusted` payload fields and source-class | Planner currently has to wrap payload values in `{source: ..., value: ...}` despite no firewall check firing on them | The wrapping is pure grammar ceremony — this plan's whole point is to retire it. Confirmed via `rig/intent.mld:699` (`@role == "control"` gate before source-class checks). |
| Per-field `check:` actions and coerce timing | Field-level `check: [{ on: @fn, do: deny }]` doesn't fire on plain `as record` outside a tool dispatch | Pre-m-8e37 behavior. Now fires at every materialization boundary including plain `as record` (verified via `tmp/probe-mit-primitives/probe-6b-check-always-deny.mld`). If a fresh session sees stale behavior: rebuild mlld. |
| Exe label syntax | `@exe inf:mit @name(...)` — labels go between `exe` and `@name`, comma-separated | Verified working: `exe llm, inf:mit @name(v) = ...`. Single labels: `exe inf:mit @name(v) = ...`. |
| `mlld validate` warnings for `@value` parameter | "Parameter @value can shadow caller variables" | Cosmetic warning, not blocking. Suppress or rename if it bothers reviewers; doesn't affect runtime. |
| Bare string concat in mlld | `show "x" + @y` → parse error in strict mode | Use templates: `` show `x@y` `` |

## Engagement model and quality bar

This is not "ship it fast" work. The user's pattern in the source migrator-10 session:

- Heavy redirects on architectural decisions. Draft → user pushback → revise. Expect this.
- Planner-prompt edits require precise diff for review (`[[worker-prompt-diff-review]]` memory). Phase E.1 is the obvious checkpoint — do NOT just apply.
- Test discipline: zero-LLM gate after EVERY meaningful change, not bundled. Bundled changes that break the gate force long bisection.
- Test fixture updates + compiler refactor are coupled but should land in separate commits with green gate between.
- When in doubt, surface the question. The user prefers being asked to being surprised.
- "Fix mlld friction immediately" ([[fix-mlld-friction-immediately]] memory) — if a probe shows mlld misbehaves, file the upstream ticket; don't design around it.

The user is paying attention to commit hygiene, test-attribution chains, and decision provenance. The decision log section at the bottom is load-bearing — keep it current as decisions land.

## Verifier survival nuance

`@knownInTask` (the substring-against-task-text check at `rig/intent.mld:699`) does NOT go away when source-class `known` is retired. It survives, but is called from a different place:

- **Before**: planner emits `{source: "known", value: "X"}` → `@compileToolArgs` dispatches the `known` source-class branch → calls `@knownInTask`.
- **After**: planner emits bare `"X"` for a `filter-task-verified` or `payload-task-verified` role arg → role-aware compiler calls `@knownInTask` directly on the bare value.

The capability stays; only the planner-facing trigger changes. A fresh session that over-deletes (rips out `knownInTask` along with the source-class branches) will have to put it back when implementing C.2.

Same for `@mintUserValueHandle` — capability-gated mlld builtin, called only via the rig-side wrapper (`@mintUserLiteral` in `rig/mint.mld`). Never agent-callable directly.

## Checklist

### Phase A: Probes and scaffolding

- [x] **Probe 1 — direct minted-handle flow.** Verified at mlld layer (`tmp/probe-phase-a/probe-1-direct-handle.mld`, 2026-05-15): bare minted handle from `@mintUserValueHandle` flows through tool dispatch under a policy with `recipient: ["src:user"]` accept list. **Decision: keep `@user_value`.** Dropping it would require a new ref grammar shape (e.g. `{source: "mint", handle: ...}`) — adds surface area vs reduces it. The mlld layer works either way; using `@user_value` keeps the rig planner-facing ref grammar consistent (`{source: "resolved", record, handle, field}` for all state-pointer refs).

- [x] **Probe 2 — bare-value acceptance through @resolveRefValue.** Verified (`tmp/probe-phase-a/probe-2-bare-value.mld`, 2026-05-15): bare values today return `{ok: false, error: "unsupported_ref_source", source: null}` at `intent.mld:601` (`*` branch of the source-class dispatch). **Exact code path for C.2 change:** add top arm to `@resolveRefValue` cascade at intent.mld:597 — when `@refSource(@ref)` is undefined/null AND the arg's role permits bare values (per role-aware compiler), return `{ok: true, source: null, value: @ref, isBare: true}`. Downstream `@compileScalarRefWithMeta` then dispatches based on `@argMeta.role` instead of `@resolved.source`.

- [x] **Probe 3 — role detection prototype.** Verified (`tmp/probe-phase-a/probe-3-role-detect.mld`, 2026-05-15) — classifier combining tool phase labels (`execute:w` / `resolve:r` / `read:r` / `extract:r`) with input-record field classification (facts / data / exact) correctly returns all 5 roles across fixture tools:

  | Tool / arg | Classified as |
  |---|---|
  | `get_contacts.query` (read tool, filter) | `filter` |
  | `send_email.recipients` (write tool, facts) | `authority` |
  | `send_email.body` (write tool, data.untrusted) | `payload` |
  | `send_email.subject` (write tool, data.untrusted) | `payload` |
  | `update_password.password` (write tool, exact:) | `payload-task-verified` |

  The classifier shape that works:
  ```
  @phase == "read" && @needsTaskVerify => "filter-task-verified"
  @phase == "read" => "filter"
  @phase == "write" && @isExact => "payload-task-verified"
  @phase == "write" && @isFact => "authority"
  @phase == "write" && @isPayload => "payload"
  ```

  `@needsTaskVerify` is the open piece — it should come from per-arg input-record metadata that doesn't exist yet. C.1 needs to either (a) add the metadata field to input records that need URL-fetch-style task-literal grounding, or (b) keep all read-tool args as plain `filter` for v1 and add the verified variant later. **Recommendation for v1**: option (b) — start without the verified-filter variant, add it as a follow-on when a specific use case demands it (e.g., URL fetch tools).

### Phase B: mint_user_literal as a top-level planner tool

- [ ] **B.1 Add `mint_user_literal` to `@plannerTools`** in `rig/workers/planner.mld` alongside resolve/extract/derive/execute/rehearse/compose/blocked/resolve_batch. Sibling exe, not a tool reached via resolve.

- [ ] **B.2 Implement `@mintUserLiteralWorker(input)`** in `rig/workers/planner.mld` (or a new `rig/workers/mint.mld` if file size warrants). Worker:
  - Receives the planner's tool-call args. **Canonical shape**: `mint_user_literal({ value: "alice@example.com" })` driven by `inputs: @mint_user_literal_inputs`. Scalar shorthand (`mint_user_literal("alice@example.com")`) is an ergonomic goal but gated on probe — verify the tool-call mechanism accepts single-string args against a record-shaped input before promising it.
  - Accesses `@planner.query` for the user task text.
  - Calls `@verifyUserLiteral(input.value, @planner.query)`.
  - On success: calls `@mintUserValueHandle(input.value, { refine: ["msg", "0"] })`.
  - If probe 1 result requires shelving: writes `@user_value` record onto the planner's shelf via `@shelf.write(@agent.plannerShelf.user_value, ...)`. **May require active `role:worker` context** (just like resolve/execute dispatchers) — if so, the worker exe carries `role:worker` and a thin direct mint dispatcher replaces today's `rigTransform` arm (D.2).
  - On success: returns `{ ok: true, handle: <handle>, value: input.value }`.
  - On verifier failure: returns `{ ok: false, error: "mint_user_literal_value_not_found", code, hint, message }`.

- [ ] **B.3 Wire shelf storage for `@user_value`** (if probe 1 says it's needed). In `rig/workers/planner.mld @runPlannerSession` (~line 1266), the `plannerShelf` is built from `@rawAgent.records`. Either:
  - Merge `@user_value` into the framework records set passed into the agent build (`agent.plannerShelf.user_value` becomes a shelf slot), OR
  - Open a separate shelf slot for `user_value` on the planner that doesn't go through the suite records map.
  - Decision recorded in Phase B exit notes. Field name reference: `@agent.plannerShelf` (not `@agent.shelf`).

- [ ] **B.4 Register `mint_user_literal` as a planner-provider tool**. The planner doesn't use a text parser — `@plannerTools` is a tool collection passed to the LLM provider. Add the entry: `mint_user_literal: { mlld: @mintUserLiteralWorker, inputs: @mint_user_literal_inputs, description: "..." }`. Update `tests/lib/mock-llm.mld` and any scripted-LLM harness to recognize the new tool name in expected emissions. No parser changes needed.

### Phase C: Role-aware arg compilation

- [ ] **C.1 Extend `@toolArgMeta`** in `rig/intent.mld:43` to return role from combined (tool-phase × input-record-field × input-record-arg-policy) signals:
  - Tool with `resolve:r` / `read:r` label + arg has NO task-literal-required marker → `filter` (bare OR ref accepted).
  - Tool with `resolve:r` / `read:r` label + arg has task-literal-required marker → `filter-task-verified` (bare values run through `@knownInTask` verifier; refs resolved as today).
  - Tool with `execute:w` label + arg in input record's `facts:` block → `authority`.
  - Tool with `execute:w` label + arg in input record's `data:` block → `payload`.
  - Tool with `execute:w` label + arg in `exact:` → `payload-task-verified` (task-text verification via input policy, not source class — see C.5).

- [ ] **C.2 Extend `@compileArgRef` / `@compileToolArgs`** in `rig/intent.mld` to dispatch based on role:
  - `filter` role: bare values pass through; structured refs resolve as today.
  - `filter-task-verified` role: bare values run through `@knownInTask` substring check against the user task; structured refs resolve as today.
  - `payload` role: accept bare values; structured refs resolve as today (planner is allowed to use a resolved value as payload).
  - `payload-task-verified` role: bare values run through `@knownInTask`; structured refs resolve.
  - `authority` role: require a proof ref shape (`{source: "resolved", ...}`, `{source: "selection", ...}`, OR the new mint-handle ref shape — TBD by probe 1).
  - Bare value passed to `authority` arg: reject with error envelope `{ ok: false, error: "bare_literal_in_authority_arg", arg: <name>, hint: "Call mint_user_literal({ value: <value> }) first; use the returned handle ref." }`.

- [ ] **C.3 Move blanket validation out of `@validatePlannerArgRefs`** (`rig/planner_inputs.mld:250`). Today this rejects bare values universally before tool metadata is in scope. Refactor so structured-ref validation only fires for the top-level action envelope (e.g., `sources:` arrays on derive, `source:` ref on extract). Per-arg validation moves into the compiler where tool metadata is available.

- [ ] **C.4 Preserve selection ref validation**. The check in `rig/workers/derive.mld:104` (validated against derive inputs) is security-relevant and must continue firing. Selection refs stay strict.

- [ ] **C.5 Preserve `exact:` task-text verification**. Fields marked `exact:` in an input record (e.g., passwords) currently require task-text match via the `knownInTask` check. Keep this enforcement but route it through role detection: `exact:` → role `payload-task-verified` → check happens at coerce or compile time without requiring a source-class wrapper.

### Phase D: Revert over-engineered scaffolding

- [ ] **D.1 Remove `rigTransform: "mint_user_literal"` branch** in `rig/workers/resolve.mld:168` (early-return arm).

- [ ] **D.2 Replace `@dispatchMintUserLiteral`** in `rig/mint.mld`. The rigTransform-style dispatcher goes; the verifier + mint + shelf-write logic moves into `@mintUserLiteralWorker` at the planner-provider tier. If shelf-write permissions require an active `role:worker` context (likely — resolve/execute dispatchers use this pattern), the worker exe carries `role:worker` and the implementation is a thin direct mint dispatcher rather than today's rigTransform-routed one. Don't delete the worker-role helper outright; pivot it.

- [ ] **D.3 Remove `@mint_user_literal_placeholder` exe** from `rig/mint.mld`. No longer needed without rigTransform.

- [ ] **D.4 Remove `@rigInternalTools` collection** from `rig/mint.mld`. Auto-injection path gone.

- [ ] **D.5 Remove `rigInternalTools` field from agent** in `rig/orchestration.mld @validateConfig`.

- [ ] **D.6 Remove rigInternalTools fallback lookup** in `rig/tooling.mld @phaseToolEntry` + `@phaseCatalog`.

- [ ] **D.7 Remove the tool catalog entry** for `mint_user_literal` (it's no longer a catalog tool — it's a planner-level provider tool).

### Phase E: Retire `known` from rig

- [ ] **E.1 Remove `source: "known"` from planner.att grammar**. Drop line 38, remove related teaching at lines 78, 82, 132-133, 182. Replace with field-role teaching: "payload fields take normal values; write authority fields need handles or mint_user_literal refs."

- [ ] **E.2 Remove `mint_user_literal` teaching from planner.att** that referenced the `resolve({...})` shape — the new shape `mint_user_literal("value")` is taught as part of the action grammar list (line 19+).

- [ ] **E.3 Remove `known` source-class branches from rig/intent.mld** — specifically the source-class dispatch arms (`@refSource(@ref) == "known"` and friends) and the `{source: "known", value: ...}` ref shape. **Keep `@knownInTask`** — it remains the verifier, but it's now called by the role-aware compiler for `filter-task-verified` and `payload-task-verified` roles (driven by input-record metadata, not by source class). The verification capability survives; the planner-facing shape that triggered it goes away.

- [ ] **E.4 Update scripted-LLM test fixtures** (`tests/scripted/*.mld`) — any `{source: "known", value: ...}` emissions in fixture planner outputs become bare values (for payload) or `mint_user_literal(...)` calls + resolved-handle refs (for authority).

### Phase F: Tests

- [ ] **F.1 Zero-LLM tier coverage**:
  - Bare payload value accepted on write tool.
  - Bare filter value accepted on read tool.
  - Bare value rejected on write authority arg with clear `bare_literal_in_authority_arg` error.
  - Resolved-handle ref accepted on write authority arg.
  - Selection-ref accepted on write authority arg (preserves existing selection validation).
  - mint_user_literal end-to-end: in-task value → handle returned; not-in-task → structured error envelope.
  - `exact:` field still requires task-text verification under role-aware path.

- [ ] **F.2 Scripted-LLM tier coverage** (`tests/scripted/`):
  - Banking parity test: bare-payload write succeeds (e.g., subject field) AND fact-grounded recipient still required.
  - Workspace parity test: same shape for send_email.
  - Slack parity test: same shape for send_channel_message.
  - Travel parity test: reserve_hotel is a write — `hotel` is authority (resolved-handle required); `start_day`/`end_day` are payload (bare values accepted). NOT filter args.
  - Per-suite security tests pass unchanged (rejection LAYER may change — `bare_literal_in_authority_arg` is the new code for authority bypass attempts).

- [ ] **F.3 Worker LLM gate** (`tests/live/workers/run.mld`): must stay green. Worker tests exercise extract/derive/compose dispatch; arg-grammar changes shouldn't affect worker prompts but worth re-running.

### Phase G: Sweep and verify

- [ ] **G.1 Targeted local probes** of canonical recoveries:
  - WS UT4 (Sarah's email known from task text → exfil): should now route through `mint_user_literal("sarah.connor@gmail.com")`, get a handle, and pass exfil:send.
  - WS UT13 / UT19 (selection_refs from derive over resolved records): mitigated worker output should flow under the inf:mit BasePolicy negation.
  - WS UT32 (file_id from create_file → share_file): inf:mit on the dispatcher should let the chain flow.
  - SL UT2 (Dora's email): split case — if email genuinely from untrusted webpage, stays denied; if also in task text, mint path lets it through.

- [ ] **G.2 Targeted sweep on workspace + slack** (the two suites with most recovery potential per this plan). Use `scripts/bench.sh workspace slack`.

- [ ] **G.3 Diagnose any new failures** via `/diagnose` — confirm regressions, if any, are honest (caused by shape misuse) rather than systemic.

- [ ] **G.4 Full benign sweep** if G.2 looks positive. Run ids cited in STATUS.md sweep history with the new arg grammar marked clearly.

- [ ] **G.5 Attack matrix** only after benign utility holds at or above prior sweep #3 baseline (60/97).

## What survives from prior work

These changes from earlier in this session stay as-is:

- `@verifyUserLiteral(value, query)` in `rig/mint.mld` — verifier logic (token-bounded substring, normalize, min-length 3).
- `@mintUserLiteral(value, query)` exe in `rig/mint.mld` — used internally by `@mintUserLiteralWorker`.
- `@mint_user_literal_inputs` record in `rig/records.mld` — input contract (single `value: string` payload field; `validate: "strict"`; planner-authorize).
- `@user_value` record in `rig/records.mld` — pending probe 1 outcome.
- `inf:mit` labels on `@dispatchExtract` / `@dispatchDerive` / `@dispatchCompose` in `rig/workers/*.mld`.
- BasePolicy split in `rig/orchestration.mld @synthesizedPolicy`: `influenced+!influenced:mitigated: { deny: ["destructive", "exfil"] }` instead of widened plain influenced rule.

## What reverts from prior work

- `@dispatchMintUserLiteral` role:worker exe in `rig/mint.mld` → moves to planner-level worker.
- `@mint_user_literal_placeholder` exe in `rig/mint.mld` → deleted.
- `@rigInternalTools` collection in `rig/mint.mld` → deleted.
- `rig/workers/resolve.mld` rigTransform branch for `mint_user_literal` → deleted.
- `agent.rigInternalTools` field in `rig/orchestration.mld @validateConfig` → deleted.
- `rig/tooling.mld @phaseToolEntry` + `@phaseCatalog` rigInternalTools fallback → deleted.

## Out of scope (deferred)

- **Phase inference / phase collapse** — keep current 7-phase planner action set. Extract/derive/compose are qualitatively different things; collapsing them is a separate decision with its own threat-model implications.
- **Generalized ref-grammar collapse beyond `known`** — `resolved` / `selection` / `extracted` / `derived` stay as-is. Selection-ref security validation is load-bearing; extracted/derived distinctions track different worker types whose threat semantics differ.
- **mlld-side changes** — none required by this plan. m-7d15, m-f4f5, m-31b5, m-5828, m-8e37 already shipped. m-5686 (formal `known` retirement in mlld) is upstream's call; this plan only retires rig's local use.
- **Suite-side records refactors** — input records (`@send_email_inputs`, etc.) stay as-is. The plan reads their existing `facts:` / `data:` split; no schema changes needed.

## Acceptance gates

This plan is done when:

1. Zero-LLM gate `tests/index.mld --no-checkpoint` ≥ 266 passing (current baseline).
2. Scripted-LLM gate `tests/run-scripted.py --suite <each>` all pass.
3. Worker LLM gate `tests/live/workers/run.mld` ≥ 24/24.
4. Planner.att teaches: bare values for payload/filter, mint for write-authority task literals. No `source: "known"` teaching.
5. `source: "known"` code path removed from `rig/intent.mld`.
6. Targeted sweep shows: utility ≥ sweep #3 baseline (60/97) OR clear per-task diagnosis for any regressions.
7. Full benign sweep + attack matrix produce honest numbers documented in STATUS.md.

## Decision log

- 2026-05-15: GPT5.5 caught three initial corrections to the migrator-10 draft. (1) mint must be a planner-level tool not a suite tool — suite tools aren't directly callable. (2) Read/filter vs write/authority distinction sharper than control/payload framing — combine tool labels with field classification. (3) @user_value default-until-probe-says-otherwise.
- 2026-05-15: User chose option (a) — planner-visible mint_user_literal — over option (b) silent auto-mint. Reasoning: structured tool error for the planner to react to vs opaque rehearse rejection. Reaffirmed against GPT5.5's contrary suggestion.
- 2026-05-15: User chose less-conservative backward-compat stance than GPT5.5 suggested: drop `known` from rig as soon as scripted-LLM tests are updated, don't keep compat indefinitely.
- 2026-05-15: Phase A probes executed by migrator-10. All three answered:
  - Probe 1: bare minted handle works at mlld layer; decision is to keep `@user_value` to preserve consistent rig ref grammar.
  - Probe 2: bare values rejected today at `intent.mld:601` (`unsupported_ref_source`); fix is a top arm in the `@resolveRefValue` source-class dispatch.
  - Probe 3: role classifier prototype works against fixture tools — 5 role classifications verified. Recommendation for v1: defer the `filter-task-verified` variant until a specific use case demands it; ship `filter` as the v1 read-arg role.
- 2026-05-15: GPT5.5 second pass — eight additional corrections, all applied:
  - Read tool args are bare-OR-ref, not bare-only (`resolved_family` hot path, URL promotion `recordArgs`, etc. still need ref resolution).
  - `mint_user_literal({value: "x"})` is the canonical shape per `inputs: @mint_user_literal_inputs`; scalar shorthand `mint_user_literal("x")` is a probe-gated ergonomic goal, not baseline.
  - No planner-output parser exists — `@plannerTools` is the registry; B.4 updates the registry + harness.
  - Shelf write may need active `role:worker` context — D.2 pivots (not deletes) the worker-role helper.
  - Agent field is `@agent.plannerShelf`, not `@agent.shelf`.
  - Task-literal verification for read filters survives via input-policy metadata on the record, not via source class — `@knownInTask` stays.
  - Architectural framing: the system still needs five ref kinds (literals, resolved, selection, extracted/derived, mint handles). The simplification is that ordinary payloads/read filters no longer need source wrappers — not "everything collapses to bare or handle."
  - F.2 travel test: reserve_hotel args are write/authority + write/payload, not filter.
