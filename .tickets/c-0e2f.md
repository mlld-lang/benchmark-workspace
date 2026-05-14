---
id: c-0e2f
status: closed
deps: []
links: []
created: 2026-04-21T04:54:27Z
type: task
priority: 2
assignee: Adam
tags: [cleanup, rig]
updated: 2026-05-14T18:05:13Z
---
# Simplify tooling.mld catalog helpers

Collapse @pairsToObject, @toolCatalogObject, @toolEntryObject, and most @tool*Args helpers now that reflection completeness is wired. These exist because the old var tools surface required wrapper gymnastics for metadata access.


## Notes

**2026-05-14T18:05:13Z** Closed 2026-05-14 (ticket-review pass): Duplicate / staler form of c-1f50; folding into structured-label migration.
