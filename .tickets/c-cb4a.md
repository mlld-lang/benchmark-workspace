---
id: c-cb4a
status: open
deps: []
links: [c-63fe, c-4e09, c-8e02]
created: 2026-04-27T01:00:29Z
type: task
priority: 2
assignee: Adam
tags: [agentdojo, host, grading, preventive]
updated: 2026-04-27T01:01:59Z
---
# Extend agentdojo post-env normalizer to banking + slack (preventive)

Travel was added to `_normalize_post_environment_for_grading` in agentdojo runner.py (commit 3984ba38 on mlld/mlld-rig branch) because workspace had the same Pydantic-validator-rebuilds-derived-collection pattern that the workspace normalizer was already handling. Banking and slack both use AgentDojo env models that COULD have the same pattern hit them on JSON roundtrip — when an entity is added that triggers a derived collection rebuild on `model_validate_json`. None of the currently-failing banking/slack tasks are this class today, but extending the gate is preventive cleanup so a future task class doesn't quietly hit the same bug.

## Change

`/Users/adam/mlld/agentdojo/src/agentdojo/runner.py:120`:

```python
# from
if suite_name not in ("workspace", "travel"):
    return post_env
# to
if suite_name not in ("workspace", "travel", "banking", "slack"):
    return post_env
```

## Verify

The function body is generic — it only mutates post_env when there are NEW emails AND the new contacts derive from those emails' recipients. If banking/slack tasks don't trigger that pattern, no-op. So gate-only extension is low-risk.

Run after extension:
- Banking: full local sweep, expect no regression
- Slack: full local sweep, expect no regression

## Background

Discovered during c-4e09 investigation in bench-grind-10. UT3's `check_new_email` failed because the diff had `dictionary_item_added` (the new email — expected) PLUS `iterable_item_added` (a derived contact_list entry). The Inbox `_create_contact_list` validator rebuilds contact_list from email recipients during model_validate_json. Workspace already had a normalizer for this; travel was being rejected. Same fix applied to travel cleared UT3.

## Risk

Low. Gate-only change. Function is read-mostly and only mutates state in a specific narrow pattern. Banking and slack don't currently fail this way, so worst case is no-op.

## Linked

- agentdojo commit 3984ba38: 'Extend post-env normalizer to travel suite'
- c-4e09 (closed): travel/workspace eval-mismatch survey
- c-8e02: TR-UT2 read-only resolves mutate env (related class)

