---
id: SL-url-promotion-shelf
status: open
deps: []
links: []
created: 2026-05-14T18:33:51Z
type: task
priority: 1
assignee: Adam
---
# [SL] Verify urlCapShelf round-trip preserves URL opacity (m-aecd dependency)

Verification target: confirm `urlCapShelf` round-trips URLs only through the private dispatcher, that `@url_ref` and `@referenced_webpage_content` carry NO public URL field, and that no extract/derive path can launder a `@url_ref` into a public string-fact. The mlld m-aecd bug (re-introduces `untrusted` on `data.trusted` after shelf round-trip) may have analogues for `urlCapShelf`. From sec-slack.md §8 Class A/E + §9 question 6.

