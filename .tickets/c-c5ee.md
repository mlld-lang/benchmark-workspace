---
id: c-c5ee
status: closed
deps: []
links: [c-91c6, c-aa56]
created: 2026-04-28T16:37:16Z
type: feature
priority: 1
assignee: Adam
tags: [typed-instruction, workspace, authority, security, ut13]
updated: 2026-05-14T18:05:14Z
---
# Typed instruction prereq: workspace delegation-grant/work-order authority records

Design a general workspace record family such as @work_order or @delegation_grant that can mint non-tainted authority for delegated file reads/writes. It must authorize source-selected file targets without laundering filenames from tainted prose, carry facts for source actor, target file handle, allowed operation, scope, and provenance, and include negative tests for arbitrary attacker-selected files.

## Acceptance Criteria

A general delegation-grant/work-order record is documented and implemented in workspace records; delegated append/read actions can bind only through this authority or clean user text; UT13 file read/write targets can be authorized without referencing benchmark-specific strings; injected valid-looking append/read instructions targeting unrelated files remain blocked at 0% ASR.


## Notes

**2026-05-14T18:05:14Z** Closed 2026-05-14 (ticket-review pass): Superseded by c-6479 deterministic-only reframe; authority records dropped from near-term path.
