---
id: SL-no-novel-construction
status: open
deps: []
links: []
created: 2026-05-14T18:33:53Z
type: task
priority: 2
assignee: Adam
---
# [SL] Verify no extract/derive path mints fact-bearing URLs from untrusted scalars

Verification target: confirm extract/derive worker output cannot mint string-facts on `url` kind (or any kind). A URL constructed by concatenating known + secret must not satisfy `@get_webpage.url`'s fact-floor. Closes Class A 'worker constructs URL by concatenation' and Class E 'worker-composed URL strings' paths. From sec-slack.md §8 Class A + Class E.

