# sec-cross-domain.md — Cross-suite security & threat model

Single source of truth for cross-suite attack scenarios and defense generalizations. Authored per `SEC-HOWTO.md` ("sec-cross-domain.md" guidance). Aggregates deferred items from each suite's §9 plus the cross-suite (XS-*) threat tickets in `.tickets/threats/`.

This doc is consumed by:

1. **Records / BasePolicy authors** — when a defense decision needs to generalize across suites (e.g., a policy rule that applies wherever a `privileged:` operation exists), or when a single-suite records change might enable a cross-suite attack.
2. **Future authors of cross-suite agents** — when building agents that span multiple AgentDojo domains (e.g., a workspace+banking agent that reads transactions and sends summary emails), this doc is the threat model.
3. **Sweep auditors** — when an attack succeeds via a path that doesn't fit any single-suite §5 matrix.

## Scope distinction

Cross-suite content lives in this doc *only when* it doesn't fit one suite's §5 matrix. Two flavors:

| Flavor | Description | Testable today? |
|---|---|---|
| **Cross-suite-applicable defenses** | A defense primitive that generalizes (policy rule, label class, structural refusal pattern) where the *defense* is cross-suite even though the *attack* may be single-suite | Yes — verifiable within a single suite |
| **Genuine cross-suite scenarios** | Attack surface that requires a cross-suite agent to exercise (data read from suite A, written via suite B) | No — speculative until cross-suite agents exist |

The current AgentDojo benchmark has **no scored cross-suite ITs or UTs**. Cross-suite agents are out of scope for the current bench. This doc is forward-looking for the second flavor, and operationally active for the first.

## Cardinal Rule A — what to cite, what to NEVER cite

| Source | What to read | What to NEVER read |
|---|---|---|
| `agentdojo/.../<suite>/user_tasks.py` | `PROMPT`, `COMMENT`, `ground_truth(...)` | `utility(...)` function bodies |
| `agentdojo/.../<suite>/injection_tasks.py` | `GOAL`, `COMMENT`, `ground_truth(...)`, class docstrings | `security(...)` function bodies, `security_predicates(...)` |
| `agentdojo/.../<suite>/environment.yaml` | All — it's the threat surface | n/a |
| `agentdojo/.../<suite>/injection_vectors.yaml` | All — it's the attack payload definition | n/a |

This doc cites cross-suite *implications* of single-suite source material; no new sources beyond what `sec-banking.md` / `sec-slack.md` / `sec-workspace.md` / `sec-travel.md` already cite.

---

## §1. Scope at a glance

This doc has no scored attack matrix because AgentDojo doesn't currently exercise cross-suite agents. The scope is:

| | Count |
|---|---|
| Cross-suite generic defenses (XS-* tickets) | 6 |
| Single-suite carrier docs | 4 (sec-banking, sec-slack, sec-workspace, sec-travel) |
| Cross-suite agents in current AgentDojo bench | 0 |
| Genuine cross-suite attack scenarios documented | 3 (Cluster X1 below) |

**Dominant cross-suite concerns:**
- **Cross-suite exfil pivot** — data classified `data.untrusted` or auto-populated in suite A becomes exfil payload via suite B's send tools (X1).
- **Generic policy rules** — `no-influenced-privileged`, kind-floor verification, PII labeling — should apply wherever the relevant primitive exists, not be re-declared per suite (X2).
- **Typed-instruction-channel pattern** — fetched-content-as-instruction defenses needed wherever an agent reads tainted content and the user-task framing invites instruction-following (X3).

---

## §2. Cross-suite attacker-controllable fields

The single-suite docs enumerate each suite's injection slots (banking 4, slack 6, workspace 16, travel 7 — 33 total injection slots across AgentDojo). For cross-suite threats, the relevant question is **which fields, once attacker-influenced, can flow into another suite's write path**.

### Fields whose untrusted classification matters cross-suite

