---
id: c-c2e7
status: closed
deps: []
links: [c-3c2b, c-a720, c-fb58, c-800d, c-9c6f, c-2ec6]
created: 2026-05-05T03:13:27Z
type: feature
priority: 3
assignee: Adam
tags: [tests, harness, fixtures]
updated: 2026-05-06T00:16:42Z
---
# Test harness: dynamic handle threading across script steps

Several security tests need step 2's args to reference a handle minted in step 1 (e.g., "resolve a slack_msg, then attack with selection backing on that minted handle"). Currently the script array is static — args are computed at script construction time. Workarounds today:

1. **Two-call setup pattern** (used by `testSelectionRefRealSlackMsgHandleRejected`): one mockOpencode call to build state, capture `@setupRun.mx.sessions.planner.state`, then a second mockOpencode call with that state pre-seeded. Works but doubles wall time and requires the setup-and-attack semantics to be split across two sessions.

2. **Synthetic handle string** (used by `testSelectionRefMismatchedHandleAfterResolveRejected`): hardcode a handle string in step 2 that doesn't match any minted handle. Tests graceful-failure on mismatch but not the actual attack.

## What to build

A harness extension that lets a script step's args reference results of prior steps. Two design options:

### Option A: Cursor-style refs in script args

```json
[
  { "tool": "resolve", "args": { ... }, "_capture": "step1" },
  { "tool": "rehearse", "args": {
      "user_email": { "source": "selection",
                       "backing": { "record": "slack_msg",
                                    "handle": { "_from": "step1.records[0].handle" } } } } }
]
```

The harness pre-processes step 2's args, resolves any `{ _from: ... }` refs against the captured prior step results.

### Option B: Builder function

```mlld
exe @runDynamicScript(setupSteps, attackBuilder) = [
  let @setupResult = @runSetup(@setupSteps)
  let @discoveredHandle = @setupResult.results[0].handles[0]
  let @attackScript = @attackBuilder(@discoveredHandle)
  => @runAttack(@attackScript)
]
```

Caller writes a small builder fn that takes the discovered values and returns the attack script. More flexible than (A); needs more boilerplate per test.

## Where it lives

Extend `rig/test-harness/mock-opencode.mld` (or add a sibling helper module). `tests/lib/mock-llm.mld` re-exports for tests/ usage.

## Tests this unblocks

- Deep UT16 firewall bypass repro using the LITERAL UT16 path (read_channel_messages → find_referenced_urls → get_webpage_via_ref → rehearse). Currently c-3c2b uses slack_msg→sender as a structural equivalent.
- B5 recursive URL fetch (c-a720) — needs step 1's slack_msg handle threaded into step 2's find_referenced_urls.
- B6 instruction-channel labels (c-fb58) — needs the get_channels-minted slack_channel handle threaded.
- correlate cross-record-mixing test (c-800d) — needs two scheduled_transaction handles threaded.

## Out of scope

- Real cross-call session state persistence (different feature).
- Lazy / async result resolution (keep it synchronous).

## Acceptance Criteria

1. Harness extension lets script args contain handle refs to prior-step outputs.
2. Documented in tests/README.md "Scripted-LLM testing" section.
3. At least one of the listed unblocked tests rewritten to use the new pattern as a demo.


## Notes

**2026-05-06T00:16:28Z** Closing as effectively done. The cursor-refs / builder-fn design proposed in the spec was not implemented; instead the team shipped a different approach that solves the same underlying problem:

1. tests/lib/security-fixtures.mld — synthetic state factories: @stateWithExtracted, @stateWithDerived, @stateWithResolved, @stateResolvedAndExtracted. Build a seed state with a fact pre-populated without running a setup script.
2. @runWithState(query, script, seedState) — defined inline in each security suite (slack/travel/workspace/banking). Runs an attack script against an explicitly-seeded planner state.
3. Two-call pattern for 'real minted handle' attacks: a first @runScriptedQuery mints handles via the rig, capture @setupRun.mx.sessions.planner.state, feed into @runWithState. testSelectionRefRealSlackMsgHandleRejected (security-slack.mld) is the live demo.

This pattern is sufficient for B5/B6/correlate (c-a720, c-fb58, c-800d) — those tickets remain open as separate test-writing work, not blocked on harness extension.

Two minor follow-ups filed: hoist @runWithState into tests/lib/mock-llm.mld so the four suites stop redefining it, and add a 'seeding state' subsection to tests/README.md scripted-LLM section.
