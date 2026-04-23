---
id: c-pe08
status: closed
deps: [c-pe05]
links: []
created: 2026-04-23T16:44:02Z
type: task
priority: 2
assignee: Adam
tags: [prompt-audit, rig]
updated: 2026-04-23T18:47:58Z
---
# Resolve attestation and extract dedup refinements

Refinements to already-working messages — lower priority polish.

Resolve attestation (planner.mld):
- Add visible field list to resolve success summary so planner can see what it got without re-resolving
- Consider adding a hint: 'If these fields answer your question, call compose now.'

Extract dedup (extract.mld):
- extract_source_already_extracted message: add list of previously extracted fields so planner can decide whether to extract differently

See plan-prompt-error-updates.md M2 + M3.

Files: rig/workers/planner.mld (resolve summary), rig/workers/extract.mld (dedup message)
Depends: c-pe05 (higher-priority error messages first)

Testing:
1. Rig test gate
2. Canary: UT2 (over-resolving should reduce)
3. Regression: UT3 (passing resolve + compose)

