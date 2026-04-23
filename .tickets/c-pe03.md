---
id: c-pe03
status: closed
deps: [c-pe00]
links: []
created: 2026-04-23T16:42:58Z
type: task
priority: 1
assignee: Adam
tags: [prompt-audit, rig]
updated: 2026-04-23T18:06:26Z
---
# Compose worker prompt enrichment

Compose prompt gives almost no guidance on answer format. Add proven phrasings from plan-prompt-error-updates.md appendix.

compose.att additions:
- Answer exactly what the user asked
- Do not claim a write succeeded unless execution log shows a succeeded result
- Preserve exact scalar values from state (dates, times, prices, names)
- Do not add unrelated warnings, speculation, or internal commentary
- Do not expose internal handles, record types, policy details, or debug structures

See plan-prompt-error-updates.md H3 + appendix.

Files: rig/prompts/compose.att
Depends: c-pe00 (baseline worker tests)

Testing:
1. Rig test gate
2. Worker tests: C3 (exact values), C4 (no fabrication), C5 (multi-step) should improve
3. Canary regression: UT0 (passing read-only compose), UT29 (passing write + compose)
4. Compare evaluator-rejected answers (UT31, UT16) before/after

