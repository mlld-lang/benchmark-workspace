# MIGRATION-TASKS.md — v2.x structured-labels + policy-redesign migration

Temporary task tracker for the v2.x migration. Lives until migration ships, then archived. **Read `.claude/skills/migrate/SKILL.md` first** (the migrate skill) — this doc tracks WHAT; the skill governs HOW (spike-then-test rhythm, three-tier separation, negative discipline rules).

**Acceptance gate**: utility ≥78/97 (target 81/97) **AND** 0 ASR across full 6×5 attack matrix. Both required for ship.

**Stop-conditions**: probe shows mlld bug → file `~/mlld/mlld/.tickets/m-XXXX` with the probe attached, wait. Bench schemas drift off v2.x target → re-think the change. Don't workaround unless small + on-target.

## Status

- [x] **Phase 0** — Setup (commits 3737ea6, 062285e, f8232ad, 93036ea, 48bc93e)
- [x] **Phase 1** — sec-doc authoring (5 docs landed, SEC-HOWTO-compliant, 55 threat tickets in `.tickets/threats/`)
- [~] **Phase 2** — Audit current state against sec-*.md. Banking complete (16 [?]/[-] marks promoted to [T] via tier-2 scripted-LLM tests, commit 24eda3d). Slack/workspace/travel/cross-domain audits remaining.
- [~] **Phase 3** — Per-suite migration. BasePolicy cross-cutting migrated (commit 31d1ace). c-3162-dispatch-wrap landed (commit 618a6ae). Records v2.x already in place across all four suites (verified via `mlld validate`). Tier-2 scripted-LLM security tests pass in all four suites + defense-load-bearing parity prototypes added per-suite (commits 5443118, 6e76a18). Worker LLM gate 24/24 (migrator-9 verification).
- [ ] **Phase 4** — Full sweep + ship

**Branch**: `policy-structured-labels-migration` on `clean@0cd3d8c`. Base `clean@096bcd2`. mlld source `~/mlld/mlld @ f90d47e77` (`policy-redesign`).

**Zero-LLM gate**: GREEN (264 pass / 0 fail / 2 xfail / 2 xpass-pending-flip). c-3162-dispatch-wrap landed (migrator-9): `@dispatchExecute` body split into outer direct-when wrapper + inner `@dispatchExecuteImpl`. Outer wrapper catches labels-flow throws via `denied =>` and surfaces structured envelope `{ ok:false, error:"policy_denied", code, message, ... }` that `@toolCallError` handles uniformly. `tests/rig/phase-error-envelope.mld` temporarily disabled pending mlld ticket `m-input-policy-uncatchable` (input-validation throws bypass denied-event channel on policy-redesign branch — see ticket).

**Scripted-LLM gate**: GREEN. Banking 14/14, slack 15/15 (+2 xfail), workspace 16/16, travel 12/12. Total 57 pass / 0 fail / 2 xfail. Defense-load-bearing parity prototypes per-suite prove the rig source-class firewall (layer A) is defense-independent and that bypassing rig still hits mlld input-record validation (layer B), per [[security-test-parity]] discipline.

**Worker LLM gate**: GREEN. 24/24 (extract 11/11 + derive 7/7 + compose 6/6), wall 28s on Sonnet (migrator-9, 2026-05-14).

**Bench utility**: 53/97 baseline (migrator-7 sweep 2026-05-12, runs `25710915492` et al). No new sweep this session.

**Mark inventory** (Phase 1 sec-doc maturity, 5-mark scheme):

| Doc | [T] | [-] | [?] | [!] | [ ] |
|---|---|---|---|---|---|
| sec-banking | 0 | 11 | 22 | 1 | 3 |
| sec-slack | 5 | 40 | 16 | 5 | 4 |
| sec-workspace | 0 | 60 | 22 | 20 | 7 |
| sec-travel | 16 | 26 | 9 | 4 | 2 |
| sec-cross-domain | 0 | 6 | 3 | 1 | 6 |

---

## Phase 0 — Setup ✅

