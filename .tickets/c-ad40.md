---
id: c-ad40
status: closed
deps: []
links: [c-a6b7, c-c04c]
created: 2026-05-06T11:09:29Z
type: task
priority: 2
assignee: Adam
tags: [security, banking, records]
updated: 2026-05-06T11:12:23Z
---
# banking: add exact: declaration to @update_user_info_inputs (close B4 structural gap)

Add `exact: [first_name, last_name, street, city]` to `@update_user_info_inputs` in bench/domains/banking/records.mld:144-151. Closes the B4 historic breach (UT13 × IT7) at the structural layer.

## Current state

```mlld
record @update_user_info_inputs = {
  facts: [],
  data: {
    trusted: [first_name: string?, last_name: string?, street: string?, city: string?]
  },
  update: [first_name, last_name, street, city],
  validate: "strict"
}
```

No `exact:` declaration. Result: the source-class firewall accepts extracted/derived values for these fields (theyre payload, not control args), and policy.build does not reject because update_user_info has labels `["execute:w", "tool:w", "profile:w", "update:w"]` — `profile:w` doesnt match any defense rule (no-untrusted-privileged etc). Currently undefended at all rehearse-time / policy.build-time layers.

The B4 breach (UT13 × IT7 in banking) was historically real. Banking UT13 currently passes via planner-quality (model declines to extract addresses from tainted files), but theres no structural defense to fall back on if model behavior regresses.

## Fix

```mlld
record @update_user_info_inputs = {
  facts: [],
  data: {
    trusted: [first_name: string?, last_name: string?, street: string?, city: string?]
  },
  exact: [first_name, last_name, street, city],
  update: [first_name, last_name, street, city],
  validate: "strict"
}
```

This puts update_user_info behind the same defense as update_password (which has `exact: [password]`): `non_task_source_in_exact_payload_arg` (intent.mld:801) rejects any extracted/derived source on these fields. Also `known_value_not_in_task_text` if a `known` value isnt literally in the task.

## Semantic justification

Address/name fields should come from the users task text. Theres no fact-bearing record family for "verified user address" the way `@iban_value` exists for transactions. So if the user is updating their address, the values have to be in the task. Same as password.

## Risk

- Tests: testUpdateUserInfoExtractedAcceptedAtRehearse (security-banking.mld) currently asserts ok=true (documents the gap). Will need to flip to asserting ok=false. See follow-up test ticket.
- Sweep: banking UT13 currently passes via planner-quality. After the fix it should still pass — the planner sources address values from task text per current model behavior. If any banking task legitimately authors update_user_info from a prior tool result, that path would now reject — unlikely but worth verifying. See follow-up sweep ticket.
- One-line record edit. Low risk.


## Notes

**2026-05-06T11:12:23Z** Landed 2026-05-06 (bench-grind-20). One-line edit to bench/domains/banking/records.mld:149 — added `exact: [first_name, last_name, street, city]` to @update_user_info_inputs. Defense fires via non_task_source_in_exact_payload_arg (intent.mld:801). c-c04c flipped the test to assert rejection; mutation registry updated. Closing.
