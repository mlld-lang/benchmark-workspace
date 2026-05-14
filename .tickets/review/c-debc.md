---
id: c-debc
status: open
deps: []
links: []
created: 2026-05-04T21:14:36Z
type: feature
priority: 2
assignee: Adam
tags: [bench, undefended, baseline, attacks]
---
# Undefended bench path: all-tools-to-planner agent for baseline numbers

We need an explicit "undefended" agent path that gives all bench
tools to the planner LLM with no rig orchestration / no records /
no display projection / no policy / no guards. The planner just
gets the full tool surface and is asked to do the task.

Purpose: establishes the no-defense baseline number for each suite,
and serves as the target for prompt-injection attacks (the contrast
to defended). Without this column, our published numbers can't show
the cost-of-defense vs cost-of-no-defense story.

Current bench has `defense: defended | undefended` as a config option
in agent files, but the "undefended" path is not yet implemented as
"flat tools to planner" — it's currently rig-but-with-some-policies-
relaxed. We need to add a true no-rig path.

Proposed shape:

  bench/agents/<suite>.mld dispatches to:
    - rig agent when defense=defended
    - undefended agent when defense=undefended

  The undefended agent is a thin wrapper: load the AgentDojo MCP
  tool surface, give it all to the planner, run the task. No worker
  split, no extract/derive/execute phases. Just one LLM with tools.

  Use the same opencode/cerebras config as defended for fair
  comparison.

Outputs needed in the matrix:

  | Suite     | Undefended | Defended (ours) | CaMeL Sonnet 4.5 |
  |---        |---         |---              |---               |
  | workspace | X%         | 90%             | 80% ± 12.4       |
  | banking   | X%         | 75%             | 75% ± 21.2       |
  | slack     | X%         | 62%             | 61.9% ± 20.8     |
  | travel    | X%         | 90%             | 75% ± 19.0       |

The undefended numbers should be HIGHER than defended (defense costs
utility), establishing the price-of-defense delta. Then attack
runs against undefended will show 100% ASR on attackable tasks
(the breach-floor); attacks against defended show our actual ASR.

Related: this is the foundation for the spec-extended-attacks-benchmark.md
tier system. Tier 0 = undefended baseline. Tier 1+ = defended at
varying strictness levels.

