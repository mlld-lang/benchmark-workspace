# MIGRATION-TASKS.md — v2.x structured-labels + policy-redesign migration

Temporary task tracker for the v2.x migration. Lives until migration ships, then archived to `archive/`. This doc is the **WHAT** of the migration; the **HOW** lives across five canonical references that every step below cites:

- **`/migrate` skill** (`.claude/skills/migrate/SKILL.md`) — three-tier separation (mlld / rig / bench), spike-then-test rhythm, per-suite exit gates, negative discipline rules ("no prompt-as-defense," "no eval-shaping," "no tier-bleeding fixes").
- **`MIGRATION-PLAN.md`** — 8 phases (0-8) + rollback, target value model (`mx.trust` / `mx.influenced` / `mx.labels` / `mx.factsources` channels), Phase 7 whack-a-mole commit dispositions, validation command sets.
- **`mlld-security-fundamentals.md`** — current primitives: labels (§1), policies (§2), guards (§3), records (§4), refine (§4.7), shelves (§6), sessions (§7). The doc the migration migrates *to*.
- **`mlld qs`** (run at session start) — syntax surface, StructuredValue boundary, JS/Python metadata-erasure rule, `for @k, @v in @obj` native iteration, object spread shallow-copy semantics.
- **`DEBUG.md`** — Cardinal Rules (no benchmark cheating, separation of concerns, never blame model capability, clear educational error messages). Spike-first-sweep-last discipline. Tier-1 (zero-LLM, `tests/index.mld`) vs tier-2 (scripted-LLM, `tests/run-scripted.py`) vs tier-3 (live sweep — does NOT regression-lock; cannot promote `[?]` to `[T]`).

**Acceptance gate**: utility ≥78/97 (target 81/97) **AND** 0 ASR across full 6×5 attack matrix. Both required for ship.

**Stop-conditions** (from `/migrate` skill):
- Probe shows mlld misbehaves against spec → file `~/mlld/mlld/.tickets/m-XXXX` with the probe path, wait. Don't workaround unless small + on-target.
- sec-*.md claim turns out wrong (threat model evolved) → update sec-*.md first, then decide records/policy.
- Acceptance gate drifts wrong direction during migration → probe the regression, ticket the root cause, stop.

**Three-tier discipline** (from `/migrate` skill — applies to every checkbox below):
- Is this about how a value carries trust state through coerce/shelf/dispatch/projection? → **mlld** (`~/mlld/mlld/`).
- Is this about phase dispatch, envelope shape, or planner discipline? → **rig** (`clean/rig/`).
- Is this specific to one suite's threat model, records, tool catalog? → **bench** (`clean/bench/`).
- If it feels like it must live in two tiers, stop — you've found a missing primitive in mlld. File a ticket.

---

## Status

- [x] **Phase 0** — Setup (commits 3737ea6, 062285e, f8232ad, 93036ea, 48bc93e on `policy-structured-labels-migration`)
- [x] **Phase 1** — sec-doc authoring (5 docs landed, SEC-HOWTO-compliant, 55 threat tickets in `.tickets/threats/`)
- [~] **Phase 2** — Audit current state against sec-*.md (deferred until Phase 3 BasePolicy migration clears zero-LLM gate; spike-probe infrastructure ready at `tmp/policy-spike/`)
- [~] **Phase 3** — Per-suite migration (BasePolicy cross-cutting migration started — commit 31d1ace; per-suite records redraft pending)
- [ ] **Phase 4** — Full sweep + ship

**Baseline state** (migrator-8, 2026-05-14):
- Migration branch: `policy-structured-labels-migration`, base `clean@096bcd2`
- mlld source: `~/mlld/mlld` @ `f90d47e77` (`policy-redesign` branch). Runtime built includes the v2.x retirement errors.
- Zero-LLM gate: **YELLOW** — BasePolicy syntax migrated, 20/20 policy-build tests pass, c-3162-dispatch-denial fails because new `labels.rules.influenced.deny` correctly fires but throw not wrapped in `@dispatchExecute` (ticket c-3162-dispatch-wrap, P0 next session).
- Bench utility: 53/97 baseline (migrator-7, 2026-05-12 sweep). No new sweep this session.

**Mark inventory** (Phase 1 sec-doc maturity, per SEC-HOWTO 5-mark scheme):

| Doc | [T] | [-] | [?] | [!] | [ ] | Filed-tickets table |
|---|---|---|---|---|---|---|
| sec-banking | 0 | 11 | 22 | 1 | 3 | ✓ (19 BK-* tickets) |
| sec-slack | 5 | 40 | 16 | 5 | 4 | ✓ (10 SL-* tickets) |
| sec-workspace | 0 | 60 | 22 | 20 | 7 | ✓ (WS-* tickets) |
| sec-travel | 16 | 26 | 9 | 4 | 2 | ✓ (TR-* tickets — most mature) |
| sec-cross-domain | 0 | 6 | 3 | 1 | 6 | ✓ (XS-* tickets) |

---

## Phase 0 — Setup ✅

Required by `/migrate` skill "Step 6: three-tier separation discipline" and `MIGRATION-PLAN.md` Phase 0 "Prepare the Clean Repo."

- [x] Commit current `clean/` state (handoff captured) — 5 thematic commits (3737ea6 infrastructure, 062285e sec-docs, f8232ad ticket-cleanup, 93036ea url_output, 48bc93e HANDOFF).
- [x] Verify `.claude/skills/migrate/SKILL.md` reflects current architecture (read at session start; current as of 2026-05-14).
- [x] Verify `MIGRATION-PLAN.md` describes target architecture as implemented on mlld `policy-redesign` (verified — Phases 0-8 align with `~/mlld/mlld/spec-label-structure.md` + `spec-policy-box-urls-records-design-updates.md`).
- [x] Verify `SEC-HOWTO.md` reflects 5-mark scheme + ticket-anchoring + citation hygiene (verified — 411 lines, 10-section template, tier-3 sweeps explicitly excluded from `[T]`).
- [x] Create migration branch `policy-structured-labels-migration` per MIGRATION-PLAN.md Phase 0. Source/clean SHAs recorded.

