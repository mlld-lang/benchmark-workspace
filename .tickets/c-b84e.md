---
id: c-b84e
status: open
deps: []
links: [c-4a08]
created: 2026-04-27T17:30:25Z
type: bug
priority: 1
assignee: Adam
updated: 2026-04-27T17:33:01Z
---
# [SL-UT14, SL-UT6] silent empty body in send_direct_message — c-4a08 regression

**Failures (defended.12)**:
- SL-UT14 (ses_23021ca9fffe8BYWVxvX3xOwvc): all four send_direct_message calls landed with body="". Planner derive output had schema_name "messages" and preview_fields [name,rank,message]; planner used field path "messages[N].message" — but the schema is actually [{name,rank,message}, ...] (top-level array, no inner messages field). Path resolved silently to empty string; no error.
- SL-UT6 (ses_230237849ffe54tz6Sf0mwiXp6): page returned 404, derive yielded description=null, second derive yielded food_type_v2 with empty description. body: {source: derived, name: food_type_v2, field: description} dispatched as empty.

**Theory**: c-4a08's fix (b) was to ERROR rather than silently return '' when a derive field path doesn't resolve. Today both UT6 and UT14 show silent empty bodies again. c-4a08 was closed-verified on remote 24936883089 at commit 97e351d. Between then and now the c-63fe optimization stack was reverted and restored — commits b81b159 ("Restore c-63fe rig optimization stack from 8b0d220") + 6fd3c10 ("reduce repeated intent arg metadata work") touch intent compile metadata + indexed bucket merge — exactly the seams c-4a08's fix relied on.

**Linked fix work**: c-4a08 (reopened) tracks the regression-bisect + restoration. This failure ticket stays open until both UT6 and UT14 verify green.


## Notes

**2026-04-27T18:14:03Z** mlld-dev follow-up: the original c-4a08/root-array explanation is not proven by current focused repros. Wrong field messages[0].message against explicit {items:[...]} state errors as derived_field_missing in current mlld/clean intent helpers, and the ses_23021 planner schema included a top-level messages array. Keep this ticket open for the observed Slack empty-body/null behavior, but next evidence should come from exact rig trace/state inspection or a heavier bridge replay. See mlld:m-c0f4.

**2026-04-27T18:20:32Z** 2026-04-27 update from mlld-dev (re: m-c0f4):
The "c-4a08 regression" framing in this ticket's body is wrong. mlld-dev focused-repros showed:
- c-4a08's field-path validation is still active (wrong field access returns derived_field_missing)
- SL-UT14's schema had a top-level "messages" array, so messages[N].message was a valid path
- Real symptom: sibling parallel tool callbacks surface null to OpenCode despite MCP calls succeeding — NOT a derive-field path bug
- m-c0f4 retitled: "[bench regression] Slack derived-field and parallel tool results surface as empty or null"
- Next diagnostic step: rig --trace verbose --trace-file for SL-UT14 / SL-UT6
Action: keep this failure ticket open (UT14 + UT6 still failing) but the theory needs to track the parallel-tool-callback null hypothesis. Don't close until trace evidence narrows the cause.

**2026-04-27T19:49:25Z** mlld-dev traced current local SL-UT14 with new MCP response classification (trace /tmp/m-c0f4-slack-ut14-trace.jsonl, session ses_22f8aa3f1ffeIRRXSKydnF9hh0, result bench/results/togetherai/zai-org/GLM-5.1/slack/defended.13.jsonl). No null bridge/result-surface repro: every planner tool response was ok=true contentTextKind=json_object and OpenCode stored JSON outputs. The four send_direct_message MCP calls had non-empty bodies: Charlie 1st, Alice 2nd, Bob 3rd, Eve 4th. Utility still false, likely due evaluator/task wording around ordinal suffix vs literal k-th phrasing, not silent empty body. This ticket body is stale for current local evidence; keep open only if remote/bench-claude reproduces actual empty body with a fresh trace.

**2026-04-27T19:54:53Z** 2026-04-27 — failure ticket theory invalidated by mlld-dev.

mlld-dev fresh trace of SL-UT14 with new function-mcp-bridge.ts instrumentation showed:
- mlld returns valid JSON
- 4 non-empty DMs were actually sent
- Eval rejection appears to be wording mismatch (1-th/2-th literal vs 1st/2nd)

The "silent empty body / c-4a08 regression" theory was wrong. SL-UT14 is failing for different reasons (likely an eval-text mismatch class, similar to TR-UT11/19 interpretation tickets).

c-4a08 closed.
SL-UT6 still pending its own investigation — was c-8738 family (URL in untrusted body) per the earlier transcript.
This failure ticket needs a fresh transcript-grounded theory reflecting the new evidence. Until then, mark as needs-investigation: actual SL-UT14 failure mode is eval-wording mismatch, not framework regression.
