# Rig Handoff: Wrong-Record Fact Bypass

## Problem

The rig source-class firewall can currently lower a resolved or selection-backed
control arg with proof from the wrong fact subject. The concrete failing shape is:

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

Core already supports explicit arg-to-proof-subject mapping through
`policy.facts.requirements`. Use that as the runtime contract.

The rig should synthesize most requirements from input records so userland does
not have to maintain a parallel policy block for every write tool.

Default for each input-record fact field:

```text
arg=<fieldName>
accepted=["known", "fact:*.${fieldName}"]
```

For example, this input record:

```mlld
record @invite_user_to_slack_inputs = {
  facts: [user: string, user_email: string],
  data: [],
  validate: "strict"
}
```

can synthesize:

```mlld
facts: {
  requirements: {
    "@invite_user_to_slack": {
      user: ["known", "fact:*.user"],
      user_email: ["known", "fact:*.user_email"]
    }
  }
}
```

This default rejects `fact:@slack_msg.sender` for `user_email` without any
hand-authored per-tool policy.

If a tool legitimately accepts a differently named origin fact, declare an
override. Example: an input arg named `recipient` may intentionally accept
authoritative contact email facts.

```mlld
policy @base = {
  defaults: {
    rules: ["no-send-to-unknown"]
  },
  operations: {
    "exfil:send": ["tool:w:invite_user_to_slack"]
  },
  facts: {
    requirements: {
      "@send_email": {
        recipient: ["known", "fact:*.email"]
      }
    }
  }
}
```

Do not implement loose token normalization such as `user_email -> email` inside
the security check. The existing fact matcher's suffix semantics are dot-path
suffixes: `fact:*.user_email` matches a fact field named `user_email`; it does
not match a field named `email`. If userland wants `user_email` to accept
`fact:*.email`, that should be an explicit override.

The security invariant is still "target arg accepts these proof subjects." The
derived default gives every input-record fact field a fail-closed requirement,
and overrides cover the intentionally renamed cases.

## Rig Changes

### 1. Synthesize fact requirements into the base policy

In the rig policy synthesis path, include a `facts.requirements` section for
write-tool input-record fact fields. For each fact field, synthesize:

```mlld
<arg>: ["known", "fact:*.<arg>"]
```

Then merge in any domain/tool overrides for cases where the accepted origin fact
has a different field name.

Example Slack requirements after default synthesis plus selected overrides:

```mlld
facts: {
  requirements: {
    "@send_direct_message": {
      >> Override: Slack users expose `name`, while the write arg is `recipient`.
      recipient: ["known", "fact:@slack_user.name"]
    },
    "@send_channel_message": {
      >> Override: Slack channels expose `name`, while the write arg is `channel`.
      channel: ["known", "fact:@slack_channel.name"]
    },
    "@invite_user_to_slack": {
      >> Override only if the domain has an authoritative user-name source.
      user: ["known", "fact:@slack_user.name"],
      >> Default would be ["known", "fact:*.user_email"].
      >> Use ["known", "fact:*.email"] only if authoritative email records exist.
      user_email: ["known", "fact:*.user_email"]
    },
    "@add_user_to_channel": {
      user: ["known", "fact:@slack_user.name"],
      channel: ["known", "fact:@slack_channel.name"]
    },
    "@remove_user_from_slack": {
      user: ["known", "fact:@slack_user.name"]
    }
  }
}
```

The exact override set should come from domain/tool config, not from hard-coded
global arg names. If no override is configured, the synthesized default remains
active and fails closed.

### 2. Reject wrong subjects during intent compilation

In `rig/intent.mld`, after `resolvedAttestations` is computed for a resolved or
selection-backed control arg and before returning `ok: true`, validate those
attestations against the target operation arg's accepted patterns.

Expected behavior:

```text
arg=user_email
attestations=["fact:@slack_msg.sender"]
accepted=["known", "fact:*.user_email"]
=> reject
```

Suggested error shape:

```json
{
  "ok": false,
  "arg": "user_email",
  "error": "control_arg_wrong_fact_source",
  "attestations": ["fact:@slack_msg.sender"],
  "accepted": ["known", "fact:*.user_email"],
  "hint": "This control arg needs proof matching one of the accepted fact patterns."
}
```

This keeps `rehearse` honest. `policy.build` will also reject once the synthesized
base policy includes the same `facts.requirements`, but compile-time rejection
gives planners a clearer blocked-arg reason and avoids returning `ok: true`.

### 3. Do not require backing record == input record

The input record describes the destination tool schema, not the origin of
legitimate values. A `send_email.recipient` arg commonly comes from
`fact:@contact.email`, not `fact:@send_email_inputs.recipient`.

The security rule should be:

```text
target arg accepts one of these proof subjects
```

not:

```text
backing record must equal input record
```

## Acceptance Tests

Required:

- Un-xfail `tests/suites-scripted/security-slack.mld::testSelectionRefRealSlackMsgHandleRejected`.
- Assert `invite_user_to_slack.user_email` rejects `fact:@slack_msg.sender`.
- Assert `invite_user_to_slack.user_email` accepts `known` when it is in task text.
- Assert default synthesis rejects a differently named fact such as
  `fact:@contact.email` for `user_email` unless a domain override explicitly
  allows `fact:*.email`.
- If an override is configured, assert `invite_user_to_slack.user_email` accepts
  the explicitly allowed email fact.
- Keep existing missing-handle and untrusted-handle rejection tests passing.

Core-side regression coverage lives in:

- `core/policy/fact-requirements.test.ts`
- `core/policy/guards-defaults.test.ts`
