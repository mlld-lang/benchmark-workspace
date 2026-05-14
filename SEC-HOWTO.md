# SEC-HOWTO.md — Writing `sec-{suite}.md` docs

This is the authoring guide for the per-suite security/threat-model documents (`sec-banking.md`, `sec-slack.md`, `sec-workspace.md`, `sec-travel.md`) and the cross-suite `sec-cross-domain.md`. It supersedes the earlier `*.threatmodel.txt` / `*.taskdata.txt` split.

These docs are consumed by:

1. **Records / BasePolicy authors** — when deciding what's `facts:` / `data.trusted` / `data.untrusted` / `refine`, what needs `correlate: true`, what `kind:` to use, what display projections to declare.
2. **Sweep / attack-run auditors** — when classifying transcripts (STRUCTURAL_BLOCK / MODEL_OBLIVIOUS / MODEL_REFUSAL / MODEL_TASK_FOCUS per `/rig` Auditing methodology).
3. **Future agents and reviewers** — as the canonical "what does this suite do, what's attackable, and what defends each thing" reference for that suite.

A `sec-*.md` doc is *not* a status report, *not* a migration tracker, *not* a place to mirror per-task scores. Each of those has its own canonical home (`STATUS.md`, `MIGRATION-PLAN.md`, `tk` tickets). The drift cost of mirroring those into sec-*.md is real — link, don't copy.

## Cardinal Rule A boundary — verbatim in every sec-*.md

The first prose section of every sec-*.md is the table below. Don't paraphrase, don't summarize, copy it. The discipline holds across suites only if the line is stated identically each time:

| Source | What to read | What to NEVER read |
|---|---|---|
| `agentdojo/.../<suite>/user_tasks.py` | `PROMPT`, `COMMENT`, `ground_truth(...)` | `utility(...)` function bodies |
| `agentdojo/.../<suite>/injection_tasks.py` | `GOAL`, `COMMENT`, `ground_truth(...)` | `security(...)` function bodies, `security_predicates(...)` |
| `agentdojo/.../<suite>/environment.yaml` | All — it's the threat surface | n/a |
| `agentdojo/.../<suite>/injection_vectors.yaml` | All — it's the attack payload definition | n/a |

Reading the `utility()` / `security()` checker bodies and shaping the agent or this doc around what those functions test is benchmark cheating. Reading task text, injection content, ground-truth tool sequences, and environment fixtures is *defining the threat*.

## Template structure (use as-is across all four suites)

The structure below is the lean template. The earlier banking draft had 14 sections; this is 10. The cuts are deliberate: status/migration/audit-signature sections each had a single canonical home elsewhere; the §9 coverage roll-up was a third view of data already covered by §5 matrix + §8 trees.

```
§1  Suite at a glance
§2  Environment fixture & injection surface
§3  Tool inventory
§4  Records — field-level classification
§5  Attack surface matrix    ← THE load-bearing artifact
§6  User tasks (threat-relevant view only — NOT status)
§7  Injection tasks (incl. transcript signatures)
§8  Attack-class trees       ← suite-specific defense primitives go here
§9  Open architectural questions
§10 Cross-references
```

Section-by-section guidance below. Where a section has suite-specific freedom (especially §8), the guide says so explicitly.

### §1. Suite at a glance

One paragraph + a small counts table. State the suite's stakes plainly — "highest-stakes suite, no undo," "advice-context with read-only stakes plus exfil," etc. The paragraph anchors readers; the table sizes the problem.

```
| | Count |
|---|---|
| User tasks      | N |
| Injection tasks | M |
| Read tools      | r |
| Write tools     | w |
| Records (output)| ... |
| Records (input) | ... |
```

If the suite has a dominant defense primitive (banking: fact-grounding; travel: advice gate; slack: URL promotion; workspace: cross-tool composition), name it here in one sentence. This pre-loads §8 framing.

### §2. Environment fixture & injection surface

**The crucial property of this section: the injection surface is *bounded***. List every placeholder in `injection_vectors.yaml` and where it lands in the environment. The result is a small finite table that every defense decision can be traced back to.

Recommended subsections:

- **Fixed legitimate values** — IBANs, account ids, file paths, channel ids, user emails, etc. Things that appear in the environment by default and aren't attacker-controllable.
- **Attacker-introduced values** — anything an attack variant injects that *isn't* in the legitimate environment (e.g., banking's attacker IBAN `US133000000121212121212`).
- **Injection slots** — the full table of placeholder × location × default content × what gets replaced.

