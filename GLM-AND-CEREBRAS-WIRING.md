# Wiring GLM 5.1 (OpenRouter) and gpt-oss-120b (Cerebras) into the bench

A standalone walkthrough of every layer the two models travel through, from the
command line that dispatches a bench run to the HTTP call that actually hits
the provider. The bench supports a *planner* model and a *worker* model
independently; the most common production configuration is
`togetherai/zai-org/GLM-5.1` for the planner and `cerebras/gpt-oss-120b` for
the workers, but every position in the stack works the same way for
`openrouter/@preset/glm-5-1`.

## 1. Two model slots, one dispatch

Every bench task runs through a single agent that internally splits its LLM
work between two roles:

- **Planner** — the long-lived outer session that selects phases, decides
  which tool to call, and drives the loop.
- **Worker** — the short-lived inner sessions invoked per phase
  (extract / derive / compose / advice / blocked). Each worker call is a
  fresh provider request with its own prompt and tool surface.

The CLI exposes three knobs:

```
--model <id>     # sets both planner and worker
--planner <id>   # overrides planner only
--worker <id>    # overrides worker only
--harness <name> # forces 'opencode' or 'claude' (auto-detected if omitted)
```

Defaults: planner `togetherai/zai-org/GLM-5.1`, worker `cerebras/gpt-oss-120b`.
The Python launcher resolves these into two separate values, then passes both
into the mlld payload as `model` (planner) and `worker_model` (worker). The
harness override, if present, becomes `harness` on the payload.

When run in CI, the orchestrating shell layer maps four environment variables
to the CLI flags: `PLANNER → --planner`, `WORKER → --worker`,
`HARNESS → --harness`, `TASKS → --task ...`. The workflow propagates four
provider secrets into the container — `OPENROUTER_API_KEY`,
`CEREBRAS_API_KEY`, `TOGETHER_API_KEY`, `FIREWORKS_API_KEY` — so any of the
matching prefixes resolves without further configuration.

## 2. Harness auto-selection

mlld's runtime exposes a tiny dispatcher: given a model string and an optional
harness override, pick which LLM bridge to invoke. The auto-detector inspects
the model string's prefix:

| Prefix | Harness |
| --- | --- |
| `stub` | built-in deterministic stub |
| `openrouter/` | opencode |
| `togetherai/` | opencode |
| `cerebras/` | opencode |
| `groq/` | opencode |
| `fireworks-ai/` | opencode |
| anything else | claude |

So `togetherai/zai-org/GLM-5.1`, `openrouter/@preset/glm-5-1`, and
`cerebras/gpt-oss-120b` all auto-route to the opencode harness; bare Anthropic
model ids like `claude-sonnet-4-6` go to the claude harness. The explicit
`--harness` flag (and matching env var) overrides this if needed — useful for
forcing one harness while iterating, or for the deterministic `stub` harness
used in zero-LLM tests.

The dispatcher runs *per call*, not once per session. The planner role
computes the harness from the planner model on its own LLM calls; each worker
role computes the harness from the worker model on its own. That's why you
can run a GLM-5.1 planner on opencode while the workers run on the same
harness against `cerebras/gpt-oss-120b` — both happen to be opencode-routed,
but they're independent decisions. Mixing claude (planner) + opencode
(worker) is fully supported with the same mechanism.

## 3. The opencode harness call shape

The opencode harness is a thin mlld wrapper around the `opencode` CLI. For
every LLM call it builds an `opencode run` invocation:

```
opencode run --format json --dir <workdir> -m <model> --agent <name> \
    [--variant <v>] [--dangerously-skip-permissions] [-s <resume-id>] \
    "<prompt>"
```

Key inputs:

- **`-m` model** comes straight from the caller — `openrouter/@preset/glm-5-1`,
  `togetherai/zai-org/GLM-5.1`, or `cerebras/gpt-oss-120b`. OpenCode parses
  the `provider/model` shape itself; the bench never inspects it.
- **`--format json`** is always set. OpenCode emits NDJSON: one JSON object
  per stdout line for each event (text chunk, reasoning, tool use, step
  start, step finish). The harness parses these into a stream-format adapter
  that yields normalized text / thinking / tool-use / metadata events back
  into mlld's streaming pipeline.
- **`--agent`** binds an invocation-local agent name (default `mlld`) so the
  per-call permission rules in the inline config below take effect. There is
  no global agent installed — every call ships its own.
