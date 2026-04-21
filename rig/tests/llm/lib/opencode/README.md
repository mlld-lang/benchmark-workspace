# @mlld/opencode

Opencode CLI invocation with session resume, streaming, and MCP tool bridging.

## tldr

```mlld
import { @opencode } from @mlld/opencode

show @opencode("What is REST?")

var @review = @opencode("Review code in src/", {
  model: "anthropic/claude-sonnet-4-5",
  dir: @base,
  stream: true,
  bypass: true
})
```

## docs

### `@opencode(prompt, config)`

Runs `opencode run --format json` and returns the final agent message. Session id, text chunks, and token usage are parsed from opencode's NDJSON events in a single call regardless of streaming mode.

| Field | Type | Default | Purpose |
|---|---|---|---|
| `model` | string | `"openrouter/z-ai/glm-5.1"` | `provider/model` string (see `opencode models`). |
| `dir` | string | `@root` | Working directory, passed via `--dir`. |
| `system` | string | — | Prepended to the prompt. Opencode has no per-call system flag — agents carry their own prompts — so this is the only per-invocation hook. |
| `agent` | string | — | Opencode agent name (`--agent`). |
| `variant` | string | — | Reasoning variant: `minimal` \| `high` \| `max`. Maps to `--variant`. |
| `bypass` | boolean | — | Adds `--dangerously-skip-permissions`. Required whenever `tools` is set, and generally needed for any tool call in non-interactive runs. |
| `stream` | boolean | — | Stream chunks through `@opencodeStreamFormat`. The adapter also emits session id + token usage + cost metadata. |
| `sessionId` | string | — | Explicit conversation tracking id (`ses_...`). Case-sensitive. |
| `resume` | string | — | Explicit resume session id. Equivalent to `opencode run -s <id>`. |
| `tools` | array | — | Standard mlld `exe llm` tools convention. The runtime builds an MCP bridge at `@mx.llm.config`; this module translates it into opencode's `{ mcp: { name: { type: "local", command, environment } } }` config and exposes it via a shadow `XDG_CONFIG_HOME`. Opencode has no per-tool gating, so `@mx.llm.native` is informational only. |

```mlld
>> Simple call
var @answer = @opencode("Explain TCP/IP")

>> Anthropic via opencode
var @review = @opencode("Code review this PR", {
  model: "anthropic/claude-sonnet-4-5",
  dir: @base
})

>> High-reasoning variant
var @deep = @opencode("Trace this race condition", {
  model: "anthropic/claude-opus-4-5",
  variant: "high"
})

>> System prompt (prepended)
var @r = @opencode("What's your codename?", {
  system: "Your codename is Zephyr. Answer in one word."
})

>> Explicit resume
var @followup = @opencode("Keep going", { resume: "ses_28591e74fffey5oyFDw6nSuzpk" })

>> mlld tool bridging — requires bypass so tool calls aren't blocked on permissions
exe @getOrders() = js { return JSON.stringify([{ id: 1 }]); }

var @summary = @opencode("Call getOrders and summarise the results.", {
  tools: [@getOrders],
  bypass: true
})
```

### Session tracking and resume

`@opencode` returns a hidden `_mlld` envelope (`{ sessionId, provider: "opencode" }`) that the interpreter harvests. Two things fall out:

1. **Public API.** Pass `config.sessionId` to seed a known id, or `config.resume` to resume explicitly. Opencode session ids are case-sensitive (`ses_<base36>`) and preserved verbatim.
2. **Guard-driven resume.** When a guard retries, the runtime injects `config._mlld.resume = { sessionId, provider, continue }`. The module only honours it when `provider === "opencode"`, so a claude or codex session never leaks across providers.

### MCP bridge via shadow XDG_CONFIG_HOME

Opencode has no `--mcp-config` flag and no `-c key=val` config overrides on `run`, so per-invocation MCP injection uses the same shadow-dir trick as the codex module:

1. Translate mlld's generated `{ mcpServers: {...} }` JSON into opencode's `{ mcp: { name: { type: "local", command: [...], environment: {...} } } }` shape.
2. Create a temp dir and symlink every entry from `$XDG_CONFIG_HOME/opencode/` into `tmpdir/opencode/` **except** the config files (`config.json`, `opencode.json`, `opencode.jsonc`).
3. Merge the user's existing config + the generated `mcp` block into a single `tmpdir/opencode/opencode.json`.
4. The sh wrapper exports `XDG_CONFIG_HOME=<tmpdir>` for that invocation.

Opencode's data dir (`$XDG_DATA_HOME/opencode` — auth tokens, sessions, snapshots) is not rerouted, so auth and session history remain intact.

### `@opencodeStreamFormat`

NDJSON adapter for `opencode run --format json`. Use with `with { streamFormat: @opencodeStreamFormat }` in custom exe definitions.

Event types handled:
- `text` → `message` chunks (`part.text`)
- `step_start` → `metadata.sessionId`
- `step_finish` → `metadata.{inputTokens, outputTokens, totalTokens, cost}`

## Known limitations

- **No per-tool native gating.** Opencode exposes its built-in tools as-is. When `config.tools` is set, mlld bridges are added alongside them.
- **Shadow config dir leaks.** Each call with tools creates a temp `XDG_CONFIG_HOME/opencode/` symlink tree in `$TMPDIR`. They're tiny and `$TMPDIR` is periodically cleaned on macOS, but there's no explicit cleanup today.
- **Box VFS isolation is partial.** The runtime passes the mlld VFS bridge through, but opencode's native shell/edit tools still hit the real filesystem. Use claude if you need strict box isolation.

## License

CC0 - Public Domain
