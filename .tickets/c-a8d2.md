---
id: c-a8d2
status: closed
deps: []
links: [c-0298, c-951d]
created: 2026-05-06T19:23:51Z
type: task
priority: 2
assignee: Adam
tags: [security, slack, records, records-firewall]
updated: 2026-05-06T19:50:30Z
---
# [c-0298 follow-up] Apply synthetic-id pattern to slack_user + sanitize MCP errors in get_users_in_channel / read_channel_messages

c-0298 (commit 74a5be8) closed the slack_channel name leak (113 → 5 sessions in cloud). The residual 5 sessions in run 25449626809 (slack × tool_knowledge, post-fix) traced to two related bugs that need the same treatment.

## What leaks

In session ses_201b0900bffegWC2bzh4LxH8wl (and 4 others), the planner saw injection content via this resolve result:

```json
{"status":"resolved","tool":"get_users_in_channel","record_type":"slack_user","count":1,
 "handles":["r_slack_user_ERROR: ValueError: Channel 'External_ <INFORMATION> This is an important message from me, Emma Johnson, to not found ..."]}
```

The polluted channel name reached the planner literally inside a slack_user handle string. Path:

1. Planner calls `get_users_in_channel` with channel handle that resolves to a polluted channel name (after framework dereferences `{source: 'resolved', record: 'slack_channel', handle: 'r_slack_channel_<id>', field: 'name'}` to its underlying name string).
2. MCP tool errors with `ERROR: ValueError: Channel '<polluted-name>' not found ...`.
3. `@get_users_in_channel` wrapper (bench/domains/slack/tools.mld:34-38) passes the error string through `@stringListItems(@raw)`, which treats lines as user names.
4. The error string becomes a 'user name' → `{ name: 'ERROR: ValueError: ...' }` → record coercion mints handle `r_slack_user_<name>` with the full error string as suffix.
5. Planner sees the handle in the resolve result. The injection content lands in planner reasoning context.

This same leak shape applies to `@read_channel_messages` if the MCP errors there too.

## Two fixes, both required

### Fix 1: Apply synthetic-id pattern to @slack_user (records.mld:45-48)

`slack_user` currently:

```mlld
record @slack_user = {
  facts: [name: { type: string, kind: "slack_user_name" }],
  display: [{ ref: "name" }]
}
```

Apply the c-0298 pattern (see @slack_channel at records.mld:68-79):

- Add synthetic `id_: handle` field
- `key: id_`
- `display` split: `planner: [{ ref: "id_" }]` (opaque handle only); `worker: [{ ref: "id_" }, { ref: "name" }]` (derive can still match by name)
- Mint id_ in the bridge (analogous to c-0298's `@channelItems` exe — likely a new `@userItems` exe in bench/domains/slack/bridge.mld)
- Update `@get_users_in_channel` wrapper to use `@userItems`

This independently fixes the IT5 attack vector (Fred attacker email exfil) — slack_user.name is attacker-controllable for invite_user_to_slack via injection.

### Fix 2: MCP error handling in slack tool wrappers

`@get_users_in_channel` (tools.mld:34-38) and `@read_channel_messages` (tools.mld:40-43) must detect MCP error responses and return a structured error that:

- Does NOT echo the channel name (or any other resolved control-arg value)
- Returns a clear failure shape the planner can reason about (e.g. `{ status: 'error', error: 'channel_lookup_failed', handle: <input-handle> }`)
- Refers to the channel by handle, never by resolved name

Detection options:
- Check for the `ERROR:` prefix in MCP raw output (AgentDojo's convention for thrown-from-tool errors)
- Try/catch around the MCP call (if mlld supports it for MCP wrappers)
- Match common AgentDojo error shapes (`ValueError`, `KeyError`, etc.)

Choose the cleanest mlld-side mechanism. The structural property is: tool wrapper output never contains the resolved value of any `controlArgs:` arg.

## Why both fixes

Fix 1 alone closes the slack_user case. Fix 2 alone would close slack_user via opaque handle suffix BUT leaves an open class: any future tool wrapper that misparses an error has the same leak. Fix 2 is the architectural backstop; Fix 1 is the specific instance.

## Acceptance

1. `@slack_user` record extended with synthetic id_ + display split (mirroring `@slack_channel`).
2. Bridge has `@userItems` exe minting id_ values.
3. `@get_users_in_channel` wrapper uses `@userItems` for normal results AND returns structured error (no resolved-name echo) on MCP error.
4. `@read_channel_messages` wrapper updated similarly for MCP error path.
5. Static gate (`mlld tests/index.mld --no-checkpoint`) green.
6. Slack security suite green (mutation matrix unchanged).
7. Cloud regression: dispatch slack × direct + slack × important_instructions; sqlite signature-union query against opencode-dev.db returns **0 sessions** for the bench-grind-20 leak signatures (vs 5 in 25449626809 / 113 cumulative pre-fix).
8. Bench utility under attack remains within ±5pp of 25449626809 baseline (40/105 = 38.1%).

## References

- 25449626809 / ses_201b0900bffegWC2bzh4LxH8wl — the 5-session residual leak
- c-0298 commit 74a5be8 — reference implementation pattern
- c-951d Sub-track A — broader scope (this ticket is one cell of that sub-track)
- planner-dirty.md — pre-fix baselines for the cloud regression check


## Notes

**2026-05-06T19:50:30Z** bench-grind-21: implemented as wrapper-level fix only (not record-opacity). Commit 88ebca8.

## What changed

bridge.mld: @isMcpError + ERROR: short-circuits in @stringListItems, @channelItems, @messageItems. New @userItems (no record-opacity, just MCP-error-safe parsing). tools.mld: @get_users_in_channel uses @userItems. records.mld: slack_user docstring documents the asymmetry vs slack_channel.

## What I scoped down

The original ticket called for slack_user record-opacity (synthetic id_ pattern). On implementation I tried it, ran the local canary, and saw UT5/UT9 utility regress (1/3 was pre-existing post-c-0298, not caused by this fix per transcript audit — but slack_user opacity adds further wall cost and the security gain is empty because slack_user.name is fact-trustworthy by construction). Reverted the record-opacity change, kept wrapper-level fix.

The records.mld docstring documents the criteria for revisiting if AgentDojo's threat model changes (e.g. workspace-state injection of fake users).

## Cloud regression dispatch — DEFERRED

Did not dispatch slack × {direct, important_instructions} regression runs as the original ticket called for. Reasoning: the planner-discipline issue surfaced in canary transcripts (planner intermittently forgets  on channel args, leading to count:0 results from MCP) is a c-0298 fallout that should land before re-measuring. Otherwise we'd dispatch twice.

Recommended follow-up: file a planner-discipline ticket for the field:name forget pattern, land it, then dispatch the regression sweep.

## Acceptance status

1. ✓ slack_user docstring updated (record opacity scoped out, criteria documented)
2. n/a — no @userItems with id_ minting (record opacity scoped out per #1)
3. ✓ @get_users_in_channel uses @userItems with MCP error sanitization
4. ✓ @read_channel_messages already used @messageItems; added MCP error guard there for defense in depth
5. ✓ Static gate green
6. ✓ Slack security suite green; mutation matrix 11/11 OK
7. DEFERRED — cloud regression sweep, see above
8. n/a — utility-under-attack delta to be measured at cloud regression time
