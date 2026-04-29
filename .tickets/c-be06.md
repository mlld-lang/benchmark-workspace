---
id: c-be06
status: open
deps: []
links: [c-8738, c-3287, c-a46d, c-1487, c-69db, c-5e2f]
created: 2026-04-28T23:44:34Z
type: feature
priority: 1
assignee: Adam
tags: [rig, url-promotion, architecture, slack]
updated: 2026-04-28T23:44:39Z
---
# OPEN: URL-promotion primitive - find_referenced_urls + get_webpage_via_ref with capability scoping

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

