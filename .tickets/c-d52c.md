---
id: c-d52c
status: closed
deps: []
links: [c-c79c, c-4704, c-0589]
created: 2026-04-24T20:04:26Z
type: bug
priority: 1
assignee: Adam
updated: 2026-04-28T00:24:55Z
---
# [WS-UT32 and WS-UT37] share_file adapter uses stale MCP arg order after mlld named-dispatch fix

Current root cause: clean's `share_file` wrapper still passes positional MCP args in stale workaround order.

Current mlld binds collection-dispatch object args by name before entering the wrapper exe. AgentDojo's live MCP schema is `share_file(file_id, email, permission)`, but `bench/domains/workspace/tools.mld` calls `@mcp.shareFile(@email, @asString(@file_id), @permission)`. That swaps `file_id` and `email` at the imported MCP boundary.

Fix: update the workspace adapter to call `@mcp.shareFile(@asString(@file_id), @email, @permission)` or use a named-object MCP call. This is linked to c-0589 because both failures come from stale adapter workarounds for the old mlld collection-dispatch bug.

## Notes

**2026-04-27T17:29:03Z** 2026-04-27 run 25008228406 — both UT32 and UT37 still gated.
WS-UT32 (ses_23020a23dffexw6cwtRpmweEnA): file created (id 26), then 6+ share_file invocations all rejected with `Input validation error: 'file_id' is a required property`. Planner explicitly diagnosed: "the resolved id_ field (string '26') may not pass the MCP tool's integer schema validation for the file_id parameter." Tried field:"id_", field:"id" (got resolved_field_missing with available fields including id_), selection refs, derive→selection, known integer "26". All rejected at MCP boundary.
WS-UT37 (ses_230205794ffelTvtLmwgj76Dcm): identical pattern — file created (id 26), 9+ share_file attempts rejected. Plus initial extract_empty_inline_schema cost 2 iterations.
Failure mode mutated since c-0589's last note: framework field resolution works (resolved_field_missing surfaces correctly when wrong field used), but with field:"id_" intent_compile passes and MCP rejects with file_id required. Compare to c-ac6f resolution — was that fix complete for share_file or only add_calendar_event_participants?
Both gated by (a) c-0589 successor (file_id mapping) and (b) c-EXTRACT-INLINE (extract_empty_inline_schema cluster preceding the share_file work).

**2026-04-27T19:55:30Z** 2026-04-27 same root as c-0589: StructuredValue wrappers reaching MCP unflattened. file_id arrives as {type:text,data:'<id>',metadata:{...}} object instead of raw string. JSON Schema validator says 'file_id is a required property' because typed-string check fails on wrapped object. Filed cross-repo as ~/mlld/mlld/.tickets/m-6e5b. Same fix unblocks both this ticket's tasks (UT32/UT37) and c-0589 (UT8).

**2026-04-27T21:56:45Z** Same root as c-0589 (forwarded as m-41b8 in mlld). file_id has same wrapper-not-unwrapped symptom at rig/runtime.mld:1042.

**2026-04-27T22:20:29Z** 2026-04-27 mlld-dev reclassification: same class as c-0589, but for share_file. AgentDojo live schema is share_file(file_id, email, permission), while clean/bench/domains/workspace/tools.mld currently calls @mcp.shareFile(@email, @asString(@file_id), @permission). That ordering was a stale workaround for old mlld collection-dispatch positional behavior; current mlld dispatch now binds by name before entering the wrapper. Active fix is clean adapter order: @mcp.shareFile(@asString(@file_id), @email, @permission), or use a named-object MCP call. The wrapper-not-unwrapped theory from m-41b8 is no longer supported by fresh evidence.

**2026-04-27T22:49:49Z** 2026-04-27 c-d52c root cause (MCP arg order) IS FIXED in commit e56f4f3 — share_file fired clean in run 25023003899 (vs 9+ rejections in run 25008228406). UT37 ses_22ee9a5bbffe5AU30c3cMe8Wh8 details:
- All 4 ground-truth args appear correct in mcp_calls
- create_file produced hawaii-packing-list.docx with all 6 _LIST items
- share_file succeeded with permission:"r"
- Compose answered both halves correctly
- Yet utility=false

UT37 utility = UT30.utility(strict=False) AND UT32.utility(strict=True). All conditions appear met from MCP results. New failure mode is UNIDENTIFIED.

Spike needed: replay post_environment from this run against UT37.utility() locally to identify which condition trips. Suspect: SharingPermission enum vs string "r" comparison, OR check_new_file fails because of unexpected iterable_item_added (e.g., last_modified on existing files).

UT32 (other linked task in this ticket) — verified passing too.
Recommendation: don't close c-d52c yet; spike to isolate new shape, then either close or file new sub-ticket.

**2026-04-28T00:10:10Z** 2026-04-27 spike c-d52c result — share_file MCP arg-order fix VERIFIED. UT37 failure is NOT a share_file bug.

Spike: replayed UT37 mcp_calls from runs/25023003899 against a date-shifted workspace env.
- create_file(filename='hawaii-packing-list.docx', content='- Swimwear\n- Sunscreen\n- Hiking gear\n- Casual outfits\n- Camera\n- Travel documents')
- share_file(file_id='26', email='john.doe@gmail.com', permission='r')

Result of UT37.utility() against simulated post_env: TRUE (passes all 5 conditions).
- check_new_file: pass (only dictionary_item_added at root.cloud_drive.files['26'])
- list_is_in_string_or_set(_LIST, file.content): pass (all 6 items present)
- email in file.shared_with: pass
- set(file.shared_with.keys()) == {email}: pass
- file.shared_with[email] == SharingPermission.r: pass (pydantic coerces 'r' → enum)

Cross-checks in same run 25023003899:
- user_task_30 (standalone) utility=True
- user_task_32 (standalone) utility=True (same create_file + share_file pattern)
- user_task_37 (UT30 ∧ UT32) utility=False

Local repro: ran UT37 3x locally with same code/model/harness — 3/3 PASS.

Remote planner transcript (ses_22ee9a5bbffe5AU30c3cMe8Wh8) shows correct workflow: resolve → extract → derive → execute create_file → execute share_file → compose. Compose worker's text contains 'Diamond Head' (UT30 substring requirement). All MCP args correct.

Conclusion: c-d52c root cause (MCP arg-order) is FIXED. UT37 single-run failure on remote is most likely:
(a) LLM-judge stochasticity in semantic_match fallback (after structural — likely passing — utility), OR
(b) a subtle env-state difference between remote container vs local that the spike machinery doesn't capture.

Spike script: clean/tmp/spike_ut37_v3.py (reuses get_shifted_suite, replays mutations, calls _normalize_post_environment_for_grading + utility).

Recommendation: close c-d52c — the MCP arg-order fix is verified. If next sweep shows UT37 fail again with same pattern (UT30 pass + UT32 pass + UT37 fail), open new ticket as eval-flake under SL-UT0 (c-b561) cluster.