- **`-s` resume id** is set only when the caller wants to continue a previous
  opencode session. The planner role uses this to maintain a long-lived
  conversation; worker roles call without it.

### Provider config: `opencode.json` plus inline overrides

OpenCode reads provider configuration from a small `opencode.json` at the
working-dir root. The bench's checked-in file declares two providers:

- An **`openrouter`** provider with a named model
  `@preset/glm-5-1` whose display name is "GLM 5.1 (OpenRouter preset)". The
  `@preset/` prefix is OpenRouter's mechanism: the actual underlying model
  string and provider routing are configured in the user's OpenRouter
  dashboard preset, and we just reference it by slug.
- A **`fireworks-ai`** provider with model
  `accounts/fireworks/models/glm-5p1`, configured with
  `response_format: { type: "json_object" }` in `extraBody` so Fireworks
  returns strict JSON when the planner asks for it.

Cerebras requires no entry here — opencode discovers Cerebras as a built-in
provider via its standard model registry and authenticates against the
`CEREBRAS_API_KEY` environment variable. Same story for Together
(`TOGETHER_API_KEY`) — the `togetherai/<org>/<model>` model id resolves
without a dedicated `opencode.json` entry.

Per-call configuration (MCP tool registration, permission rules, MCP
timeouts) is **not** written to `opencode.json`. Instead the harness builds
an inline JSON document on every call and sets `OPENCODE_CONFIG_CONTENT` in
the subprocess env. OpenCode merges this content over its file-based config
for the lifetime of that one invocation. The inline doc includes:

- `mcp` — translated from mlld's runtime MCP catalog into opencode's local
  MCP server shape (`type: 'local'`, `command: [...]`, `environment: {...}`,
  `enabled: true`).
- `agent.<name>.permission` — `{'*': 'deny', 'allowed_tool': 'allow', ...}`
  built from the runtime's `@mx.llm.allowed` CSV so the model can only call
  the tools the planner has authorized for this phase.
- `agent.<name>.tools` — the same allow/deny set in opencode's tool-toggle
  format.
- `experimental.mcp_timeout` — optional override (otherwise opencode's
  default applies).

So a single GLM-5.1 planner call ends up as: `opencode run --format json
--dir /workspace/clean -m openrouter/@preset/glm-5-1 --agent mlld
"<prompt>"`, with `OPENCODE_CONFIG_CONTENT` carrying the MCP servers and
per-call permission table, plus the four provider API keys in the inherited
environment.

### XDG isolation for nested sessions

The bench runs opencode at two nesting levels in a single task: an outer
planner session and one or more inner worker sessions. To prevent these
from sharing storage and cross-contaminating each other's session
databases, the harness can override `XDG_DATA_HOME` and `XDG_STATE_HOME`
per call via two passthrough parameters (`dataHome` and `stateHome` on the
shell wrapper). Worker calls get their own data home so the inner
opencode.db doesn't get mixed into the planner's session archive.

### Stream-format adapter

OpenCode's NDJSON differs slightly from Anthropic's streaming shape — most
notably, opencode fuses the `tool_use` request and its result into a single
event emitted when the tool finishes. The harness ships a stream-format
adapter that normalizes this into mlld's internal event types:

- `text` event → `message` kind with `chunk` = `part.text`
- `reasoning` event → `thinking` kind with `text` = `part.text`
- `tool_use` event → `tool-use` kind extracting name, call id, input,
  result, and status from `part.tool` / `part.callID` / `part.state.*`
- `step_start` → `metadata` carrying `sessionID`
- `step_finish` → `metadata` carrying token counts, reasoning tokens, cost,
  and finish reason

This adapter is what lets the rig framework treat opencode-backed calls
identically to claude-backed calls for purposes of logging, lifecycle
events, and prompt-builder accounting.

## 4. Per-role wiring at the worker layer

Each worker role (`extract`, `derive`, `compose`, `advice`) sets up its LLM
call the same way:

```
@llmCall(harness, prompt, { model: @agent.workerModel ?? @agent.model, ... })
```

The `workerModel ?? model` fallback means: if the agent was launched with a
distinct worker model, use it; otherwise fall back to the planner model. So
the default config (`--planner togetherai/zai-org/GLM-5.1
--worker cerebras/gpt-oss-120b`) makes every worker call hit Cerebras while
the outer planner call hits Together's GLM-5.1 endpoint — and a single-model
config (`--model openrouter/@preset/glm-5-1`) routes both through
OpenRouter's GLM-5.1 preset.

The agent struct that carries these values is built once at session start
from the orchestration config:

