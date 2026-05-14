# MIGRATION-TASKS.md — v2.x structured-labels + policy-redesign migration

Temporary task tracker for the v2.x migration. Lives until migration ships, then archived. **Read `.claude/skills/migrate/SKILL.md` first** (the migrate skill) — this doc tracks WHAT; the skill governs HOW.

**Acceptance gate**: utility ≥78/97 (target 81/97) **AND** 0 ASR across full 6×5 attack matrix. Both required for ship.

**Stop-conditions**: probe shows mlld bug → file `~/mlld/mlld/.tickets/m-XXXX` with the probe attached, wait. Bench schemas drift off v2.x target → re-think the change. Don't workaround unless small + on-target.

## Status

- [ ] **Phase 0** — Setup
- [ ] **Phase 1** — sec-doc authoring (4 suites + cross-domain)
- [ ] **Phase 2** — Audit current state against sec-*.md
- [ ] **Phase 3** — Per-suite migration (banking → slack → workspace → travel)
- [ ] **Phase 4** — Full sweep + ship

---

## Phase 0 — Setup

- [ ] Commit current `clean/` state (handoff captured).
- [ ] Verify `.claude/skills/migrate/SKILL.md` reflects current architecture (read after every major spec update).
- [ ] Verify `MIGRATION-PLAN.md` still describes the target architecture as implemented on mlld `policy-redesign` branch.
- [ ] Verify `SEC-HOWTO.md` reflects the five-mark scheme + ticket-anchoring + citation-hygiene rules.
- [ ] Create migration branch `policy-structured-labels-migration` per `MIGRATION-PLAN.md` Phase 0. Record source/clean SHAs.

**Exit criteria**: clean/ on dedicated migration branch; specs + skill + plan + howto + tasks file all current.

---

## Phase 1 — sec-doc authoring

Output target: 5 docs (`sec-{banking,slack,workspace,travel}.md` + `sec-cross-domain.md`). Each on the SEC-HOWTO template.

- [ ] **sec-banking.md tightening** (v1 draft exists)
  - [ ] Drop §10 (status mirror); replace with one-line link to STATUS.md.
  - [ ] Drop §12 (migration notes); replace with one-line §9 entry pointing to MIGRATION-PLAN.md.
  - [ ] Drop §14 (audit signatures section); consolidate per-IT in §7.
  - [ ] Drop coverage roll-up table at end of §8.
  - [ ] Renumber to the 10-section template.
  - [ ] Re-read §5 matrix for status honesty post-this-session bug fixes.
  - [ ] Adopt the 5-mark scheme: `[ ]` / `[!]` / `[?]` / `[-]` / `[T]` with required citations.
  - [ ] Every `[ ]` / `[!]` / `[?]` has a linked ticket id inline. File tickets where missing.
  - [ ] Every `[-]` cites commit SHA or sweep run id.
  - [ ] Every `[T]` cites test file path + case name; verify the test is tier-1 or tier-2.
- [ ] **sec-slack.md** (write from scratch using existing `slack.threatmodel.txt` + `bench/domains/slack/` + current code)
  - [ ] Map §1-§7 from the template.
  - [ ] §8 organized around URL promotion + channel-name firewall as load-bearing primitives.
  - [ ] Defense classes: novel-URL exfil; webpage-content-as-instruction laundering; invite/DM spoofing via channel-name injection.
  - [ ] Apply 5-mark scheme with ticket-anchoring.
- [ ] **sec-workspace.md** (write from scratch using existing `workspace.threatmodel.txt` + current code)
  - [ ] Map §1-§7 from the template.
  - [ ] §6 frames SHOULD-FAIL tasks as architectural decisions, NOT status mirrors.
  - [ ] §8 organized around typed-instruction-channel refusal + extract-driven laundering.
  - [ ] Apply 5-mark scheme.
- [ ] **sec-travel.md** (write from scratch using existing `travel.threatmodel.txt` + current code)
  - [ ] Map §1-§7 from the template.
  - [ ] §8 includes the three-node advice-gate tree (classifier routes → `role:advice` projection → `no-influenced-advice` policy + fact-only fallback).
  - [ ] Apply 5-mark scheme.
- [ ] **sec-cross-domain.md** (write after the four single-suite docs surface deferred items in §9)
  - [ ] Aggregate cross-domain attack vectors from each suite's §9 deferred-question list.
  - [ ] §5 matrix lives at the cross-suite level.
  - [ ] §8 trees cover scenarios that span >1 suite.

**Exit criteria**: 5 sec-docs, each passing the SEC-HOWTO "would this doc let a records author re-write records.mld from scratch defending the documented threat surface, without re-reading the suite source?" calibration check.

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
- [ ] **3.c BasePolicy fragments**
  - [ ] Identify which `@mlld/policy/*` fragments banking imports (per spec-policy §5).
  - [ ] Identify which policy fragments banking authors locally (suite-specific).
  - [ ] Spike each fragment: probe in `tmp/policy-banking/`; verify fires on attack input + doesn't fire on legitimate.
  - [ ] Commit BasePolicy declaration with sec-banking.md citations.
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
