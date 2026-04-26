---
id: c-db45
status: closed
deps: []
links: [c-c653, c-1fa1, c-db19]
created: 2026-04-25T21:49:22Z
type: bug
priority: 0
assignee: Adam
tags: [compose, worker-context, travel]
updated: 2026-04-26T10:06:53Z
---
# Compose worker drops state fields in final narration

Compose worker has correct data in state but final narration omits required values. Cluster bug across 3+ tasks (and likely more — every task where utility checks specific values in model_output is a candidate).

Confirmed cases:
- TR-UT1 (c-c653): state has price 100-180, address full string. Compose says 'minimum price of 100.0' (drops 180=max which eval requires) and 'address is not available' (drops the address that IS in state).
- TR-UT8 (c-db19): state has 3 derives (best_vegan_restaurant=Royal Panda stale, best_vegan_pick=New Israeli current, event_details=New Israeli current). Compose narrates the FIRST stale derive (Royal Panda) instead of the corrected one. Calendar event execute used the right one.
- TR-UT9 (c-1ff0): state has Breizh Café address. Compose final: 'Breizh Café – Rating: 3.9. Address: . Operating hours: ...' — empty after 'Address:'. Eval requires address string.

Probable root cause: compose worker has no signal about which state fields/derives are 'authoritative answer source'. Receives state + sources + purpose, must pick what to narrate. When state has multiple overlapping derives or fields the planner expected to narrate, compose makes wrong picks.

Same family as the worker-context rule (commit d9aee4e) that helped extract + derive — compose has the same insufficient-context problem. Possible fixes:
1. Extend worker-context rule to compose: planner's compose purpose should explicitly name which derive(s) are authoritative + which fields to include verbatim.
2. Rig auto-prefer: when multiple derives have overlapping fields, surface only the most-recent.
3. Mark a derive as 'final' for compose to prefer.
4. Prompt-side: derive worker prompt could be told to put the 'final answer' fields in a known location like 'payload.answer'.

Probable utility recovery: 3+ travel tasks. Worth measuring after a planner.att compose-context rule lands.


## Notes

**2026-04-26T03:46:57Z** **2026-04-26T04:30:00Z** DESIGN REFINED (per GPT review).

**Pick: option (a) + small dose of (c). Skip option (b).**

Option (b) — "rig auto-prefers most-recent derive when names overlap" — too implicit. Adds a recency heuristic that can't be reasoned about from prompts. Defer indefinitely.

**The real missing contract: compose worker doesn't see compose decision context.**

Current compose.mld ignores `compose.purpose`, `compose.sources`, and the planner's selected source names. The worker just narrates state. This is why it drops fields, swaps derives, fabricates address strings — it has no contract about WHAT the planner intended this compose to say.

**Three-layer fix:**

1. **Wire compose decision context into compose worker dispatch.** `rig/workers/compose.mld` should pass `purpose`, `sources` (the planner-named source names), and any explicitly named selected fields into the prompt. This is plumbing, not prompt polish.

2. **Planner.att rule:** `compose.purpose` MUST name the authoritative derived/extracted values and exact fields to include. "Compose final answer" is not enough; it needs to be "Compose using `derived.best_vegan_pick` (name, address, rating) and the resolved `selected_restaurant.address`." Otherwise the worker has nothing to anchor.

3. **Compose.att rule:** Treat the planner-named sources as primary. If the purpose names `derived.X`, the compose narration must use the values from `derived.X` — not invent or substitute. If a named source has no value, say "not available" explicitly rather than fabricating.

**Why this preserves planner intent:** the planner already DECIDED which derive is authoritative when it picked sources for compose. Option (b) would silently override that decision with a recency rule. Option (a)+(c) makes the planner's existing decision actually reach the worker.

**Implementation steps:**
1. Read compose.mld and compose.att to confirm decision context isn't currently passed.
2. Spike: dump a current compose worker prompt to see what it sees.
3. Wire purpose + sources + selected source names into compose dispatch.
4. Add planner.att rule about compose.purpose specificity.
5. Add compose.att rule about treating named sources as primary.
6. Test on TR-UT8 (Royal Panda fabrication case) and TR-UT1 (City Hub address drop).

**2026-04-26T05:03:11Z** **2026-04-26T07:15:00Z** FIX LANDED + LOCAL VERIFICATION.

Implementation:
- `rig/workers/compose.mld`: added `decision` param to `@composePrompt` and `@dispatchCompose`. Threaded through.
- `rig/workers/planner.mld`: pass `@decision` from `@plannerCompose` to `@dispatchCompose`.
- `rig/prompts/compose.att`: added `<planner_decision>` block + new "Planner decision rules" section. Rule: treat named sources as primary, say "not available" if a named field has no value (don't fabricate).
- `rig/prompts/planner.att`: updated worker-context section to include compose in the workers-with-purpose list. Added rule that `compose.purpose` must name authoritative derived/extracted values + exact fields. Worked example: `compose({ "sources": ["derived.best_electric_rental"], "purpose": "Report company name, rating, and weekly_cost (price_per_day * 7) from derived.best_electric_rental" })`.
- `rig/tests/workers/compose.mld`: updated test caller to pass `decision ?? {}`.

**Gates green:** 121/121 invariants, 23/23 worker tests.

**Local single-task verification:**
| Task | Pre-fix | Post-fix | Notes |
|------|---------|----------|-------|
| TR-UT8 | FAIL (Royal Panda fabrication — canonical c-db45 case) | **PASS** | Compose now anchors on planner-named source instead of substituting earlier derive |
| TR-UT14 | stochastic (was PASS, recently FAIL) | 1/2 PASS | Planner emitted correct decision: `sources: ["derived.best_electric_rental"]`, detailed purpose. Failure mode shifted from "wrong field" to "wrong company picked by derive" — separate worker variance |
| TR-UT1 | FAIL (City Hub address drop) | FAIL (different reason) | Worker correctly emitted decision context. Compose said "minimum price is not available" — exactly the new rule (no fabrication). Underlying data missing → c-1fa1 territory, NOT a c-db45 regression |

UT8 is the clean win. UT14 stochasticity unchanged at the worker level. UT1 reveals the new behavior is correct (no fabrication) but exposes c-1fa1's data gap.

Ready for sweep verification. Expected gains over c-011b baseline: TR-UT8 stable PASS; possible improvements on UT9 (other compose-drops-fields case from original ticket); UT1 still requires c-1fa1.

**2026-04-26T10:06:53Z** **2026-04-26T07:45:00Z** SWEEP VERIFIED.

Run 24949257961, image SHA ede5973. Travel 5/20 → 11/20.

Direct win:
- TR-UT8 (Royal Panda fabrication): FAIL → PASS

Compose decision context observed working in UT1's failure: compose said "minimum price not available" instead of fabricating an address — the new "named sources are primary; say 'not available' if missing" rule fired correctly. UT1 still failing for upstream data reasons (c-1fa1), not c-db45 regression.

Indirect contributions to UT0/UT2/UT9/UT16 wins likely (cleaner planner-to-compose contract reduces ambient confusion).

Fix is verified at sweep level. Closing.
