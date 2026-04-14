# Bench v2

Benchmark runner and suite catalogs for rig v2.

The host keeps the same high-level shape as v1:

- `src/run.py` loads AgentDojo suites through the date-shift adapter
- `src/host.py` launches the mlld agent and records lifecycle/session data
- `src/mcp_server.py` exposes the per-task AgentDojo tools over MCP

Default development run (pick any simple read-and-compose workspace task as a canary — do NOT use instruction-following tasks like `user_task_13` as canaries; see `ARCHITECTURE.md` "Explicitly out of scope"):

```sh
uv run python3 clean/bench/src/run.py \
  -s workspace \
  -d defended \
  -p 1 \
  --harness opencode \
  --model openrouter/z-ai/glm-5.1 \
  -t user_task_0
```

Attack run:

```sh
uv run python3 clean/bench/src/run.py \
  -s slack \
  -d defended \
  -a important_instructions \
  -p 1 \
  --harness opencode \
  --model openrouter/z-ai/glm-5.1
```

Results land under `clean/bench/results/<model>/<suite>/`.

Suite entrypoints:

- [agents/workspace.mld](/Users/adam/mlld/clean/bench/agents/workspace.mld)
- [agents/banking.mld](/Users/adam/mlld/clean/bench/agents/banking.mld)
- [agents/slack.mld](/Users/adam/mlld/clean/bench/agents/slack.mld)
- [agents/travel.mld](/Users/adam/mlld/clean/bench/agents/travel.mld)
