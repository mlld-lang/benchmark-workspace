# MIGRATION-TASKS.md — v2.x structured-labels + policy-redesign migration

Temporary task tracker for the v2.x migration. Lives until migration ships, then archived. **Read `.claude/skills/migrate/SKILL.md` first** (the migrate skill) — this doc tracks WHAT; the skill governs HOW.

**Acceptance gate**: utility ≥78/97 (target 81/97) **AND** 0 ASR across full 6×5 attack matrix. Both required for ship.

**Stop-conditions**: probe shows mlld bug → file `~/mlld/mlld/.tickets/m-XXXX` with the probe attached, wait. Bench schemas drift off v2.x target → re-think the change. Don't workaround unless small + on-target.

## Status

- [x] **Phase 0** — Setup (commits 3737ea6, 062285e, f8232ad, 93036ea, 48bc93e on policy-structured-labels-migration)
- [~] **Phase 3 cross-cutting** — BasePolicy synthesis migrated to new v2.x schema (commit 31d1ace). Imports `@standard` + `@urlDefense` from `@mlld/policy`, produces new-schema data shape directly. `rig/workers/advice.mld` migrated to `union(@noInfluencedAdvice)`. Spike probes in `tmp/policy-spike/`. Test failure surfaced + ticketed at c-3162-dispatch-wrap (commit 5a03de1).
- [x] **Phase 1** — sec-doc authoring (4 suites + cross-domain): all 5 docs landed + verified per SEC-HOWTO discipline (10-section template, 5-mark scheme, ticket-anchored, no coverage roll-up). 55 threat tickets filed in `.tickets/threats/`. Mark inventory:
  - sec-banking: 0 [T] / 11 [-] / 22 [?] / 1 [!] / 3 [ ]
  - sec-slack: 5 [T] / 40 [-] / 16 [?] / 5 [!] / 4 [ ]
  - sec-workspace: 0 [T] / 60 [-] / 22 [?] / 20 [!] / 7 [ ]
  - sec-travel: 16 [T] / 26 [-] / 9 [?] / 4 [!] / 2 [ ]
  - sec-cross-domain: 0 [T] / 6 [-] / 3 [?] / 1 [!] / 6 [ ]
- [ ] **Phase 2** — Audit current state against sec-*.md
- [ ] **Phase 3** — Per-suite migration (banking → slack → workspace → travel)
- [ ] **Phase 4** — Full sweep + ship

**Baseline state** (migrator-8, session start 2026-05-14):
- Migration branch: `policy-structured-labels-migration`, base `clean@096bcd2`
- mlld source: `~/mlld/mlld` @ `f90d47e77` (policy-redesign), runtime built includes the v2.x retirement
- Zero-LLM gate at session end: **YELLOW** — BasePolicy syntax migrated, 20/20 policy-build tests pass, c-3162-dispatch-denial fails because defense correctly fires but throw not wrapped (ticket c-3162-dispatch-wrap filed for follow-up). Other tests likely have similar shape issues to surface in next pass.

---

## Phase 0 — Setup

- [x] Commit current `clean/` state (5 commits on migration branch).
- [x] Verify `.claude/skills/migrate/SKILL.md` reflects current architecture (read this session; current).
- [x] Verify `MIGRATION-PLAN.md` still describes the target architecture as implemented on mlld `policy-redesign` branch (verified — Phases 0-8 match spec).
- [x] Verify `SEC-HOWTO.md` reflects the five-mark scheme + ticket-anchoring + citation-hygiene rules (verified — 411 lines, 10-section template + 5-mark scheme + ticket-anchoring + tier-3 sweeps excluded from [T]).
- [x] Create migration branch `policy-structured-labels-migration` per `MIGRATION-PLAN.md` Phase 0. Source/clean SHAs recorded above.

**Exit criteria**: clean/ on dedicated migration branch; specs + skill + plan + howto + tasks file all current. ✅

---

## Phase 1 — sec-doc authoring

Output target: 5 docs (`sec-{banking,slack,workspace,travel}.md` + `sec-cross-domain.md`). Each on the SEC-HOWTO template.

- [x] **sec-banking.md** — 10-section template, 5-mark scheme, no coverage roll-up, 19 tickets filed in `.tickets/threats/`. §5 matrix uses STRUCTURAL BLOCK / STRUCTURAL BLOCK (pending verify) honestly per c-6935 audit boundary.
- [x] **sec-slack.md** — load-bearing primitives: URL promotion + channel-name firewall. §8 has 5 attack classes (A: novel-URL exfil; B: webpage-content-as-instruction laundering; C: invite/DM spoofing; D: tier-2 contact substitution; E: tier-3 web-beacon).
- [x] **sec-workspace.md** — §6 frames SHOULD-FAIL as architectural decisions per c-d0e3 class. §8 organized around typed-instruction-channel refusal + extract-driven laundering. 20 [!] marks reflect the suite's threat-surface immaturity (the most pending-fix tickets of any suite).
- [x] **sec-travel.md** — advice-gate three-node tree in §8 (classifier routes → role:advice projection → no-influenced-advice policy + fact-only fallback). 16 [T] marks tied to `tests/rig/advice-gate.mld` + `tests/bench/travel-classifier-labels.mld` + `tests/scripted/security-travel.mld` cases. Most mature sec-doc.
- [x] **sec-cross-domain.md** — XS-* tickets from each suite §9 deferred. Aggregates flavors: cross-suite-applicable defenses (testable today) vs genuine cross-suite scenarios (speculative until cross-suite agents exist).