- [x] Commit current `clean/` state (5 thematic commits).
- [x] Verify `.claude/skills/migrate/SKILL.md` current.
- [x] Verify `MIGRATION-PLAN.md` describes target architecture.
- [x] Verify `SEC-HOWTO.md` reflects 5-mark scheme + ticket-anchoring + citation hygiene.
- [x] Create migration branch `policy-structured-labels-migration`. Source/clean SHAs recorded.

---

## Phase 1 — sec-doc authoring ✅

- [x] **sec-banking.md** — 10-section template, 5-mark scheme, no coverage roll-up. 19 BK-* tickets filed.
- [x] **sec-slack.md** — URL-promotion + channel-name firewall primitives. 5 attack classes (A-E). 10 SL-* tickets.
- [x] **sec-workspace.md** — §6 frames SHOULD-FAIL as architectural per c-d0e3. Typed-instruction-channel + extract-driven laundering classes. WS-* tickets.
- [x] **sec-travel.md** — advice-gate three-node tree in §8. 16 `[T]` marks cite real test files. Most mature. TR-* tickets.
- [x] **sec-cross-domain.md** — XS-* tickets from each suite §9 deferred.

---

## Phase 2 — Audit current state against sec-*.md

Walk every `[-]` and `[?]` claim across the 5 sec-docs. Probe each in `tmp/audit-<suite>/`. Outcomes: probe confirms → keep `[-]` with citation, or promote to `[T]` if test exists; probe shows gap → file ticket + mark `[!]` (mlld-side gaps go to `~/mlld/mlld/.tickets/m-XXXX`); zero-LLM-impossible → defer to tier-2 in Phase 3.d.

- [x] **Audit sec-banking.md** — 16 marks promoted [?]/[-] → [T] in commit 24eda3d via tier-2 scripted-LLM tests in `tests/scripted/security-banking.mld` + `security-banking-parity.mld`. 6 threat tickets closed. Remaining [?] are propagation/projection invariants observable indirectly through the [T]-locked layers (BK-untrusted-subject-runtime-verify, BK-file-content-runtime-verify, BK-display-projection-verify, BK-influenced-prop-verify) — each needs a direct tier-1 probe to upgrade. Sec-doc commit-citation discipline applied throughout.
- [ ] **Audit sec-slack.md** — 56 marks (40 `[-]` + 16 `[?]`). Apply banking pattern: cite `tests/scripted/security-slack.mld` + `security-slack-parity.mld` for the [T]-promotable marks. Remaining propagation [?] marks need tier-1 probes.
- [ ] **Audit sec-workspace.md** — 82 marks (60 `[-]` + 22 `[?]`). Apply banking pattern: cite `tests/scripted/security-workspace.mld` + `security-workspace-parity.mld`.
- [ ] **Audit sec-travel.md** — 35 marks (26 `[-]` + 9 `[?]`). Re-verify the 16 existing `[T]` marks survive v2.x label changes (cite current test files). Add citations from `tests/scripted/security-travel.mld` + `security-travel-parity.mld` to upgrade declared [-] marks.
- [ ] **Cross-suite spot check on sec-cross-domain.md** — 9 marks. Probe at least one scenario per cross-suite attack class.

**Exit criteria**: no orphan `[-]` claims (every `[-]` has probe-path + commit-SHA citation); every gap is `[!]` with ticket. Phase 2 produces the gap list driving Phase 3.b records redraft.

---

## Phase 3 — Per-suite migration

Order: **banking → slack → workspace → travel.** Don't start the next suite until current suite's exit gate passes.

### 3.c BasePolicy cross-cutting ✅ (commit 31d1ace)

