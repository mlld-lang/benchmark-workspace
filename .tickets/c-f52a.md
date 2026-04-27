---
id: c-f52a
status: closed
deps: []
links: []
created: 2026-04-26T18:06:50Z
type: bug
priority: 1
assignee: Adam
tags: [compose, execution-log, travel]
updated: 2026-04-27T20:13:35Z
---
# [TR-UT4] compose worker reports 'was not created' despite execute success

**Symptom (run 24962959633):**
TR-UT4 transcript shows planner reasoning "The calendar event was created successfully. Now I need to compose..." Compose IN includes execution_log. Compose OUT says: "...The calendar event 'Booking hotel Montmartre Suites' on April 6th 2026 at 23 Rue Lepic, 75018 Paris, France **was not created**."

The execute call DID succeed (`status:executed`, `summary:executed create_calendar_event`). The first execute attempt failed with `intent_compile_failed` (allow_requires_no_control_args), but the second succeeded. Compose may be reporting the FIRST log entry's failure status, OR may be applying the c-db45 "say not available" rule too conservatively when there's any error in the log.

## Possible causes

1. **Compose reads first matching log entry**: the failed attempt's `status:error` got read instead of the successful retry's `status:executed`.
2. **c-db45 ripple at the execution_log level**: compose can't distinguish "operation eventually succeeded after retry" from "operation failed".
3. **Conservative interpretation**: the compose.att rule "say not available" extends to "say not created" for execute confirmations.

## Fix candidates

1. **compose.att rule:** "If execution_log contains BOTH an error AND a successful status:'executed' or 'sent' entry for the same operation+args, the operation succeeded — report success. Look for the LATEST status entry."
2. **compose stateSummary projection:** filter execution_log to show only the FINAL status per operation (latest entry wins).
3. **Planner.att rule:** "If a write retried after error, mention the success in compose.purpose explicitly (e.g., 'execute succeeded on retry')."

## Connection

Adjacent to c-db45 v2 (c-5a24) — same compose-conservatism pattern. Filed separately because the fix shape differs (execution_log interpretation vs state value visibility).

## Discovered in

Sweep 24962959633 transcript investigation.


## Notes

**2026-04-27T20:13:35Z** 2026-04-27 NOT REPRODUCING post-c-c79c. Same story as c-c23a / c-3457 (both closed as subsumed).

Local TR-UT4 reruns (4 in parallel): 3 PASS, 1 FAIL.
- All 4 runs' compose now narrates SUCCESS ("Calendar event ... has been created"). Original c-f52a symptom was compose saying "was not created" despite execute succeeding — that shape is gone.
- The 1 FAIL (defended.91) has compose narrating success and the actual MCP create_calendar_event call has correct title/date/location. Eval rejects for a different reason — eval-vs-output mismatch class (c-4e09 family), not compose-stale-outcome.

Hypothesis: c-f52a's original symptom from run 24962959633 was a downstream artifact of c-c79c. When the planner burned iterations on the validator's false rejections of inline schemas, the execution_log accumulated mixed error/success rows; compose conservatively narrated failure. With c-c79c fixed, the planner reaches execute cleanly, the log doesn't have failure clutter, compose narrates the actual outcome.

Closing as subsumed. The 1/4 stochastic TR-UT4 fail is a separate eval-mismatch issue, not c-f52a.
