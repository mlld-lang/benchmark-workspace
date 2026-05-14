---
id: SL-output-checks-test-lock
status: open
deps: []
links: []
created: 2026-05-14T18:34:10Z
type: task
priority: 2
assignee: Adam
---
# [SL] Tier-1/2 regression test that locks @noUntrustedUrlsInOutput firing

Test target: `rig/policies/url_output.mld` declares two per-input guards currently verified firing on the 2026-05-12 canary sweeps (closed c-d0e3, c-bac4, c-e414). A tier-1 or tier-2 test that asserts the guard rejects a body string containing a URL when the source is `data.untrusted` would promote the marks from [-] to [T]. From sec-slack.md §9 question 7.

