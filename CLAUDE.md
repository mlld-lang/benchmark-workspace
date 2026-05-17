# fp — agent benchmark workspace

This repo is a clean scaffold for redesigning the **rig** agent framework
on top of mlld, with AgentDojo as the evaluation benchmark.

The plumbing is in place. The architecture is intentionally not.

## Layout

```
fp/
  setup                      # symlinks .mlld-sdk and runs uv sync
  .env.example               # MLLD_SDK_PATH
  mlld-config.json           # resolvers, trusted domains
  rig/
    agentdojo-mcp/           # canonical MCP server over vanilla agentdojo (from PyPI)
  src/                       # Python host
    run.py                   # CLI entrypoint
    host.py                  # MlldAgent — invokes mlld, reads back env state
    agentdojo_runner.py      # suite loader / env setup / grading orchestration
    agentdojo_{agents_base,grading,judge,ground_truth,results}.py
    bench_mcp_extras.py      # domain helper tools (get_email_by_id, etc.)
    date_shift.py            # AgentDojo date-shifted suites
    fetch_run.py / remote.py / opencode_debug.py
  bench/
    pyproject.toml           # uv project; agentdojo>=0.1.35, mcp, mlld-sdk
    docker/                  # remote-run images
    agents/                  # (empty — to be designed)
    domains/                 # (empty — to be designed)
    tests/                   # (empty)
  tests/
    runner.mld               # @suite, @group, @runSuites
    assert.mld               # @assertOk, @assertEq, deep-eq helpers
    _template.mld            # copy this for a new suite
    index.mld                # top-level entrypoint; imports all suites
    lib/                     # (empty)
  scripts/
    bench.sh                 # GH workflow dispatch — full / fast / grind
    bench-attacks.sh         # attack-sweep dispatch matrix
  .github/workflows/         # bench-image, bench-run, mlld-prebuild, opencode-prebuild
```

## What's deliberately absent

- No `rig/*.mld` design files. The framework is being rebuilt from first
  principles against current mlld primitives.
- No bench domain implementations (`bench/agents/`, `bench/domains/`).
  These attach the redesigned rig to AgentDojo suites; they come after
  the framework shape stabilizes.
- No test suites against the old rig.
- No `bench/grind-tasks.json` yet — `scripts/bench.sh` needs it before
  it can be invoked.

## Running things

```bash
./setup                              # one-time: symlink mlld SDK, uv sync
mlld tests/index.mld --no-checkpoint # run the test framework against the template suite
```

The Python host runs once there's a bench agent entrypoint to call. See
`src/run.py --help`.

## Design notes

- `rig/agentdojo-mcp/` is infrastructure: it serves vanilla AgentDojo
  tools over MCP. It knows nothing about records, labels, or trust —
  those concerns belong to whatever wrapping layer the redesigned rig
  defines.
- `src/` is mostly suite/grading machinery from AgentDojo's Python world.
  The `host.py` ↔ mlld contract (how Python invokes a per-suite mlld
  agent and reads back env state) is the seam you'll want to look at
  when the rig redesign defines its entrypoint shape.
- `mlld-security-fundamentals.md` (at repo root) is the current mlld
  security model reference. Read this before making framework design
  decisions.
- `sec-{banking,slack,travel,workspace,cross-domain}.md` are per-suite
  threat-model writeups for the AgentDojo domains. They describe the
  attack surface each suite presents, independent of any particular rig
  shape — useful when designing how the framework should defend each
  domain.
