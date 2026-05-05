---
id: c-3c2b
status: open
deps: []
links: [c-c2e7, c-5ef9]
created: 2026-05-05T03:08:52Z
type: bug
priority: 1
assignee: Adam
tags: [security, firewall, rig, c-5ef9]
updated: 2026-05-05T03:13:32Z
---
# Security tests: deep UT16 firewall bypass — the wrong-record-fact bug

Active firewall bug surfaced by xfail test `testSelectionRefRealSlackMsgHandleRejected` (security-slack.mld). The rig source-class firewall accepts a selection-ref backing on a completely-different record as proof for a control arg. This is the same class as the UT16 cloud sweep finding (run 25324557648).

## What to read first

1. `spec-firewall-wrong-record-bypass.md` — full bug writeup with reproduction, attack shape, where the firewall fails (rig/intent.mld:734-783), and the two-part fix surface (rig + mlld policy.build).
2. `tests/suites-scripted/security-slack.mld` — the xfail test `testSelectionRefRealSlackMsgHandleRejected` and the `@setupSlackMsgState` helper that builds a factsource-bearing fixture by running a real read_channel_messages resolve.
3. `rig/SECURITY.md` §4 "Selection Refs Are Derive-Only and Rig-Validated" — the design intent that the bypass violates (selection refs must point to derive-validated backings, not arbitrary resolved records).
4. The original UT16 transcript: opencode session in `runs/25324561113/opencode.db` — the planner-authored intent that returned ok=true on the cloud:
   ```json
   { "source": "selection",
     "backing": { "record": "referenced_webpage_content",
                  "handle": "r_referenced_webpage_content_web_url_ref_792e70adcae9" } }
   ```

## Test repro (zero-LLM, deterministic)

```
uv run --project bench python3 tests/run-scripted.py --suite slack --index tests/scripted-index-slack.mld
```

The test setup runs a real `read_channel_messages` resolve to mint slack_msg handles, then rehearses `invite_user_to_slack(user_email: {source: "selection", backing: {record: "slack_msg", handle: <real>, field: "sender"}})`. Rehearse returns `ok: true` — the bypass.

## Fix path

Two layers (do both for defense-in-depth):

1. **Rig** (rig/intent.mld:734-783, the resolved-source branch in `compileScalarRefWithMeta`): when emitting `flat_attestations` for a control-arg-eligible value derived from a selection ref, validate that the backing record can actually produce the required label for this arg. The tool's `inputs` record declares the expected fact origin; the backing record must either match or coerce-to-match.

2. **mlld policy.build**: tighten `no-send-to-unknown` and `no-destroy-unknown` so "any `fact:*`" requires the attestation's record/field to align with what's declared on the input record's fact field for that arg, not just any fact attestation in the system.

When the fix lands, the xfail test will xpass and the `selection-ref-wrong-record-bypass` group's note should be updated to record the fix commit.

## Acceptance Criteria

1. testSelectionRefRealSlackMsgHandleRejected xpasses (rehearse returns ok=false on slack_msg.sender → user_email).
2. Equivalent test added for the original UT16 path: read_channel_messages → find_referenced_urls → get_webpage_via_ref → rehearse with selection backing on referenced_webpage_content (also xpass, ok=false).
3. No regression on the source-class firewall tests (12 tests across slack/banking/workspace).
4. SECURITY.md §4 updated with the validation-rule wording the fix implements.


## Notes

**2026-05-05T03:37:07Z** 2026-05-04: mlld-dev sent SECURITY-RIG-WRONG-RECORD-BYPASS.md with the fix design. Authoritative writeup (read this first).

Status:
- mlld policy.build supports policy.facts.requirements ✓ (core/policy/fact-requirements.ts already lands the verifier)
- rig synthesizes facts.requirements into base policy ✗ (NOT WIRED — open work)
- rig rejects wrong subjects at intent compile ✗ (open work, optional but improves rehearse blocked-arg surfacing)

Test status: xfail still — testSelectionRefRealSlackMsgHandleRejected fails with rehearse ok=true. Confirmed by un-xfailing and re-running 2026-05-04. Re-marked xfail.

Implementation breakdown (per SECURITY-RIG-WRONG-RECORD-BYPASS.md §1-§3):

1. Declare per-tool fact requirements in suite tool catalogs.
   Recommended schema (clean addition to the tool entry):
     factRequirements: {
       user: ["known", "fact:@slack_user.name"],
       user_email: ["known", "fact:*.email"]
     }
   Initial set per the doc: send_direct_message, send_channel_message,
   invite_user_to_slack, add_user_to_channel, remove_user_from_slack
   (slack); equivalent for banking/workspace/travel write tools.

2. Synthesize into base policy in rig/orchestration.mld @synthesizedPolicy.
   Walk the tool catalog, collect factRequirements per tool, emit
   under `facts: { requirements: { "@<tool>": { ... } } }`. mlld
   policy.build will then enforce.

3. (Recommended) Add control_arg_wrong_fact_source rejection in
   rig/intent.mld @compileScalarRefWithMeta after resolvedAttestations
   is computed. Rejects with the intended error envelope so rehearse
   surfaces a clear blocked-arg reason. mlld policy.build will catch
   anyway, but compile-time rejection gives planners a better signal.

Acceptance per SECURITY doc + test:
- testSelectionRefRealSlackMsgHandleRejected xpasses
- Companion tests added: invite_user_to_slack.user_email accepts
  known-in-task-text and explicitly-allowed email facts (e.g.
  fact:@contact.email)
- Existing graceful-failure tests still pass
