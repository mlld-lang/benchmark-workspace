---
id: c-2af7
status: closed
deps: []
links: []
created: 2026-04-21T23:54:35Z
type: task
priority: 2
assignee: Adam
tags: [rig, cleanup]
updated: 2026-04-22T00:04:32Z
---
# Simplify callToolWithOptionalPolicy after circular-ref fix lands

Once m-e091 (circular ref checker false positive on local exe variables) is fixed in mlld, refactor callToolWithOptionalPolicy in rig/runtime.mld. Remove slice(0,1) param truncation, singleArg/preferDirect workarounds, and the 6-block cascade. Prefer collection dispatch for all input-record tools, keep raw exe as fallback only. Blocked on m-e091.


## Notes

**2026-04-21T23:54:42Z** Blocked on mlld runtime ticket m-e091 (circular ref checker). Once that lands, the refactor is straightforward — the GPT agent already proved the collection dispatch pattern works in ~/mlld/mlld/tests/cases/var-tools/input-record-multi-param-policy/.
