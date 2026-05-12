---
id: c-acd8
status: open
deps: []
links: [c-3162, c-41e1]
created: 2026-05-12T01:21:47Z
type: task
priority: 2
assignee: Adam
updated: 2026-05-12T01:21:50Z
---
# [c-3162 followup] Rewrite 2 execute-worker-policy xfail'd tests post-Gap-C

## What needs to happen

Two tests in tests/rig/execute-worker-policy.mld are xfail'd because they relied on the silent-bypass:

- testExecuteWorkerOptionalFactOmission
- testKnownDatetimeCanonicalization

Both dispatch schedule_meeting (labels: exfil:send) WITHOUT participants. mlld's no-send-to-unknown rule correctly denies — there's no known destination. Pre-fix this silently passed via @toolCallError narrowness.

## Options

Option A: Move both tests to a non-exfil tool (e.g. create_note). Lose the schedule_meeting-specific shape coverage.

Option B: Add participants=[{known: 'Alice'}] to the fixture, change what optional fact is being omitted (if schedule_meeting has another optional field). Preserves shape but the optional-fact-omission becomes about a different field.

Option C: Reframe both tests to assert the policy denial fires — they become 'deny tests' instead of 'pass tests', verifying the defense layer specifically.

Option D: Argue the case to mlld-dev that no-send-to-unknown should only fire when destination is PRESENT AND NOT KNOWN — missing destination = no exfil = no deny. This is a real semantic question for AgentDojo 'create solo focus block' workspace tasks where users legitimately schedule events with no participants.

## Recommendation

C for the test rewrite (clean assertion of the defense), then surface D to mlld-dev separately as a workspace-domain question. C is bounded (~30min); D is a design discussion.

## Linked
c-3162, c-41e1

