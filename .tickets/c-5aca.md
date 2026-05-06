---
id: c-5aca
status: open
deps: []
links: [c-bc1f, c-83f3, c-ae22]
created: 2026-05-06T05:52:18Z
type: task
priority: 2
assignee: Adam
tags: [security, tests, coverage]
updated: 2026-05-06T05:52:22Z
---
# Extend mutation-coverage registry to all 35 scripted security tests

tests/run-mutation-coverage.py registers 3 mutations covering 11 of 41 scripted security test exes (6+2+3). The other 24 pre-existing security tests have not been mutation-verified — they assert ok=false but do not prove the specific defense their docstring claims actually fired.

Mutation 1 (source-class firewall, intent.mld:791-800) was expected to fail 21 tests claiming defense A2/A3, but only 6 failed. The other 15 source-class-firewall-claimed tests pass under mutation — they are catching the attack via some OTHER defense path (kind firewall, exact-arg, optional-field, lookup-fail short-circuit, etc.) or via a stale fixture shape (related: c-bc1f).

Work to do:

1. For each existing test in tests/scripted/security-{slack,banking,workspace,travel}.mld, identify which defense rule(s) the docstring claims to verify.

2. For each defense rule, design a one-line mutation in rig/ that disables only that rule (e.g. flipping `if @role == "control"` to `if false`).

3. Add a MUTATIONS entry to tests/run-mutation-coverage.py with the expected_fails list.

4. Run the harness. If the test is not in the actual fail set under the mutation, EITHER:
   (a) Strengthen the test assertion (check last.error == "<specific_error>" or last.blocked_args.includes("<arg>"))
   (b) Fix the seed shape so the lookup actually succeeds and the firewall is reached
   (c) Re-classify the test if it actually catches the attack via a different (still real) defense

5. Iterate until every security test is in some mutation entry and the registry mirrors the actual coverage matrix.

Defenses already verified:
- intent.mld:791-800 payload_only_source_in_control_arg (6 tests)
- intent.mld:683-685 allow_requires_no_control_args (2 tests)
- workers/extract.mld:269 extract_empty_response (3 tests)

Defenses with claimed-but-unverified coverage:
- intent.mld:701-708 known_value_not_in_task_text (4 tests claim it; not verified)
- intent.mld:467 selection_backing_missing + companions (5 tests claim selection-ref defenses)
- can_authorize:false hard auth deny (1 test in banking)
- kind-tag firewall on selection-ref (slack + travel wrong-record-bypass tests)
- update_user_info taint-based defense (banking; deferred per docstring)
- known-missing-value compile error (slack testKnownMissingValueRejected)

Likely pulls in c-bc1f follow-up (stale @stateWithExtracted/@stateWithDerived fixtures) — many tests may be broken at the seed layer, not the assertion layer.


## Notes

**2026-05-06T06:37:58Z** Update 2026-05-06 (bench-grind-20): registry now covers 30 of 41 scripted security tests across 7 mutations:

OK mutations:
1. source-class-firewall (intent.mld:791) - 6 tests, single-layer
2. allow-control-args-gate (intent.mld:683) - 2 tests, single-layer
3. known-value-task-text-check (intent.mld:701) - 4 tests, single-layer
4. extract-empty-response-guard (workers/extract.mld:269) - 3 tests, single-layer
5. policy-build-backstop (workers/execute.mld:138) - 2 tests, single-layer (banking hard-auth-deny + slack selection-ref-real-msg-handle wrong-record bypass)
6. exact-arg-and-backstop-combined - 3 tests, defense-in-depth (banking update_password extracted/derived/hard-deny — caught by both exact-arg check AND policy.build kind firewall)
7. source-class-and-backstop-combined - 19 tests, defense-in-depth (the 6 source-class single-layer tests + 13 caught by policy.build backstop only when source-class is also off)

11 unverified remaining:
- 3 positive controls (assert ok=true): testInviteUserKnownInTaskTextAccepted (slack), testUpdateUserInfoExtractedAcceptedAtRehearse (banking), testReserveHotelKnownInTaskTextAccepted (travel)
- 1 malformed shape: testKnownMissingValueRejected (slack) — known with no value field
- 2 caught by known-value-task-text-check on a SECOND control arg when source-class is also disabled: updateScheduledTxExtractedRecipientRejected (banking, id field), shareFileExtractedEmailRejected (workspace, file_id field). Need 3-way mutation.
- 5 caught by mlld-runtime policy.build kind-tag firewall (rig framework has no rejection layer between them and the runtime backstop): selectionRefNonexistentBackingHandleRejected, selectionRefBackingWithoutIdentityRejected, selectionRefMismatchedHandleAfterResolveRejected, selectionRefRealSlackMsgHandleRejected (slack), reserveHotelSelectionRefRestaurantNameRejected (travel) — already covered by source-class-and-backstop-combined for some, others need runtime kind-firewall mutation
