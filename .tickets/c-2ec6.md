---
id: c-2ec6
status: closed
deps: []
links: [c-c2e7, c-9c6f]
created: 2026-05-06T00:16:39Z
type: chore
priority: 3
assignee: Adam
tags: [tests, docs]
updated: 2026-05-07T00:46:33Z
---
# Document seeding/state-factory pattern in tests/README.md

tests/README.md scripted-LLM section currently doesn't cover:

1. The state factories in tests/lib/security-fixtures.mld (@stateWithExtracted/Derived/Resolved/ResolvedAndExtracted).
2. @runWithState — when to use it vs the basic @runScriptedQuery.
3. The two-call pattern for 'real minted handle' attacks (mint via setup query, capture @setupRun.mx.sessions.planner.state, feed to @runWithState).

Add a 'Seeding state' subsection. testSelectionRefRealSlackMsgHandleRejected in security-slack.mld is the worked example to point at.

Acceptance:
- README has a Seeding state subsection that covers all three points above
- A new author writing 'attack against a real minted handle' has enough to start without reading the existing security suites


## Notes

**2026-05-07T00:46:33Z** Done in commit 686b0fe. New 'Seeding state for security tests' subsection in TESTS.md covers @stateWithExtracted/Derived/Resolved/ResolvedAndExtracted factories, the two-call setup pattern for real-handle attacks, and when to use each. testSelectionRefRealSlackMsgHandleRejected called out as the canonical worked example.
