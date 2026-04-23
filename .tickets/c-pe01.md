---
id: c-pe01
status: closed
deps: [c-pe00]
links: [c-f337]
created: 2026-04-23T15:45:51Z
type: task
priority: 1
assignee: Adam
tags: [prompt-audit, rig, h1]
updated: 2026-04-23T18:06:26Z
---
# Intent compilation error messages — repair examples

Improve error messages in rig/intent.mld to include repair examples showing the correct call shape. The planner retries 3-10 times on Pattern A/E failures because error messages return codes without showing what the corrected ref should look like.

Errors to improve:
- payload_only_source_in_control_arg: add 'Control args require resolved or known source. Change { source: "extracted" } to { source: "resolved", record: "<type>", handle: "<handle>", field: "<field>" } using a handle from a prior resolve.'
- control_ref_requires_specific_instance: already has hint + handles list, but add a concrete example ref using available_handles[0]
- known_value_not_in_task_text: append available resolved handles so planner can immediately switch to resolved
- no_update_fields: 'This is an update tool. You must include at least one changed field from: [field list].'
- correlate_control_args_cross_record_mixture: 'All control args must come from the same resolved record instance.'
- non_task_source_in_exact_payload_arg: explain what exact payload args are and that they must come from task text

Files: rig/intent.mld (primary), rig/workers/execute.mld (no_update_fields context)

Testing:
1. mlld clean/rig/tests/index.mld --no-checkpoint (gate)
2. Canaries: UT8 (Pattern A/E), UT7 (budget from ref errors), banking UT2 (correlate)
3. Regression: UT6 (passing write)
4. Transcript review: verify model corrects in fewer retries