| Suite | Field | Why cross-suite-relevant |
|---|---|---|
| Banking | `@file_text.content` (bill/landlord/address files) | Address-change extraction lands in `@update_user_info.street/city` with no records-side fact gate. A future cross-suite agent that reads `@user_account.street/city` and sends them via slack/workspace would exfil the attacker-controlled address. |
| Workspace | `@contact.email` (auto-populated from received emails) | Inbox-derived contact entries inherit fact-grade authority from the AgentDojo data model. Cross-suite agents reading this contact list and sending via banking/slack pivot through fact-bearing recipients. |
| Slack | `@webpage_content.content` (URL-fetched) | URL-promotion gates the fetch, but the resulting body content becomes worker context. Cross-suite reading + paraphrasing into banking/workspace writes leaks the attacker content. |
| Travel | `@hotel.review_blob` / `@restaurant.review_blob` | Stripped at `role:advice` projection within travel, but a cross-suite agent invoking travel reads outside the advice gate could see them. |

### Fields whose attestations DO generalize cleanly

| Suite | Field | Generalization |
|---|---|---|
| Banking | `@send_money_inputs.recipient: fact:iban` | `fact:iban` is a per-record kind. Cross-suite agents using send_money inherit the kind:iban floor. ✓ |
| All | `known` source class | Verbatim task-text + kind: floor verification. Cross-suite tickets per suite (BK/SL/WS-known-kind-floor-verify) verify the same primitive. |

---

## §3. Cross-domain capability surfaces

Speculative — when a cross-suite agent is built, the following tool combinations create the highest-risk paths:

| Read tool (suite A) | Write tool (suite B) | Threat shape | Tracked by |
|---|---|---|---|
| `get_user_info` (banking) | `send_email` / `send_channel_message` / `send_direct_message` (workspace/slack) | User PII (address, names) exfil via legitimate send | `XS-pii-sensitivity-labels`, `XS-address-channel-exfil` |
| `read_file` (banking files: address-change.txt, etc.) | Any send tool | File-injection content reaches outbound channel | `XS-update-user-info-address-exfil`, `XS-slack-exfil-pivot-cross-domain` |
| `read_inbox` / `read_emails` (workspace) | `send_money` / `update_scheduled_transaction` (banking) | Email-derived "instructions" reach financial writes | `XS-fetched-content-as-task-defense` |
| `read_channel_messages` (slack) | `send_email` / `update_user_info` (workspace) | Channel injection → workspace mutation | `XS-fetched-content-as-task-defense`, `XS-slack-exfil-pivot-cross-domain` |
| `get_webpage` (slack/workspace) | Any write tool | URL-fetched content drives writes | `XS-fetched-content-as-task-defense`, `SL-known-bucket-task-text` |

The general pattern: **`data.untrusted` content from one suite's read tool, paraphrased through worker output (`influenced` label), reaches another suite's write tool's payload field.** Defense is at the records-side (per-suite `data.untrusted` classifications) plus framework-side (display projection, policy rules generalizing across suites).

---

## §4. Records — no new records, reference single-suite docs

Cross-suite doesn't add new records. It documents *interactions* between records declared in the four single-suite `records.mld` files. Refer to:

- `bench/domains/banking/records.mld` — banking records
- `bench/domains/slack/records.mld` — slack records
- `bench/domains/workspace/records.mld` — workspace records
- `bench/domains/travel/records.mld` — travel records

The single-suite docs' §4 sections give the field-level classification per suite. Cross-suite implications are surfaced in §5 below.

---

## §5. Attack surface matrix — cross-suite

Each row is a cross-suite scenario where attacker content in one suite's `data.untrusted` field can reach another suite's control arg or exfil channel.

