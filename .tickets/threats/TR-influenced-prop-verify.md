---
id: TR-influenced-prop-verify
status: open
deps: []
links: [BK-influenced-prop-verify, WS-influenced-rule-verify]
created: 2026-05-14T18:34:28Z
type: task
priority: 2
assignee: Adam
updated: 2026-05-14T19:07:48Z
---
# [TR] Verify untrusted-llms-get-influenced propagates through derive/extract to advice gate input

Verify untrusted-llms-get-influenced propagates the influenced label from a worker that read review_blob (data.untrusted) into its output, so the advice gate's no-influenced-advice rule fires when influenced state reaches the advice worker. This is the defense-in-depth catching anything slipping past role:advice display projection. Verify propagation post-mlld-2.1.0 / records-as-policy migration through the new mx.influenced channel. From sec-travel.md §8 Class A + Class B + §9 question 2.

