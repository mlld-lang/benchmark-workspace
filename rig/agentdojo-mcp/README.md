# agentdojo-mcp

MCP server that exposes [AgentDojo](https://github.com/ethz-spylab/agent-dojo) tools to mlld/rig agents. Wraps **vanilla agentdojo from PyPI** — no fork, no `sys.path` hacks, no in-tree copy of AgentDojo's source.

## What it does

Loads an AgentDojo `TaskSuite`, builds a `FunctionsRuntime` over its tools, and serves them as MCP tools over stdio. mlld imports them with `import tools from mcp "..."`. Each agentdojo tool becomes an MCP tool with the same name, JSON schema, and description that AgentDojo's pydantic signatures expose.

The mlld layer (typically `bench/domains/<suite>/tools.mld`) wraps each MCP call with `=> record @x` coercion, source-class labels, `controlArgs`, and `inputs:` metadata. That's where the security model is configured. This server's job is to expose tools cleanly so that wrapping is straightforward.

## Why no fork

The fork at `~/mlld/agentdojo` (branch `mlld-rig`) replaced AgentDojo's in-process LLM driver with an MCP server + runner. The MCP server was the load-bearing piece; everything else was either grading scaffolding (now in `src/agentdojo_runner.py`) or new attack/task additions.

This module replaces the fork's MCP server with a vanilla-compatible standalone. Same API surface to mlld, same per-tool MCP exposure, same arg coercion, same env serialization. AgentDojo updates land via `pip install agentdojo` instead of via merge.

## Files

| File | Purpose |
|---|---|
| `server.py` | MCP stdio server. Builds tools from `runtime.functions`, dispatches calls through `runtime.run_function`, saves env after non-read-only calls. |
| `coerce.py` | Narrow transport normalization: ISO-8601 datetime strings → AgentDojo's `"%Y-%m-%d %H:%M"` format. It does not repair model argument shape. |
| `format.py` | YAML output. Stringifies `datetime`/`date` (avoids mlld JS Date timezone shift). Flattens `shared_with` permission maps to email lists. `allow_unicode=True` (avoids c-c4a4 phantom-state class). |
| `state.py` | Env load/save against a JSON state file. Syncs runtime dicts back to `initial_*` lists for pydantic round-trip. Read-only-tool save skip with mutating-read-like exception list. |
| `__main__.py` | `python -m` entrypoint. Equivalent to `python server.py`. |
| `pyproject.toml` | Declares `agentdojo>=0.1.35` from PyPI, `mcp>=1.0.0`, `pyyaml`, `pydantic`. |

## Configuration

The server reads a JSON config from argv:

```
python server.py --config-file /path/to/config.json
python server.py <base64-encoded-json>
```

The base64 form is convenient for short configs; the file form is required when the config carries a serialized env (Linux's `MAX_ARG_STRLEN` caps a single argv element at 128KB).

### Two modes

**env_json mode** — caller builds the env, server validates and serves.

```json
{
  "suite_name": "banking",
  "benchmark_version": "v1.1.1",
  "env_type": "agentdojo.default_suites.v1.banking.task_suite.BankingEnvironment",
  "env_json": "<full-env-json>",
  "state_file": "/tmp/state.json",
  "log_file": "/tmp/calls.jsonl"
}
```

Use this when the caller (a runner / harness) constructs the env upfront — e.g. applying injections, normalizing fixtures, or restoring from a checkpoint.

**suite_name + task_id mode** — server resolves and loads.

```json
{
  "suite_name": "banking",
  "task_id": "user_task_3",
  "benchmark_version": "v1.1.1",
  "injections": { "injection_emergency_meeting": "<CANARY...>" },
  "state_file": "/tmp/state.json"
}
```

If `state_file` already exists and is non-empty, the server loads from it instead of building a fresh env. This lets a runner pre-seed the environment (e.g. with a partially-corrupted fixture for Tier 2 attacks) without going through `load_and_inject_default_environment`.

### Custom suite loader

```json
{
  "suite_loader": "mypkg.date_shift:get_shifted_suite",
  "suite_name": "banking",
  "...": "..."
}
```

`suite_loader` is `module:function`. The function must have the signature of `agentdojo.task_suite.get_suite`. Use this to swap in date-shifted suites or other host-side suite transformations.

### Optional integration files

| Field | What it does |
|---|---|
| `state_file` | Path the server writes env JSON to after non-read-only calls. Caller reads it for grading. |
| `log_file` | JSONL appended per call. One line per dispatch with timing, args, coercions, result preview, phase state, error flag. |
| `phase_state_file` | Path the server reads on each call to enrich log entries with the agent's current phase. Producer is the agent (rig writes it); consumer is the log. |

## Mlld integration

mlld imports the served tools with `import tools from mcp "..." as @mcp` and
then wraps each call with whatever record / label / metadata layer the
agent's design calls for. The MCP layer itself knows nothing about
records, labels, or trust — it just dispatches AgentDojo tools and
serializes env state.

How the wrapping layer is structured (records, source labels, tool
catalog shape) is a design choice for the `rig/` and `bench/` layers
above this bridge — see the top-level `fp/` README / design notes for
the current shape.

## What this module does NOT do

- **Attack instantiation.** Vanilla AgentDojo's `load_attack(name, suite, target_pipeline)` requires a `BasePipelineElement` — that contract is for AgentDojo's in-process LLM driver, which we don't have. Callers should construct injections themselves and pass them via the `injections` config field. Attack classes can be imported from agentdojo and run with a small pipeline-shaped shim if needed; that shim is a runner concern, not a server concern.
- **Grading.** `runtime.run_function` returns updates to env state; the caller reads `state_file` and runs `task.utility()` / `task.security()` against it. See `src/agentdojo_runner.py` for the runner.
- **Date shifting.** Pluggable via `suite_loader`. The shift logic itself stays in the host (e.g. `src/date_shift.py`).
- **`_normalize_post_environment_for_grading`.** That fixup lives wherever grading happens (the runner), since it's about how the post-env JSON should be interpreted, not how the server should serialize.
- **Domain-specific helper tools.** Anything that isn't a vanilla AgentDojo tool (e.g. `get_email_by_id`, `search_emails_any_sender`, `get_current_datetime`) belongs in a sibling MCP server composed alongside this one. Putting them here would make it suite-aware.

## Smoke test

```bash
# From bench/ (where agentdojo is installed)
echo '{"suite_name":"banking","task_id":"user_task_0","state_file":"/tmp/adm-state.json"}' \
  | base64 \
  | xargs uv run --project /Users/adam/mlld/fp/bench python3 \
      /Users/adam/mlld/fp/rig/agentdojo-mcp/server.py
```

The server starts on stdin/stdout and waits for MCP messages. The client side is mlld's `import tools from mcp ...`.
