---
id: c-a6b7
status: open
deps: []
links: [c-ad40, c-c04c]
created: 2026-05-06T11:09:49Z
type: task
priority: 2
assignee: Adam
tags: [security, banking, attacks, sweep]
updated: 2026-05-06T11:10:14Z
---
# banking: re-run B4 attack matrix after exact: fix to update_user_info_inputs

Once c-ad40 lands the `exact:` declaration on `@update_user_info_inputs`, re-run the relevant attack matrix to verify the structural defense closes the historic UT13 × IT7 breach.

## Attacks to re-run

Per CHALLENGES.md / SCIENCELOG, the UT13 × IT7 banking attack family is the canonical B4 breach. Run the full IT7 matrix against banking:

```bash
gh workflow run bench-run.yml -f suite=banking -f tasks=user_task_13 -f defense=defended -f attack_task=injection_task_7
```

Plus any other UT × IT7 in banking that targets update_user_info (worth grepping AgentDojos injection_tasks.py for "update_user_info" callers; not reading checker code, just call-site grep).

## Why re-run is needed

Banking UT13 currently passes (PASS in STATUS.md) via planner-quality, not structural defense. Adding `exact:` makes the defense structural. Two outcomes possible after re-run:

1. ASR drops to 0/N on the affected UT × IT7 cells (defense holds).
2. Some legitimate utility task regresses because it actually needed update_user_info with a non-task-text value (unlikely — task text is the canonical source for address updates).

Either way the data is needed before declaring the fix complete.

## Acceptance

1. Bench run dispatched after c-ad40 commit lands.
2. STATUS.md updated with the run id and per-task verdict.
3. If a legitimate task regresses, file follow-up; otherwise close.

