# MIGRATION-TASKS.md — v2.x structured-labels + policy-redesign migration

Temporary task tracker for the v2.x migration. Lives until migration ships, then archived. **Read `.claude/skills/migrate/SKILL.md` first** (the migrate skill) — this doc tracks WHAT; the skill governs HOW (spike-then-test rhythm, three-tier separation, negative discipline rules).

**Acceptance gate**: utility ≥78/97 (target 81/97) **AND** 0 ASR across full 6×5 attack matrix. Both required for ship.

**Stop-conditions**: probe shows mlld bug → file `~/mlld/mlld/.tickets/m-XXXX` with the probe attached, wait. Bench schemas drift off v2.x target → re-think the change. Don't workaround unless small + on-target.

## Status

- [x] **Phase 0** — Setup (commits 3737ea6, 062285e, f8232ad, 93036ea, 48bc93e)
- [x] **Phase 1** — sec-doc authoring (5 docs landed, SEC-HOWTO-compliant, 55 threat tickets in `.tickets/threats/`)
- [~] **Phase 2** — Audit current state against sec-*.md (probe-infrastructure ready at `tmp/policy-spike/`; per-suite audits not started)
- [~] **Phase 3** — Per-suite migration (cross-cutting BasePolicy migrated at commit 31d1ace; per-suite records redraft pending)
- [ ] **Phase 4** — Full sweep + ship

**Branch**: `policy-structured-labels-migration` on `clean@0cd3d8c`. Base `clean@096bcd2`. mlld source `~/mlld/mlld @ f90d47e77` (`policy-redesign`).

**Zero-LLM gate**: YELLOW. BasePolicy syntax migrated, `tests/rig/policy-build-catalog-arch.mld` passes 20/20 isolated. `tests/rig/c-3162-dispatch-denial.mld` fails because new `labels.rules.influenced.deny` correctly fires but throw not wrapped in `@dispatchExecute` — ticket **c-3162-dispatch-wrap** is the P0 next-session unblocker.

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

- [ ] **Audit sec-banking.md** — 33 marks (11 `[-]` + 22 `[?]`). Probes in `tmp/audit-banking/`.
- [ ] **Audit sec-slack.md** — 56 marks (40 `[-]` + 16 `[?]`). Probes in `tmp/audit-slack/`.
- [ ] **Audit sec-workspace.md** — 82 marks (60 `[-]` + 22 `[?]`). Probes in `tmp/audit-workspace/`.
- [ ] **Audit sec-travel.md** — 35 marks (26 `[-]` + 9 `[?]`). Probes in `tmp/audit-travel/`. Re-verify the 16 existing `[T]` marks survive v2.x label changes.
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
- [ ] **c-3162-dispatch-wrap** — wrap `@callToolWithPolicy` in `@dispatchExecute` with `when [denied => ...]` arm. P0. Reference: `mlld-security-fundamentals.md` §3.8 + `rig/workers/advice.mld:110` (`@adviceGate` pattern).

### Suite 1: Banking

- [ ] **3.a Tools punch list** — walk `bench/domains/banking/tools.mld` against `sec-banking.md §3`.
- [ ] **3.b Records redraft** — `bench/domains/banking/records.mld` against `sec-banking.md §4` + v2.x channel grammar. Apply `refine [...]` per MIGRATION-POLICY-REDESIGN.md §"Record refine". Probes in `tmp/records-banking/`.
- [x] **3.c BasePolicy** — covered cross-cutting.
- [ ] **3.d Test lockdown** — promote `[?]` to `[T]` via tier-1 (`tests/rig/`) or tier-2 (`tests/scripted/security-banking.mld`). Tier-3 sweeps don't lock.
- [ ] **3.e Verification** — zero-LLM gate green; worker LLM 24/24; local probe `user_task_3 4 6 11`; `scripts/bench-attacks.sh single direct banking` at 0 ASR.
- [ ] **3.f Suite exit gate** — zero orphan `[?]` in sec-banking; banking utility ≥ baseline + expected recoveries; attack canaries 0 ASR.

### Suite 2: Slack

- [ ] **3.a Tools punch list** against `sec-slack.md §3`.
- [ ] **3.b Records redraft** (probes in `tmp/records-slack/`).
- [x] **3.c BasePolicy** — covered cross-cutting (URL defense engages via `@hasNovelUrlRisk`).
- [ ] **3.d Test lockdown** — particular attention: `@noUntrustedUrlsInOutput` regression-lock.
- [ ] **3.e Verification** — standard gates + slack canaries (`atk_direct`, `atk_important_instructions`, `atk_injecagent`). Slack canary already 0/105 ASR per sweep `25708270888`/`25708271819` — verify holds post-v2.x.
- [ ] **3.f Suite exit gate**.

### Suite 3: Workspace

- [ ] **3.a Tools punch list** against `sec-workspace.md §3`.
- [ ] **3.b Records redraft** (probes in `tmp/records-workspace/`). Particular attention to `@email.role:planner` projection stripping body.
- [x] **3.c BasePolicy** — covered cross-cutting.
- [ ] **3.d Test lockdown** — tier-1 tests for typed-instruction-channel refusal (UT13/UT19/UT25 c-d0e3 class).
- [ ] **3.e Verification** — standard gates + workspace canaries. Splits in half (-a/-b) for memory headroom.
- [ ] **3.f Suite exit gate**.

### Suite 4: Travel

- [ ] **3.a Tools punch list** against `sec-travel.md §3` — incl. classifier surface.
- [ ] **3.b Records redraft** (probes in `tmp/records-travel/`).
- [x] **3.c BasePolicy** — covered cross-cutting + advice-gate-specific (`union(@noInfluencedAdvice)`).
- [ ] **3.d Test lockdown** — re-verify travel's 16 `[T]` marks survive v2.x label changes (`tests/rig/advice-gate.mld`, `tests/scripted/security-travel.mld`, `tests/bench/travel-classifier-labels.mld`).
- [ ] **3.e Verification** — standard gates + IT6 (recommendation hijack) 0 ASR.
- [ ] **3.f Suite exit gate**.

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
