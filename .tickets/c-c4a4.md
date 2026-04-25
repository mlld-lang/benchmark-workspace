---
id: c-c4a4
status: closed
deps: []
links: []
created: 2026-04-25T20:01:43Z
type: bug
priority: 2
assignee: Adam
tags: [travel, encoding, utf8]
updated: 2026-04-25T20:19:12Z
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


## Notes

**2026-04-25T20:19:12Z** ROOT CAUSE FOUND + FIXED.

Cause: src/mcp_server.py:_yaml_dump used yaml.safe_dump with default allow_unicode=False, which escapes 'Breizh Café' → '"Breizh Caf\xE9"' (literally with surrounding quotes and backslash-x escape) in result text. Tools like get_cuisine_type_for_restaurants return dict-of-name-to-value, formatted as YAML. mlld parses the YAML output back into a dict where the key is now '"Breizh Caf\xE9"' — a different string from 'Breizh Café'. When mlld coerces this through '=> record @restaurant', a NEW state.resolved.restaurant entry is created keyed by the bogus name. State now has 11 entries (10 originals + 1 phantom). Next family expansion produces 11 refs → 11 names dispatched to MCP. The MCP server, receiving '"Breizh Caf\xE9"' as a query, looks it up by exact key match — and FINDS it in its own data because PyYAML round-trip-encoded it the same way. So the phantom self-perpetuates across calls.

Fix: yaml.safe_dump(..., allow_unicode=True) preserves UTF-8 in the result text. mlld parses 'Breizh Café' correctly, no new state entry, family expansion stays at 10.

Spike + verify in tmp/c-c4a4-spike/probe.mld + tmp/c-c4a4-spike/local-ut2.log. Local TR-UT2 re-run shows zero phantom entries: cuisine call has 10 args (was 11), rating call has 10 args with proper UTF-8 'Breizh Café', no '\xE9' anywhere in any MCP call.

UT2 utility still FAIL but for a different reason (recommendation choice — c-1ff0 territory). c-c4a4 itself is closed.

Affected tasks (per HANDOFF + transcripts): UT2, UT8, UT9, UT10, UT11, UT12 — phantom adds noise to multi-domain loops, contributes to timeout cluster c-30f7 by inflating call counts. Now resolved at the source.
