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
`policy.facts.requirements`. Use that as the authoritative contract instead of
inferring from arg names.

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
      "@invite_user_to_slack": {
        user_email: ["known", "fact:*.email"]
      }
    }
  }
}
```

This means `user_email` accepts task-text `known` or a fact label whose field
suffix is `email`. It rejects `fact:@slack_msg.sender`.

Do not implement loose name normalization such as `user_email -> email` inside
the security check. If userland wants that mapping, it should declare it
explicitly in `policy.facts.requirements`.

## Rig Changes

### 1. Synthesize fact requirements into the base policy

In the rig policy synthesis path, include a `facts.requirements` section for
write-tool control args that need narrower proof than `known | fact:*`.

Initial Slack requirements:

```mlld
facts: {
  requirements: {
    "@send_direct_message": {
      recipient: ["known", "fact:@slack_user.name"]
    },
    "@send_channel_message": {
      channel: ["known", "fact:@slack_channel.name"]
    },
    "@invite_user_to_slack": {
      user: ["known", "fact:@slack_user.name"],
      user_email: ["known", "fact:*.email"]
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

The exact set should come from domain/tool config, not from hard-coded global
arg names.

### 2. Reject wrong subjects during intent compilation

In `rig/intent.mld`, after `resolvedAttestations` is computed for a resolved or
selection-backed control arg and before returning `ok: true`, validate those
attestations against the target operation arg's accepted patterns.

Expected behavior:

```text
arg=user_email
attestations=["fact:@slack_msg.sender"]
accepted=["known", "fact:*.email"]
=> reject
```

Suggested error shape:

```json
{
  "ok": false,
  "arg": "user_email",
  "error": "control_arg_wrong_fact_source",
  "attestations": ["fact:@slack_msg.sender"],
  "accepted": ["known", "fact:*.email"],
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
- Assert `invite_user_to_slack.user_email` accepts an explicitly allowed email fact such as `fact:@contact.email` or a domain-specific email record.
- Keep existing missing-handle and untrusted-handle rejection tests passing.

Core-side regression coverage lives in:

- `core/policy/fact-requirements.test.ts`
- `core/policy/guards-defaults.test.ts`