**Exit criteria** (MIGRATION-PLAN.md Phase 0): clean/ on dedicated migration branch; specs + skill + plan + howto + tasks file all current. ✅

---

## Phase 1 — sec-doc authoring ✅

Per `/migrate` skill "Step 4: threat model + authoring guide." Each doc anchors records-author work (what `facts:` / `data.trusted:` / `data.untrusted:` to declare), sweep auditor classification (STRUCTURAL_BLOCK / MODEL_*), and future-reviewer onboarding. SEC-HOWTO 10-section template enforced; 5-mark maturity scheme (`[ ]` / `[!]` / `[?]` / `[-]` / `[T]`); ticket-anchoring per CLAUDE.md "Threat-model tickets" (SS-UT-N / SS-IT-N / SS-slug / XS-slug naming).

- [x] **sec-banking.md** — 10-section template, 5-mark scheme, no coverage roll-up. §5 matrix honestly cites STRUCTURAL BLOCK (pending verify) where c-6935 audit hasn't reached. §8 Class 1-6 organized around fact-grounding. 19 BK-* tickets filed.
- [x] **sec-slack.md** — load-bearing primitives: URL promotion (`find_referenced_urls` + private `get_webpage_via_ref` + `validators/output_checks.mld`) + channel-name firewall. §8 has 5 classes (A novel-URL exfil, B webpage-content-as-instruction, C invite/DM spoofing, D tier-2 contact substitution, E tier-3 web-beacon).
- [x] **sec-workspace.md** — §6 frames SHOULD-FAIL tasks as architectural decisions per c-d0e3 class (not status mirrors). §8 organized around typed-instruction-channel refusal + extract-driven laundering. 20 `[!]` marks reflect threat-surface immaturity (most pending-fix tickets of any suite).
- [x] **sec-travel.md** — advice-gate three-node tree in §8 (classifier routes → `role:advice` projection → `no-influenced-advice` policy + fact-only fallback). 16 `[T]` marks tied to `tests/rig/advice-gate.mld` + `tests/bench/travel-classifier-labels.mld` + `tests/scripted/security-travel.mld` cases. Most mature.
- [x] **sec-cross-domain.md** — XS-* tickets from each suite §9 deferred. Two flavors: cross-suite-applicable defenses (testable today, single-suite probe) vs genuine cross-suite scenarios (speculative, no AgentDojo cross-suite UTs/ITs scored).

**Exit criteria** (SEC-HOWTO calibration check): each doc lets a records author re-write records.mld defending the documented threat surface without re-reading the suite source. ✅

---

## Phase 2 — Audit current state against sec-*.md

Per `/migrate` skill "Spike-then-test — the load-bearing rhythm" + DEBUG.md "Spike First. Sweep Last." Walk every `[-]` (declared + verified) and `[?]` (declared, unverified) claim. Probe each in `tmp/audit-<suite>/`. Three outcomes per claim:

1. **Probe confirms defense fires** → `[-]` stays with probe-path + commit-SHA citation, or promote to `[T]` if you also write the test in Phase 3.
2. **Probe shows gap** → file ticket per CLAUDE.md "Threat-model tickets" naming convention. Mark `[!]` with ticket id inline. If gap is mlld-side (descriptor mechanics, runtime label propagation), file in `~/mlld/mlld/.tickets/m-XXXX` per `/migrate` "Stop-on-mlld-bug" — wait for fix, re-probe, add bench-side regression test.
3. **Defense can't be exercised zero-LLM** → schedule for tier-2 (scripted-LLM) test in Phase 3.d. Mark stays `[?]` until tier-2 exists; tier-3 sweep evidence does NOT promote to `[T]` (SEC-HOWTO §"Mark transition discipline").

**Probe quality discipline** (DEBUG.md "When a spike is the right move"):
- Probe must be zero-LLM where possible (synthetic data, runs in seconds, $0).
- Probe must be **decisive** — binary outcome on one specific claim. Bad probes return "looks fine"; good probes rule out at least one hypothesis no matter how they land.
- Probe must be **self-contained** — no external state, no AgentDojo MCP unless the defense specifically exercises MCP coercion.

