---
id: c-be06
status: closed
deps: []
links: [c-8738, c-3287, c-a46d, c-1487, c-69db, c-5e2f, c-2923, c-1d65, c-84d5]
created: 2026-04-28T23:44:34Z
type: feature
priority: 1
assignee: Adam
tags: [rig, url-promotion, architecture, slack]
updated: 2026-05-01T07:52:26Z
---
# URL-promotion primitive — find_referenced_urls + get_webpage_via_ref (CLOSED)

Implementation work for the URL-promotion primitive. Design at rig/URL_PROMOTION.md (review v3 — Claude review + iterations applied).

## Summary

Two slack-domain resolve tools for safely fetching URLs that appear in untrusted message bodies:

- find_referenced_urls(slack_msg) → url_ref[] (deterministic regex over message body)
- get_webpage_via_ref(url_ref) → referenced_webpage_content (the only tool that can dereference the URL)

The url_ref record has no URL field; the actual URL string lives in a private state.capabilities.url_refs map. URL is fetch-scoped — usable for fetching, NOT reusable as a generic URL for post_webpage etc.

## What it unblocks (3-4 tasks directly + sibling cases)

- SL-UT4 (c-8738): Eve's blog URL in Bob's inbox
- SL-UT6 (c-8738): restaurant URL in channel message
- SL-UT15 (c-3287): all URLs in general channel
- SL-UT20 (c-1487): UT15+UT16 combined (URL fetch part)
- SL-UT1 (c-a46d): article URL in Bob's message — also URL-promotion family

## Key design decisions

- v1 capability map (state.capabilities.url_refs) instead of projection-aware resolveRefValue (deferred; see c-5e2f)
- url_ref has no URL field; the URL is stored only in capabilities map
- referenced_webpage_content is a sibling record family, no public URL fact (prevents laundering)
- Conservative v1 safety gate: query/fragment/template URLs blocked
- Measurement gate: ≥4/5 PASS on SL-UT4/UT6 before locking the addendum
- Future projection-aware deref (c-5e2f) would let url_ref hold URL as masked field — v2 cleanup, not v1 dependency

## Implementation surface

See rig/URL_PROMOTION.md for the full migration plan. Highlights:

- state.capabilities.url_refs in rig state
- rigTransform metadata + dispatch branch in dispatchResolve
- recordArgs validation (handle-only, no fielded refs)
- rig/transforms/url_refs.mld deterministic parser
- bench/domains/slack/records.mld: url_ref + referenced_webpage_content
- bench/domains/slack/tools.mld: 2 new catalog entries
- bench/domains/slack/prompts/planner-addendum.mld: workflow rule

## Sibling primitive

parse_value (c-69db) is the deterministic-extraction primitive for non-URL cases. Both share the design pattern of "deterministic transform mints fact-bearing values from untrusted content." parse_value lacks capability scoping; URL-promotion adds it because URL has multiple control-arg uses (fetch vs post) we want to distinguish.

## Linked

- c-5e2f: futr projection-aware resolveRefValue (longer-term mlld v2 cleanup)
- c-69db: parse_value sibling primitive
- c-8738, c-3287, c-a46d, c-1487 (the deferred slack tasks)


## Notes

**2026-04-29T17:33:38Z** Group A landed (zero-LLM parser tests). Created rig/transforms/url_refs.mld with @applyUrlRefs(body) + @urlRefId(handle, ordinal). Added UR-1..UR-10 to rig/tests/index.mld. All pass. Group B (capability map invariants) and Group C (recordArgs source-class firewall) deferred to next pass — they need state.capabilities.url_refs + dispatchResolve recordArgs validation hooks first.

**2026-04-29T18:18:03Z** Group B + C landed. Group B helpers in rig/transforms/url_refs.mld: @buildUrlRefRecordValue (no url field), @buildUrlRefCapabilityEntry (returns null for blocked), @mergeUrlRefCapabilities, @lookupUrlCapability. Group C @compileRecordArgs in rig/intent.mld validates fieldless resolved record-handle refs and rejects extracted/derived/known/family/forged-handle sources. UR-11..UR-20 all pass. Note: a JS exe returning literal null roundtrips through mlld as a wrapped non-null value, so test-side null detection inlines the check (see urBlockedYieldsNoCapability / urLookupReturnsNullFor in rig/tests/index.mld). Gate: 179 pass / 1 xfail. Next: dispatchResolve rigTransform branch + the actual url_ref / referenced_webpage_content records in bench/domains/slack and the find_referenced_urls / get_webpage_via_ref catalog entries.

**2026-04-29T19:48:18Z** Group D landed: dispatchResolve rigTransform branch + handlers for find_referenced_urls and get_webpage_via_ref. State.capabilities now propagates through @rigState (5th param) so updateResolvedStateWithDef/updateNamedState/updateResolvedState/updateExtractSources preserve the url_refs map across other state transitions. Tests UR-21..UR-24 in rig/tests/index.mld build a synthetic slack-shaped agent, seed state with a slack_msg, and dispatch the full rigTransform → mint records + capability deltas → fetch via stub backend path. Gate: 183 pass / 1 xfail. urlRefId trimmed to bare hash (no 'url_ref_' prefix) so state handles compose cleanly as r_url_ref_<hash>. Files: rig/runtime.mld, rig/transforms/url_refs.mld, rig/intent.mld, rig/workers/resolve.mld, bench/domains/slack/tools.mld, rig/tests/index.mld. Outstanding: planner-addendum (Layer 2 prompt change) needs user approval before any flow canary on SL-UT4/UT6/UT15. Worth filing mlld-dev: rigTransform tools should be allowed to omit 'mlld:' (currently requires placeholder exe).

**2026-04-30T20:48:43Z** Closed 2026-04-30 (bench-grind-13). Implementation landed across Groups A-D plus adoption + canary commits (7162305, 42922f2, 8a4d254, 10aeff9, 11ad2f5, 7732847, 045b33e). 24 zero-LLM tests (UR-1..UR-24) pass.

Canary results:
- 9/9 PASS on SL-UT4/UT6/UT15 (target gate ≥4/5)
- 11/13 in-scope slack regression (other 2 are unrelated stochasticity per c-b561 reproductions)

Unblocked: SL-UT1 (c-a46d), SL-UT4 + SL-UT6 (c-8738), SL-UT15 (c-3287).

NOT unblocked: SL-UT20 (c-1487 — UT16 portion is untrusted-content → control-arg, retitled SHOULD-FAIL).

Architectural ratchet: URL-promotion's capability-scoping pattern (URL stored in private state.capabilities map; url_ref has no public URL field; get_webpage_via_ref is the only deref path) is the safe shape for fetch-only access to URLs that appear in untrusted content. Contrast with parse_value-as-fact-promoter (rejected this session) — URL-promotion does not promote untrusted-source content to fact; it just scopes a capability to fetch-only without exposing the raw URL string for arbitrary control-arg use.

Sibling rule arriving from mlld-dev: no-untrusted-or-unknown-urls-in-output (defense-in-depth on the body-write side of the same threat surface).
