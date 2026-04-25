---
id: c-dc75
status: closed
deps: []
links: []
created: 2026-04-25T04:33:32Z
type: bug
priority: 1
assignee: Adam
tags: [travel, planner-prompt]
updated: 2026-04-25T04:45:18Z
---
# Travel Pattern C compact: planner stalls in resolve phase at 3-8 iters with no derive/extract/compose

Symptom (post per-task tool routing + resolved_family + c-d428): 12 of 14 travel failures end at 3-8 iterations, all in the resolve phase, with NO extract/derive/execute/compose phases. Affects travel UT2, UT3, UT5, UT6, UT8, UT9, UT10, UT11, UT12, UT17, UT18, UT19.

Earlier this session, Pattern C was the planner doing 30+ resolves on family→metadata tools without ever progressing. Per-task tool routing (only ~5 tools per task) and resolved_family (one ref expands to all instances) reduced the symptom severity from infinite loops to short give-ups, but didn't fix the underlying workflow understanding. The planner now resolves the family + maybe one metadata tool, then stops without trying to derive or compose.

Hypothesis: the planner doesn't understand that after resolving family → metadata, the data is in state and the next step is derive (to rank/filter/select) or compose (to narrate). Tries one or two resolves, gets stuck on what to do next, abandons.

This is the residual 'how to chain family→metadata→derive' workflow gap the travel suite addendum tried to teach but evidently doesn't transmit to the planner reliably.

Spike approach: read 2-3 transcripts from short-stall failures (e.g. UT2/UT5/UT6) and find the reasoning step where the planner gives up. Identify the specific gap in the addendum or planner.att.

Concrete fix candidates:
1. Sharper travel addendum: explicit 'after resolving family + at least one metadata tool, the next call is ALWAYS derive (to rank or select) — do NOT call resolve again on the same family.'
2. Resolve-attestation hint: when state has a family with metadata loaded, the resolve attestation suggests 'derive next.'
3. Per-task tool maps could include the typical phase sequence as a hint to the planner.

Run: 24921398132 (post-cluster-A). 6/20 pass, 14 fail. Transcripts in runs/24921398132/opencode.


## Retraction (2026-04-25)

This ticket is **wrong** — the symptom diagnosed as "Pattern C compact"
is actually MCP server disconnections during travel runs on the
remote runner, not planner workflow confusion.

Evidence: 177 MCP errors in travel run 24921398132 ("Not connected",
"Request timed out", "Connection closed"). The planner was retrying
the same `resolve_family` call repeatedly because each call's tool
result was an MCP infrastructure error, not because the planner
misunderstood the workflow.

opencode_debug.py rendered these MCP errors as `output=null` in the
parts listing, masking the actual error string. Reading the raw part
data via sqlite revealed the true error.

Cross-ref new ticket about MCP server stability on remote runners.
Travel's actual model/framework behavior is unmeasurable from this
run. Need a re-run on a stable MCP host before re-evaluating travel
failure modes.
