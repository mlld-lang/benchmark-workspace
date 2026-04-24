---
id: c-4d2a
status: closed
deps: []
links: []
created: 2026-04-24T14:26:51Z
type: bug
priority: 1
assignee: Adam
updated: 2026-04-24T19:54:42Z
---
# Claude harness returns empty text for worker LLM calls. All three Claude models (Haiku 4.5, Sonnet 4, Sonnet 4.6) score 1/17 on worker tests with identical failure patterns — extract 0/7, derive 0/5. The assertions show empty strings where content should be. The opencode harness works correctly (GLM 5.1 = 16/17, MiniMax = 16/17, Kimi = 15/17). The claude harness likely doesn't return the response text in the format the worker test runner expects. Needs investigation into how @claude() returns text vs how @opencode() returns it, and alignment so both harnesses work for rig worker calls.

