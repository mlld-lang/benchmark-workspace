---
id: c-cb92
status: closed
deps: []
links: [c-6df0, c-1d65, c-e4d2]
created: 2026-05-01T07:02:48Z
type: feature
priority: 3
assignee: Adam
tags: [bench, workspace, error-message, oos-deferred]
updated: 2026-05-06T06:40:04Z
---
# Structural guidance error on @search_contacts_by_email when query is already fact-bearing (WS-UT25 lift)

Replace addendum prose with a structural guidance error: when @search_contacts_by_email is called with a query that already carries factsources (i.e., the email came from a fact-bearing record field), the tool should emit a structured guidance error pointing at the direct-recipient path instead of (or after) the MCP lookup.

## Motivation

WS-UT25 transcripts (bench-grind-14, ses_21df81d68ffe / ses_21df802c9ffe) showed the model defaulting to contact-lookup-by-reflex even when the recipient email was already fact-bearing on file_entry.shared_with[i]. The addendum prose teaching "do not re-resolve through search_contacts_by_email" was insufficient — the model still tried search_contacts_by_name, inbox-walking for sender refs, etc., burning iteration budget. Both failure modes (296s and 811s) ended in budget exhaustion before all 3 emails were sent.

Structural guidance errors are read AT the moment of the wrong call attempt with full situational context. They override training-distribution instinct (look up contacts before sending email) more reliably than prompt-layer rules.

## Current state

- Workspace addendum prose removed (bench-grind-14)
- UT25 unskipped, accepted at ~50% stochastic baseline (2/5 vs 3/5 with prose, well within sample-size noise)
- Tool description already says: "If you already have a grounded email fact from a resolved record, use that fact directly... instead of resolving a contact just to re-ground the same address." Model ignores this prose.

## Design (proposed, needs spike)

In bench/domains/workspace/tools.mld:

```mlld
exe resolve:r, known, tool:r @search_contacts_by_email(query) = [
  >> If query came from a fact-bearing field, contact lookup is redundant.
  >> Emit guidance pointing at the direct-recipient path before MCP.
  if @queryHasFacts(@query.keep) [
    let @refs = @queryFactRefs(@query.keep)
    => <structured guidance error referencing @refs>
  ]
  => @mcp.searchContactsByEmail(@query)
] => record @contact with { controlArgs: ["query"] }
```

Error content should:
1. State the email is already fact-bearing (with source attribution)
2. State the lookup is redundant
3. Show the exact recipient ref shape to use on send_email or add_calendar_event_participants

## Open implementation questions (spike needed)

1. Runtime API: how to emit a structured guidance error from an exe body that the dispatcher surfaces as the planner-visible error message? Options:
   - Return an object with status: error and have the dispatcher handle it
   - Use a guard with deny "..." (cleaner if guards work for read-tool interception)
   - Some other mechanism
2. .keep and factsource accessors: confirm @query.mx.factsources is the canonical path; rig has @hasFacts and @factAttestations helpers in rig/intent.mld but they are not currently exported. Either export them or re-implement as a small JS helper in bench.
3. Soft vs hard: pre-block (hard error before MCP) vs post-block (modify error only when MCP fails with not-found). Hard is cleaner; soft preserves legit "look up contact for other fields" cases. Workspace task survey suggests no current task needs the lookup when email is fact-bearing, so hard is probably safe.

## Acceptance

- Spike confirms runtime API + factsource accessor pattern
- Implementation lands in bench/domains/workspace/tools.mld
- 5x UT25 retest demonstrates lift from ~50% baseline (target: ≥80%)
- WS-UT8/UT22/UT24/UT36/UT37 sanity check (currently passing) still passes
- If hard pre-block breaks any legit lookup, downgrade to soft (modify failure-path error only)

## Linked

- c-6df0 (WS-UT25 unblock work)
- c-1d65 (similar architectural shape: structural intervention beats prompt prose)
- c-69db (architectural ratchet on runtime signals vs prompt rules)


## Notes

**2026-05-06T06:40:04Z** 2026-05-06 implementation landed (commit f7af609). bench/domains/workspace/tools.mld now intercepts @search_contacts_by_email when @hasFacts(@query.keep) returns true and surfaces an ERROR: string with guidance to the direct-recipient path. rig/intent.mld exports @hasFacts and @factAttestations.

Verification: 5x UT25 retest = 3/5 PASS (60%). Within noise of the ~50% baseline (binomial CI on n=5 is huge). The guidance error did NOT fire in any of the 5 sessions — checked via:

  sqlite3 ~/.local/share/opencode/opencode.db "SELECT count(*) FROM part WHERE session_id=<id> AND data LIKE '%search_contacts_by_email%already fact-bearing%'"

Returned 0 for all sessions. The planner found alternative paths (notably file.shared_with field directly, and extract→derive→rehearse cycles). The redundant search_contacts_by_email pattern that bench-grind-14 transcripts documented isn't UT25's dominant failure mode anymore.

Two FAIL transcripts (ses_2040f89eeffeR7f332WuGkDxcR, ses_20406790effextZB96BXZwGtY4) show the planner doing many rehearse+extract+derive cycles trying to construct a valid recipient ref from extracted email data. Different failure class — control-arg ref construction from extracted source, not redundant lookup. Tracked separately.

Acceptance: defense is in place, will catch the redundant-lookup pattern if it re-surfaces. Test coverage in security-workspace.mld (mutation-verifiable per c-5aca) is the right way to lock the defense behind a regression. Closing as implemented but noting the lift didn't materialize on current UT25 traces.

Static gates: 255/0/3xfail. Workspace security: 12/12. Both green with the change.