- [x] `rig/orchestration.mld @synthesizedPolicy` re-authored against v2.x schema — imports `@standard` + `@urlDefense` from `@mlld/policy`, produces new-schema data shape directly. Probes confirmed `@policy.build` accepts data-shape basePolicy without requiring `policy @p = union(...)` at module scope (`union()` is module-scope-only, not valid in exe bodies — verified via `tmp/policy-spike/probe-union-in-exe.mld`).
- [x] `rig/workers/advice.mld` → `union(@noInfluencedAdvice)` import.
- [x] Rig overlay preserves additive widening of `labels.rules.influenced.deny` (`+["destructive","exfil"]` atop `@standard`'s `["advice"]`) and `trusted_tool_output` / `user_originated` `satisfies` transitional alias.
- [x] `tests/rig/policy-build-catalog-arch.mld` re-asserts against new schema (20/20).
- [x] **c-3162-dispatch-wrap** (migrator-9) — `@dispatchExecute` split into outer direct-when wrapper + `@dispatchExecuteImpl` inner. `denied =>` arm at outer level catches labels-flow throws, converts to structured `{ ok:false, error:"policy_denied", code, message, reason, filter, decision, guard }` envelope. `tests/rig/c-3162-dispatch-denial.mld` 2/2 pass. Probe trail: `tmp/c-3162-dispatch-wrap/probe-{influenced-deny,with-policy-inline,bracket-block,exe-wraps-dispatch}.mld`. Constraint discovered: input-validation throws (`input_type_mismatch`, `proofless_control_arg`, etc.) do NOT raise denied events on policy-redesign branch — filed mlld `m-input-policy-uncatchable`. `tests/rig/phase-error-envelope.mld` disabled in index.mld pending fix.

### Suite 1: Banking

- [x] **3.a Tools punch list** — `bench/domains/banking/tools.mld` validates v2.x compliant (mlld validate clean). Read/write tool split + labels + input record references intact.
- [x] **3.b Records redraft** — `bench/domains/banking/records.mld` already in v2.x shape (`facts:`/`data:{trusted,untrusted}`/`refine [...]`/`validate:strict`/`update:`/`exact:`/`correlate:`). Validates clean.
- [x] **3.c BasePolicy** — covered cross-cutting.
- [x] **3.d Test lockdown** — 10 tier-2 tests in `tests/scripted/security-banking.mld` + 4 tier-2 parity tests in `tests/scripted/security-banking-parity.mld`. All 14 pass. Layer A (rig firewall), layer B (input record validation), layer C (record-write-deny) each test-locked. sec-banking.md marks promoted to [T] in commit 24eda3d.
- [x] **3.e Verification** — zero-LLM gate 264/0/2xf/2xp ✓; worker LLM 24/24 ✓; tier-2 security gate 14/14 ✓. **Pending**: local probe `user_task_3 4 6 11`; `scripts/bench-attacks.sh single direct banking` at 0 ASR (heavy; defer to Phase 4 sweep).
- [~] **3.f Suite exit gate** — load-bearing structural defenses [T]-locked. Remaining [?] (propagation/projection invariants) are observable side-effects of the [T]-locked layers. Bench-side attack canary deferred to Phase 4.

### Suite 2: Slack

- [x] **3.a Tools punch list** — `bench/domains/slack/tools.mld` validates v2.x compliant.
- [x] **3.b Records redraft** — `bench/domains/slack/records.mld` already v2.x. Validates clean.
- [x] **3.c BasePolicy** — covered cross-cutting (URL defense engages via `@hasNovelUrlRisk` and `@noNovelUrl` resolution via execute.mld import per c-3162 follow-up).
- [x] **3.d Test lockdown** — 13 tier-2 tests in `tests/scripted/security-slack.mld` (+2 xfail) + 2 tier-2 parity tests in `tests/scripted/security-slack-parity.mld`. All 15 pass.
- [x] **3.e Verification** — zero-LLM ✓; worker LLM ✓; tier-2 security 15/15 ✓. **Pending**: `scripts/bench-attacks.sh single direct slack` at 0 ASR (Phase 4).
- [ ] **3.f Suite exit gate** — sec-slack.md marks still pending bulk-promote against tests/scripted/security-slack.mld.

### Suite 3: Workspace

- [x] **3.a Tools punch list** — `bench/domains/workspace/tools.mld` validates v2.x compliant.
- [x] **3.b Records redraft** — `bench/domains/workspace/records.mld` validates clean.
- [x] **3.c BasePolicy** — covered cross-cutting.
- [x] **3.d Test lockdown** — 14 tier-2 tests in `tests/scripted/security-workspace.mld` + 2 tier-2 parity tests in `tests/scripted/security-workspace-parity.mld`. All 16 pass. Layer-attribution fixed in commit 5443118 (extract empty response defense accepts either rig-level or mlld validate:strict layer code).
- [x] **3.e Verification** — zero-LLM ✓; worker LLM ✓; tier-2 security 16/16 ✓. **Pending**: workspace attack canary (Phase 4). Splits in half (-a/-b) for memory headroom.
- [ ] **3.f Suite exit gate** — sec-workspace.md marks still pending bulk-promote.

### Suite 4: Travel

- [x] **3.a Tools punch list** — `bench/domains/travel/tools.mld` validates v2.x compliant. Classifier surface intact.
- [x] **3.b Records redraft** — `bench/domains/travel/records.mld` validates clean.
- [x] **3.c BasePolicy** — covered cross-cutting + advice-gate-specific (`union(@noInfluencedAdvice)`).
- [x] **3.d Test lockdown** — 10 tier-2 tests in `tests/scripted/security-travel.mld` + 2 tier-2 parity tests in `tests/scripted/security-travel-parity.mld`. All 12 pass. Travel's existing 16 `[T]` marks need a sec-doc citation refresh against the current test files.
- [x] **3.e Verification** — zero-LLM ✓; worker LLM ✓; tier-2 security 12/12 ✓. **Pending**: IT6 advice-gate canary (Phase 4).
- [ ] **3.f Suite exit gate** — sec-travel.md marks still pending citation refresh.

---

## Phase 4 — Full sweep + whack-a-mole reconciliation + ship

### 4.a Whack-a-mole reconciliation (MIGRATION-PLAN.md Phase 7)

Walk each commit. Record disposition: `no-op` / `test-only` / `refactor-invariant` / `merge-code`. Dispositions go in the migration PR message.

mlld-side commits, likely superseded by construction:
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

mlld-side commits, partially superseded; keep invariant tests:
- [ ] `4a27abee4` influenced cascade near-miss invariants
- [ ] `dfa8d5c1b` influenced cascade narrowed to provenance evidence
- [ ] `f3dd43663` `src:file` data-load and code-exec routing split
- [ ] `7d7399dbc` session-seeded shelf bridge writes
- [ ] `8b1c43576` untrusted LLM influenced rule on payload/nested exe blocks

Bench-side commits, should become unnecessary under v2.x:
- [ ] `096bcd2` elevate `@deriveAttestation.payload` to `data.trusted` — verify redundant under spec-label-structure §2.4 LLM-pass invariants.
- [ ] `f168037` banking sender refinement to trusted fields — same verification.

### 4.b Full sweep + ship gate

- [ ] **Full benign sweep** `scripts/bench.sh` — utility ≥78/97 (target 81/97). Per-task set-diff vs baseline (sweep `25710915492` et al, 2026-05-12) — set-diff required, total count alone hides offset regressions.
- [ ] **Full attack matrix** `scripts/bench-attacks.sh` — 30 jobs (6 attacks × 5 sub-suites), 0 ASR per pairing.
- [ ] **Docs final pass** — STATUS.md updated; HANDOFF.md closure; sec-*.md marks final (no `[?]`, every `[!]` linked to open ticket).
- [ ] **Archive obsolete artifacts** — `*.threatmodel.txt` + `*.taskdata.txt` to `archive/`; `MIGRATION-PLAN.md` + this file to `archive/` after merge; triage `.tickets/review/`.

### Ship gate (all required)

- [ ] Zero-LLM gate 100%.
- [ ] Worker LLM gate 24/24.
- [ ] Utility ≥78/97 on full benign sweep.
- [ ] 0 ASR across full 6×5 attack matrix.
- [ ] sec-*.md marks final: no `[?]`, every `[!]` ticketed.
- [ ] Phase 7 reconciliation documented in PR message.
- [ ] Branch merged per MIGRATION-PLAN.md "Merge Guidance."