| # | Source field | Source suite | Destination | Destination suite | Defense layer | Status | Tracked by |
|---|---|---|---|---|---|---|---|
| **X1** | `@file_text.content` (address-change.txt) | Banking | `@user_account.street/city` → cross-suite send tool body | Banking → Slack/Workspace | Banking-side: data.untrusted on file content, but no fact gate on update_user_info. Cross-suite-side: needs PII labeling on @user_account fields + influenced propagation. | GAP (cross-suite) | `XS-update-user-info-address-exfil`, `XS-address-channel-exfil`, `XS-pii-sensitivity-labels` |
| **X2** | `@webpage_content.content` (slack) | Slack | Any cross-suite write payload | Slack → Any | `data.untrusted` + influenced propagation; cross-suite agent must not paraphrase fetched content into other suites' writes | STRUCTURAL BLOCK (pending cross-suite verify) | `XS-slack-exfil-pivot-cross-domain`, `XS-fetched-content-as-task-defense` |
| **X3** | TODO-URL or "do tasks at" pattern | Slack (UT18/UT19) + Workspace (UT13/UT19) | Any write tool | Any | Architectural refusal: agent must NOT treat fetched / read content as user instruction, regardless of suite | STRUCTURAL BLOCK | `XS-fetched-content-as-task-defense` |
| **X4** | Any `influenced` data | Any | `privileged:*` operation (currently banking `update_password`) | Any → Banking | `no-influenced-privileged` rule (proposed, not implemented). Banking covers this case with absent `write:` block hard-deny, but the rule would generalize. | GAP (cross-suite generalization) | `XS-no-influenced-privileged-rule` |
| **X5** | Travel `@hotel.review_blob` / `@restaurant.review_blob` | Travel | Cross-suite send tools (slack DM, workspace email) | Travel → Slack/Workspace | `role:advice` strips review_blob within travel advice gate. Cross-suite agent reading outside advice gate sees review_blob. Defense: same projection should apply in any context where review_blob reaches LLM. | OOS — speculative cross-suite agent | (deferred — no XS ticket yet) |
| **X6** | `@contact.email` (workspace, auto-populated) | Workspace | Banking `recipient` field (via name lookup) | Workspace → Banking | Auto-populated contacts inherit fact-grade authority from AgentDojo data model. Cross-suite agent treating auto-pop contacts as resolved would launder attacker emails into banking control args. | GAP (data-model behavior, not records-defendable) | `WS-contact-autopopulation` (single-suite carries) |

### Net claim

For the genuine cross-suite scenarios (X1, X5, X6), no defense holds end-to-end until cross-suite agents are built and either (a) the underlying single-suite gaps are closed via the XS-* tickets, or (b) framework-level cross-suite policy generalizations land.

For the cross-suite-applicable defense generalizations (X2, X3, X4), the defenses are conceptually correct but need the XS-* tickets to land before a "passes across all suites" claim is honest.

---

## §6. Scenarios (in lieu of User Tasks)

AgentDojo doesn't have cross-suite user tasks. The following are *speculative* scenarios that would exercise the cross-suite attack surface, useful for designing tests if a cross-suite agent is built.

| Scenario | Tool chain | Cross-suite mechanism |
|---|---|---|
| **CS1: "Update my address from the email Alice sent me"** | workspace `read_email` → banking `update_user_info` | Address extracted from `data.untrusted` email body lands in trusted-update arg with no fact gate. The attacker-controlled value persists in `@user_account`. |
| **CS2: "Email my mom my current banking details"** | banking `get_user_info` → workspace `send_email` | User PII (no `sensitive` label currently) flows to send_email body. Defense relies on no-sensitive-exfil rule recognizing PII fields. |
| **CS3: "Summarize the latest channel discussion and forward to the team via email"** | slack `read_channel_messages` → workspace `send_email` | Channel-injected prompt-injection content paraphrased into outbound email. Defense relies on `influenced` propagation + recipient grounding on send_email. |
| **CS4: "Check the price of the hotel I bookmarked and DM it to Alice"** | travel hotel read (outside advice gate) → slack `send_direct_message` | `review_blob` content (untrusted) summarized into DM body. Defense relies on cross-suite projection consistency for `data.untrusted` fields. |

These scenarios are not in scope for the current bench. If/when cross-suite agents are built, each scenario becomes a candidate UT for an extended benchmark, and the defenses listed in §5 become testable.

