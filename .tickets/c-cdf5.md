---
id: c-cdf5
status: closed
deps: []
links: []
created: 2026-05-09T20:56:05Z
type: feature
priority: 2
assignee: Adam
external-ref: mlld:m-3116
tags: [testing, xfail, mlld-upstream]
updated: 2026-05-09T21:39:56Z
---
# Adopt mlld try expression in test runner once m-3116 lands

When mlld lands m-3116 (try expression result capture), upgrade rig's test framework to use it. The catchable subset of m-3116 covers exactly the failure modes that currently force delete-and-comment for xfail-style tests:

## What unlocks

**1. Real xfail for recoverable interpreter errors.** tests/runner.mld @xfailGroup currently only catches assertion failures (tests that return { ok: false }). With try, wrap each @testExe() call:

```mlld
exe @runGroup(suiteName, groupRec, resolvedOpts) = [
  ...
  for @testExe in @groupRec.tests [
    let @attempt = try @testExe()
    let @entry = when [
      @attempt.ok => { id: @id, ok: @attempt.value.ok, detail: @attempt.value.detail, ...}
      * => { id: @id, ok: false, detail: `thrown: @attempt.error.code: @attempt.error.message`, thrown: true, ...}
    ]
    ...
  ]
]
```

This lets xfail catch failed casts/parses, undefined refs, JS-block exceptions, and managed-policy denials. Update the limitation doc on @xfailGroup to reflect what's now catchable and what's still delete-and-comment territory (the hard-security set in m-3116's NOT-catchable list: WRITE_DENIED_*, TOOL_AUTHORIZE_*, capability-policy denials, etc.).

**2. Cleaner error-path tests.** Tests that want to assert 'this call should error' can write:

```mlld
exe @testFailedParseRejects() = [
  let @r = try @parse.address('not_an_address')
  => @assertEq(@r.ok, false)
]
```

Replaces the current pattern of asserting on returned-as-data error shapes from helpers that conditionally return { ok: false }.

**3. Re-evaluate the deferred dispatch tests** (named-state-and-collection.mld 3 cross-tool tests, identity-contracts handle-drift xfails, url-refs-b Group D pre-m-e730). Most of these throw what fall in m-3116's NOT-catchable set (WRITE_DENIED, TOOL_AUTHORIZE), so try doesn't help — but check the matrix per test, some may have moved to catchable error classes by the time m-3116 lands.

## Acceptance criteria

- @xfailGroup at clean/tests/runner.mld wraps test invocations in try
- Limitation doc updated to distinguish: (a) recoverable errors → try-catchable, classified as XFAIL; (b) hard-security errors → still delete-and-comment, with explicit list per m-3116's NOT-catchable matrix
- Regression: a known-throwing test (catchable class) marked xfail produces XFAIL, not bail
- Regression: a known-throwing test (NOT-catchable class) still bails the suite (verify the discipline holds)
- Audit: walk through deleted-test comments in named-state-and-collection.mld + url-refs-b.mld + identity-contracts.mld; restore any whose error class is now catchable

## Out of scope

- Hard-security failures stay uncatchable — m-3116 explicitly excludes them
- The runner doesn't try to roll back side effects; if a test exe wrote to a shelf before throwing, the writes commit per normal mlld semantics

## Discovered while

Auditing rig's null-conformance behavior and surfacing the xfail interpreter-error gap (clean-side mitigation in 71c369c). mlld-dev's current m-3116 description acknowledges 'the immediate pressure came from clean/tests/runner.mld'.

## Acceptance Criteria

xfailGroup wraps via try; limitation doc distinguishes catchable vs hard-security; deleted-test audit identifies revivable cases.


## Notes

**2026-05-09T21:39:47Z** ## Closed at <pending commit>

Implemented in tests/runner.mld@runGroup — wraps `@testExe()` in `try`, classifies thrown errors as test failures with `thrown: true` flag and `detail: "thrown: <code>: <message>"`. xfailGroup picks them up as XFAIL.

Updated @xfailGroup doc to describe the catchable-vs-hard-security split per m-3116's NOT-catchable matrix. Added @testIntentionallyThrows to tests/_template.mld's known-broken xfailGroup as a regression demonstrating the try-wrap behavior.

**Verified end-to-end**:
- Recoverable thrown error inside xfailGroup → classified as XFAIL (gate now 229/0/2 — was 229/0/1)
- Hard-security thrown error (WRITE_DENIED_NO_ROLE probe) inside xfailGroup → still bails the suite per m-3116's NOT-catchable matrix; error trace shows `nodeType: TryExpression` confirming mlld's try correctly re-throws

**Audit per acceptance criterion #4**: walked through delete-and-comment notes in named-state-and-collection.mld + url-refs-b.mld + identity-contracts.mld:
- testRescheduleDispatchSucceeds, testCollectionDispatchPolicyBuild, testCollectionDispatchCrossModuleM5178: all WRITE_DENIED_* — stays deleted per F5 (still in NOT-catchable matrix)
- testUr19RecordArgsRejectsForgedHandle: not error-class issue — recordArgs validator stopped checking handle existence, needs reframe as @lookupResolvedEntry test (independent of m-3116)
- testCrossResolveIdentitySlackHandleDrift / testSelectionRefSurvivesHandleDriftSlack: not error class — needs slack_msg `key:` declaration (bench-side records change, F4)
- identity-contracts entry-shape-bucket tests: concept-obsolete (deleted bucket sentinel), unrelated to m-3116
- no-progress fingerprint anchor: covered by FP-2 generic, unrelated

Net revival yield from m-3116: 0 currently-deleted tests. But going forward, new tests can use try cleanly and failed casts/parses/JS-block-exceptions are now xfail-able.

**Friction reported to mlld-dev**: IDE/LSP lint emits "Parse error: Expected end of input but ' ' found" diagnostic on `try @testExe()` even though the runtime parser accepts the syntax. Stale grammar in the highlighter not caught up to m-3116; runtime works.

Closing.
