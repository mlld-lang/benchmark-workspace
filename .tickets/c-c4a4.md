---
id: c-c4a4
status: open
deps: []
links: []
created: 2026-04-25T20:01:43Z
type: bug
priority: 2
assignee: Adam
tags: [travel, encoding, utf8]
---
# Double-encoded UTF-8 in restaurant names appears as separate values across multiple travel tasks

Multiple travel tasks (UT2, UT8, UT9, UT10, UT11, UT12) show '\"Breizh Caf\\xE9\"' as a SEPARATE entry alongside 'Breizh Café' in restaurant_names arrays passed to MCP tools. The escaped form appears wrapped in extra quotes, suggesting somewhere a string is being JSON-encoded with non-ASCII converted to \\xE9 and then re-quoted as a literal value.

Example pattern (UT2 get_rating_reviews_for_restaurants call):
  restaurant_names: ['Breizh Café', 'Bistrot Paul Bert', '"Breizh Caf\\xE9"', 'Chez L'Ami Jean', ...]

Three things wrong:
1. Same restaurant appears twice — one as 'Breizh Café' (correct) and one as '"Breizh Caf\\xE9"' (a literal string of 18 characters that is NOT the restaurant's actual name).
2. The escaped form has surrounding double quotes IN the value — '"Breizh Caf\\xE9"' as a python string is literally "Breizh Caf\xE9".
3. Whatever produced this is round-tripping through some JSON-stringify path that doesn't handle UTF-8 correctly.

Likely sources:
- Planner-derived 'restaurant_names' list passed to MCP — might be coming from a derive worker output that was JSON-stringified and re-parsed somewhere.
- Worker prompt rendering — when rig embeds a planner-supplied list into the worker's prompt template, character encoding may break.
- The intent compiler unwrapping a StructuredValue where the .text or .data has the escaped form.

Investigation: spike with a minimal restaurant_names list including 'Breizh Café' through the call path. Print at each layer:
  planner intent → @compileToolArgs → @callTool → MCP

The double-encoded value adds noise to many travel calls (extra MCP fetches that 404, padding the burn rate of multi-domain loops). May be a contributing factor to TR-UT10/11/12/19 timeouts. Could also confuse derive workers that see two near-identical names.

Likely a runtime issue (mlld) or rig issue, not bench. Worth filing in mlld if root-caused there.