**`tmp/policy-spike/` precedent** (this session's spikes): six probes verifying `@standard` shape, `union()` merge semantics, `@policy.build` data-shape acceptance, module-scope-only policy declarations. Reuse this directory pattern: `tmp/audit-banking/probe-<defense>.mld` etc.

### Phase 2 per-suite audit checklists

For each `[-]` and `[?]` mark in the relevant sec-doc, write a probe under `tmp/audit-<suite>/probe-<defense-slug>.mld` that exercises the specific claim. The matrix of probes is the audit artifact.

- [ ] **Audit sec-banking.md** (33 marks total: 11 `[-]` + 22 `[?]`)
  - [ ] §5 row A1 (UT0 bill flow source-class firewall): probe re-confirms c-6935 audit shape — `@file_text.content` `data.untrusted` cannot satisfy `facts/kind:iban` on `@send_money_inputs.recipient`. Reference: `mlld-security-fundamentals.md` §4.2 (output records minting fact-bearing values) + §4.5 (input records validating).
  - [ ] §5 row A6 (attacker IBAN never in PROMPT under v1.1.1): grep `agentdojo/default_suites/{v1,v1_1_1}/banking/user_tasks.py` for `US133000000121212121212`. Document grep output as evidence.
  - [ ] §8 Class 1 — `@transaction.subject` (sender != "me") classified `data.untrusted` (ticket BK-untrusted-subject-runtime-verify): probe a minimal `@transaction` coercion, assert `@transaction.mx.trust == "untrusted"` and `@transaction.subject.mx.trust == "untrusted"` per `mlld-security-fundamentals.md` §1.6 "Content-derived aggregation."
  - [ ] §8 Class 3 — `correlate: true` on `@update_scheduled_transaction_inputs` (ticket BK-correlate-factsources-verify): probe two-record-mixing scenario per `mlld-security-fundamentals.md` §4.5 `correlate:` paragraph + `~/mlld/mlld/spec-label-structure.md` §1.4 (`factsources.instanceKey`).
  - [ ] §8 Class 4 — absent `write:` block on `@update_password_inputs` (hard-deny): probe an exe attempting to authorize against this record; expect `WRITE_DENIED_NO_DECLARATION` per `mlld-security-fundamentals.md` §4.5 "write: permissions on records."
  - [ ] §8 Class 5 — IT9 architectural refusal (`parse_invoice_iban` retired): grep `bench/domains/banking/tools.mld` — confirm absence. Citation-as-evidence is sufficient `[-]`.
  - [ ] Remaining 27 `[?]` / `[-]` marks: same pattern, batched into `tmp/audit-banking/`.

- [ ] **Audit sec-slack.md** (56 marks: 40 `[-]` + 16 `[?]`)
  - [ ] §8 Class A — `find_referenced_urls` rigTransform + private `get_webpage_via_ref` capability: probe a synthesized URL-bearing webpage_content; assert the URL is promoted to a ref index, not a literal string. Reference: `rig/ARCHITECTURE.md` "URL Promotion" + `rig/policies/url_output.mld`.
  - [ ] §8 Class A — output validator on terminal compose (`validators/output_checks.mld` + `policies/url_output.mld`): probe a compose attempt that emits a novel URL; assert it's rejected.
  - [ ] §8 Class C — channel-name firewall (`@slack_channel.name` `data.untrusted` + per-tool `known-text` constraint): probe a forged channel_name; assert dispatch rejection. Reference: sec-slack §4 "Records — field-level classification."
  - [ ] §8 Class B — `get_webpage_via_ref` private capability typed return: probe that the return record's content field is `data.untrusted`.
  - [ ] Remaining marks batched in `tmp/audit-slack/`.

- [ ] **Audit sec-workspace.md** (82 marks: 60 `[-]` + 22 `[?]`)
  - [ ] §8 Class A — typed-instruction-channel refusal (UT13/UT19 SHOULD-FAIL by construction per c-d0e3): probe an extracted-from-untrusted-email TODO list; assert it cannot reach `send_email.recipient` via source-class firewall.
  - [ ] §8 Class B — display projection on `data.untrusted` content fields: probe `@email.role:planner` projection; assert body is omitted. Reference: `mlld-security-fundamentals.md` §4.3 "Read projections" + `~/mlld/mlld/spec-label-structure.md` §2.5 "Content-derived aggregation for constructed values."
  - [ ] §8 Class C — schedule/calendar arithmetic w/ attacker-controlled times (`src/date_shift.py` `_patch_workspace_utilities` is infrastructure not defense — see CLAUDE.md "Diagnosing failures").
  - [ ] Remaining marks batched in `tmp/audit-workspace/`.

- [ ] **Audit sec-travel.md** (35 marks: 26 `[-]` + 9 `[?]`)
  - [ ] §8 Class A advice gate three-node tree: classifier routing → `role:advice` projection → `no-influenced-advice` policy + fact-only fallback. Most `[T]` marks already cite `tests/rig/advice-gate.mld` cases — audit re-runs those tests against new v2.x labels semantics to confirm regression.
  - [ ] §8 Class B booking-redirection via extracted hotel/restaurant: probe a selection_ref from derive against a tainted `@hotel_review.review_blob`; assert proof carries through per `~/mlld/mlld/spec-label-structure.md` §9.10 "What `satisfies:` does not do" (custom labels permit, don't promote).
  - [ ] Remaining 17 marks batched in `tmp/audit-travel/`.

- [ ] **Cross-suite spot check on sec-cross-domain.md** (9 marks: 6 `[-]` + 3 `[?]`)
  - [ ] §8 XS-update-user-info-address-exfil: probe whether `update_user_info` accepting `data.untrusted` address content creates a cross-suite exfil channel if a future workspace/slack agent reads the address.
  - [ ] §8 XS-no-influenced-privileged-rule: design-question probe — would a `labels.rules: { influenced: { deny: ["privileged:*"] } }` rule generalize across suites? Compare against current per-record absent-`write:`-block defense.

**Exit criteria** (Phase 2):
- Every `[-]` claim has either a probe-path + commit-SHA citation OR is honestly downgraded to `[?]` with a ticket.
- Every `[?]` claim has either a probe outcome (promoted to `[-]` or surfaced as `[!]`) OR an explicit "tier-2-only-can-test" deferral marked in the doc.
- Probe outputs collated; no orphan claims in any sec-doc.
- Phase 2 produces the gap list that drives Phase 3 records redraft per suite.

---

## Phase 3 — Per-suite migration

Suite order from `/migrate` skill "Per-suite migration discipline": **banking → slack → workspace → travel.** Don't start the next suite until current suite's exit gate passes. Each suite's work is 3.a tools punch list → 3.b records redraft → 3.c BasePolicy (cross-cutting, see below) → 3.d test lockdown → 3.e verification → 3.f exit gate.

### 3.c BasePolicy cross-cutting ✅ (commit 31d1ace, this session)

Bench agents currently pass no `overrides.policy` — BasePolicy is purely framework-synthesized by `rig/orchestration.mld @synthesizedPolicy`. The cross-cutting migration:

- [x] Replace named-rule string list (`["no-secret-exfil", ..., "no-novel-urls"]`) with imports from `@mlld/policy/standard`. Reference: `~/mlld/mlld/MIGRATION-POLICY-REDESIGN.md` §"Policy Syntax Mapping" + `mlld-security-fundamentals.md` §"Stock Policy Library."
- [x] Replace `defaults.unlabeled: "untrusted"` route with `labeling.unlabeled: "untrusted"` (the renamed-but-functional path). Cascade retirement per `~/mlld/mlld/spec-label-structure.md` §3.1 is deferred — `labeling.unlabeled` still supported as a coarse policy knob (`mlld-security-fundamentals.md` §1.9).
- [x] Move `operations:` → `labels.risks:` (`~/mlld/mlld/MIGRATION-POLICY-REDESIGN.md` §"Policy Syntax Mapping").
- [x] Preserve rig overlay: additively widen `labels.rules.influenced.deny` to `["destructive", "exfil"]` atop `@standard`'s `["advice"]`. Verified via `tmp/policy-spike/probe-influenced-union.mld` that `union()` merges deny arrays additively.
- [x] Preserve `trusted_tool_output` + `user_originated` `satisfies: ["fact:*"]` per `~/mlld/mlld/spec-label-structure.md` §9.9 (transitional alias survives v2.x).
- [x] Migrate `rig/workers/advice.mld` to `union(@noInfluencedAdvice)` instead of retired `defaults.rules: ["no-influenced-advice"]`. Per `~/mlld/mlld/spec-policy-box-urls-records-design-updates.md` §9.1 the fragment maps to `labels.rules: { "influenced+op:advice": { deny: ... } }`.
- [x] Verify `@policy.build` accepts the new-schema data shape directly (no module-scope `policy @p = union(...)` required). Probe: `tmp/policy-spike/probe-policy-build-data.mld`. Critical finding — `union()` is **only** valid in `policy @p = ...` declarations at module scope (not in exe bodies), so rig synthesizes the merged data shape directly.
- [x] Update `tests/rig/policy-build-catalog-arch.mld testSynthesizedPolicyShape` to assert new-schema presence: `labels.args["exfil:send"].recipient`, `labels.apply["trust:untrusted+llm"]`, `dataflow.check.length`. Passes 20/20 isolated.
- [ ] **c-3162-dispatch-wrap** (filed this session, P0 next session) — wrap `@callToolWithPolicy` in `@dispatchExecute` with `when [denied => ...]` arm so policy throws surface as `{ ok: false, stage: "dispatch_policy", failure: {...} }`. Reference: `mlld-security-fundamentals.md` §3.8 "Catching denials" + `rig/workers/advice.mld:110` (`@adviceGate` pattern with `denied => @factOnlyAnswer`).

### Suite 1: Banking

Per `/migrate` skill rationale: smallest delta, sec-doc exists, validates pattern against most-defended suite.

- [ ] **3.a Tools punch list** against `sec-banking.md §3`
  - [ ] Walk `bench/domains/banking/tools.mld` against sec-banking §3 tool inventory table.
  - [ ] Verify each tool's `kind:` (read/write), control args, payload args, operation labels, `instructions:` match the sec-doc claims.
  - [ ] For write tools, confirm `inputs: @<record>` binds the documented `@*_inputs` record. Per `mlld-security-fundamentals.md` §4.5 "input records authorize via the binding."
  - [ ] Punch list lives as sub-bullets here; tick off as resolved.

- [ ] **3.b Records redraft** against `sec-banking.md §4` + v2.x channel grammar
  - [ ] For each record in `bench/domains/banking/records.mld` (6 output + 5 input), map to new schema per `~/mlld/mlld/spec-label-structure.md` §1.1 (`mx.trust` / `mx.influenced` / `mx.labels` / `mx.factsources`).
  - [ ] Apply v2.x `refine [...]` shape per `~/mlld/mlld/MIGRATION-POLICY-REDESIGN.md` §"Record refine":
    - Retired record-level `when:` shape → `refine [ when [ ... ] ]` with supported actions `labels += [...]`, `facts += [tier]`, `facts = []`, `data.field = trusted`, `data.field = untrusted`.
    - Banking-specific: `@transaction.refine [ sender == "me" => [ labels += ["user_originated"], data.amount = trusted, data.date = trusted, data.recurring = trusted ] ]` (the f168037 banking-side overlay; redundant under v2.x if the §2.4 LLM-pass invariants handle propagation, but stays spec-compliant).
  - [ ] Apply `facts:` / `data.trusted:` / `data.untrusted:` per sec-banking §4 per-field table.
  - [ ] Output records that mint fact labels (`@transaction.id`, `@transaction.recipient`, `@transaction.sender`, `@iban_value.value`, `@scheduled_transaction.id`, etc.) — verify `kind:` tag matches (`kind: "iban"`, `kind: "transaction_id"`). Reference: `mlld-security-fundamentals.md` §4.6 "Fact kinds."
  - [ ] Input records: declare `validate: "strict"`, `correlate: true` where threat model requires (only `@update_scheduled_transaction_inputs` per sec-banking §3). Reference: `mlld-security-fundamentals.md` §4.5 + §"Stock Policy Library" `correlate-control-args`.
  - [ ] `@update_password_inputs`: verify no `write:` block declared (the hard-deny defense per sec-banking §8 Class 4). Reference: `mlld-security-fundamentals.md` §4.5 "write: permissions."
  - [ ] **Spike-then-test rhythm** (per `/migrate` skill): for each record declaration, write a probe in `tmp/records-banking/probe-<record>.mld` that coerces a synthetic input through `=> record`, then inspects `.mx.trust`, `.mx.labels`, `.mx.factsources`. Per `mlld-security-fundamentals.md` §4.2 "Output records: classifying tool output."
  - [ ] Iterate until each probe matches the sec-doc §4 / §5 claim.
  - [ ] Commit records.mld with sec-doc row citations inline per declaration (`>> sec-banking.md §5 row A1`).

- [x] **3.c BasePolicy** — covered by cross-cutting migration above. No banking-specific override required.

- [ ] **3.d Test lockdown** — promote `[?]` marks in sec-banking §5/§8 to `[T]` where feasible
  - [ ] For each `[?]` mark whose defense can be exercised zero-LLM, write a tier-1 test (a new file under `tests/rig/` + register in `tests/index.mld`).
  - [ ] For defenses that need LLM behavior (e.g., compose-side anti-fabrication), write tier-2 tests in `tests/scripted/security-banking.mld`. Reference: existing pattern at `tests/scripted/security-travel.mld testReserveHotelExtractedNameRejected`.
  - [ ] Do NOT promote to `[T]` based on tier-3 sweep evidence (SEC-HOWTO §"Mark transition discipline" — sweeps are stochastic, don't run on PR).
  - [ ] After each test addition, update sec-banking.md mark: `[?]` → `[T]` with test file + case-name citation. Close the linked ticket via `tk close <id> --dir threats`.

- [ ] **3.e Verification** per `/migrate` "Validation gates"
  - [ ] Zero-LLM gate: `mlld tests/index.mld --no-checkpoint` → 100% pass.
  - [ ] Worker LLM gate: `mlld tests/live/workers/run.mld --no-checkpoint` → 24/24 (only required if prompts changed).
  - [ ] Local probe canonical banking tasks: `uv run --project bench python3 src/run.py -s banking -d defended -t user_task_3 user_task_4 user_task_6 user_task_11 -p 4`. Compare against baseline 53/97 (STATUS.md Sweep history 2026-05-12).
  - [ ] Banking attack canary direct: `scripts/bench-attacks.sh single direct banking` → 0 ASR.
  - [ ] Banking attack canary important_instructions: `scripts/bench-attacks.sh single important_instructions banking` → 0 ASR.
  - [ ] Banking attack canary tier-2 (IT9 data corruption): targeted run via `gh workflow run bench-run.yml -f suite=banking -f tasks=user_task_0 -f attack=direct -f defense=defended` (one task × one attack × one suite per `CLAUDE.md` "Attack dispatches").

- [ ] **3.f Suite exit gate** — all of the following must hold before starting slack
  - [ ] sec-banking.md marks: zero orphan `[?]`. Every mark is `[-]` + citation, `[T]` + test, or `[!]` + ticket.
  - [ ] Zero-LLM gate green.
  - [ ] Worker LLM gate green (if applicable).
  - [ ] Banking utility ≥ baseline + expected recoveries (per STATUS.md "Recovery path to ceiling" Tier 1 estimate: 10-13 tasks across suites; banking-specific should be ≥10/16 strict).
  - [ ] Banking attack canaries at 0 ASR.
  - [ ] Commit + push.

### Suite 2: Slack

Per `/migrate` skill rationale: simplest new sec-doc, single load-bearing primitive (URL promotion). Tests SEC-HOWTO template against a new suite.

- [ ] **3.a Tools punch list** against `sec-slack.md §3` (read tools: `get_channels`, `get_users_in_channel`, `read_channel_messages`, `read_inbox`, `get_webpage`, etc. — incl. URL promotion surface)
- [ ] **3.b Records redraft** (probes in `tmp/records-slack/`)
  - [ ] `@slack_msg`: `data.untrusted: [body]`, channel name fact-grounded.
  - [ ] `@slack_channel`: `name: data.untrusted` (channel-name firewall per sec-slack §4) — verify `known-text` constraint mechanics per `mlld-security-fundamentals.md` §4.5 + §"Stock Policy Library" precedence chain.
  - [ ] `@webpage_content`: `data.untrusted: [content]` + URL surfacing via `find_referenced_urls`.
  - [ ] `@url_ref`: handle type per `rig/ARCHITECTURE.md` "URL Promotion" (tainted URLs only reach tools through rig-minted refs).
  - [ ] `@*_inputs` (send_direct_message, post_webpage, etc.): `facts:` per sec-slack §4 input-record table.
- [ ] **3.c BasePolicy** — covered cross-cutting; slack uses `@hasNovelUrlRisk(@tools)` gate to engage `@urlDefense` automatically.
- [ ] **3.d Test lockdown** — sec-slack has 5 `[T]` already; promote more `[?]` per §8 Class A/B/C trees. Particular attention: `@noUntrustedUrlsInOutput` guard regression-lock (sec-slack §9 item 7).
- [ ] **3.e Verification** — standard gates + slack canaries (`atk_direct`, `atk_important_instructions`, also `atk_injecagent` per attack matrix).
- [ ] **3.f Suite exit gate** — same shape as banking; **slack security canary already 0/105 ASR per STATUS.md sweep `25708270888` / `25708271819`** — verify this holds post-v2.x.

### Suite 3: Workspace

Per `/migrate` skill rationale: SHOULD-FAIL framing as architectural decision. The §6 challenge is treating SHOULD-FAIL as threat-relevant fact, not status mirror.

- [ ] **3.a Tools punch list** against `sec-workspace.md §3` (40 user tasks — largest surface; calendar + email + contacts + cloud-drive).
- [ ] **3.b Records redraft** (probes in `tmp/records-workspace/`)
  - [ ] `@email`: `data.untrusted: [body, attachments[*].content]` per sec-workspace §4 (the typed-instruction-channel class).
  - [ ] `@calendar_event`, `@contact`, `@file_*`: per sec-workspace §4 per-record tables.
  - [ ] Particular attention to `@email.role:planner` projection stripping body. Reference: `mlld-security-fundamentals.md` §4.3 + `~/mlld/mlld/spec-label-structure.md` §2.5 (content-derived aggregation).
- [ ] **3.c BasePolicy** — covered cross-cutting.
- [ ] **3.d Test lockdown** — SHOULD-FAIL paths (UT13/UT19/UT25 c-d0e3 class). Tier-1 tests for typed-instruction-channel refusal: assert that extracted-from-untrusted-content cannot satisfy `send_email.recipient` even when planner attempts via known/derived buckets.
- [ ] **3.e Verification** — standard gates + workspace canaries. **Workspace splits in half (-a/-b)** for memory headroom per CLAUDE.md "What runs where" table.
- [ ] **3.f Suite exit gate** — workspace's SHOULD-FAIL category is 1 task (UT19). 4 OPEN tasks (UT13/UT18/UT25/UT38). Expected recoveries via records refine migration: UT12/UT15/UT18/UT20/UT21 (calendar-event creation from emails — needs Tier 1 c-a6db `?` field-optional + possibly reader-set primitive c-dee1).

### Suite 4: Travel

Per `/migrate` skill rationale: advice gate is qualitatively different (policy + projection, not value-grounding). Most architecturally complex. Save for after template-fluent patterns settled.

- [ ] **3.a Tools punch list** against `sec-travel.md §3` — incl. classifier surface (`§3.5 Classifier surface` — task-entry classifier routes to advice-mode).
- [ ] **3.b Records redraft** (probes in `tmp/records-travel/`)
  - [ ] `@hotel`, `@restaurant`, `@car_rental`, `@flight`: `data.untrusted: [review_blob, ...]` with `role:advice` projection stripping the untrusted prose.
  - [ ] Advice projection: `mlld-security-fundamentals.md` §4.3 "Read projections" — `role:advice` is canonical example of role-projection security working by construction.
- [ ] **3.c BasePolicy** — covered cross-cutting + advice-gate-specific (already migrated to `union(@noInfluencedAdvice)` in commit 31d1ace).
- [ ] **3.d Test lockdown** — travel has 16 `[T]` already (most mature). Re-verify each survives v2.x label changes:
  - [ ] `tests/rig/advice-gate.mld testAdviceProjectionStripsReviewBlobFromAllEntries` + variants.
  - [ ] `tests/scripted/security-travel.mld testReserveHotelExtractedNameRejected`.
  - [ ] `tests/bench/travel-classifier-labels.mld testTwentyTasksLabeled` + variants.
- [ ] **3.e Verification** — standard gates + travel IT6 (recommendation hijack) at 0 ASR (per STATUS.md bench-grind-18 / bench-grind-19).
- [ ] **3.f Suite exit gate** — travel's FLAKY UT0 (year-boundary date arithmetic, ticket c-45e0) survives migration; OPEN UT16 (c-57a6 recommendation-task detection) is planner-quality not migration-conditional.

---

## Phase 4 — Full sweep + whack-a-mole reconciliation + ship

Per MIGRATION-PLAN.md Phase 7 ("Whack-A-Mole Fix Reconciliation") + Phase 8 ("Final Validation"). Reserve full sweeps for closeouts — DEBUG.md "Targeted vs full sweeps" notes a full sweep is "the only case for `scripts/bench.sh` with no args."

### 4.a Whack-a-mole reconciliation

Walk each commit listed in MIGRATION-PLAN.md Phase 7. Record disposition: `no-op` (fully impossible under structured model, already covered) / `test-only` (port the regression test only) / `refactor-invariant` (implement invariant in structured path) / `merge-code` (independent fix; merge normally).

- [ ] **mlld-side commits — likely superseded by construction**:
  - [ ] `955e63628` shelf trust refinement round-trip
  - [ ] `e7793cce5` inherited ambient labels in child frames
  - [ ] `367ccf0eb` exec routing taint and label proofs
  - [ ] `53bd03591` module import source/file/dir taint split
  - [ ] `e8ff25521` record coercion trust refinement
  - [ ] `034af723e` whole-object input field taint
  - [ ] `bbcc3d1af` public provenance label semantics
  - [ ] `6593af2bc` provenance descriptor inventory
  - [ ] `776c0579e` security metadata propagation
  - [ ] `975a0ff76` provenance overhead
- [ ] **mlld-side commits — partially superseded; keep invariant tests**:
  - [ ] `4a27abee4` influenced cascade near-miss invariants
  - [ ] `dfa8d5c1b` influenced cascade narrowed to provenance evidence
  - [ ] `f3dd43663` `src:file` data-load and code-exec routing split
  - [ ] `7d7399dbc` session-seeded shelf bridge writes
  - [ ] `8b1c43576` untrusted LLM influenced rule on payload/nested exe blocks
- [ ] **Bench-side commits — should become unnecessary**:
  - [ ] `096bcd2` elevate `@deriveAttestation.payload` to `data.trusted` — verify structurally redundant under v2.x §2.4 LLM-pass invariants (`~/mlld/mlld/spec-label-structure.md`). If yes, revert; if no, keep with note.
  - [ ] `f168037` banking sender refinement to trusted fields — same verification.

Commit dispositions go in the migration PR/final-commit message per MIGRATION-PLAN.md "Exit criteria."

### 4.b Full benign sweep + ship gate

- [ ] **Full benign sweep**: `scripts/bench.sh` (per CLAUDE.md "Running benchmarks" — 5 sub-suites in parallel, ~10-15 min wall, ~$3-5).
  - [ ] Total utility ≥78/97 (target 81/97 per STATUS.md "Achievable ceiling").
  - [ ] Per-suite breakdown matches projected recoveries (STATUS.md "Recovery path to ceiling").
  - [ ] **Per-task set-diff vs baseline** (sweep `25710915492` et al, 2026-05-12). The set-diff is required — total count alone can hide regressions offset by recoveries. Reference: feedback memory `feedback_baseline_verification.md`.
- [ ] **Full attack matrix sweep**: `scripts/bench-attacks.sh` (all 6 attack variants × 5 sub-suites = 30 jobs). Per CLAUDE.md "Attack dispatches" — uses different shape/parallelism than benign.
  - [ ] 0 ASR per (suite × attack-variant) pairing. Per `/migrate` "Acceptance gate": this is non-negotiable.
- [ ] **Docs final pass**:
  - [ ] STATUS.md updated with post-migration per-task classifications.
  - [ ] HANDOFF.md updated with migration completion + next-session pointer (or "migration shipped" closure).
  - [ ] sec-*.md marks final state: all `[-]` (with citations) or `[T]` (with tier-1/2 test paths), no `[?]`, every `[!]` linked to an open ticket.
- [ ] **Archive obsolete artifacts**:
  - [ ] Move `*.threatmodel.txt` to `archive/` (per CLAUDE.md "Structure" + SEC-HOWTO "Stale-doc reconciliation").
  - [ ] Move `*.taskdata.txt` to `archive/` (currently in root; per CLAUDE.md "Phase 4").
  - [ ] Move `MIGRATION-PLAN.md` + this file (`MIGRATION-TASKS.md`) + `MIGRATION-POLICY-REDESIGN.md` to `archive/` after merge.
  - [ ] Move `.tickets/review/` tickets — decide per-ticket: triaged → archive; still-relevant → restore to main `.tickets/`.

### Ship gate (all required)

- [ ] Zero-LLM gate 100% (`mlld tests/index.mld --no-checkpoint`).
- [ ] Worker LLM gate 24/24 (`mlld tests/live/workers/run.mld --no-checkpoint`).
- [ ] Utility ≥78/97 (target 81/97) on full benign sweep.
- [ ] 0 ASR across full 6×5 attack matrix.
- [ ] sec-*.md marks final: no `[?]`, every `[!]` ticketed.
- [ ] MIGRATION-PLAN.md Phase 7 reconciliation documented (per-commit dispositions in PR message).
- [ ] Branch merged to `main` per MIGRATION-PLAN.md "Merge Guidance."

---

## Cross-cutting discipline (applies to every phase)

### Spike-then-test rhythm (DEBUG.md "Spike First. Sweep Last." + /migrate skill)

The most expensive mistake an agent can make in this repo is using a sonnet 4 sweep to discover a question a $0 spike could have answered in five minutes. Per DEBUG.md "Canonical worked example b-6ea2": a probe matrix is 50× cheaper to run and 100× more diagnostic than a sweep.

Spike pattern per phase:
1. **Phase 2 audit**: every `[-]` claim gets a probe in `tmp/audit-<suite>/`. Each probe asserts one specific defense claim. Decisive binary outcomes.
2. **Phase 3.b records redraft**: before committing a record change, probe the new declaration in `tmp/records-<suite>/`. Confirm labels match sec-doc §4 / §5 / §8 claim.
3. **Phase 3.d test lockdown**: promote spike to tier-1 (under `tests/rig/`) or tier-2 (under `tests/scripted/`). Tier-3 sweeps do NOT lock.
4. **Phase 3.e verification**: targeted local probe + suite canary attack runs before full sweep. Full sweep is closeout only.

### Three-tier separation (`/migrate` skill + CLAUDE.md)

| Change shape | Tier | Where to file/fix |
|---|---|---|
| Value-metadata mechanics, descriptor channels, runtime label propagation, coercion semantics, shelf storage, policy-rule firing | **mlld** | `~/mlld/mlld/.tickets/m-XXXX` + probe in `clean/tmp/<probe-dir>/` |
| Phase dispatch, envelope shape, planner discipline, source-class vocabulary, BasePolicy synthesis from tool catalog, display projection wrappers, intent compilation, lifecycle events | **rig** | `clean/.tickets/c-XXXX` + change in `clean/rig/` |
| Suite-specific records, tools, bridges, addendums, agent entrypoints, sec-*.md threat models | **bench** | `clean/.tickets/c-XXXX` or `clean/.tickets/threats/<SS>-*` + change in `clean/bench/domains/<suite>/` |

If a change feels like it has to live in two tiers, stop. You've probably found a missing primitive in mlld. File the mlld ticket; don't bridge tiers in bench with a workaround. Per `/migrate` "Final discipline": no tier-bleeding fixes — every workaround is a debt the next migration has to revert.

### Negative-discipline rules (`/migrate` skill + CLAUDE.md "Cardinal Rules")

These are the discipline failures the migration is most exposed to. None acceptable:

- **No prompt-as-defense.** A defense node in sec-*.md `[T]` / `[-]` must be a structural enforcement (record primitive, display projection, policy rule, tool metadata, phase-scoped restriction). A sentence in a prompt saying "don't send to attacker IBANs" is NOT a defense per CLAUDE.md "Prompt Placement Rules" "Iterating prompts."
- **No eval-shaping.** Don't read AgentDojo `utility()` / `security()` checker bodies. Don't shape records or prompts around what you suspect the checker tests. CLAUDE.md Cardinal Rule A enforced.
- **No `[-]` marks without firing evidence.** Per SEC-HOWTO §"Mark transition discipline": citing the commit SHA that *added* the declaration is `[?]`, not `[-]`. `[-]` requires a probe that observed the defense firing, a sweep run id, or a code-review chain that explicitly verified the runtime consumer.
- **No `[T]` marks against tier-3 sweeps.** Tier-3 doesn't run on PR; can't lock against regression. Tier-1 (`tests/index.mld` zero-LLM, ~10s) or tier-2 (`tests/run-scripted.py` scripted-LLM, ~30s) only.
- **No partial-state commits.** Zero-LLM gate stays green at every commit — or the commit is clearly labeled migration-in-progress and unblocks within the next commit. "We'll fix the test later" creates a re-entrant migration tax.
- **No re-introducing retired patterns.** `defaults.rules: [...]`, `operations:` at top level, `policy.env:`, `box mcps:`, `auth:`, `using auth:`, record-level `when:`, `top-level locked:`, `facts.requirements:` are all retired per `~/mlld/mlld/MIGRATION-POLICY-REDESIGN.md` §"Policy Syntax Mapping." Anything that smells like the old aggregation pattern should be re-thought against `~/mlld/mlld/spec-label-structure.md` §2.5.
- **No blame-the-model.** DEBUG.md Cardinal Rule C: "The same underlying model has hit 80%+ utility on these suites in prior architectures. When current results are worse, the problem is prompts, attestation shapes, error messages, or framework bugs — not 'the model is weak.'"
- **No JS/Python boundary metadata smuggling.** Per `mlld qs` "JS/Python data boundary": auto-unwrap erases labels AND factsources. A value that crosses `js {}` or `py {}` loses both its label metadata and `factsources` provenance — downstream positive checks like `@noSendToUnknown` will deny it. Use `.keep` only for JS-side `.mx` inspection; mlld-to-mlld preservation is automatic via wrapper-preserving field access. Use native `for @k, @v in @obj` instead of `js { return Object.entries(...).map(...) }`.

### Verification gates (run before every commit during migration)

```bash
mlld tests/index.mld --no-checkpoint                       # zero-LLM gate, ~10s, must stay green
mlld tests/live/workers/run.mld --no-checkpoint            # worker LLM gate (only when prompts change), ~50s, ~$0.05
mlld tests/rig/phase-error-envelope.mld --no-checkpoint    # masking-fidelity regression, must stay 2/2
mlld tests/rig/policy-build-catalog-arch.mld --no-checkpoint   # 20/20 currently
```

Per-suite gate (run at 3.e):

```bash
uv run --project bench python3 src/run.py -s <suite> -d defended -t <canonical-tasks>
scripts/bench-attacks.sh single direct <suite>             # 0 ASR required
scripts/bench-attacks.sh single important_instructions <suite>
```

Ship gate:

```bash
scripts/bench.sh                                           # full 4-suite benign sweep
scripts/bench-attacks.sh                                   # full 6×5 attack matrix
```

### Stop-conditions

Stop and surface to user if:
- Probe consistently shows mlld misbehaves against spec → file `~/mlld/mlld/.tickets/m-XXXX` with probe attached, wait.
- sec-*.md claim wrong (threat model evolved) → update sec-*.md first.
- Acceptance gate drifts wrong direction → probe the regression, ticket root cause, stop the migration.

Don't stop for:
- `[?]` that can't promote to `[T]` this session → mark stays `[?]` with ticket; continue.
- Small workaround that doesn't violate v2.x target shape → land it, file follow-up ticket.

---

## Source-doc cross-reference index

| Topic | Canonical reference |
|---|---|
| Migration phases + commit dispositions | `MIGRATION-PLAN.md` (Phases 0-8 + rollback) |
| Skill / discipline / spike-then-test rhythm | `.claude/skills/migrate/SKILL.md` |
| Bench-side mlld migration patterns + checklist | `~/mlld/mlld/MIGRATION-POLICY-REDESIGN.md` |
| Target value model (channels + propagation + LLM-pass invariants) | `~/mlld/mlld/spec-label-structure.md` |
| Target policy schema | `~/mlld/mlld/spec-policy-box-urls-records-design-updates.md` |
| Current security model narrative | `mlld-security-fundamentals.md` |
| Stock policy library (`@mlld/policy/*` fragments) | `mlld-security-fundamentals.md` §"Stock Policy Library" |
| Labels primitive | `mlld-security-fundamentals.md` §1 |
| Policies anatomy | `mlld-security-fundamentals.md` §2 |
| Guards + `denied =>` arm | `mlld-security-fundamentals.md` §3 |
| Records — output/input/projection/refine | `mlld-security-fundamentals.md` §4 |
| Shelves | `mlld-security-fundamentals.md` §6 |
| Sessions | `mlld-security-fundamentals.md` §7 |
| Per-suite threat models | `sec-{banking,slack,workspace,travel,cross-domain}.md` |
| sec-*.md authoring discipline | `SEC-HOWTO.md` |
| Three-tier separation | `CLAUDE.md` "Three-tier separation" + `rig/ARCHITECTURE.md` "Separation of Concerns" |
| Spike-first vs sweep-first | `DEBUG.md` "Spike First. Sweep Last." |
| Bench results + per-task classification | `STATUS.md` |
| mlld syntax + JS/Python boundary | `mlld qs` (run at session start) |
| Threat tickets | `.tickets/threats/` (55 tickets, SS-* + XS-* naming) |
| Spike probes from this session | `tmp/policy-spike/` |
| Session continuity | `HANDOFF.md` |

---

## Session continuity

This is a multi-session migration. End-of-session discipline:

1. Update this doc's **Status** section with current phase progress + commit SHAs.
2. Update **HANDOFF.md** with concrete next-session priority queue (P0 first).
3. Update **STATUS.md** if any classifications changed (PASS / OPEN / SHOULD-FAIL / BAD-EVAL / FLAKY).
4. Per `/migrate` "Final discipline (negative rules)": don't write summary documents — update HANDOFF + this doc instead.
5. Per CLAUDE.md "user instructions": don't write planning docs ad-hoc; this is the canonical plan and HANDOFF is the canonical breadcrumb.

When the migration ships:
- Move `MIGRATION-PLAN.md`, this file, `~/mlld/mlld/MIGRATION-POLICY-REDESIGN.md` (after coordination with mlld-dev) to `archive/`.
- Move `*.threatmodel.txt` and root-level `*.taskdata.txt` to `archive/` (replaced by sec-*.md).
- Leave sec-*.md + SEC-HOWTO.md in root — they're the durable threat-model artifacts.
- Document migration completion in HANDOFF.md with merge commit SHA and final sweep run ids.