**Exit criteria** ✅: 5 sec-docs, each passing the SEC-HOWTO calibration check.

---

## Phase 2 — Audit current state against sec-*.md

For each sec-doc, walk every `[-]` (declared + verified) and `[?]` (declared, unverified) claim. Probe each. Convert findings to one of three outcomes per claim:

1. Probe confirms the defense fires → `[-]` stays with probe citation, or promote to `[T]` if you also write the test (Phase 3 work — defer if not zero-LLM-able now).
2. Probe shows gap → file ticket, mark `[!]` with ticket id inline. If gap is mlld-side, file in `~/mlld/mlld/.tickets/` with the probe attached.
3. Defense can't be exercised zero-LLM → defer to Phase 3 as tier-2 scripted-LLM test.

- [ ] **Audit sec-banking.md** — every `[-]` and `[?]` from §5 matrix + §8 trees.
  - [ ] Spike each defense claim. Write probes in `tmp/audit-banking/`.
  - [ ] File tickets for any gaps found. Mark `[!]` inline.
  - [ ] Update sec-banking.md marks with probe citations.
- [ ] **Audit sec-slack.md** — same shape; probes in `tmp/audit-slack/`.
- [ ] **Audit sec-workspace.md** — same shape; probes in `tmp/audit-workspace/`.
- [ ] **Audit sec-travel.md** — same shape; probes in `tmp/audit-travel/`.
- [ ] **Cross-suite spot check on sec-cross-domain.md** — probe at least one scenario per cross-suite attack class.

**Exit criteria**: no orphan `[-]` claims in any sec-doc; every `[-]` has a probe-and-commit-sha citation; every gap surfaced as `[!]` with ticket. Phase 2 produces the gap list that drives Phase 3 records redraft.

---

## Phase 3 — Per-suite migration

Order: **banking → slack → workspace → travel**. Don't start the next suite until the current suite's exit gate passes.

For each suite, the work is:

```
3.a Tools punch list against sec-doc §3.
3.b Records redraft against v2.x channel grammar.
3.c BasePolicy fragments draft.
3.d Test lockdown (spike-then-test → tier-1/tier-2).
3.e Verification (gates + canaries).
3.f Suite exit gate.
```

### Suite 1: Banking

- [ ] **3.a Tools punch list**
  - [ ] Read `bench/domains/banking/tools.mld` against sec-banking.md §3.
  - [ ] Identify any tool whose declaration doesn't match sec-doc claims (control args, payload args, labels, instructions).
  - [ ] Punch list lives in this doc as sub-bullets here; tick off as resolved.
- [ ] **3.b Records redraft**
  - [ ] For each record in `bench/domains/banking/records.mld` (output + input):
    - [ ] Map current declarations to new schema (mx.trust / mx.influenced / mx.labels / mx.factsources).
    - [ ] Apply `refine` actions under the v2.x grammar (per spec-label-structure §2 + records subsection).
    - [ ] Apply `facts:` / `data.trusted:` / `data.untrusted:` per sec-banking.md §4.
    - [ ] Spike each declaration: write probe in `tmp/records-banking/`; verify labels match sec-doc claim post-coerce.
    - [ ] Iterate until probe matches sec-doc.
  - [ ] Commit records.mld with comments citing sec-banking.md row per declaration.
- [x] **3.c BasePolicy fragments** (cross-suite — banking inherits via rig/orchestration.mld)
  - [x] rig synthesizes a new-schema basePolicy importing `@standard` + `@urlDefense` from `@mlld/policy` (commit 31d1ace).
  - [x] Advice gate uses `@noInfluencedAdvice` fragment (commit 31d1ace).
  - [ ] Banking-specific override (if any) — none required currently; bench agents pass no `overrides.policy`.
- [ ] **3.d Test lockdown**
  - [ ] For each `[?]` mark in sec-banking.md that should land as `[T]`:
    - [ ] Promote spike to tier-1 test (`tests/rig/<file>.mld`, registered in `tests/index.mld`) OR tier-2 test (`tests/run-scripted.py` suite).
    - [ ] Update sec-banking.md mark to `[T]` with test file + case-name citation.
  - [ ] Verify zero-LLM gate green after each test addition.
