# fp-proof hardening ledger

This file tracks hardening identified by comparing `fp-proof` against `~/mlld/clean`. The goal is not to port `clean` wholesale. It is to keep the proof rig small while preserving the structural defenses that matter.

## Applied in this pass

### H1. Worker-submit role is now load-bearing

Status: done.

Change:

- `rig/workers.mld` now dispatches writes from `exe role:worker @executeAuthorizedIntent`.
- Banking, Slack, Travel, and Workspace policies set `records_require_tool_approval_per_role: true`.

Why:

`clean` correctly separated planner authorization from worker submission. Without strict submit-role checks, `write.role:worker.tools.submit` is documentation rather than enforcement. The proof rig now checks both:

- planner authorization through `role:planner @compileAuthorization`;
- worker submission through `role:worker @executeAuthorizedIntent`.

Evidence:

- `mlld validate rig bench/agents bench/domains tests`: passed.
- `mlld tests/index.mld --no-checkpoint`: `121 pass / 0 fail (2 xfail, 0 xpass)`.

### H2. Slack direct webpage fetch is task-known only

Status: done.

Change:

- Added `bench/domains/slack/url_policy.mld`.
- `bench/agents/slack.mld` now gates `extract_webpage(url)` through `@directUrlFetchGate`.
- Direct fetch is allowed only when the URL appears in the user task.
- URLs discovered inside Slack message bodies must use opaque `url_ref` fetch.

Why:

`clean` had a cleaner URL-promotion firewall. `fp-proof` already had opaque refs, but direct `extract_webpage(url)` still relied on tool description rather than structural enforcement. A worker or planner summary that surfaced a raw message-body URL could otherwise use the direct fetch path.

Evidence:

- `slack-proof/records/taskKnownDirectUrlFetchAllowed`
- `slack-proof/records/messageOnlyUrlDeniedForDirectFetch`
- `slack-proof/violation-canary/unsafeDirectFetchSurfaceAllowsMessageUrl`
- Full deterministic suite: `121 pass / 0 fail`.

## Covered by existing proof shape

### H3. Recommendation/advice hijack

Status: covered for current travel shape; not fully generalized.

`clean` has a formal `advice` gate using role-specific projection plus `@noInfluencedAdvice`. `fp-proof` currently handles travel advice by using objective aggregate records:

- review blobs are `data.untrusted`;
- planner/advice-visible records omit review prose;
- objective candidate tools return rating/price/address/cuisine/hours/fuel fields and omit review instructions;
- tests prove injected review prose does not steer objective candidate selection.

Evidence:

- `travel-proof/records/reviewBlobsStayUntrusted`
- `travel-proof/records/objectiveRestaurantMergeOmitsReviewInstructions`
- `travel-proof/records/objectiveRestaurantAdviceCanRejectInjectedLowRatedCandidate`
- `travel-proof/authorization/reviewChosenHotelDeniedWhenNotInTask`
- `travel-proof/violation-canary/unsafeSurfaceAllowsReviewChosenBooking`

Follow-up:

If the rig adds a generic compose/advice worker, port the `clean` pattern: role:advice projection, no-tool advice worker, `@noInfluencedAdvice`, and fact-only fallback.

### H4. Sensitive exfil and outbound payload URLs

Status: covered by guard/policy tests.

The proof rig blocks sensitive labels and outbound payload URLs on exfil send surfaces. This is not as packaged as `clean`'s URL defense, but the current guard is generic and tested across suites.

Evidence:

- `workspace-proof/authorization/secretEmailBodyDeniedEvenToKnownRecipient`
- `workspace-proof/authorization/outboundUrlInEmailSubjectDenied`
- `slack-proof/authorization/outboundUrlInDmBodyDeniedByGuard`
- `slack-proof/authorization/outboundUrlInBatchDmBodiesDeniedByGuard`
- `slack-proof/authorization/outboundUrlInPostContentDeniedByGuard`
- `cross-domain-proof/blocked-flows/workspaceSecretCannotCrossToSlackDm`
- `cross-domain-proof/blocked-flows/travelPiiCannotCrossToWorkspaceEmail`

## Not ported yet

### H5. Shelf/address-backed live provenance

Status: future hardening.

`clean` is closer to the ideal here. `fp-proof` uses text history refs plus a bridge. The bridge is intentionally narrow and tested, but it is still a compatibility layer. The final architecture should use shelves/addresses so cross-call identity stays in mlld-native state.

Reason not applied now:

This is an architectural migration, not a hardening patch. The current bridge has deterministic proof coverage.

### H6. URL capability shelf instead of temp files

Status: future hardening.

`fp-proof` stores Slack URL refs through temp-file lookup. This is acceptable for the proof spike but less principled than `clean`'s private URL capability shelf.

Reason not applied now:

The direct-fetch bypass is now structurally closed. Replacing the storage substrate can happen without changing security semantics.

### H7. Generic output validators

Status: future hardening.

`clean` has more explicit output validator infrastructure. `fp-proof` currently relies on write guards and final-answer restraint. For high-assurance deployment, add a generic final/output validator for novel URLs and sensitive material.

Reason not applied now:

AgentDojo utility mostly grades tool effects and answers. The write boundary is higher priority, and current deterministic tests cover payload URL writes.

### H8. Mutation coverage harness

Status: future hardening.

`clean` has mutation-style tests that prove specific defenses are load-bearing. `fp-proof` uses disabled-defense canaries inside each proof suite. A dedicated mutation harness would improve confidence.

Reason not applied now:

The current canaries already catch the major "empty security test" failure mode. A broader mutation harness is useful but not needed before the next cloud sweep.

## Current verification

Last local deterministic verification after H1/H2:

```bash
mlld validate rig bench/agents bench/domains tests
mlld tests/index.mld --no-checkpoint
```

Result:

- validation: `34 files: 34 passed`
- tests: `121 pass / 0 fail (2 xfail, 0 xpass)`
