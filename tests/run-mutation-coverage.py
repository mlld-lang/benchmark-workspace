#!/usr/bin/env python3
"""Mutation-coverage harness for the scripted security tests.

For each registered defense, this script:
  1. Confirms the canonical baseline is green.
  2. Applies a one-line mutation that disables the defense.
  3. Re-runs the affected suites.
  4. Compares the actual [FAIL] set to the expected_fail set.
  5. Restores the file (always — try/finally).

The output is a coverage matrix that proves the listed tests actually
catch the defense regression. A test that "passes" claiming to verify
defense X but doesn't fail when X is disabled is fake coverage —
something else is rejecting the attack.

Add a new mutation when you add a security test. Match the mutation's
expected_fails list to the test ids whose docstrings claim that defense.

Usage:
    uv run --project bench python3 tests/run-mutation-coverage.py
    uv run --project bench python3 tests/run-mutation-coverage.py --only source-class-firewall
"""

from __future__ import annotations

import argparse
import concurrent.futures
import re
import subprocess
import sys
from pathlib import Path

CLEAN_ROOT = Path(__file__).resolve().parents[1]


# Each mutation: a single text replacement that disables one defense.
# search/replace must be uniquely matchable in the file.
# expected_fails: test ids that claim to verify this defense AND have been
# manually confirmed to fail under the mutation.
#
# Tests not in any expected_fails:
#   * Positive controls (assert ok=true), untouched by negative mutations:
#       - security-slack/.../inviteUserKnownInTaskTextAccepted
#       - security-banking/.../updateUserInfoExtractedAcceptedAtRehearse
#       - security-travel/.../reserveHotelKnownInTaskTextAccepted
#       - security-workspace/allow-source-firewall/allowSourceOnNoControlArgsAccepted
#   * Shape-validation tests (planner JSON malformedness, not security):
#       - security-slack/source-class-firewall/knownMissingValueRejected
#         The defense lives somewhere downstream of @policy.build but the
#         exact rejection point hasn't been pinned down. Low security
#         value (it defends against planner emitting bad JSON, not
#         attacker-controlled values), so accepted unverified.
MUTATIONS = [
    {
        "id": "source-class-firewall",
        "description": "rig/intent.mld:791-800 payload_only_source_in_control_arg — extracted/derived source class on a control arg must reject",
        "file": "rig/intent.mld",
        "search": '''  if @resolved.source == "extracted" || @resolved.source == "derived" [
    if @role == "control" [
      => {
        ok: false,
        arg: @arg,
        error: "payload_only_source_in_control_arg",''',
        "replace": '''  if @resolved.source == "extracted" || @resolved.source == "derived" [
    if false [  >> MUTATION-COVERAGE: source-class firewall disabled
      => {
        ok: false,
        arg: @arg,
        error: "payload_only_source_in_control_arg",''',
        "suites": ["slack", "banking", "workspace", "travel"],
        "expected_fails": [
            "security-slack/source-class-firewall/extractedEmailAsControlArgRejected",
            "security-slack/source-class-firewall/extractedControlArgNamesBlockedField",
            "security-slack/source-class-firewall/derivedEmailAsControlArgRejected",
            "security-slack/source-class-firewall/getWebpageExtractedUrlRejected",
            "security-slack/recursive-url-fetch/recursiveWebpageFetchRejected",
            "security-workspace/source-class-firewall/createCalendarEventExtractedParticipantsRejected",
            "security-workspace/source-class-firewall/rescheduleCalendarEventExtractedIdRejected",
            "security-travel/source-class-firewall/createCalendarEventExtractedParticipantsRejected",
        ],
    },
    {
        "id": "allow-control-args-gate",
        "description": "rig/intent.mld:683-685 allow_requires_no_control_args — source:'allow' on a tool with control args must reject",
        "file": "rig/intent.mld",
        "search": '''  if @resolved.source == "allow" [
    if @argMeta.control_count > 0 [
      => { ok: false, arg: @arg, error: "allow_requires_no_control_args" }
    ]''',
        "replace": '''  if @resolved.source == "allow" [
    if false [  >> MUTATION-COVERAGE: allow-control-args gate disabled
      => { ok: false, arg: @arg, error: "allow_requires_no_control_args" }
    ]''',
        "suites": ["workspace"],
        "expected_fails": [
            "security-workspace/allow-source-firewall/allowSourceOnControlArgRejected",
            "security-workspace/allow-source-firewall/allowSourceBlockedArgsNamesControl",
        ],
    },
    {
        "id": "known-value-task-text-check",
        "description": "rig/intent.mld:701-708 known_value_not_in_task_text — known-source control args must literally appear in the user's task text. Also catches malformed `{source:'known'}` (no value field) because @knownInTask(query, undefined) returns false.",
        "file": "rig/intent.mld",
        "search": '''  if @resolved.source == "known" [
    if !@knownInTask(@query, @resolved.value) && @role == "control" [
      => {
        ok: false,
        arg: @arg,
        error: "known_value_not_in_task_text",''',
        "replace": '''  if @resolved.source == "known" [
    if false [  >> MUTATION-COVERAGE: known-task-text check disabled
      => {
        ok: false,
        arg: @arg,
        error: "known_value_not_in_task_text",''',
        "suites": ["slack", "banking", "workspace", "travel"],
        "expected_fails": [
            "security-slack/source-class-firewall/knownEmailNotInTaskTextRejected",
            "security-slack/source-class-firewall/influencedNovelUrlOnGetWebpageRejected",
            "security-banking/source-class-firewall/sendMoneyKnownIbanNotInTaskTextRejected",
            "security-workspace/source-class-firewall/sendEmailKnownRecipientNotInTaskTextRejected",
            "security-travel/source-class-firewall/reserveHotelKnownNotInTaskTextRejected",
        ],
    },
    {
        "id": "exact-arg-and-backstop-combined",
        "description": "Disable BOTH exact-arg-task-text-check (intent.mld:801, extracted/derived branch) AND policy.build backstop. Catches the 2 banking update_password tests, which depend on defense-in-depth across both layers (neither alone suffices because the OTHER also rejects).",
        "edits": [
            {
                "file": "rig/intent.mld",
                "search": '''    if @exactArg [
      => {
        ok: false,
        arg: @arg,
        error: "non_task_source_in_exact_payload_arg",
        source_class: @resolved.source,''',
                "replace": '''    if false [  >> MUTATION-COVERAGE: non_task_source_in_exact_payload_arg disabled (combined)
      => {
        ok: false,
        arg: @arg,
        error: "non_task_source_in_exact_payload_arg",
        source_class: @resolved.source,''',
            },
            {
                "file": "rig/workers/execute.mld",
                "search": '''  if !@built.valid [
    => { ok: false, stage: "policy", failure: { error: "policy_build_invalid", payload: @built, issues: @built.issues ?? null } }
  ]''',
                "replace": '''  if false [  >> MUTATION-COVERAGE: policy.build backstop disabled (combined with exact-arg)
    => { ok: false, stage: "policy", failure: { error: "policy_build_invalid", payload: @built, issues: @built.issues ?? null } }
  ]''',
            },
        ],
        "suites": ["banking"],
        "expected_fails": [
            "security-banking/privileged-writes/updatePasswordExtractedRejected",
            "security-banking/privileged-writes/updatePasswordDerivedRejected",
            # Collateral: policy.build is also disabled here, so the hard-auth-deny test fails too.
            "security-banking/authorization-deny/updatePasswordHardDeniedInDefendedMode",
        ],
    },
    {
        "id": "policy-build-backstop",
        "description": "rig/workers/execute.mld:138-140 — disable the @policy.build invalid-verdict check. policy.build is the kind-tag/fact-attestation backstop: when nothing earlier rejects, it enforces that attestations match the tool's required kind. Tests that fail ONLY under this mutation rely solely on the runtime policy backstop.",
        "file": "rig/workers/execute.mld",
        "search": '''  if !@built.valid [
    => { ok: false, stage: "policy", failure: { error: "policy_build_invalid", payload: @built, issues: @built.issues ?? null } }
  ]''',
        "replace": '''  if false [  >> MUTATION-COVERAGE: policy.build backstop disabled
    => { ok: false, stage: "policy", failure: { error: "policy_build_invalid", payload: @built, issues: @built.issues ?? null } }
  ]''',
        "suites": ["slack", "banking"],
        "expected_fails": [
            "security-banking/authorization-deny/updatePasswordHardDeniedInDefendedMode",
            "security-slack/selection-ref-wrong-record-bypass/selectionRefRealSlackMsgHandleRejected",
        ],
    },
    {
        "id": "source-class-and-backstop-combined",
        "description": "Disable BOTH the rig source-class firewall (intent.mld:791) AND the policy.build backstop (execute.mld:138). Tests that fail here are caught by EITHER layer (defense-in-depth). Tests still passing are caught by some THIRD layer — investigate.",
        "edits": [
            {
                "file": "rig/intent.mld",
                "search": '''  if @resolved.source == "extracted" || @resolved.source == "derived" [
    if @role == "control" [
      => {
        ok: false,
        arg: @arg,
        error: "payload_only_source_in_control_arg",''',
                "replace": '''  if @resolved.source == "extracted" || @resolved.source == "derived" [
    if false [  >> MUTATION-COVERAGE: source-class firewall disabled (combined)
      => {
        ok: false,
        arg: @arg,
        error: "payload_only_source_in_control_arg",''',
            },
            {
                "file": "rig/workers/execute.mld",
                "search": '''  if !@built.valid [
    => { ok: false, stage: "policy", failure: { error: "policy_build_invalid", payload: @built, issues: @built.issues ?? null } }
  ]''',
                "replace": '''  if false [  >> MUTATION-COVERAGE: policy.build backstop disabled (combined)
    => { ok: false, stage: "policy", failure: { error: "policy_build_invalid", payload: @built, issues: @built.issues ?? null } }
  ]''',
            },
        ],
        "suites": ["slack", "banking", "workspace", "travel"],
        "expected_fails": [
            # source-class-firewall alone catches these 6 (single-layer):
            "security-slack/source-class-firewall/extractedEmailAsControlArgRejected",
            "security-slack/source-class-firewall/extractedControlArgNamesBlockedField",
            "security-slack/source-class-firewall/derivedEmailAsControlArgRejected",
            "security-workspace/source-class-firewall/createCalendarEventExtractedParticipantsRejected",
            "security-workspace/source-class-firewall/rescheduleCalendarEventExtractedIdRejected",
            "security-travel/source-class-firewall/createCalendarEventExtractedParticipantsRejected",
            # caught by policy.build backstop when source-class is also off (defense-in-depth):
            "security-slack/source-class-firewall/sendDmExtractedRecipientRejected",
            "security-slack/source-class-firewall/getWebpageExtractedUrlRejected",
            "security-slack/recursive-url-fetch/recursiveWebpageFetchRejected",
            "security-slack/selection-ref-wrong-record-bypass/selectionRefRealSlackMsgHandleRejected",
            "security-banking/source-class-firewall/sendMoneyExtractedRecipientRejected",
            "security-banking/source-class-firewall/scheduleTxExtractedRecipientRejected",
            "security-banking/authorization-deny/updatePasswordHardDeniedInDefendedMode",
            "security-workspace/source-class-firewall/sendEmailExtractedRecipientRejected",
            "security-workspace/source-class-firewall/sendEmailDerivedRecipientRejected",
            "security-workspace/source-class-firewall/deleteFileAttackerIdRejected",
            "security-travel/source-class-firewall/reserveHotelExtractedNameRejected",
            "security-travel/source-class-firewall/reserveRestaurantExtractedNameRejected",
            "security-travel/source-class-firewall/reserveCarRentalExtractedCompanyRejected",
            "security-travel/source-class-firewall/sendEmailExtractedRecipientsRejected",
            "security-travel/source-class-firewall/cancelCalendarEventExtractedEventIdRejected",
            "security-travel/source-class-firewall/reserveHotelDerivedNameRejected",
            # 4 tests not in this list (caught by yet-deeper third layers, in their own
            # layer-specific mutations: exact-arg-task-text-check covers the 2 banking
            # update_password tests; the 2 banking/workspace tests with handle-string
            # control args are caught by known-value-task-text-check on those args):
            #   - security-banking/privileged-writes/updatePasswordExtractedRejected
            #   - security-banking/privileged-writes/updatePasswordDerivedRejected
            #   - security-banking/source-class-firewall/updateScheduledTxExtractedRecipientRejected
            #   - security-workspace/source-class-firewall/shareFileExtractedEmailRejected
        ],
    },
    {
        "id": "source-class-known-task-text-and-backstop-combined",
        "description": "3-way: disable source-class firewall, known_value_not_in_task_text, AND policy.build backstop. Catches tests where the attack uses extracted-source on one control arg AND known-but-not-in-task-text on another control arg (handle string). Only 3 layers off lets these through.",
        "edits": [
            {
                "file": "rig/intent.mld",
                "search": '''  if @resolved.source == "extracted" || @resolved.source == "derived" [
    if @role == "control" [
      => {
        ok: false,
        arg: @arg,
        error: "payload_only_source_in_control_arg",''',
                "replace": '''  if @resolved.source == "extracted" || @resolved.source == "derived" [
    if false [  >> MUTATION-COVERAGE: source-class disabled (3-way)
      => {
        ok: false,
        arg: @arg,
        error: "payload_only_source_in_control_arg",''',
            },
            {
                "file": "rig/intent.mld",
                "search": '''  if @resolved.source == "known" [
    if !@knownInTask(@query, @resolved.value) && @role == "control" [
      => {
        ok: false,
        arg: @arg,
        error: "known_value_not_in_task_text",''',
                "replace": '''  if @resolved.source == "known" [
    if false [  >> MUTATION-COVERAGE: known-task-text disabled (3-way)
      => {
        ok: false,
        arg: @arg,
        error: "known_value_not_in_task_text",''',
            },
            {
                "file": "rig/workers/execute.mld",
                "search": '''  if !@built.valid [
    => { ok: false, stage: "policy", failure: { error: "policy_build_invalid", payload: @built, issues: @built.issues ?? null } }
  ]''',
                "replace": '''  if false [  >> MUTATION-COVERAGE: policy.build backstop disabled (3-way)
    => { ok: false, stage: "policy", failure: { error: "policy_build_invalid", payload: @built, issues: @built.issues ?? null } }
  ]''',
            },
        ],
        "suites": ["banking", "workspace"],
        "expected_fails": [
            # Tests specifically requiring 3 layers off (extracted control + known-not-in-task on second arg):
            "security-banking/source-class-firewall/updateScheduledTxExtractedRecipientRejected",
            "security-workspace/source-class-firewall/shareFileExtractedEmailRejected",
            "security-workspace/source-class-firewall/deleteFileAttackerIdRejected",
            # Captured collaterally because these defenses are subset-disabled by this 3-way:
            "security-banking/source-class-firewall/scheduleTxExtractedRecipientRejected",
            "security-banking/source-class-firewall/sendMoneyExtractedRecipientRejected",
            "security-banking/source-class-firewall/sendMoneyKnownIbanNotInTaskTextRejected",
            "security-banking/authorization-deny/updatePasswordHardDeniedInDefendedMode",
            "security-workspace/source-class-firewall/createCalendarEventExtractedParticipantsRejected",
            "security-workspace/source-class-firewall/rescheduleCalendarEventExtractedIdRejected",
            "security-workspace/source-class-firewall/sendEmailDerivedRecipientRejected",
            "security-workspace/source-class-firewall/sendEmailExtractedRecipientRejected",
            "security-workspace/source-class-firewall/sendEmailKnownRecipientNotInTaskTextRejected",
        ],
    },
    {
        "id": "control-ref-lookup-and-backstop-combined",
        "description": "Forge @lookupResolvedControlValue to return ok:true with synthetic factsource AND disable policy.build backstop. Catches selection-ref tests where the rig framework's control_ref_backing_missing + the runtime kind-tag firewall together provide defense-in-depth.",
        "edits": [
            {
                "file": "rig/intent.mld",
                "search": '''exe @lookupResolvedControlValue(state, recordName, handle, fieldName) = [
  let @entry = @lookupResolvedEntry(@state, @recordName, @handle)
  if !@entry [ => { ok: false, error: "control_ref_backing_missing" } ]''',
                "replace": '''exe @lookupResolvedControlValue(state, recordName, handle, fieldName) = [
  >> MUTATION-COVERAGE: forge synthetic ok:true to bypass control_ref_backing_missing + downstream lookup defenses
  => { ok: true, source: "resolved", record: @recordName, handle: @handle, field: @fieldName ?? "synthetic", value: "synthetic_attacker_value", policy_attestations: [`fact:@@recordName.synthetic`] }
]
exe @lookupResolvedControlValueOriginal(state, recordName, handle, fieldName) = [
  let @entry = @lookupResolvedEntry(@state, @recordName, @handle)
  if !@entry [ => { ok: false, error: "control_ref_backing_missing" } ]''',
            },
            {
                "file": "rig/workers/execute.mld",
                "search": '''  if !@built.valid [
    => { ok: false, stage: "policy", failure: { error: "policy_build_invalid", payload: @built, issues: @built.issues ?? null } }
  ]''',
                "replace": '''  if false [  >> MUTATION-COVERAGE: policy.build backstop disabled (with control-ref-lookup forged)
    => { ok: false, stage: "policy", failure: { error: "policy_build_invalid", payload: @built, issues: @built.issues ?? null } }
  ]''',
            },
        ],
        "suites": ["slack", "travel", "workspace"],
        "expected_fails": [
            "security-slack/selection-ref-graceful-failure/selectionRefNonexistentBackingHandleRejected",
            "security-slack/selection-ref-graceful-failure/selectionRefBackingWithoutIdentityRejected",
            "security-slack/selection-ref-graceful-failure/selectionRefMismatchedHandleAfterResolveRejected",
            "security-slack/selection-ref-wrong-record-bypass/selectionRefRealSlackMsgHandleRejected",
            "security-travel/wrong-record-fact-firewall/reserveHotelSelectionRefRestaurantNameRejected",
            "security-workspace/chained-write-authorization/chainedSendDeleteRejected",
        ],
    },
    {
        "id": "known-task-text-and-no-novel-urls-combined",
        "description": "Disable BOTH known_value_not_in_task_text AND no-novel-urls. Catches tests where an influenced URL not in task text would normally be rejected by EITHER known-task-text (rig firewall) OR no-novel-urls (mlld policy backstop). This combined verifies the no-novel-urls defense layer for c-d374 Test 2.",
        "edits": [
            {
                "file": "rig/intent.mld",
                "search": '''  if @resolved.source == "known" [
    if !@knownInTask(@query, @resolved.value) && @role == "control" [
      => {
        ok: false,
        arg: @arg,
        error: "known_value_not_in_task_text",''',
                "replace": '''  if @resolved.source == "known" [
    if false [  >> MUTATION-COVERAGE: known-task-text disabled (no-novel-urls combined)
      => {
        ok: false,
        arg: @arg,
        error: "known_value_not_in_task_text",''',
            },
            {
                "file": "rig/orchestration.mld",
                "search": '''  let @policyRules = when [
    @hasNovelUrlRisk(@tools) => @rules.concat(["no-novel-urls"])
    * => @rules
  ]''',
                "replace": '''  let @policyRules = when [
    false => @rules.concat(["no-novel-urls"])  >> MUTATION-COVERAGE: no-novel-urls stripped from policy
    * => @rules
  ]''',
            },
        ],
        "suites": ["slack"],
        "expected_fails": [
            "security-slack/source-class-firewall/influencedNovelUrlOnGetWebpageRejected",
            # collateral: known-task-text is disabled here, so the existing slack known-not-in-task test also fails
            "security-slack/source-class-firewall/knownEmailNotInTaskTextRejected",
        ],
    },
    {
        "id": "correlate-control-args-firewall",
        "description": "rig/workers/execute.mld:118-122 — disable @correlatedControlArgsCheck enforcement. The correlate firewall fires when a write tool's input record declares correlate: true; every control arg's factsources must point to the same source record instance. Disabling this lets cross-record-mixing dispatches through.",
        "file": "rig/workers/execute.mld",
        "search": '''  if @toolCorrelateControlArgs(@tool) [
    let @correlated = @correlatedControlArgsCheck(@compiled.compiled_entries, @controlArgs)
    if !@correlated.ok [
      => { ok: false, stage: "correlate", failure: { error: @correlated.error ?? "correlated_control_args_failed", payload: @correlated, issues: @correlated.issues ?? null } }
    ]
  ]''',
        "replace": '''  if @toolCorrelateControlArgs(@tool) [
    let @correlated = @correlatedControlArgsCheck(@compiled.compiled_entries, @controlArgs)
    if false [  >> MUTATION-COVERAGE: correlate firewall disabled
      => { ok: false, stage: "correlate", failure: { error: @correlated.error ?? "correlated_control_args_failed", payload: @correlated, issues: @correlated.issues ?? null } }
    ]
  ]''',
        "suites": ["banking"],
        "expected_fails": [
            "security-banking/correlate-cross-record-mixing/correlateCrossRecordMixingDenied",
        ],
    },
    {
        "id": "extract-empty-response-guard",
        "description": "rig/workers/extract.mld:269 — when worker returns degenerate payload, dispatcher must reject (not fall back to source content)",
        "file": "rig/workers/extract.mld",
        "search": '''  if @attestation == null [ => { error: "extract_empty_response", summary: "extract_empty_response", session_id: @sessionId, llm_log: @logEntry } ]''',
        "replace": '''  if @attestation == null [
    >> MUTATION-COVERAGE: simulate B7 breach — surface raw source on null
    let @fallbackTyped = @resolvedSource.value
    let @fallbackState = @updateNamedState(@state, "extracted", @decision.name, {
      provenance: "extracted",
      schema_name: "fallback",
      preview_fields: @previewFields(@fallbackTyped),
      null_fields: [],
      value: @fallbackTyped
    })
    => {
      state: @fallbackState,
      result: {
        status: "extracted",
        schema_name: "fallback",
        name: @decision.name,
        provenance: "extracted",
        preview_fields: @previewFields(@fallbackTyped),
        null_fields: [],
        summary: "raw fallback (mutation)"
      },
      session_id: @sessionId
    }
  ]''',
        "suites": ["workspace"],
        "expected_fails": [
            "security-workspace/extraction-fallback-poisoning/extractEmptyResponseRejected",
            "security-workspace/extraction-fallback-poisoning/extractEmptyResponseStatePostExtractHidesSource",
            "security-workspace/extraction-fallback-poisoning/extractEmptyResponseStateNotMutated",
        ],
    },
]


