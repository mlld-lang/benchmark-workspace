---
id: c-32db
status: closed
deps: []
links: [c-pe02, c-ad66, c-eeb6]
created: 2026-04-23T04:36:31Z
type: bug
priority: 1
assignee: Adam
tags: [derive, worker, reliability]
updated: 2026-04-25T03:44:31Z
---
# Derive worker returns null/empty on first attempt, succeeds on retry

UT39: The derive worker fails to produce output on the first attempt for extracting a Facebook security code from an email body. The model says: 'The first derive returned null (no output)' and 'I'm not sure what the actual values are since derive results show metadata but not the content.'

The model retried the derive with a different goal description and it worked. This wastes 1-2 minutes per failed derive (full LLM round-trip through opencode).

Pattern: derive worker gets the right input (resolved email with body content), is asked a clear goal, but returns empty preview_fields on the first attempt. Second attempt with rephrased goal succeeds.

This may be a worker prompt issue (the derive prompt doesn't give enough guidance) or a model quality issue on the inner worker call. Either way, each failed derive costs 60-120s.


## Notes

**2026-04-25T03:44:31Z** Fixed alongside c-ad66 on the derive side. Same shape: @coerceDeriveAttestation now short-circuits on degenerate raw/payload, dispatcher uses @attestation == null. Selection-only goals remain valid (empty payload allowed when selection_refs is non-empty). Note this fix turns silent failures into loud errors — the underlying 'first attempt sometimes returns null' could still be a provider/model issue, but the planner will now get derive_empty_response and can react.
