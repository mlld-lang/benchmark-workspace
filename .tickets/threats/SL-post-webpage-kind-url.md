---
id: SL-post-webpage-kind-url
status: open
deps: []
links: []
created: 2026-05-14T18:34:19Z
type: task
priority: 4
assignee: Adam
---
# [SL] Add kind:url to @post_webpage_inputs.url to tighten validity check

Open question: `@post_webpage_inputs.url: facts` is a bare string fact with no `kind:url` annotation. UT4's `www.our-company.com` is task-text-known and passes; the lack of `kind:url` means any task-text string passes regardless of URL-shape. Decision: add `kind:url` to bolt the validity check tighter? Speculative — no current IT exploits this. From sec-slack.md §9 question 9.

