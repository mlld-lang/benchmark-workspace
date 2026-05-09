---
id: c-60ff
status: closed
deps: []
links: []
created: 2026-05-09T01:23:49Z
type: bug
priority: 2
assignee: Adam
tags: [records, policy, rig]
updated: 2026-05-09T18:19:18Z
external-ref: was-mlld:m-60ff
---
# Remove implicit correlate default for multi-fact input records

The security fundamentals say correlate is explicit and does not default true by arity, but rig/tooling.mld previously treated undefined correlate with >1 control args as true. This was stricter than intended but created inconsistent security posture between omitted correlate and correlate:false.

## Acceptance Criteria

Input records only enable correlate-control-args when correlate: true is explicitly declared. Tests cover omitted correlate on a multi-control-arg input record and correlate:false producing the same behavior.


## Notes

**2026-05-09T03:08:45Z** Originally filed as mlld:m-60ff. Implementation lives under rig/tooling.mld, outside the active writable mlld package. The likely code fix is clear: remove the implicit @inputControlArgs.length > 1 default and require correlate: true explicitly, with clean-side regression coverage.

**2026-05-09T18:19:13Z** ## Closed clean-side at 71c369c

Implemented in rig/tooling.mld@toolCorrelateControlArgs — dropped the implicit "@inputControlArgs.length > 1 → true" branch. Correlate is now opt-in only: explicit `correlate: true` enables, omitted or `correlate: false` both disable.

Verified: every correlate-using record in bench/domains/ declares correlate explicitly (banking update_scheduled_transaction_inputs declares `correlate: true`; workspace/slack/travel update-input records declare `correlate: false`). No existing record relied on the implicit default.

Regression added at tests/rig/tool-metadata.mld in a `correlate-opt-in` group (3 tests: explicit-true, explicit-false, omitted — last two must produce identical no-check behavior). Narrative comment in tests/scripted/security-banking.mld B5 group updated to drop the "(or has >1 fact fields)" clause. Gate at 217/0/1 (was 214; +3 from regression).

Closing.

**2026-05-09 (handoff)** Migrated from mlld:m-60ff → c-60ff. Original ticket lived in ~/mlld/mlld/.tickets but the implementation is purely clean-side; relocating to clean tracker for proper home. ID hash preserved.
