---
id: c-sweep
status: open
deps: []
links: []
created: 2026-04-23T20:10:47Z
type: task
priority: 1
assignee: Adam
tags: [measurement, suites]
---
# Run other suite sweeps: slack, banking, travel

Workspace is at 31/40 (77.5%). The prompt/error audit changes (c-pe00 through c-pe08) and suite addendums are landed for all four suites. Run the other three to measure:

Commands:
  uv run --project bench python3 src/run.py -s slack -d defended -p 21 --stagger 5
  uv run --project bench python3 src/run.py -s banking -d defended -p 16 --stagger 5
  uv run --project bench python3 src/run.py -s travel -d defended -p 20 --stagger 5

Previous baselines (from SCIENCE.md):
- Slack: 8/21
- Banking: 6/16
- Travel: 0/20 (1/20 previously)

The travel addendum + tool description improvements are the biggest expected gain — Pattern C (resolve loop) was the dominant travel failure and the addendum directly addresses it.

After all three suites run, update SCIENCE.md with results and identify per-suite failure patterns.

