---
id: c-ade3
status: closed
deps: []
links: []
created: 2026-04-24T20:04:26Z
type: task
priority: 2
assignee: Adam
updated: 2026-05-01T08:59:40Z
---
# Sonnet 4 measurement run on workspace. Run the full workspace suite with --harness claude (defaults to claude-sonnet-4-20250514 for both planner and worker). Compare utility against GLM 5.1 hybrid baseline. Check if flaky tasks (UT22, UT36, UT39) stabilize on a stronger model.


## Notes

**2026-05-01T08:59:40Z** Closing 2026-05-01 per user direction. Original premise (check if flaky UT22/UT36/UT39 stabilize on stronger model) is partly resolved — UT22/UT24/UT36/UT37 verified passing on GLM 5.1 in bench-grind-14 closeout. The headline-comparison story (vs CaMeL Table 2 Claude 4 Sonnet) is captured in SCIENCE.md / HANDOFF.md without needing our own Sonnet 4 measurement run. Reopen if the comparison story needs an apples-to-apples model match.
