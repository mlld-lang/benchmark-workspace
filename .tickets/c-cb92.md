---
id: c-cb92
status: open
deps: []
links: [c-6df0, c-1d65, c-e4d2]
created: 2026-05-01T07:02:48Z
type: feature
priority: 3
assignee: Adam
tags: [bench, workspace, error-message, oos-deferred]
updated: 2026-05-01T07:03:23Z
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