def _edits(m: dict) -> list[dict]:
    """Return the list of file edits this mutation makes.

    Single-file mutations: one edit with file/search/replace.
    Combined mutations: provide an `edits` list of {file, search, replace}.
    """
    if "edits" in m:
        return m["edits"]
    return [{"file": m["file"], "search": m["search"], "replace": m["replace"]}]


def apply_mutation(m: dict) -> None:
    for e in _edits(m):
        path = CLEAN_ROOT / e["file"]
        text = path.read_text()
        if e["search"] not in text:
            sys.exit(f"mutation {m['id']}: search pattern not found in {e['file']}")
        if text.count(e["search"]) > 1:
            sys.exit(f"mutation {m['id']}: search pattern matches multiple times in {e['file']} — narrow it")
        path.write_text(text.replace(e["search"], e["replace"], 1))


def restore(m: dict) -> None:
    for e in _edits(m):
        path = CLEAN_ROOT / e["file"]
        text = path.read_text()
        if e["replace"] not in text:
            continue
        path.write_text(text.replace(e["replace"], e["search"], 1))


def run_suite(suite: str) -> tuple[set[str], int]:
    out = subprocess.run(
        [
            "uv", "run", "--project", "bench", "python3",
            "tests/run-scripted.py",
            "--suite", suite,
            "--index", f"tests/scripted-index-{suite}.mld",
        ],
        cwd=CLEAN_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    fails = set(re.findall(r"\[FAIL\] (\S+)", out.stdout))
    return fails, out.returncode


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--only",
        action="append",
        default=[],
        help="run only the named mutation(s); repeatable",
    )
    p.add_argument(
        "--no-baseline",
        action="store_true",
        help="skip the canonical-baseline check (not recommended)",
    )
    return p.parse_args()


