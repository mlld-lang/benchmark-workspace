---
id: c-edd4
status: closed
deps: []
links: []
created: 2026-05-05T15:40:58Z
type: feature
priority: 4
assignee: Adam
tags: [bench, classifier, advice-gate]
updated: 2026-05-14T18:05:13Z
---
# Extend @toolSet convention to workspace/banking/slack suites


## Notes

**2026-05-05T15:41:31Z** Travel adopted @toolSets in bench/domains/travel/tools.mld during the advice-gate spike (2026-05-05). Workspace/banking/slack still ship the whole tool catalog without sub-set decomposition because they don't currently need classifier-driven routing. If/when the LLM-based classifier pattern proves itself on travel, lift to other suites: declare @toolSets in each domain's tools.mld with named sub-sets that match how their tasks decompose, then their suite agent can fan out classifiers via @rig.classify the same way travel does. No urgency — file alongside that work, not before. Cross-ref: rig/ADVICE_GATE.md, rig/classify.mld, bench/domains/travel/tools.mld.

**2026-05-14T18:05:13Z** Closed 2026-05-14 (ticket-review pass): Premature; refile if classifier routing becomes active outside travel.
