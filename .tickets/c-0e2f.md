---
id: c-0e2f
status: open
deps: []
links: []
created: 2026-04-21T04:54:27Z
type: task
priority: 2
assignee: Adam
tags: [cleanup, rig]
---
# Simplify tooling.mld catalog helpers

Collapse @pairsToObject, @toolCatalogObject, @toolEntryObject, and most @tool*Args helpers now that reflection completeness is wired. These exist because the old var tools surface required wrapper gymnastics for metadata access.

