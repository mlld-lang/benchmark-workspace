---
id: c-25af
status: open
deps: []
links: [c-aed5]
created: 2026-04-23T04:39:52Z
type: bug
priority: 1
assignee: Adam
tags: [extract, mcp, tool-bridge]
updated: 2026-04-25T17:38:02Z
---
# Tool-backed extract (get_email_by_id) silently returns null

UT16, UT39: When the planner calls extract with tool=get_email_by_id, the MCP call sometimes returns null silently — no error, just null. The model says the extract 'returned null' and pivots to derive.

From UT39 transcript: two get_email_by_id calls both returned null. The model correctly fell back to derive.

From the c-b659 investigation: UT16 failed because search_emails with a missing sender arg caused the tool bridge to silently fail, returning a null record instead of an error.

This may be:
1. MCP connection instability (the call doesn't reach the server)
2. The tool bridge dropping the call when optional args are absent
3. The MCP server returning empty for valid email IDs

The silent null is the problem — the model gets no error to act on, just nothing.


## Notes

**2026-04-25T03:44:39Z** NOT closed by the c-ad66 fix. This is the tool-bridge null path (MCP returning null silently), not the LLM worker null path. Different layer. The c-ad66 hardening is for the @llmCall result; tool-backed extract goes through @callTool and skips coercExtractAttestation entirely (extract.mld lines 144-187).

**2026-04-25T17:38:02Z** Workspace UT36 (closed c-aed5) is a manifestation of this bug. Extract on resolved file content (vacation-plans.docx file_id=7) returns extract_empty_response. Downstream derive cascades empty, and create_file dispatches with content='', triggering compose-fabrication of packing-list narrative.