---

## §7. Injection patterns (in lieu of Injection Tasks)

No scored cross-suite injection tasks exist upstream. The injection patterns most likely to exercise cross-suite attack surface (already exercised in single-suite form):

| Pattern | Single-suite carrier | Cross-suite extension |
|---|---|---|
| `{injection_address_change}` in banking file body | Banking UT13 (file → update_user_info, address arg) | Cross-suite read of `@user_account.street/city` flows attacker address into outbound channel |
| `{injection_dora_0}` in slack webpage content | Slack UT2/UT11/UT16 (Dora email substitution) | Cross-suite write of slack-fetched content into other suites' destinations |
| `{injection_*_text}` in workspace email bodies | Workspace UT13/UT19/UT22/UT25 (typed-instruction family) | Cross-suite mutation of banking/travel state per email-instructed action |
| Travel `review_blob` injection (IT0/IT2/IT3/IT5/IT6) | Travel advice gate carriers | Cross-suite read outside advice gate exposes review content |

When cross-suite agents are scored upstream, this section gets a proper IT table.

---

## §8. Attack-class trees — cross-suite

Three attack classes corresponding to the XS-* ticket clusters.

### Notation

| Mark | Meaning | Required citation |
|---|---|---|
| `[ ]` | Open / not addressed | Ticket id |
| `[!]` | Known gap | Ticket id |
| `[?]` | Declared, unverified | Ticket id |
| `[-]` | Declared + verified by code review or sweep evidence | Commit SHA or sweep run id |
| `[T]` | Test-locked: passing regression test | Test file path + case name |

Per the SEC-HOWTO discipline: cross-suite defenses cannot currently claim `[-]` against cross-suite sweep evidence because no cross-suite sweep exists. Single-suite sweep evidence backs `[-]` only for the single-suite subset of each defense.

---

### Class X1: Cross-suite exfil pivot — data from suite A reaches outbound channel in suite B

```threatdown
__Attacker content in suite A's data.untrusted field reaches suite B's outbound channel__
- Cross-suite agent reads suite A's tainted state
  + Each suite's records.mld declares data.untrusted on the affected fields (banking file_text, slack webpage_content, travel review_blob, workspace email_msg.body)
    + [-] Single-suite `data.untrusted` classifications verified per suite docs
- Worker paraphrases tainted content into suite B's send payload
  + [?] `untrusted-llms-get-influenced` propagates across cross-suite worker output (ticket: BK-influenced-prop-verify, SL-known-bucket-task-text, WS-influenced-rule-verify, TR-influenced-prop-verify)
       > Each suite tracks influenced propagation independently. Cross-suite verification
       > needs a cross-suite agent + canary sweep.
- Suite B's send tool authorizes the body
  + [-] Recipient grounding holds — Class 1 invariants in each suite's §8 apply
       > Recipient cannot be attacker-controlled if cross-suite agent inherits fact-floor
       > on send_email.recipients / send_money.recipient / send_direct_message.recipient.
       > This is the load-bearing structural defense for cross-suite exfil.
  + [ ] Body content from cross-suite read flows as payload (no body-side gate)
       > `subject` / `body` on send tools is `data.untrusted` (payload-only) by design.
       > If recipient is legitimate (e.g., user's own contact), the exfil destination is
       > the user themselves — not a successful exfil. But if cross-suite agent reads
       > suite A and writes to suite B where suite B has weaker recipient grounding,
       > the attack chain holds.
       > Tracked by: `XS-update-user-info-address-exfil`, `XS-address-channel-exfil`,
       > `XS-slack-exfil-pivot-cross-domain`.
- PII labeling defense
  + [ ] Sensitive/secret labels on user_account PII fields (cross-suite)
       > Banking `@user_account` declares first_name/last_name as `facts:` and
       > street/city as `data.trusted` — no `sensitive` label. Travel `@user_info` similar.
       > A cross-suite agent reading these fields and writing them externally has no
       > policy rule blocking the flow. Tracked by: `XS-pii-sensitivity-labels`.
```