- `model: <planner model>`
- `workerModel: <worker model or null>`
- `harness: <explicit harness or @defaultHarness(model)>`

Every subsequent call re-reads these fields, so there's no hidden state — the
selected models stay stable for the entire bench task.

## 5. End-to-end example: a single bench task

Putting it together, a planner-on-OpenRouter / worker-on-Cerebras run looks
like this:

1. CI dispatches the bench workflow with
   `PLANNER=openrouter/@preset/glm-5-1`, `WORKER=cerebras/gpt-oss-120b`,
   and the four provider keys.
2. The container entrypoint maps these to
   `--planner openrouter/@preset/glm-5-1 --worker cerebras/gpt-oss-120b`
   on the launcher CLI.
3. The Python agent class builds a payload with
   `model = "openrouter/@preset/glm-5-1"` and
   `worker_model = "cerebras/gpt-oss-120b"`, then invokes the mlld bench
   agent for the task.
4. mlld's orchestration constructs the per-task agent struct with both
   model fields and computes `harness = @defaultHarness("openrouter/...")`,
   which returns `"opencode"`.
5. The planner role makes its first LLM call. The runtime dispatcher routes
   it to the opencode bridge with `model = "openrouter/@preset/glm-5-1"`.
6. The opencode bridge builds the inline config (MCP servers, permission
   table for the phase's allowed tools), sets `OPENCODE_CONFIG_CONTENT`,
   and execs `opencode run --format json --dir . -m
   openrouter/@preset/glm-5-1 --agent mlld "<prompt>"`. OpenCode
   authenticates to OpenRouter using `OPENROUTER_API_KEY` and resolves the
   `@preset/glm-5-1` slug against the user's OpenRouter preset config,
   which selects the underlying provider for GLM-5.1.
7. NDJSON events stream back; the adapter converts them into mlld text /
   tool-use / metadata events. The planner consumes them, picks the next
   phase, and emits a worker dispatch.
8. The worker role's call goes through the same dispatcher, but with
   `model = "cerebras/gpt-oss-120b"` and a fresh per-call inline config
   carrying that worker's allowed tools. Opencode shells out the same way,
   authenticates to Cerebras via `CEREBRAS_API_KEY`, and streams back.
9. Steps 5–8 repeat across phases until the planner emits a terminal
   decision. The harness/model selection is recomputed on every call but
   stays stable because the agent struct doesn't change.

## 6. Verifying a provider before a real sweep

The fastest sanity check is to run the worker LLM tests against a candidate
configuration:

```
PLANNER=openrouter/@preset/glm-5-1 mlld tests/live/workers/run.mld --no-checkpoint
```

This exercises every worker role with a real provider call but no bench
harness around it. ~50s round-trip. If those 17 worker assertions all pass,
the provider auth, the opencode CLI shape, the stream-format adapter, and
the per-call inline config are all working — a real bench dispatch with the
same `PLANNER` value will reach the model. Cerebras can be verified the
same way with `WORKER=cerebras/gpt-oss-120b`.

## 7. Summary table

| Layer | What it does for GLM-5.1 / gpt-oss-120b |
| --- | --- |
| CI workflow | Reads workflow inputs `planner` / `worker`, passes the four provider secrets into the container environment |
| Container entrypoint | Maps `PLANNER` / `WORKER` env vars to `--planner` / `--worker` CLI flags |
| Python launcher | Splits one or both flags into `model` (planner) and `worker_model` payload fields |
| mlld orchestration | Builds the agent struct: `model`, `workerModel`, and `harness = @defaultHarness(model)` |
| Harness dispatcher | Prefix-matches the model string to opencode (for openrouter / togetherai / cerebras / groq / fireworks-ai) or falls back to claude |
| Opencode bridge | Builds per-call inline config (MCP + permission rules), sets `OPENCODE_CONFIG_CONTENT`, execs `opencode run --format json -m <model> --agent mlld` |
| `opencode.json` | Declares the OpenRouter `@preset/glm-5-1` model entry; Cerebras / Together resolve via built-in provider discovery |
| API keys | `OPENROUTER_API_KEY`, `CEREBRAS_API_KEY`, `TOGETHER_API_KEY`, `FIREWORKS_API_KEY` inherited from the workflow secrets |
| Stream adapter | Normalizes opencode's NDJSON events into mlld's internal text / thinking / tool-use / metadata kinds |
| Worker fallback | Each worker role picks `workerModel ?? model`, so single-model and split-model configs both work without code changes |
