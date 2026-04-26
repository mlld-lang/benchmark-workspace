---
id: c-36fe
status: open
deps: []
links: [c-9d56, c-011b, c-bd28, c-19ee, c-ebd6]
created: 2026-04-26T02:39:38Z
type: bug
priority: 2
assignee: Adam
tags: [planner, recovery, budget, orchestration, travel]
updated: 2026-04-26T03:02:47Z
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

