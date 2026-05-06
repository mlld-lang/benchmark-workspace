---
id: c-bd28
status: open
deps: []
links: [c-9d56, c-011b, c-36fe, c-ebd6]
created: 2026-04-26T02:39:22Z
type: bug
priority: 2
assignee: Adam
tags: [selection-ref, validation, unicode, worker-output, travel]
updated: 2026-04-26T03:02:47Z
---
# selection_ref handle validation: tolerate worker-introduced Unicode dash variants

**Symptom.** Worker LLMs autocorrect ASCII hyphen (U+002D) to Unicode dash variants (typically U+2011 non-breaking hyphen, sometimes U+2010) when emitting product-name-shaped handles in selection_refs. Rig's selection_backing_missing validator does byte-exact comparison and rejects the worker's output even though the handle is logically the same.

**Concrete reproducer.** travel UT15, run 24944774440, session ses_238b02b34ffek21OMAFk4VTg7l, derive call prt_dc7513ad50017QH90l8rCUqMgf.

```
worker emitted:    "r_car_company_review_SunSet Rent‑A‑Car"  (U+2011 NON-BREAKING HYPHEN)
available_handles: "r_car_company_review_SunSet Rent-A-Car"  (U+002D ASCII HYPHEN, correct)
```

Rig hands the worker the ASCII handle in its prompt; the worker model (Cerebras gpt-oss-120b) types it back with U+2011. Result: selection_ref_validation_failed → selection_backing_missing → planner thrashes → planner_error_budget_exhausted.

This is a known LLM behavior on product names containing hyphens. Will recur on any benchmark with hyphenated entity names.

**GPT's framing — do NOT casually fuzzy-match handles.** Handles are identifiers. Casual normalization breaks identity guarantees and can cause collisions. The narrow safe fix:

**Canonicalize only known Unicode dash variants to ASCII U+002D during comparison.** Specifically: U+2010 (HYPHEN), U+2011 (NON-BREAKING HYPHEN), U+2012 (FIGURE DASH), U+2013 (EN DASH), U+2014 (EM DASH), U+2212 (MINUS SIGN). Preserve the stored handle exactly. Reject the call (NOT auto-canonicalize and accept) if two handles in the same available_handles bucket would collide after normalization.

Where:
- selection_ref validation in `rig/intent.mld` (or wherever `selection_backing_missing` is emitted)
- Apply normalization only to the handle field, only on the comparison path
- Add a paired test: two records that synthesize handles `Foo-Bar` (ASCII) and `Foo‑Bar` (U+2011) in the same bucket → validator must error rather than silently canonicalize one

**Companion: derive worker prompt rule.** Add to derive.att: "When emitting a selection_ref handle, copy it byte-for-byte from the available_handles list. Do not autocorrect, prettify, or normalize punctuation."

Both layers: validator tolerates known dash variants, prompt teaches the worker not to autocorrect in the first place. Defense in depth without breaking handle identity.

**Discovered in.** c-9d56 spike. See c-9d56 note 2026-04-26T03:00:00Z.


## Notes

**2026-04-26T18:08:14Z** **2026-04-27T17:50:00Z** Status:
- @canonicalizeDashes helper landed in rig/intent.mld (handles U+2010-2014, U+2212)
- Wiring into @lookupResolvedEntry rolled back due to wrapper-shape issue: the canonical-fallback returns a value where .isDefined()=true but !x=true (no .handle field), breaking @lowerSelectionRef's `if !@entry` guard
- xfail/c-bd28/UH-1 invariant test captures the regression cleanly
- compose.att ASCII hyphen rule shipped in commit ef751e0 (compose-output flavor of the issue — UT13)

Remaining work:
1. Debug the wrapper-shape issue in canonical-fallback path (`@matched[0]` from for-when returns lossy value)
2. Wire canonicalizeDashes once #1 fixed
3. Verify xfail/UH-1 flips to PASS

Stochastic: UT13 and UT15 flip between PASS/FAIL based on whether the worker autocorrects hyphens. Compose ASCII rule should help compose-output flavor; the validator fix is needed for selection_ref handle flavor.

**2026-05-06T01:32:23Z** Filed upstream as **m-4bcd** (priority 0) in /Users/adam/mlld/mlld with full repro + acceptance criteria, including the security implication (Unicode dash variants in injected payloads can bypass selection-ref handle matching).
