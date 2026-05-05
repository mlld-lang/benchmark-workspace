# Rig Handoff: Wrong-Record Fact Bypass

## Problem

The rig source-class firewall must not lower a control arg with proof from the
wrong fact subject. The concrete failing shape is:

```json
{
  "operation": "invite_user_to_slack",
  "args": {
    "user": { "source": "known", "value": "Dora" },
    "user_email": {
      "source": "selection",
      "backing": {
        "record": "slack_msg",
        "handle": "<real slack_msg handle>",
        "field": "sender"
      }
    }
  }
}
```

The lowered `user_email` carries `fact:@slack_msg.sender`. That proves the value
came from a Slack message sender field. It does not prove the value is an
acceptable email destination for `invite_user_to_slack.user_email`.

## Core Contract

Core now supports semantic fact matching through kind-tagged fact fields.
Fact field declarations can carry:

```mlld
kind: "email"
kind: ["email", "verified_email"]
accepts: ["known", "fact:*.email"]
```

`kind` matching is exact string equality. There is no field-name normalization:
`user_email` and `email` match only if both fields are explicitly tagged with
the same kind, or if an `accepts` override says so.

At `@policy.build` / `@policy.validate` time, core derives
`policy.facts.requirements` for input-record fact fields:

1. Build a kind index from records in scope, including tool `inputs`, tool
   `returns`, and directly imported records.
2. For each control arg backed by an input-record fact field:
   - If the field declares `accepts`, use those patterns.
   - Else if the field declares `kind`, accept `known` plus every indexed
     `fact:@record.field` with a matching kind.
   - Else fall back to `["known", "fact:*.argName"]`.
3. Explicit `policy.facts.requirements` still overrides derived requirements.

Example:

```mlld
record @contact = {
  facts: [
    email: { type: string, kind: "email" }
  ]
}

record @slack_msg = {
  facts: [
    sender: { type: string, kind: "slack_user_name" }
  ]
}

record @invite_user_to_slack_inputs = {
  facts: [
    user: { type: string, kind: "slack_user_name" },
    user_email: { type: string, kind: "email" }
  ],
  validate: "strict"
}
```

Derived result:

```text
invite_user_to_slack.user_email accepts:
  known
  fact:@contact.email
  fact:@invite_user_to_slack_inputs.user_email

invite_user_to_slack.user_email rejects:
  fact:@slack_msg.sender
```

## Rig Changes

### 1. Tag records and input records

Bench domains should tag both producers and consumers with shared kind strings.
For example:

```mlld
record @shared_file_entry = {
  facts: [
    shared_with: { type: array, kind: "email" }
  ]
}

record @send_email_inputs = {
  facts: [
    recipients: { type: array, kind: "email" },
    cc: { type: array?, kind: "email" },
    bcc: { type: array?, kind: "email" }
  ],
  validate: "strict"
}
```

After this, `send_email.recipients <- shared_file_entry.shared_with[0]` should
work without a per-tool requirement override.

### 2. Mirror core derivation in rehearse

Drop any rig-only `@synthesizedFactRequirements` based on per-tool boilerplate.
Where the rig needs pre-core validation or blocked-arg display, derive accepts
the same way core does:

```text
if input field has accepts:
  accepted = accepts
else if input field has kind:
  accepted = ["known"] + kindIndex[kind]
else:
  accepted = ["known", "fact:*.argName"]
```

The rig kind index should walk the same record set: tool inputs, tool returns,
and directly imported records.

### 3. Reject wrong subjects during intent compilation

In `rig/intent.mld`, after `resolvedAttestations` is computed for a resolved or
selection-backed control arg and before returning `ok: true`, validate those
attestations against the target operation arg's accepted patterns.

Expected behavior:

```text
arg=user_email
attestations=["fact:@slack_msg.sender"]
accepted=["known", "fact:@contact.email", "fact:@invite_user_to_slack_inputs.user_email"]
=> reject
```

Suggested error shape:

```json
{
  "ok": false,
  "arg": "user_email",
  "error": "control_arg_wrong_fact_source",
  "attestations": ["fact:@slack_msg.sender"],
  "accepted": ["known", "fact:@contact.email"],
  "hint": "This control arg needs proof matching one of the accepted fact patterns."
}
```

Core now rejects the same bad proof during `@policy.build`, but rig-side
compile-time rejection gives planners a clearer blocked-arg reason.

### 4. Keep these invariants

- Do not normalize names such as `user_email -> email`.
- Do not require backing record == input record.
- Untagged fields stay strict via `fact:*.argName`.
- Use `accepts` only for narrow schema-level exceptions.
- Use explicit `policy.facts.requirements` only as a last-resort override.

## Acceptance Tests

Required:

- Un-xfail `tests/suites-scripted/security-slack.mld::testSelectionRefRealSlackMsgHandleRejected`.
- Assert `invite_user_to_slack.user_email` rejects `fact:@slack_msg.sender`.
- Assert `invite_user_to_slack.user_email` accepts `known` when it is in task text.
- Assert `invite_user_to_slack.user_email` accepts `fact:@contact.email` when
  both fields are tagged `kind: "email"`.
- Assert `send_email.recipients` accepts `fact:@shared_file_entry.shared_with`
  after both fields are tagged `kind: "email"`.
- Assert an untagged field keeps strict `fact:*.argName` behavior.
- Keep existing missing-handle and untrusted-handle rejection tests passing.

Core-side regression coverage lives in:

- `interpreter/eval/record.test.ts`
- `interpreter/eval/exec/policy-builder.test.ts`
- `core/policy/fact-requirements.test.ts`
- `core/policy/guards-defaults.test.ts`
