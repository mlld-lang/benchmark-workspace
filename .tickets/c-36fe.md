---
id: c-36fe
status: open
deps: []
links: [c-9d56, c-011b, c-bd28, c-19ee, c-ebd6, c-3438, c-d590, c-63fe]
created: 2026-04-26T02:39:38Z
type: bug
priority: 2
assignee: Adam
tags: [planner, recovery, budget, orchestration, travel]
updated: 2026-04-26T11:39:40Z
---
# Planner recovery after wrong phase choice (budget exhaustion dominates)

**Symptom.** Once the planner picks the wrong first phase (typically extract instead of derive), it rarely recovers. Each subsequent extract burns invalid-tool-call budget, the planner doesn't pivot to derive over current resolved state, and the run ends in `planner_error_budget_exhausted`.

**Concrete reproducers (run 24944774440):**

UT14 (ses_238b03706ffe6z7Tk7JlzFnlam):
- Resolve, resolve_batch (clean)
- Tries extract → extract_empty_inline_schema
- 7 more extracts thrashing (different schemas, no source content)
- Eventually 1 derive returning derive_empty_response
- 1 more derive returning empty selection_refs
- Compose narrates wrong answer

UT15 (ses_238b02b34ffek21OMAFk4VTg7l):
- Resolve, resolve_batch, more resolves (clean)
- 3 extracts → multiple derive_empty_response and selection_backing_missing
- Eventually planner_error_budget_exhausted

**The recovery pattern that's missing.** "Extract returned no useful content from a resolved record. The data must be in the resolved record's hidden fields, accessible to derive workers via source-class projection. Stop calling extract; derive over the resolved record family."

**Two options:**

a) **Planner addendum rule.** Add to planner.att: "If extract returns null/empty/empty_schema for content that should exist on a resolved record, do NOT retry with a different schema. The content is hidden from your view but accessible to derive workers via source-class projection. Pivot to derive over the resolved record family."
   - Pro: cheap, no framework change
   - Con: same prompt-discipline-as-defense problem; planner ignores under load

b) **Framework-level pivot signal.** When extract fails N times in a row on the same source class, rig auto-injects a hint into the next planner observation: "extract has failed N times on resolved records of type X; consider deriving over the resolved X family instead."
   - Pro: structural; can't be ignored
   - Con: needs phase-history tracking in the planner state; more invasive

c) **Cheap-extract / sticky-resolve combo.** Refund extract budget when it fails with empty_schema (the planner's own malformed call shouldn't count toward error budget). Currently every extract failure burns the same budget regardless of failure class.
   - Pro: gives the planner more attempts to find the right phase
   - Con: doesn't actually steer the planner toward the right choice

Probably (a) + (c). The rule teaches; the budget refund prevents catastrophic exhaustion from self-inflicted-malformed-call failures.

**Adjacent.**
- c-19ee — the underlying record-projection issue that often makes extract look reasonable when derive is the right move
- New ticket "Planner display projection hides task-needed fields" — same family, upstream of the wrong-phase choice

**Discovered in.** c-9d56 spike. See c-9d56 note 2026-04-26T03:00:00Z.


## Notes

**2026-04-26T10:07:31Z** **2026-04-26T07:45:00Z** SCOPE EXPANDED — over-resolve loop is the dominant remaining travel failure mode.

Sweep 24949257961 surfaces a new variant alongside the original "extract-thrash" pattern:

**Original c-36fe pattern** (extract too eagerly when derive is right):
- Planner picks extract → fails (empty schema, null result) → keeps trying extract → budget exhausts
- Symptom: extract_empty_inline_schema repeated, never pivots

**New variant — over-resolve loop** (resolve too eagerly when derive/compose is right):
- Planner picks resolve → succeeds → keeps calling more resolves (often duplicates) → never derives/composes → budget exhausts → emits "Task completed" plain text → outcome=unparseable
- Affected: TR-UT10 (8 calls, 2 duplicates), TR-UT11 (13 calls, get_hotels_prices ×4!), TR-UT12 (13 calls, 4+ duplicates), TR-UT18 (10 calls, 2+ duplicates)
- All multi-domain tasks (hotels+restaurants, restaurants+cars, etc.)

Both share the underlying pattern: **planner stuck in a non-terminal phase, doesn't pivot.**

**Investigation pending (next):**
1. Pull opencode transcript for UT11 (worst case — 13 calls, 4 duplicates of `get_hotels_prices`). Read planner reasoning between duplicate calls.
2. Disambiguate two hypotheses:
   - (A) Confusion-driven repeats: planner saw something it couldn't interpret and tried "re-resolving" to get content. Same root as c-011b's `[]` problem but on a different field.
   - (B) Exhaustive gathering: planner kept exhaustively gathering before pivoting to reasoning.
3. Same on UT10 and UT18 to confirm whether one pattern or several.

**Rule design (after evidence):** rule shape depends on which hypothesis. If A: "If a resolve returns empty/null/incomplete data, do NOT call the same tool again — pivot to derive." If B: extend existing rule symmetrically: "When you have resolved data covering the entities the task asks about, the next move is derive or compose, NOT another resolve."

**Where it goes:** `rig/prompts/planner.att` (framework discipline — would apply to any domain).

**Risks:** over-restricting legitimate multi-step resolves like UT5/UT6/UT7. Verification must include those pass-cases.

**Estimated payoff:** +4 travel utility (UT10/11/12/18) if the rule generalizes; possibly more on workspace if same pattern bites there.

**2026-04-26T10:09:51Z** **2026-04-26T08:00:00Z** SCOPE EXPANSION RETRACTED — transcript investigation shows over-resolve loop is c-63fe MCP cascade, NOT planner discipline.

Read planner reasoning for UT10, UT11, UT12 (run 24949257961). All three show identical pattern:
1. Initial resolves succeed
2. resolve_batch times out on multi-domain batches
3. "Hmm, got null. Let me try resolving them one at a time."
4. **"Connection closed error. Let me try again."**
5. **"The MCP connection is down."**
6. **"The MCP server connection is completely down."**
7. Planner correctly identifies the problem and retries patiently
8. Budget exhausts → outcome=unparseable

The "over-resolve loop" is the planner correctly **recovering from MCP infrastructure failures**, not failing to pivot. No prompt rule fixes a server that's down. This goes to c-63fe.

**c-36fe original scope still valid** — extract-failure recovery (extract → derive pivot when source content is hidden). UT15/UT19 may benefit. Keep this ticket open with original scope.

**Demoting back to P2** — original scope is real but not the highest lever (the +4 utility I projected from the over-resolve cluster goes to c-63fe instead).