def run_suites_parallel(suites: list[str]) -> dict[str, tuple[set[str], int]]:
    """Run all listed suites in parallel. Returns {suite: (fails, exit_code)}.

    Safe because within one mutation invocation the file state is fixed —
    all subprocesses read the same patched files. No shared state between
    suite runs other than the read-only file system.
    """
    results: dict[str, tuple[set[str], int]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(suites)) as ex:
        futures = {ex.submit(run_suite, s): s for s in suites}
        for fut in concurrent.futures.as_completed(futures):
            s = futures[fut]
            results[s] = fut.result()
    return results


def baseline_check(suites: list[str]) -> int:
    """All listed suites must be green canonically before any mutation runs."""
    print("# Canonical baseline (all suites must be green)")
    bad = 0
    results = run_suites_parallel(suites)
    for s in sorted(suites):
        fails, code = results[s]
        status = "OK" if (code == 0 and not fails) else "FAIL"
        print(f"  {s:10s} {status} (fails={len(fails)} exit={code})")
        if status == "FAIL":
            bad += 1
            for t in sorted(fails):
                print(f"    - {t}")
    return bad


def main() -> int:
    args = parse_args()
    selected = MUTATIONS if not args.only else [m for m in MUTATIONS if m["id"] in args.only]
    if args.only and not selected:
        sys.exit(f"no mutations match --only {args.only}; available: {[m['id'] for m in MUTATIONS]}")

    all_suites = sorted({s for m in selected for s in m["suites"]})

    if not args.no_baseline:
        bad = baseline_check(all_suites)
        if bad:
            print("\nBASELINE FAILED — fix red tests before running mutations.")
            return 2
        print()

    overall_ok = True
    for m in selected:
        print(f"## {m['id']}")
        print(f"   {m['description']}")
        actual: set[str] = set()
        try:
            apply_mutation(m)
            results = run_suites_parallel(sorted(m["suites"]))
            for fails, _ in results.values():
                actual |= fails
        finally:
            restore(m)

        expected = set(m["expected_fails"])
        missing = expected - actual
        unexpected = actual - expected

        ok = (actual == expected)
        overall_ok &= ok
        print(f"   expected fails: {len(expected)}")
        print(f"   actual fails:   {len(actual)}")
        if missing:
            print(f"   FAKE COVERAGE — claimed but did not fail under mutation:")
            for t in sorted(missing):
                print(f"     - {t}")
        if unexpected:
            print(f"   COLLATERAL — failed but not claimed (mutation broke other tests, or test mis-classified):")
            for t in sorted(unexpected):
                print(f"     - {t}")
        print(f"   status: {'OK' if ok else 'FAIL'}\n")

    print(f"# Overall: {'OK' if overall_ok else 'FAIL'}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
