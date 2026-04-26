---
id: c-25af
status: open
deps: []
links: [c-aed5]
created: 2026-04-23T04:39:52Z
type: bug
priority: 2
assignee: Adam
tags: [extract, mcp, tool-bridge]
updated: 2026-04-26T03:50:21Z
---
# WS-UT36 tool-backed extract on resolved file content silently returns null

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

**2026-04-25T18:29:02Z** Per c-aed5 closure (linked): WS-UT36 confirmed manifestation. Extract on resolved vacation-plans.docx (file_id=7) returns extract_empty_response, downstream derive cascades empty, create_file dispatches with content='', compose fabricates packing list. May affect other workspace file/email tasks too — needs spike to confirm scope.

**2026-04-25T18:41:18Z** Spike (tmp/c25af-spike/probe.mld) and regression test (E11 in rig/tests/workers/extract.mld, 23/23 PASS) both ESTABLISH the structural path is clean:

1. resolveRefValue on a synthetic resolved file_entry returns the value with content intact.
2. extractPrompt(query, value, schema, decision) embeds the full file content in the worker prompt (verified: prompt.includes('Diamond Head') == true, prompt length 2484 chars).
3. GLM 5.1 worker LLM, given the clean prompt, returns a properly-shaped extract response with payload.content populated.
4. coerceExtractAttestation accepts the response, payload survives, preview_fields populated.

So the c-25af bug class is NOT structural in the dispatch wiring or the worker prompt or the coercion. The production WS-UT36 failure (preview_fields=[] on the 4th extract attempt) must be one of:

A. Multi-extract session interaction. UT36 had 4 extract calls in sequence — 1st no-schema fail, 2nd tool-backed succeeded, 3rd inline-schema rejected, 4th preview_fields=[]. The 4th may have been deduped via extract_source_already_extracted (rig returns an error envelope summarizing prior preview_fields, which could LOOK like preview_fields=[] depending on how the planner sees it). Need to check whether extract_source_already_extracted fired on call 4 and what it surfaced.

B. Production state shape vs synthetic. Real resolved entry from get_file_by_id may carry wrapper metadata my synthetic lacks. Worth re-running the spike with a state built from an actual MCP call result.

C. Worker behavior under context. The production session had budget warnings + multiple prior errors before call 4. Worker might respond differently in long context vs my isolated probe.

E11 worker test locks in the clean-prompt baseline. If WS-UT36 starts working post a multi-extract investigation, the regression test stays as a canary.

Recommendation: defer further investigation — the spike has shown the structural path is clean, so the next move is a focused production trace pull on UT36's 4th extract specifically, looking for whether dedup fired or whether the worker actually got called at all. Lower priority than c-d52c (which is structural and has a clear fix in flight).