- [ ] **3.e Verification**
  - [ ] Zero-LLM gate: `mlld tests/index.mld --no-checkpoint` → 100% pass.
  - [ ] Worker LLM gate: `mlld tests/live/workers/run.mld --no-checkpoint` → 24/24 (if prompts changed).
  - [ ] Local probe canonical banking tasks: `uv run --project bench python3 src/run.py -s banking -d defended -t user_task_3 user_task_4 user_task_6 user_task_11 -p 4`. Expected recoveries vs prior baseline.
  - [ ] Banking attack canary: `scripts/bench-attacks.sh single direct banking` → 0 ASR.
  - [ ] Banking attack canary: `scripts/bench-attacks.sh single important_instructions banking` → 0 ASR (if applicable).
- [ ] **3.f Suite exit gate**
  - [ ] sec-banking.md marks: zero orphan `[?]`. Every mark is `[-]` + citation or `[T]` + test or `[!]` + ticket.
  - [ ] Zero-LLM gate green.
  - [ ] Banking utility ≥ baseline + expected recoveries.
  - [ ] Banking attack canaries at 0 ASR.
  - [ ] Commit + push.

### Suite 2: Slack

- [ ] **3.a Tools punch list** (see banking template)
- [ ] **3.b Records redraft** (probes in `tmp/records-slack/`)
- [ ] **3.c BasePolicy fragments** (probes in `tmp/policy-slack/`)
  - [ ] URL-defense fragment from `@mlld/policy/url-defense` (or equivalent — verify name per spec-policy library)
  - [ ] Channel-name firewall: per-tool known-text constraint
- [ ] **3.d Test lockdown** — all `[?]` → `[T]` where feasible
- [ ] **3.e Verification**
  - [ ] Standard gates
  - [ ] Slack attack canaries: `direct` + `important_instructions` → 0 ASR
- [ ] **3.f Suite exit gate** (same shape as banking)

### Suite 3: Workspace

- [ ] **3.a Tools punch list**
- [ ] **3.b Records redraft** (probes in `tmp/records-workspace/`)
- [ ] **3.c BasePolicy fragments** (probes in `tmp/policy-workspace/`)
- [ ] **3.d Test lockdown** — particular attention to typed-instruction-channel refusal (SHOULD-FAIL paths)
- [ ] **3.e Verification**
  - [ ] Standard gates
  - [ ] Workspace attack canaries: applicable variants → 0 ASR
- [ ] **3.f Suite exit gate**

### Suite 4: Travel

- [ ] **3.a Tools punch list**
- [ ] **3.b Records redraft** (probes in `tmp/records-travel/`)
- [ ] **3.c BasePolicy fragments** (probes in `tmp/policy-travel/`)
  - [ ] Advice gate: `no-influenced-advice` policy rule, `role:advice` projection, fact-only fallback
- [ ] **3.d Test lockdown** — particular attention to advice-gate three-node tree
- [ ] **3.e Verification**
  - [ ] Standard gates
  - [ ] Travel attack canaries: IT6 (recommendation hijack) → 0 ASR
- [ ] **3.f Suite exit gate**

---

## Phase 4 — Full sweep + ship

- [ ] **Full benign sweep**: `scripts/bench.sh`
  - [ ] Total utility ≥78/97 (target 81/97).
  - [ ] Per-suite breakdown matches projected recoveries.
  - [ ] Per-task set-diff vs baseline: identify any unexpected regressions.
- [ ] **Full attack matrix sweep**: `scripts/bench-attacks.sh` (all 6 attack variants × 5 sub-suites).
  - [ ] 0 ASR per (suite × attack-variant) pairing.
- [ ] **Whack-a-mole reconciliation** (MIGRATION-PLAN.md Phase 7):
  - [ ] Walk each listed commit. Record disposition: `no-op` / `test-only` / `refactor-invariant` / `merge-code`.
  - [ ] Commit dispositions in migration PR message.
- [ ] **Docs final pass**:
  - [ ] STATUS.md updated with post-migration per-task classifications.
  - [ ] HANDOFF.md updated with migration completion + next-session pointer.
  - [ ] sec-*.md marks final state (all `[-]` or `[T]`, no `[?]`, all `[!]` linked to open tickets).
- [ ] **Archive obsolete artifacts**:
  - [ ] Move `*.threatmodel.txt` to `archive/`.
  - [ ] Move `*.taskdata.txt` to `archive/` (if still in root).
  - [ ] Move `MIGRATION-PLAN.md` and this file (`MIGRATION-TASKS.md`) to `archive/` after merge.

**Ship gate**: zero-LLM 100%, worker LLM 24/24, utility ≥78/97 (target 81), 0 ASR across 6×5 matrix, sec-*.md marks final, MIGRATION-PLAN.md Phase 7 reconciliation documented.

---

## Open issues / blockers

Track here as they surface during migration. Each entry: short description + ticket id + mitigation/wait status.

(none yet — will accumulate as migration proceeds)

---

## Discovered punch lists

Per-suite tool / records / policy punch lists go here, surfaced during Phase 3.a / 3.b / 3.c. Each entry should be small enough to resolve in one commit.

### Banking
(populated during Phase 3 banking)

### Slack
(populated during Phase 3 slack)

### Workspace
(populated during Phase 3 workspace)

### Travel
(populated during Phase 3 travel)
