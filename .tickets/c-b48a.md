---
id: c-b48a
status: closed
deps: []
links: []
created: 2026-04-24T23:15:10Z
type: bug
priority: 2
assignee: Adam
updated: 2026-04-25T03:07:14Z
---
# File ticket: travel router synonyms incomplete

After replacing the LLM router with a deterministic keyword matcher (commit pending), travel UT0 'place to stay' didn't match the hotel group. Fixed by adding synonyms (place to stay, lodge, lodging, accommodation, stay at, reservation, etc). Verify travel UT0 now passes router classification with hotel tools available.