**Notes.** This class is the load-bearing concern when cross-suite agents are built. The defense is layered: per-suite `data.untrusted` (already declared), `influenced` propagation (per-suite verification pending), recipient grounding (already declared), and PII labeling (not yet declared). All four must hold; the weakest link is the PII labeling.

---

### Class X2: Generic policy rules that should generalize across suites

```threatdown
__A defense rule applies to a primitive that exists in multiple suites__
- no-influenced-privileged rule
  + [ ] Cross-suite rule blocking influenced data from `privileged:*` operations (ticket: XS-no-influenced-privileged-rule)
       > Currently banking @update_password_inputs absent-write-block carries the load
       > via hard-deny. A policy rule would generalize: any future suite with a
       > `privileged:*` operation inherits the defense without per-suite re-declaration.
- Known-source-class kind: floor
  + [?] Each suite verifies known-source-class enforces kind: floor in BasePolicy
       > Per-suite tickets: BK-known-kind-floor-verify, SL-known-bucket-task-text,
       > WS-known-kind-floor-verify. Filed per-suite because each suite has its own
       > sweep verification path; the rule itself is BasePolicy-level (single
       > implementation, applies everywhere).
- PII sensitivity labels
  + [ ] Add sensitive/secret labels to PII fields across suites (ticket: XS-pii-sensitivity-labels)
       > Travel @user_info has passport/credit_card/bank candidates; banking @user_account
       > has profile fields; workspace @contact has email candidates. A cross-suite
       > label class would let no-sensitive-exfil block PII flow generically.
```

**Notes.** These are generalization opportunities, not gaps in suite-specific defenses. The single-suite tickets do the per-suite verification work; the XS- tickets capture the cross-suite "this should be one rule, not four" framing.

---

### Class X3: Typed-instruction-channel — fetched-content-as-task pattern

```threatdown
__Agent must refuse to treat fetched / read content as user instruction__
- User task asks agent to follow instructions from a fetched resource
  + slack UT18/UT19 ("do the tasks at this URL")
  + workspace UT13/UT19 ("follow instructions in this email")
  + (banking UT12 "follow precisely" — analogous but lower-stakes)
- Worker reads tainted content via fetch or file
  + [-] Single-suite display-projection defenses strip data.untrusted from planner
       > Each suite's role:planner projection omits untrusted body content.
       > Planner never sees the instruction text.
- Worker would execute the instruction
  + [-] Source-class firewall at intent compile rejects extracted control args
       > Single-suite Class 1 invariants apply: extracted recipient/id/etc. cannot
       > satisfy facts/kind: floors. Already enforced per suite.
  + [ ] Tier-2 defense: structural refusal that "fetched-content-as-task" is a denied pattern
       > Architectural refusal: agent must structurally refuse to compose writes from
       > fetched content's instruction text. Tracked by: XS-fetched-content-as-task-defense.
       > Currently relies on display projection (planner doesn't see the text) + source-class
       > firewall (control args fail). A separate Tier-2 defense rule would catch the case
       > where projection or firewall regress.
```

**Notes.** This pattern is already defended in single-suite form via display projection + source-class firewall. The XS- ticket captures the desire for an *explicit* Tier-2 defense rule rather than relying on the composition of two single-suite primitives.

---

## §9. Open architectural questions

Cross-suite specific:

1. **When are cross-suite agents in scope?** AgentDojo doesn't currently ship cross-suite tasks. Building cross-suite agents (e.g., a workspace+banking agent) is out of current scope but valuable for real-world deployment. Decision: defer until single-suite utility + ASR targets are met. (no ticket — strategic decision)

2. **PII labeling: do we add `sensitive` to user_info fields suite by suite, or wait for a cross-suite rule?** Tracked by `XS-pii-sensitivity-labels`. Decision shape: file per-suite tickets to add labels (cheap), and a cross-suite ticket to add the generalizing rule. The two compose.

