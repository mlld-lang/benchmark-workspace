---
id: c-8ffd
status: open
deps: []
links: []
created: 2026-05-09T18:58:27Z
type: bug
priority: 1
assignee: Adam
tags: [rig, records, policy, security]
external-ref: was-mlld:m-8ffd
---
# Mixed authority: catalog can_authorize and record write: can disagree on the same tool

@synthesizedAuthorizations (rig/tooling.mld:319) reads @entry.can_authorize from the tool catalog to build the planner-side authorization deny list, while @policy.build at dispatch time enforces record write: declarations from the input record. These two surfaces can disagree on the same tool — for example, a tool can have can_authorize: "role:planner" in the catalog while its input record declares an empty write: {} (effectively can-not-authorize), or vice versa.

Pre-Phase-1 this was the only authorization surface. Phase 1 introduced record-bound write: and intended the catalog can_authorize to become a fallback / UX hint, but synthesizedAuthorizations still treats catalog can_authorize as the primary source. Result: the planner-prompted authorization model and the runtime-enforced model can drift.

## Acceptance criteria

- Record write: declarations are the SINGLE source of truth for authorization.
- Catalog can_authorize is either deleted from tools.mld or repurposed as UX/grouping metadata only (e.g. "which role surface should this tool appear under in planner docs").
- @synthesizedAuthorizations (or its successor) computes the deny list from input records' write: blocks, not from catalog can_authorize.
- Tests cover: tool with catalog can_authorize but record write:{} → denied; tool with no catalog can_authorize but record write:{role:planner:{tools:{authorize:true}}} → allowed.

## Notes

This should LEAD Phase 3 (planner prompt + remaining docs) per advisor — it's a security-posture fix, not cosmetic. Currently the divergence is invisible because all bench tools' catalog can_authorize and record write: happen to agree (audited during Phase 1). But that consistency is by hand, not by the runtime; nothing prevents future drift.

**Lands as its own commit, separate from the planner prompt revision** (Phase 3 ordering per migration-plan §3.B) — bundling means the planner-prompt bench sweep can't attribute which change moved which numbers.

**2026-05-09 (handoff)** Migrated from mlld:m-8ffd → c-8ffd. Original ticket lived in ~/mlld/mlld/.tickets but the implementation is purely clean-side; relocating to clean tracker for proper home. ID hash preserved. Status: open, awaiting Phase 3.