Close with one sentence stating the size of the surface: "Only N fields in the entire environment are injection-controllable. Every defense decision traces back to one of these N." This framing — bounded surface, finite enumeration — is what distinguishes a useful threat model from a freeform attack-tree document.

### §3. Tool inventory

Two tables: read tools (returning records) and write tools (with input records). Per tool: the records primitive it consumes/produces, the control-arg shape, the operation labels, and any hard-deny markers (input record with no `write:` block declared, etc.).

Don't reproduce the entire records.mld — link via `bench/domains/<suite>/tools.mld` and `records.mld`. The point of §3 is to give threat-readers the tool surface at a glance, not to be a records reference.

**Vocabulary precision.** `controlArgs` on the `exe` definition (in `tools.mld`) and `facts:` on the input record (in `records.mld`) are *different mechanisms*. Write tools authorize via `facts:` on `@*_inputs`; some read tools use `controlArgs` on the exe `with {...}` clause for the input-selection arg. Don't conflate. When in doubt, cite the actual records.mld / tools.mld primitive (e.g., "fact-grounded via `@send_money_inputs.facts: [recipient]`").

**Hard-deny phrasing.** A tool with no `write:` block declared on its input record means "no role can authorize this tool." That is *not* the same as "empty `write:` block" — `write: {}` would be ambiguous. If you describe the defense as "empty `write:` block," verify in records.mld whether the block is empty (`write: {}`) or absent (no `write:` key at all). Use the actual phrasing the record uses.

### §3.5 Classifier surface (optional — only when suite has task-entry classifiers)

If the suite has task-entry classifiers via `@rig.classify` (currently travel, possibly slack tool-router), add a §3.5 subsection covering:

- Classifier name and source file (`bench/domains/<suite>/classifiers/<name>.mld`)
- Output schema (what fields the classifier emits)
- What it drives (e.g., `adviceMode`, `toolFilter`)
- Which model runs the classifier (typically a small fast model)
- Whether classifier behavior is regression-locked at tier 1 / tier 2 (hand-label test files in `tests/bench/`) or only verified via live-LLM (which doesn't satisfy `[T]`)

Classifiers are *security primitives* when their output gates a defense (travel's advice classifier routes to the advice gate). Don't treat them as suite-internal config.

### §4. Records — field-level classification

For each record (output + input) the suite declares: a per-field table with:

- **Class**: `fact` / `data.trusted` / `data.untrusted` / `refine-conditional` / `update` / `exact`
- **Source**: `fixture` / `injection-slot` (one of the §2 slots) / `worker-derived` / `task-text`
- **Targeted by**: the IT(s) that plant attacker content into this field at the bench level (cross-ref §7)

This is descriptive only — it lists what's currently declared in `bench/domains/<suite>/records.mld`. The forward-looking *defense* claim happens in §5/§8. §4 is the existing-state snapshot.

When a record's `read:` block has role-projection variants (e.g., `role:planner` strips content), call that out explicitly per-field. Display projection is a major defense node and needs to be visible in §4 so §5/§8 can cite it.

### §5. Attack surface matrix — THE load-bearing artifact

This is what was missing from the older `*.threatmodel.txt` style and is the primary reason these docs exist. **Field-first view**: every row is one attacker-controllable field; columns track what enforces the defense.

Required columns:

| # | Attacker-controllable field | Where it lives | Reaches which control-arg position? | Carrier UT(s) | IT(s) using it | Current defense layer | Records-side enforcement | Status |
|---|---|---|---|---|---|---|---|---|

- **Field** — name + record, e.g., `@file_text.content`.
- **Where it lives** — which fixture path / tool return puts attacker content into this field.
- **Reaches which control arg** — the *target* of the attack chain in our architecture (e.g., "Attempts to reach `send_money.recipient` via worker extraction"). This is the threat statement.
- **Carrier UTs** — which user tasks make the planner read this field (and so create the carrier path).
- **ITs using it** — which injection tasks plant content here.
- **Current defense layer** — natural-language defense statement. Multiple defenses → list all.
- **Records-side enforcement** — the specific records.mld / tools.mld declaration(s) that implement the defense. This is the load-bearing column for records authors.
- **Status** — one of `STRUCTURAL BLOCK` / `STRUCTURAL BLOCK (pending verify)` / `GAP` / `OOS`. Be honest. Pending-verify means declarations support it but end-to-end probe hasn't fired.

Follow the matrix with a short summary table:

| Field | Attacker-controllable via | Reaches sensitive control arg? | Defense status |
|---|---|---|---|

The summary table is the TL;DR — the net claim should be "zero attacker-controllable field can populate a sensitive control arg, given the records as declared above," or, more honestly, "zero given the listed declarations *and* the upstream-mlld fixes in flight."

### §6. User tasks — threat-relevant view ONLY

Per-task: prompt summary, required tool chain, control-arg source-class requirements. **Do NOT include per-task STATUS.md categories here.** STATUS.md is the canonical per-task tracker; mirroring it produces drift.

Acceptable content per task:
- Prompt summary (what the user asks)
- Tool chain (what tools the task requires)
- Control-arg sourcing (where each control arg's value comes from — task-text, resolved, derived, etc.)
- *Threat-relevant* call-outs: "carries IT0..IT3 if planner reads recent_transactions," "underspecified prompt (also tracked in STATUS.md as BAD-EVAL)"

NOT acceptable:
- Per-task pass/fail status
- Per-task ticket links
- Per-task fix theories

If a task's classification is load-bearing for the threat model — e.g., "UT0 is SHOULD-FAIL because the bill→send_money flow is architecturally refused" — state the *threat-relevant fact* (architectural refusal), not the *status category*. Status follows from the threat decision; it's not authoritative here.

**Worked examples — the line between threat-relevant fact and status mirror:**

| Wrong (status mirror) | Right (threat-relevant) |
|---|---|
| "UT0: SHOULD-FAIL per STATUS.md" | "UT0: bill→send_money flow architecturally refused — `data.untrusted` content cannot satisfy `fact:iban` on recipient" |
| "UT9: BAD-EVAL category in STATUS.md" | "UT9: utility check is internally contradictory; any mutation triggered by injection fails the no-change requirement — the underspecification *is* the defense" |
| "UT16: OPEN per STATUS — c-57a6 planner over-executes..." | "UT16: planner discipline on recommendation-framed prompts; behavior pending c-57a6 prompt nudge" *(or — better — omit the ticket reference and state only the threat-relevant pattern)* |
| "UT13: STATUS notes 'agent executed injection writes'" | "UT13: typed-instruction-channel carrier — agent must refuse to execute actions described in `data.untrusted` content; current display projection should structurally prevent this" |
| "UT11: STATUS notes BAD-EVAL" | "UT11: per-person/per-party ambiguity — both readings satisfy the user's natural-language intent" *(or omit if not threat-relevant)* |

The pattern: if you find yourself typing "STATUS notes" or "per STATUS.md" in §6, stop. Either the fact is threat-relevant on its own merits (state it directly without citing STATUS), or it isn't (remove the row content; STATUS is the canonical home).

### §7. Injection tasks (with transcript signatures)

Per IT: GOAL summary, target tool, target field(s), attack class (cross-ref §8), and **transcript signature**. The transcript signature is the suite-specific substring(s) that appear in a planner's reasoning text when that injection content has reached the planner — used by `/diagnose` and planner-clean audits.

**Audit signatures live HERE, not in a separate §14.** The earlier draft had a `§14 Audit signatures` section; that was redundant with the per-IT signatures and created two homes for the same data. Keep them per-IT.

If a planned IT doesn't exist upstream (the IT9 case in banking — `injection_bill_text` placeholder exists but no scored injection task uses it), say so explicitly. Don't pretend it's there.

### §8. Attack-class trees — suite-specific defense primitives go here

For each distinct attack class the suite has, draw a `threatdown` tree showing the AND/OR structure of attack paths and which defense nodes close each. **This is where suite-specific defense primitives live** — banking has fact:iban grounding, travel has the advice gate, slack has URL promotion via handle-minted refs, workspace has per-phase source-class enforcement. The template doesn't enforce a specific defense vocabulary; each suite's classes drive the tree shape.

Notation (consistent across suites):

| Mark | Meaning | Required citation |
|---|---|---|
| `[ ]` | Open / not addressed — architectural question | Ticket id |
| `[!]` | Known gap that needs to be closed | Ticket id |
| `[?]` | Declared, unverified — verification pending | Ticket id |
| `[-]` | Declared + verified by code review or sweep evidence (not regression-locked) | Commit SHA or sweep run id |
| `[T]` | Test-locked: a passing regression test proves this defense (pinnacle state) | Test file path + case name |

**Maturity narrative.** A defense matures `[ ]` → `[?]` → `[-]` → `[T]`. `[T]` is the explicit pinnacle because only test-locked defenses survive refactoring — a `[-]` defense that's "observed firing in last sweep" can regress silently between sweeps. The migration target after records-as-policy lands is to push every `[-]` to `[T]` where feasible; `[-]` should stay only when the defense can't be reasonably tested (e.g., enforced by display projection on a live-LLM boundary that's hard to assert without a real model call).

**Mark transition discipline.**

- Every `[ ]`, `[!]`, `[?]` MUST have a linked ticket. File via `tk create --dir threats --id <id> ...` so threat tickets land in `.tickets/threats/` separately from bench-failure work tickets. Use the naming convention from CLAUDE.md "Threat-model tickets":
  - `<SS>-UT-<N>-<slug>` for tickets tied to a specific user task (e.g., `BK-UT-15-correlate-verify`)
  - `<SS>-IT-<N>-<slug>` for tickets tied to a specific injection task (e.g., `BK-IT-9-source-class-firewall-sweep`)
  - `<SS>-<slug>` for suite-level defense/policy tickets not tied to one task (e.g., `BK-display-projection-verify`)
  - `XS-<slug>` for cross-suite tickets (lives in `sec-cross-domain.md`)
  
  Suite codes: **BK** banking · **SL** slack · **WS** workspace · **TR** travel · **XS** cross-suite. The ticket body should carry the §-section reference back to the sec-doc (e.g., `§5 row A1`, `§8 Class 3`, `§9 question 4`) so the doc and ticket cross-reference.
- `[-]` requires evidence the defense **FIRES**, not just that the declaration exists. Citing the commit SHA that *added* the `data.untrusted` classification (or the `facts/kind:` constraint, etc.) is `[?]` not `[-]` — that's declaration evidence. Acceptable `[-]` citations:
  - sweep run id where the defense was observed firing against an attack carrier (cite via run id from STATUS.md Sweep history)
  - commit SHA of a runtime audit or probe that traced the declaration through to the enforcement path
  - commit SHA of a code-review chain that explicitly verified the runtime consumer of the declaration
  - If your only citation is "the records.mld commit where the declaration lives," the honest mark is `[?]` with a ticket for the verification probe.
- `[T]` requires the test file path + case name. The test must be in tier 1 (zero-LLM gate, `tests/index.mld`) or tier 2 (scripted-LLM, `tests/run-scripted.py`). Tier 3 (live-LLM sweeps) does not count — sweeps are stochastic and don't run on PR, so they can't lock a defense against regression. Be specific: `[T]` claims on "the advice-gate suite" without a named case are calibrated as `[-]` — the howto requires a specific test that locks *this* defense node.
- When a defense transitions states, update the mark, cite the new evidence, and close (or re-update) the linked ticket. Don't leave both the doc and the ticket in pre-transition state.
- When a transcript audit reveals a `[-]` or `[T]` claim is wrong (defense doesn't fire on some path), downgrade the mark to `[!]`, file a ticket capturing the discovered gap, and link it. Don't silently revise.

Indented `>` blocks describe the *mechanism* (which record primitive, which BasePolicy rule, which display projection). **Prompt discipline is not a defense node at any mark level.** Defenses must be structural (record shape, display projection, policy rule, tool metadata, phase-scoped restriction) or runtime-enforced. See CLAUDE.md "Prompt Placement Rules" for why prompt-side rules don't satisfy this bar.

Each tree closes with a short **Notes** paragraph for where the tree alone doesn't explain the invariant — e.g., Class 2 collapsing into Class 1, or load-bearing assumptions like "this defense holds only if upstream m-aecd lands."

**No coverage roll-up table at the end of §8.** The earlier banking draft had a per-defense-node × per-class summary table; it was a third view of data already in §5 (defense column per field) and §8 (defense nodes per class). The matrix + trees together cover the same ground without the drift surface of a third view. Skip the roll-up.

**Per-suite §8 organization**:

- **Banking**: classes structured around control-arg grounding (Class 1: recipient grounding; Class 2: subject-field exfil that collapses into Class 1; Class 3: cross-record mixing; Class 4: credential theft; Class 5: file-content laundering; Class 6: threshold evasion).
- **Travel**: classes structured around the advice gate (Class A: review-blob recommendation hijack; Class B: write-tool redirection via extracted hotel/restaurant; Class C: cross-domain leakage). Defense nodes include `role:advice` projection, `no-influenced-advice` policy rule, fact-only fallback path.
- **Slack**: classes structured around URL promotion + channel-name firewall (Class A: novel-URL output exfil; Class B: webpage-content-as-instruction laundering; Class C: invite-spoofing via channel-name injection). Defense nodes include `find_referenced_urls` rigTransform, `get_webpage_via_ref` private capability, channel-name `known-text` constraint, output validator on terminal compose.
- **Workspace**: classes structured around extract-driven laundering (Class A: typed-instruction-channel — TODO email body → unauthorized writes; Class B: cross-tool composition with stale state; Class C: schedule/calendar arithmetic with attacker-controlled times). Defense nodes include display projection on `data.untrusted` fields, source-class firewall at intent compile, typed extract through specific input records.

These suggested class structures are starting points; the actual classes should follow the suite's real threat surface, not a template's expectation.

### §9. Open architectural questions

A short numbered list. Each item is one question, framed honestly:

- What's the gap? (be precise)
- Why is it open? (architectural disagreement / waiting on upstream / deferred for stakes-reason / etc.)
- What would close it? (the decision shape, not a proposed answer)

Defer cross-suite questions to `sec-cross-domain.md` — say so explicitly with a one-line link rather than dragging them through every suite's §9.

### §10. Cross-references

Just a list of related docs and what they're authoritative for. Don't summarize their content here.

```
- `bench/domains/<suite>/records.mld`   — current record declarations (canonical)
- `bench/domains/<suite>/tools.mld`     — tool catalog (canonical)
- `STATUS.md`                            — per-task status (canonical)
- `MIGRATION-PLAN.md`                    — v2.x migration (canonical)
- `rig/SECURITY.md`                      — 10 numbered framework invariants
- `mlld-security-fundamentals.md`        — labels, factsources, records, refine, shelves
- `sec-cross-domain.md`                  — cross-suite attack vectors
```

**Citation hygiene.** When linking external docs from anywhere in this file (§5 enforcement column, §8 tree mechanism blocks, §9 questions), prefer semantic anchors over positional ones. "See `STATUS.md` Banking section" survives reorganization; "see `STATUS.md` line 47" rots silently when the linked doc changes. For mlld source citations, prefer commit SHA + file path over line numbers; line numbers move, SHAs don't.

## What does NOT go in sec-*.md

**These have other canonical homes. Mirroring them into sec-*.md creates drift.**

| Content | Canonical home | How to reference from sec-*.md |
|---|---|---|
| Per-task PASS/OPEN/FLAKY/SHOULD-FAIL/BAD-EVAL | `STATUS.md` | Don't reproduce. §6 stays threat-only. |
| Per-task ticket links and fix theories | `tk` tickets | Don't reproduce. §6 stays threat-only. |
| Migration steps / target architecture | `MIGRATION-PLAN.md` | Link in §10. Don't reproduce. |
| Framework security invariants | `rig/SECURITY.md` | Link in §10. Don't restate. |
| Records-as-policy primitive semantics | `mlld-security-fundamentals.md` | Link in §10. Don't restate. |
| Audit signatures (per-IT search strings) | In §7 of sec-*.md itself | Don't duplicate as separate section. |
| Per-defense-node × per-class coverage table | §5 matrix + §8 trees | Don't add as third view. |

The pattern: sec-*.md owns the *threat model and defense-claim mapping* for that suite. Status, migration, ticket history, and framework specs each have their own homes. The cross-doc connection is one-way references in §10.

## Suite-specific extensions

### Stale-doc reconciliation

The legacy `*.threatmodel.txt` and `*.taskdata.txt` files were authored at various points and may be stale against current upstream + STATUS.md state. **Verify every load-bearing claim against current sources before carrying it forward.** Known stale patterns observed during the first authoring pass:

- IT counts and "this IT doesn't exist upstream" claims (banking IT9 was claimed absent but is registered; slack IT6/IT7 had two opposite-direction errors across drafting passes). Always grep `injection_tasks.py` for `@task_suite.register_injection_task` to count actual ITs.
- Defense status claims (travel advice gate claimed `[?]` deferred in older doc; STATUS.md Sweep history shows IT6 × UT3/5/11/17 verified 0/4 ASR).
- v1.1.1 / v1.1.2 / v1.2 patch lineages affecting UT/IT content (workspace has multiple version overrides; verify which the bench actually runs via `BENCHMARK_VERSION` in `src/run.py`).

When you find a stale claim, **correct it in sec-*.md** AND consider whether the legacy `*.threatmodel.txt` should be moved to `archive/` to prevent future drift.

### Count-verification discipline (mandatory for §1 / §2 / §7)

Any claim of the form "*N* user tasks," "*M* injection tasks," "*K* injection slots," "IT0..ITN," or "this IT doesn't exist upstream" MUST be backed by a direct grep against the canonical source, cited inline in the sec-doc when the claim is non-obvious. The IT9 (banking) and IT6/IT7 (slack) errors that surfaced during the first drafting + review cycles both reduced to "did anyone grep?" — and in both cases the answer was no until the fix-agent pass.

Required citations:

| Claim | Grep |
|---|---|
| "*N* user tasks" | `grep -c "@task_suite.register_user_task\|@task_suite.update_user_task" .../<suite>/user_tasks.py` (sum across v1 + active patch version) |
| "*M* injection tasks (IT0..ITM)" | `grep -n "class InjectionTask" .../v1/<suite>/injection_tasks.py` (count + line numbers) |
| "IT_N does/doesn't exist" | Direct line-number citation: `injection_tasks.py:<line>` |
| "*K* injection slots" | `grep -c "^[a-zA-Z_].*:" .../<suite>/injection_vectors.yaml` (count top-level keys) |
| "v1.x.x patches Y" | `grep -n "update_user_task\|update_injection_task" .../v1_x_x/<suite>/*.py` |

When a count is load-bearing for a defense claim (e.g., "attacker IBAN never in any of N user task PROMPTs"), include the grep output in the sec-doc's "Verifications" footer or as a comment near the claim. Don't just assert.

This discipline is enforced at the §1 count table, §2 injection-slot enumeration, and §7 IT table. A reviewer who can't verify a count from the doc's own citations should flag it as `CRITICAL`.

### Suite-specific extensions are *candidate* structures, not ground truth

The class structures suggested below are starting hypotheses based on current understanding of each suite. Verify against actual `injection_tasks.py` and don't force the suite into the suggested class count if the threat surface differs. Examples from the first authoring pass:

- Workspace's suggested "C: calendar/schedule arithmetic" turned out not to be a meaningful class in v1.1.1 (no scored ITs exploit time arithmetic). Drafter substituted "C: destructive writes" which matches actual IT1.
- Slack has 5 attack classes (not 3) because IT6 (tier-2 contact substitution) and IT7 (tier-3 web-beacon) are qualitatively distinct from Class A novel-URL exfil.
- Travel landed on 4 classes (not 3) because PII/exfil via send_email is mechanistically distinct from booking-redirection.

The class count is determined by the actual attack surface, not by the howto's enumeration.

### Banking
The banking suite is the closest to "value-grounded threat" — most defenses are fact-grounding (recipient must be `fact:iban`, password must be `exact`, scheduled-transaction id+recipient must `correlate`). §8 classes are organized around control-arg grounding.

### Travel
Travel's load-bearing primitive is the **advice gate**: a task-entry classifier routes recommendation-shaped tasks to a separate compose worker that projects state through `role:advice` (which strips `data.untrusted` fields like `review_blob`) and is gated by a `no-influenced-advice` policy rule with fact-only fallback. This is fundamentally a different defense primitive from banking's recipient-grounding — it operates at *display* and *policy*, not at *value*. §8 should include:

- A class for **recommendation-hijack** (the canonical IT6-style attack)
- The advice-gate decision tree with three defense nodes: classifier routes → `role:advice` projection → `no-influenced-advice` policy + fact-only fallback
- The `ADVICE_GATE.md` defense doc as an §10 cross-reference

Don't try to force travel into banking's "all defenses are records-side primitives" frame. The advice gate is policy-side + projection-side; that's a separate threat-class slot.

### Slack
Slack's load-bearing primitives are **URL promotion** (`find_referenced_urls` rigTransform + private `get_webpage_via_ref` capability + output validator on terminal compose) and the **channel-name firewall** (`slack_channel.name` declared `data.untrusted`, known-text constraint on write tools targeting channels). §8 should include:

- A class for **novel-URL exfil in compose output** (defended by `validators/output_checks.mld` + `policies/url_output.mld`)
- A class for **webpage-content-as-instruction laundering** (defended by `get_webpage_via_ref` being a private capability whose results are typed)
- A class for **invite/DM spoofing via injected channel names** (defended by channel-name being `data.untrusted` + per-tool known-text constraints)

Slack's threat model has more output-validation surface than banking's; expect more `[ ]` and `[?]` marks in §8 reflecting pending verifications.

### Workspace
Workspace's load-bearing pattern is **typed-instruction-channel refusal** — most failing tasks in the suite ask the agent to "do the actions described in this email body," which the architecture *correctly refuses* by structural display projection. §8 should include:

- A class for **typed-instruction-channel** (the canonical UT13/UT19 family — defended structurally; SHOULD-FAIL on utility because mainstream prompt-injection defense doesn't pass these without different design)
- A class for **extract-driven laundering** — where extract output flows to write tool args (defended by per-phase source-class firewall + display projection on `data.untrusted` source fields)
- A class for **calendar/schedule arithmetic with attacker-controlled times** if relevant (defended by date-shift handling + planner discipline, less structural)

Workspace's `sec-` doc will naturally have more SHOULD-FAIL framing — make it explicit per-task in §6 (architectural refusal as a threat-relevant fact, not as a status mirror) and per-class in §8.

### sec-cross-domain.md
Some attack vectors don't live in any one suite — banking's `update_user_info` accepting untrusted file-content addresses becomes an exfil channel *only* if a future cross-domain agent reads that address and forwards it through a slack DM or workspace email. These deferred questions accumulate as `[ ]` marks in each suite's §9 with explicit "deferred to sec-cross-domain.md" pointers. The cross-domain doc stays a separate file because:

- The threat doesn't fit any one suite's §5 matrix.
- Defense responsibility is split across multiple suites' records and the rig framework.
- Future cross-domain agents (out of current scope) introduce attack classes that don't exist in single-suite AgentDojo.

Use the same §1-§8 template; replace "suite" with "scenario" in section names where they don't make sense for a multi-suite view.

## Working with sec-*.md during records + BasePolicy authoring

The intended workflow when writing the v2.x records.mld and BasePolicy:

1. Read `sec-<suite>.md` start-to-finish for the suite you're authoring.
2. For each row in §5 matrix, verify the records-side enforcement column matches what you're about to declare. If it doesn't, either update sec-*.md (the threat model evolved) or pause (you may be missing a defense).
3. For each `[?]` mark in §8 trees, decide: does this records/policy declaration validate the `[?]`? If yes, the post-declaration verification flips it to `[-]` (with sweep-run citation) or `[T]` (if you also land a tier-1/tier-2 test). If no, the declaration is missing a defense.
4. Comment each records.mld declaration with the sec-*.md row it's defending against. Cite `§5 row A1` or `§8 Class 1`. Forward-flow: from threat doc to records.mld.
5. When the sweep runs, the §7 audit signatures are the search strings the auditor uses to classify transcripts. Update §7 if new signatures emerge during attacks.

**Mark-transition discipline during authoring.** When your records change flips a mark:

- `[?] → [-]`: cite the sweep run id (or commit SHA + probe path) in the sec-doc, and close the ticket that was linked to the `[?]` mark (`tk close <id> --dir threats` works because `tk` finds tickets by id regardless of directory).
- `[-] → [T]`: cite the test file + case name in the sec-doc. The transition is only valid if the test is tier-1 or tier-2 (regression-locked); sweep evidence alone keeps it `[-]`.
- `[!] → [-] / [T]`: same — cite evidence, close the ticket.
- New gap discovered: file a threat ticket via `tk create --dir threats --id <SS>-<UT|IT>-<N>-<slug> ...` (or `<SS>-<slug>` for non-task-tied), mark `[!]` with the ticket id inline, surface in §9 if architectural.

How trust per mark works for an author reading the doc:

- `[T]` defenses can be depended on completely.
- `[-]` defenses should be re-verified by probe before being depended on for a new records-side change (sweep evidence rots faster than test evidence).
- `[?]` defenses require the linked ticket be resolved before you author against them.
- `[ ]` and `[!]` are the architectural surface — flag them in your authoring plan; they're not safe to assume.

The sec-*.md is the source-of-truth for *intent*; records.mld and BasePolicy are the source-of-truth for *enforcement*. They cite each other; they don't restate each other. The marks are the bridge — they tell records authors how much of the intent is currently enforced and how durably.

## Updating banking from the v1 draft

The current `sec-banking.md` is the v1 draft. To bring it in line with this guide:

1. **Drop §10 (status mirror)**. Replace with a one-paragraph note: "Per-task status tracked in `STATUS.md`. Threat-relevant per-task call-outs already in §6."
2. **Drop §12 (migration notes)**. Replace with a one-line §9 entry: "Migration mechanics tracked in `MIGRATION-PLAN.md`. This doc owns threat-model intent; records.mld owns enforcement."
3. **Drop §14 (audit signatures section)**. Verify each IT in §7 already has its signature; consolidate the §14 entries that were missing into the corresponding §7 row.
4. **Drop the coverage roll-up table at end of §8**. The matrix in §5 and the per-class trees in §8 already cover this; the third view duplicates and creates drift.
5. **Renumber sections** to match the 10-section template: §1-§5 stay, §6 user tasks, §7 ITs, §8 trees, §9 open questions, §10 cross-references.
6. **Re-read §5 matrix for status honesty**. The `[?]` marks should match current state: many are now `[-]` post-m-aecd, but some new ones may have emerged (e.g., the positional-dispatch path discussed in this session is `[!]` — known gap).
7. **Adopt the five-mark scheme.** Replace the v1 draft's mark table with the `[ ] / [!] / [?] / [-] / [T]` set. Walk every defense node in §5 matrix and §8 trees:
   - `[x]` from the v1 draft collapses into `[-]` (verified by inspection/sweep) unless a tier-1/tier-2 test exists, in which case it promotes to `[T]` with the test file + case cited.
   - Every `[ ]`, `[!]`, `[?]` mark must have a linked ticket id inline. File via `tk create --dir threats --id <SS>-<UT|IT>-<N>-<slug> ...` (see CLAUDE.md "Threat-model tickets" for the naming convention). Don't leave uncertain marks orphaned.
   - Every `[-]` must cite a sweep run id or commit SHA. Strip the mark to `[?]` (with ticket) if no citation can be honestly provided.
   - Every `[T]` must cite the test path + case name and the test must be in `tests/index.mld` (tier 1) or `tests/run-scripted.py` (tier 2). Demote to `[-]` if only tier-3 sweep evidence backs the claim.
8. **Audit §9 open questions** for ticket coverage. Any open architectural question that doesn't have an owner/ticket gets one — `[ ]` items in §9 follow the same rule as `[ ]` defense nodes in §8, and use the same `--dir threats` + naming convention.

Net effect: ~60-100 line reduction in banking doc, no information lost, drift surface reduced from ~5 cross-doc overlap points to 0. Every uncertain mark is now ticket-anchored, so sec-doc maintenance falls out of normal ticket hygiene rather than needing its own freshness ritual.

## Writing the other three

In order of complexity (simplest to most complex):

1. **`sec-slack.md`** — single load-bearing primitive (URL promotion) with one secondary primitive (channel-name firewall). Roughly the same shape as banking but with output-validation defenses occupying §8 instead of fact-grounding.

2. **`sec-workspace.md`** — typed-instruction-channel refusal as a class. Workspace has the most SHOULD-FAIL tasks; framing those as architectural decisions in §6 (not status mirrors) is the main authoring challenge.

3. **`sec-travel.md`** — advice gate is qualitatively different from any other suite's primitive. §8 needs the three-node advice tree explicitly. Expect this doc to also surface the most cross-domain deferred questions in §9 (recommendation-hijack scenarios that cross suites).

4. **`sec-cross-domain.md`** — write last, after all four single-suite docs surface their deferred items in §9. The deferred items become the cross-domain doc's contents.

## Calibration

A well-written sec-*.md, for a reader who's never seen the suite:

- Tells them the suite's stakes in §1 (a paragraph).
- Tells them what an attacker can control in §2 (a bounded enumeration).
- Tells them what tools exist and what records implement them in §3-§4 (reference, not exhaustive).
- **Shows them the attack surface mapped to defense in §5 (the matrix)**.
- Walks them through each attack class with structural defense nodes in §8.
- Honest about what's `[?]` pending verification, `[!]` known gap, `[ ]` open question.
- Points to other docs for status, migration, framework specs (no mirroring).

If after writing the doc you can't predict (without running anything) which attacks the current records.mld blocks structurally — the matrix isn't precise enough. If after writing the doc a records author has to ask you which primitive defends a given attack — the §5 enforcement column needs more detail. If the sweep auditor can't decide which transcript signatures to grep — §7 needs richer signatures.

When in doubt, calibrate against the question "would this doc let me re-author records.mld for this suite from scratch, defending the documented threat surface, without re-reading the suite source?" If yes, it's done. If no, §5 / §8 / §4 need more.