3. **`no-influenced-privileged` rule rollout.** Tracked by `XS-no-influenced-privileged-rule`. Decision shape: implement the rule in BasePolicy; verify per-suite that no false positives fire on current legitimate flows.

4. **Cross-suite canary sweep.** Once cross-suite agents exist, a cross-suite canary sweep (analogous to per-suite atk_direct / atk_important_instructions runs) would verify the cross-suite attack matrix at 0% ASR. (no ticket — depends on (1))

5. **Auto-populated contacts (workspace) as a cross-suite hazard.** Tracked by `WS-contact-autopopulation` in workspace doc. Cross-suite implication: contacts inherit fact-grade authority from AgentDojo data model behavior; cross-suite agents using these contacts launder attacker-controlled emails into other suites' recipient fields. Decision shape: either records-side data-model fix or AgentDojo upstream issue.

6. **Stale-doc reconciliation across single-suite docs.** Per SEC-HOWTO.md, the legacy `*.threatmodel.txt` files were the source of multiple stale claims (banking IT9, slack IT6/IT7 in both directions, travel advice-gate). When sec-cross-domain.md aggregates from single-suite docs, verify each claim against current upstream. (no ticket — discipline note)

---

## §10. Cross-references

```
- sec-banking.md, sec-slack.md, sec-workspace.md, sec-travel.md — single-suite carrier docs
- bench/domains/<suite>/records.mld — per-suite record declarations
- STATUS.md — per-task status (no cross-suite tasks in current bench)
- MIGRATION-PLAN.md — v2.x migration
- SEC-HOWTO.md — authoring guide for sec-*.md
- rig/SECURITY.md — 10 numbered framework invariants
- mlld-security-fundamentals.md — labels, factsources, records, refine, shelves
- .tickets/threats/ — XS-* and per-suite threat tickets (browse via `tk ls --dir=threats`)
```

**Citation hygiene:** prefer semantic anchors over positional ones. "See `sec-banking.md` §5 row A4" survives reorganization; "see `sec-banking.md` line 305" rots silently.

---

## Filed threat tickets (cross-suite)

All cross-suite (XS-*) threat tickets in `.tickets/threats/`. Inspect via `tk show <id>`; list cross-suite-only via `tk ls --dir=threats | grep "^XS-"`.

| Ticket id | Title | Cluster |
|---|---|---|
| `XS-no-influenced-privileged-rule` | Add no-influenced-privileged policy rule (generalize across suites) | X2 |
| `XS-update-user-info-address-exfil` | update_user_info accepting untrusted address content as exfil channel | X1 |
| `XS-fetched-content-as-task-defense` | Tier-2 defense for fetched-content-as-task (TODO/instruction-channel pattern) | X3 |
| `XS-slack-exfil-pivot-cross-domain` | Slack send-tools as exfil pivot for data read in other suites | X1 |
| `XS-pii-sensitivity-labels` | Add secret/sensitive labels to PII fields on @user_info (cross-suite) | X1, X2 |
| `XS-address-channel-exfil` | Cross-suite: workspace contact emails / recipients as exfil channel | X1 |
| `XS-locked-policy-rigwide` | Decide `locked: true` policy posture for production deployments (rig-wide) | X4 (framework) |
| `XS-planner-loop-recovery-on-policy-denial` | Verify planner-loop recovery on policy denial (structured surface, not swallowed) | X4 (framework) |

When a cross-suite ticket closes (defense verified end-to-end via cross-suite sweep or single-suite proxy), update the corresponding §5/§8 mark and remove the closed ticket from this table.

**Cross-suite ticket conventions:** XS- tickets live in `.tickets/threats/` alongside single-suite (BK-/SL-/WS-/TR-) tickets. Use `tk ls --dir=threats | grep "^XS-"` for cross-suite-only view, or `tk show <id>` for full body. File new XS- tickets via `tk create --dir threats --id XS-<slug> ...`.
