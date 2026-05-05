# Counter-proposal: kind-tagged fact fields, auto-derived requirements

**Replaces:** `SECURITY-RIG-WRONG-RECORD-BYPASS.md` design (per-tool `factRequirements`)
**Status:** counter-proposal back to mlld-dev
**Scope:** mlld core (record schema + policy.build), bench domain migration

## Problem with the current design

The current proposal closes the wrong-record-fact bypass via per-tool `factRequirements:` on the tool catalog entry, with mlld auto-deriving `["known", "fact:*.<argName>"]` defaults from input-record fact field names. Two real costs:

**1. Default rule is strict but rarely useful.** `send_email.recipients` defaulting to `["known", "fact:*.recipients"]` rejects ALL real-world flows because no record has a `recipients` field — emails come from `@contact.email`, `@shared_file_entry.shared_with[*]`, etc. Every consumer that crosses record boundaries (which is almost every consumer) needs an explicit override.

**2. Override locus is wrong.** Per-tool `factRequirements:` on catalog entries spreads the same source list across every consumer. `email` is accepted by `send_email.{recipients,cc,bcc}`, `invite_user_to_slack.user_email`, `share_file.email`, `create_calendar_event.participants`, etc. — six entries on the workspace tool catalog all listing `["known", "fact:*.email"]`. Adding a new email-producing record means editing every one of them.

