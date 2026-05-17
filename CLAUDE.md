# fp-proof benchmark workspace

`fp-proof` is the current defended AgentDojo proof agent for mlld. The rig is intentionally small: records, policy, projections, and guards carry the security model; the planner chooses structured actions.

Read these first:

- `AGENTS.md` for timeless orientation.
- `ARCHITECTURE.md` for the implemented architecture.
- `DEBUG.md` for transcript-first diagnosis.
- `STATUS.md` for task status and evidence rules.
- `HARDENING.md` for clean-derived hardening.
- `mlld-agentdojo-guide.md` for the rebuild/development process.

## Cardinal rules

**No benchmark cheating.** Do not read AgentDojo checker bodies. Do not add task-id-specific behavior. Do not shape prompts around expected answers.

**Rig stays generic.** `rig/` must not know AgentDojo suites, task ids, fixture names, or expected outputs. Suite contracts live in `bench/`.

**Prompts are not defenses.** Prompts may explain how to use the interface. Security must come from records, projections, policy, guards, role/write gates, and deterministic wrapper checks.

**Read transcripts before diagnosing.** Final JSONL rows and MCP calls are symptoms. The OpenCode transcript is the definitive source for why the agent failed or stopped.

**SHOULD-FAIL must fail structurally.** A failure only counts if the route is blocked by a named primitive: fact/kind proof, exact-known check, projection, policy, guard, write-role denial, correlation, or missing provenance primitive.

## Layout

```text
fp-proof/
  rig/                    Generic structured-action defended runtime.
  bench/agents/           Suite entrypoints and minor suite notes.
  bench/domains/          Suite records, tools, policies, bridge config.
  llm/                    Provider wrappers.
  src/                    AgentDojo host, runner, grading, cloud fetch/debug helpers.
  tests/                  LLM-free proof suites and disabled-defense canaries.
  scripts/                Cloud benign and attack dispatch helpers.
  .github/workflows/      bench-image, bench-run, mlld/opencode prebuilds, runner probe.
```

## Local commands

```bash
# Static validation
mlld validate rig bench/agents bench/domains tests

# Full deterministic proof gate
mlld tests/index.mld --no-checkpoint

# Single local benign task
PYTHONPATH=src uv run --project bench python3 src/run.py \
  -s workspace -t user_task_11 -p 1 -d defended --harness opencode --debug

# Local attack slice
PYTHONPATH=src uv run --project bench python3 src/run.py \
  -s slack -t user_task_0 --attack direct -p 1 -d defended --harness opencode --debug
```

Run proof tests before live sweeps. Use live runs to verify model/tool behavior, not to discover basic data-flow or security questions.

## Cloud workflow wiring

Workflows are in `.github/workflows/` and are active on the `proof` branch:

- `bench-image.yml` builds `ghcr.io/mlld-lang/benchmark-workspace:proof`.
- `bench-run.yml` runs one benign or attack suite dispatch.
- `mlld-prebuild.yml` refreshes the mlld runtime prebuilt image.
- `opencode-prebuild.yml` refreshes the opencode prebuilt image.
- `runner-probe.yml` verifies Namespace runner labels.

Local dispatch scripts support `BENCH_REF=proof` and optional `BENCH_IMAGE_TAG`.

```bash
# Benign cloud sweep, batched to respect provider limits
BENCH_REF=proof scripts/bench.sh

# One suite or sub-suite
BENCH_REF=proof scripts/bench.sh slack
BENCH_REF=proof scripts/bench.sh workspace-a

# Attack cycles, batched two jobs at a time
BENCH_REF=proof scripts/bench-attacks.sh cycle1
BENCH_REF=proof scripts/bench-attacks.sh cycle2
BENCH_REF=proof scripts/bench-attacks.sh cycle3
```

Cloud run helpers:

```bash
gh run list --workflow=bench-run.yml --limit 20
uv run --project bench python3 src/fetch_run.py <run-id>
python3 src/opencode_debug.py --home runs/<run-id>/opencode sessions
python3 src/opencode_debug.py --home runs/<run-id>/opencode parts --session <session> --limit 300
```

`bench-run.yml` checks image freshness against the dispatched branch SHA and mlld prebuilt SHA, rebuilds when stale, and uploads artifacts for `fetch_run.py`.

## Status semantics

- `PASS`: actual AgentDojo task passed in this repo.
- `PASS*`: deterministic proof triple exists, but no benchmark pass claim.
- `OPEN`: expected secure utility route without benchmark pass.
- `FLAKY`: expected utility route but unstable.
- `*-FAIL`: missing provenance primitive; must fail at the intended security boundary.

Do not promote statuses without evidence. Attack suite results are regression signals, not the primary proof of security.
