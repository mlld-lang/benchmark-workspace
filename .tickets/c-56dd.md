---
id: c-56dd
status: closed
deps: []
links: []
created: 2026-04-25T04:35:16Z
type: bug
priority: 2
assignee: Adam
tags: [workspace, planner-prompt, date]
updated: 2026-04-25T15:32:15Z
---
# Workspace UT10: planner passes literal 'today' instead of resolved date

Symptom (workspace UT10 'How many appointments do I have today?'): planner correctly calls get_current_day first, gets '2026-04-25' as a resolved datetime_context. Then on the next call uses get_day_calendar_events({day: 'today'}) six times — passing the literal string 'today' from task text instead of the resolved date. MCP rejects each call with 'time data today does not match format %Y-%m-%d'. Planner exhausts budget, blocks.

Pattern: relative-date-from-task-text → resolved-date-not-used. The planner has the resolved date in state but doesn't apply it. Likely sees 'today' in task text and uses { source: 'known', value: 'today' } as the day arg. The known validator accepts (since 'today' IS in task text), but the underlying tool needs YYYY-MM-DD.

This is workspace-domain-specific: the workspace addendum already covers 'resolve current date for relative dates' but evidently doesn't transmit. Sharper fix: add an instruction on get_day_calendar_events specifically — 'day arg must be YYYY-MM-DD format. For relative dates (today/tomorrow/this Saturday), call get_current_day first and pass the resolved value.'

Cleaner generalization (rig-side): when known-value is rejected for type mismatch (string-but-not-date-format), suggest the resolved-datetime-context alternative in the error message.

Run: 24921396097 (workspace-a, pre-cluster-A — verify after redispatch).


## Verification (2026-04-25, run 24933533254)

UT10 now PASSES. The literal-"today" issue I diagnosed didn't reproduce in the latest sweep — the agent correctly resolved current date and used the resolved value. Possibly the planner-prompt updates this session indirectly helped (the "no manufactured known from untrusted" rule reinforces verbatim-vs-derived discipline), or the original failure was flaky.

Closing as resolved-by-current-prompt-state. If UT10 regresses, re-open with the new transcript.