The information about which record-field combinations are semantically interchangeable (a contact email, a slack user's email, a shared-file recipient — all "emails") doesn't live anywhere coherent. Per-tool overrides flatten an N-to-N graph into per-consumer boilerplate.

## Proposed design: `kind:` on fact fields

Tag fact fields with a string `kind:`. mlld walks the record set, builds a kind→source index, and derives requirements automatically. No central registry, no per-tool overrides for the common case.

### Schema change

Fact fields gain an optional `kind:` annotation:

```mlld
record @contact = {
  facts: [
    name: { type: string, kind: "user_name" },
    email: { type: string, kind: "email" },
    phone: { type: string?, kind: "phone" }
  ]
}

record @slack_user = {
  facts: [
    name: { type: string, kind: "slack_user_name" },
    email: { type: string?, kind: "email" }
  ]
}

record @shared_file_entry = {
  facts: [
    file_id: { type: handle, kind: "file_id" },
    shared_with: { type: array, kind: "email" }
  ]
}
```

Input records use the same kind tags:

```mlld
record @send_email_inputs = {
  facts: [
    recipients: { type: array, kind: "email" },
    cc: { type: array?, kind: "email" },
    bcc: { type: array?, kind: "email" }
  ],
  data: { ... }
}

record @invite_user_to_slack_inputs = {
  facts: [
    user: { type: string, kind: "slack_user_name" },
    user_email: { type: string, kind: "email" }
  ]
}
```

`kind` is just a string — mlld doesn't need to know its semantic meaning. Tag matching is exact-string equality. Consumers establish conventions; mlld enforces consistency.

Fact fields without `kind:` keep current behavior (strict `fact:*.<argName>` default). Migration is incremental.

### Auto-derivation algorithm

At `policy.build` time:

1. **Build kind index.** Walk every record in `tools.<*>.returns` AND `tools.<*>.inputs` (and any directly imported records). For each fact field with `kind: K`, append `fact:@<recordName>.<fieldName>` to `kindIndex[K]`. Array-typed fields contribute the bare path; runtime selection refs to `[*]` indices match the path naturally.

2. **Derive requirements.** For each tool with input record fact fields:
   - For each fact field with `kind: K`, accepted patterns = `["known"] ++ kindIndex[K]`
   - For each fact field WITHOUT `kind:`, fall back to current default `["known", "fact:*.<argName>"]`

3. **Apply overrides.** If `policy.facts.requirements[<op>][<arg>]` is already declared (via tool catalog or basePolicy), use that instead of the derived accepts. Userland override path is still available for the rare case.

### Concrete result

For workspace `send_email.recipients` after kind tagging:

```text
kindIndex["email"] = [
  "fact:@contact.email",
  "fact:@slack_user.email",
  "fact:@shared_file_entry.shared_with",
  ...any other email-tagged record fields
]

policy.facts.requirements["@send_email"]["recipients"] = [
  "known",
  "fact:@contact.email",
  "fact:@slack_user.email",
  "fact:@shared_file_entry.shared_with"
]
```

Adding a new email-producing record (say a directory record) — tag its email field `kind: "email"`, and every email-accepting tool input automatically picks it up. No tool-catalog edits.

### Override path (rare)

When a fact field's `kind:` is intentionally narrow but a specific tool input wants additional sources:

```mlld
record @send_email_inputs = {
  facts: [
    recipients: { type: array, kind: "email", accepts: ["known", "fact:*.email", "fact:@directory.list_email"] }
  ]
}
```

`accepts:` on the input record field overrides the derived list. Lives at the schema layer where the rest of the input contract lives. The current `factRequirements:` on tool catalog entries can stay as a last-resort escape hatch but should be deprecated in normal use.

## Migration

### Phase 1 — mlld core: parse + ignore (no behavior change)

mlld accepts `kind:` on fact field declarations. It's metadata; nothing reads it yet. Allows consumers to start tagging without coordination.

### Phase 2 — mlld core: derive from kinds at policy.build

`policy.build`:
1. Builds kind index from all records in scope
2. For each tool's input record fact field, derives accepts from kindIndex if `kind:` is set, else falls back to current `fact:*.<argName>` default
3. Pre-existing `factRequirements` (tool entry) and `policy.facts.requirements` (basePolicy) override the derived list

This phase makes kind tags load-bearing for security. It's a behavioral change but only for tools whose fact fields are tagged. Untagged fields keep current behavior.

### Phase 3 — consumer migration

Bench domains add `kind:` to record fact fields. Test suite catches any flows that needed an override (currently passing tests fail with `control_arg_wrong_fact_source` until the right kind is added or an `accepts:` override is declared).

In clean/rig:
- Drop my opt-in `@synthesizedFactRequirements` (mlld does it now via kinds)
- Keep my rig-side intent-compile validator but switch to opt-out — derive accepts from kind index, fall back to `fact:*.<argName>`, surface rejection at rehearse with the same error envelope

### Phase 4 — deprecate `factRequirements:`

Once consumers have migrated to kinds, the tool-catalog `factRequirements:` field is deprecated. Remove from rig synthesizer. The `accepts:` override at input record field level remains as a narrow override path.

## Why this is the right shape

**O(records + consumers), not O(records × consumers).** Each fact field gets one tag. Each input field gets one tag. The N-to-N matching is auto-derived. Adding sources or sinks is one edit each, not N.

**Decoupled from local arg names.** `send_email.recipients` and `invite_user_to_slack.user_email` can both be `kind: email` regardless of what they're called locally. The semantic match is the kind, not the name. This is the explicit-not-normalized property the original SECURITY doc wanted, with the boilerplate cost amortized.

**Strict by default, no surprises.** Untagged fact fields keep the current strict behavior (`fact:*.<argName>`). Tagged fields get the matching set. There's no implicit name normalization — the only way for two fields to be considered equivalent is if their tags match exactly.

**Discoverable governance.** Reading a record tells you what kinds it produces. Reading an input record tells you what kinds it accepts. The kind index is derived; no separate file to drift.

**Lives at the schema layer.** Records and input records are where types belong. Tool catalog entries are about identity (name, mlld function, labels) — not about value flow. Putting type-flow info on tool entries was wrong.

## The wrong-record-bypass test under this design

`testSelectionRefRealSlackMsgHandleRejected`: planner authors `invite_user_to_slack.user_email = selection backing on slack_msg.sender`.

- `slack_msg.sender` is `kind: "slack_user_name"` (or unspecified — definitely not `kind: "email"`).
- `invite_user_to_slack_inputs.user_email` is `kind: "email"`.
- kindIndex["email"] does NOT include `fact:@slack_msg.sender`.
- Rehearse rejects with `control_arg_wrong_fact_source`.

The bypass closes structurally — no per-tool override needed.

## Open questions

1. **Kind namespace conventions.** Should mlld provide a recommended starter set (`email`, `phone`, `iban`, `user_name`, `handle`, etc.) or leave it fully userland? Probably leave userland; document conventions in app-side docs.

2. **Inheritance / composition.** If `kind: "verified_email"` and `kind: "email"`, should a `verified_email` source be acceptable for an `email` sink? Probably no — exact-match only, just like the no-name-normalization rule. If userland wants subtype semantics, declare both kinds explicitly via `kind: ["verified_email", "email"]`.

3. **Multi-kind fields.** `record @directory = { facts: [contact: { type: string, kind: ["email", "user_name"] }] }` — should be allowed. Field appears in both kindIndex["email"] and kindIndex["user_name"].

4. **Kind on data fields?** Probably not — only fact fields participate in the security firewall. Data fields are payload, not authorization proof.

## Acceptance criteria

1. `kind:` is parseable on fact field declarations (string or string[])
2. `accepts:` is parseable on fact field declarations as an override (string[] of patterns)
3. policy.build derives `policy.facts.requirements` from kind matches
4. Untagged fact fields keep current `fact:*.<argName>` default
5. `policy.facts.requirements` declared explicitly (basePolicy or tool factRequirements) overrides derivation
6. The UT16 wrong-record bypass test passes without per-tool overrides — only kind tagging
7. The rig invariant test for `send_email.recipients ← shared_file_entry.shared_with[0]` passes after tagging both `kind: "email"` — no per-tool override
8. Existing tests for explicit `factRequirements` continue to pass (override path remains)

## Why migration is worth it

Per-tool `factRequirements:` would land 40-80 hand-authored requirement clauses across the four bench suites, each duplicating the same source-list information. Adding a new email source means editing six places. Drift between input-record schema and tool-catalog overrides is inevitable.

Kind tags give us:
- ~15-25 record fact fields tagged with kinds (one tag each)
- ~15-25 input record fact fields tagged with the same kinds
- 3-6 kind names in active use (`email`, `iban`, `slack_user_name`, `slack_channel_name`, `handle`, maybe one or two more)
- Zero per-tool override boilerplate for the common case

The schema layer is where types belong. Tool catalogs should describe identity, not flow.
