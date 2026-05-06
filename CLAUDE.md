# clean/ project

Rig v2 framework + AgentDojo benchmark implementation for mlld.

## First Actions

```bash
mlld tests/index.mld --no-checkpoint              # zero-LLM invariant gate (must pass; ~10s)
mlld rig/tests/workers/run.mld --no-checkpoint    # live-LLM worker tests (~50s, ~$0.05)
tk ready                                           # active work items
```

For the test architecture, see `TESTS.md`. Three tiers live alongside each other: zero-LLM (`tests/index.mld`), scripted-LLM (`tests/run-scripted.py`), live-LLM (`rig/tests/workers/run.mld` for now; consolidation tracked in c-ed77).

## Structure

```
clean/
  rig/                    Framework (the reusable agent framework)
    ARCHITECTURE.md         Why it's structured this way
    SECURITY.md             10 numbered security invariants (load-bearing)
    PHASES.md               Implementation contract for single-planner session
    workers/planner.mld     Planner session + 6 tool wrappers
    session.mld             var session @planner schema
    runtime.mld             State helpers, display projection, tool dispatch
    intent.mld              Authorization intent compilation
    tooling.mld             Catalog helpers, policy synthesis
    prompts/planner.att     THE MAIN ITERATION TARGET for utility work
    tests/index.mld         Zero-LLM invariant gate (must pass 100%)
    tests/workers/          Live LLM worker tests (17 tests, ~50s)
  tests/                  mlld-native test framework (see tests/README.md)
    assert.mld             Assertion helpers (@assertOk, @assertEq, etc.)
    runner.mld             Suite/group construction + @runSuites
    lib/mock-llm.mld       Scripted-LLM test harness (re-exports rig/test-harness)
    suites/                Test suites (one topic per file)
  bench/                  Benchmark (consumes rig, suite-specific)
    ARCHITECTURE.md         How bench consumes rig
    agents/<suite>.mld      Agent entrypoints (~20 lines each)
    domains/<suite>/        Records, tools, bridge per suite
  STATUS.md               Current bench results + per-task classification (canonical state)
  archive/SCIENCE.md      Old experiment log (archived; do not write to)
  DEBUG.md                Investigation methodology
  archive/*.taskdata.txt  Per-suite tool/model/task reference (from AgentDojo, archived)
  *.threatmodel.txt       Per-suite attack trees and defense specs
  labels-policies-guards.md  Security model narrative (symlink to benchmarks/)
  src/                    Python host (minimal — run.py, host.py, mcp_server.py)
```

## Cardinal Rules

**A. No benchmark cheating.** Never read AgentDojo checker code. Never shape prompts or in-task reasoning around expected answers. Never add task-id-specific logic to *behavior* — prompts, error messages, decision rules, policy, intent compilation, dispatch.

**A.1. Per-task tool routing is allowed.** Tool-set selection is *configuration*, not capability under test. AgentDojo dumps every tool on the agent because it's testing tool-discovery noise tolerance — that's noise we don't measure. We measure whether the agent does the right work with the available tools. A `@taskTools[user_task_X] = ["hotel", "calendar"]` map populated from `taskdata.txt` ground truth is fine. The line is whether the per-task entry shapes *which capabilities exist*, not *what to do with them*.

**B. Separation of concerns.** Rig is generic. Bench is specific. Suite knowledge goes in tool `instructions:` or suite addendums — never in `rig/prompts/`.

**C. Don't blame the model.** GLM 5.1 outperforms Sonnet 4.6. Past architectures hit 80%+ on these suites. When utility is low, the problem is prompt education or framework bugs.

**D. SERIOUSLY. DON'T BLAME THE MODEL OR "NONDETERMINISM" OR "FLAKINESS"** Read the agent transcripts. No GUESSES as to WHY tests fail without EVIDENCE. 

## Current Focus

See STATUS.md for current results and per-task classification, and HANDOFF.md for session context. Use `/rig` at the start of each session to load all required context docs.

## Model Comparison (worker tests, 17 assertions, 2026-04-24)

| Model | Provider | Score | Wall Time | Avg/call | Harness | Notes |
|-------|----------|-------|-----------|----------|---------|-------|
| cerebras/gpt-oss-120b | Cerebras | 17/17 | 14s | ~0.9s | opencode | Fastest perfect score |
| claude-sonnet-4-6 | Anthropic | 17/17 | 24s | ~1.4s | claude | Perfect |
| togetherai/openai/gpt-oss-120b | Together AI | 17/17 | 29s | ~1.7s | opencode | Same model, slower provider |
| togetherai/zai-org/GLM-5.1 | Together AI | 17/17 | 32s | ~1.9s | opencode | Current default planner |
| claude-haiku-4-5-20251001 | Anthropic | 17/17 | 44s | ~2.6s | claude | Solid |
| togetherai/deepseek-ai/DeepSeek-R1 | Together AI | 17/17 | 132s | ~7.8s | opencode | Perfect but slow (thinking) |
| togetherai/MiniMaxAI/MiniMax-M2.7 | Together AI | 16/17 | 141s | ~8.3s | opencode | Good, slow |
| togetherai/moonshotai/Kimi-K2.6 | Together AI | 15/17 | 152s | ~9.0s | opencode | Good, slow |
| togetherai/Qwen/Qwen3-235B-A22B-Instruct-2507-tput | Together AI | 12/17 | 34s | ~2.0s | opencode | Weak on derive |
| togetherai/openai/gpt-oss-20b | Together AI | 1/17 | 16s | ~1.0s | opencode | Too small for workers |
| groq/openai/gpt-oss-120b | Groq | 1/17 | 14s | — | opencode | Empty responses (provider issue) |
| togetherai/google/gemma-4-31B-it | Together AI | — | — | ~75s | opencode | Errors: slow + markdown-fenced JSON |

**Recommended configs:**
- **Fast iteration**: `cerebras/gpt-oss-120b` for everything (~14s worker tests, ~65s/bench task). 1 flaky derive miss per run.
- **Quality baseline**: `togetherai/zai-org/GLM-5.1` — 17/17, proven as planner
- **Anthropic**: `claude-sonnet-4-6` — 17/17, 24s. Best quality + reasonable speed if using Anthropic API
- **Router only**: `togetherai/openai/gpt-oss-20b` (simple classification, speed matters)

## Prompt Placement Rules

Three layers of prompt content, each with a clear scope. When writing or reviewing a rule, ask: "Would this be true in a completely different domain?" If yes → rig prompt. If true for any task in this suite → suite addendum. If true for any caller of this tool → tool description/instructions.

### Layer 1: Rig prompt (`rig/prompts/planner.att`)

Framework discipline only. Phase rules, ref grammar, source class rules, terminal discipline, anti-looping, budget awareness. Must be domain-agnostic — no mention of calendars, contacts, emails, hotels, channels, or any suite-specific entity.

**Test:** Would removing this rule cause a wrong tool call shape, a wrong source class, or a protocol violation regardless of domain? If yes, it belongs here.

### Layer 2: Suite addendums (`bench/domains/<suite>/prompts/`)

Domain workflow patterns. How to reason about data in this specific domain — multi-step patterns, availability calculations, cross-record reasoning strategies, arithmetic conventions. Must be true for any task in that suite, not just one task.

Suite addendums are split per-worker. Each suite agent passes the addendum text its workers actually need:

- `plannerAddendum` — top-level workflow patterns the planner uses to pick phases and shape goals.
- `deriveAddendum` — arithmetic, ranking, selection conventions enforced inside the derive worker. Use when the rule must hold even if the planner forgets to restate it in `goal:`.
- `extractAddendum` — content-parsing conventions inside the extract worker (e.g. structured-field extraction patterns, verbatim-preservation rules).
- `composeAddendum` — output-rendering conventions inside the compose worker.

Each defaults to empty string. A suite opts in by exporting an addendum var (e.g. `@travelDeriveAddendum` from `bench/domains/travel/prompts/planner-addendum.mld`) and wiring it through the agent file (`bench/agents/<suite>.mld` calls `@rig.run({ ..., deriveAddendum: @travelDeriveAddendum })`).

The framework wires addendums via:
- `rig/orchestration.mld` — accepts the four addendum config fields
- `rig/workers/<worker>.mld` — reads `@agent.<worker>Addendum` and passes to its prompt
- `rig/prompts/<worker>.att` — interpolates `@suiteAddendum` at the same position in each worker template

**Test:** Would removing this rule cause wrong reasoning for a CLASS of tasks in this suite? If yes, it belongs here. If it only helps one task, it's overfitting. Use the smallest worker scope that catches the failure — a derive arithmetic rule belongs in `deriveAddendum`, not `plannerAddendum`, unless the planner needs to know it to construct the right `goal:`.

**Approval rule:** Every prompt change at this layer — tool descriptions/instructions, suite addendums (any worker), planner.att, worker prompt templates — needs explicit user approval before being written to a file. Show the proposed text, the rationale, and the test plan; do not edit until the user says go. Even small nudges like adding one sentence to a tool's `instructions:` field require approval. The reason: prompts are load-bearing and stochastic — a one-line tweak can shift behavior across many tasks in unpredictable ways. The user reviews to catch overfitting, eval-shaping, or other classes of error that aren't visible to the agent making the change.

### Layer 3: Tool descriptions and `instructions:` fields

Per-tool usage guidance in the tool catalog entry. Arg format constraints, scalar-vs-array clarification, when to prefer this tool over similar ones. Must be true for any caller of the tool.

**Test:** Would removing this cause a wrong call to THIS specific tool? If yes, it belongs here. If the guidance is about when to call the tool relative to other tools, it might belong in the suite addendum instead.

### What does NOT belong in any prompt layer

- Task-id-specific logic ("for task X, do Y")
- Evaluator-shaped rules ("the checker expects this exact wording")
- Model-specific workarounds ("GLM sometimes does X, so add Y")
- Redundant restatements of rules already in a higher layer
- Rules that only help one task — if a rule's entire justification is one benchmark result, it's overfitting

## Commands

```bash
# Invariant gate (must pass 100%)
mlld clean/rig/tests/index.mld --no-checkpoint

# Worker LLM tests (must pass 100%, ~50s)
mlld rig/tests/workers/run.mld --no-checkpoint

# Single task (local)
uv run --project bench python3 src/run.py -s workspace -d defended -t user_task_11

# Build mlld after runtime changes
cd ~/mlld/mlld && npm run build

# Tickets
tk ready          # what's actionable
tk ls             # all open
tk show <id>      # details
```

## Diagnosing failures with /diagnose

`/diagnose` (defined at `.claude/commands/diagnose.md`) fans out one Explore subagent per failing task to read its opencode transcript, apply the DEBUG.md A–E triage, and return a transcript-cited diagnosis. Use it after a sweep when you want a parallel read of every `utility=false` row instead of paging through transcripts by hand.

```
/diagnose <suite> [tasks=all] [source=latest|local|<run-id>] [model=sonnet]
```

Examples:

```
/diagnose slack all latest                       # all failing slack tasks in the most recent cloud run
/diagnose workspace user_task_8,user_task_32     # specific tasks, latest workspace run
/diagnose banking all 24922644697                # explicit run id
/diagnose travel all local                       # most recent local opencode session set
```

What it does:

1. Resolves `OPENCODE_HOME` + `defended.jsonl` for the chosen source (`latest` matches the newest `runs/*/manifest.json` whose `suite` field matches; `local` reads `~/.local/share/opencode` plus `bench/results/.../defended.jsonl`; bare run-id reads `runs/<id>/`).
2. Filters `utility=false` rows from the JSONL, scoped by the task list.
3. Dispatches all subagents in a single message (parallel, capped ~10/batch). Each subagent self-locates its session by sqlite substring match on a distinctive query phrase against `part.data` — opencode `session.title` is a model-summary, not the verbatim query, so title matching does NOT work.
4. Each subagent returns: triage class A–E, 100–200 word transcript-grounded verdict, 3–5 citations (`part:<id>` reasoning excerpts preferred over raw tool calls, `denial:<rule>`, `mcp[<n>]`), and a proposed next move.
5. Main agent collates per-task results, groups them into root-cause clusters, and surfaces existing `tk ls` ticket ids per task (read-only — does not file or modify tickets).

The subagent prompt enforces Cardinal Rules C/D (no model blame, no "flakiness"), the transcript-grounded discipline (unverified claims must be marked `UNVERIFIED`), and the prompt-approval rule (subagents do not propose task-id-shaped prompt edits or evaluator-shaped rules). Known infra traps are flagged: travel `Not connected` errors are c-63fe, not planning failures; "wrong date" suspicions check `_patch_<suite>_utilities` in `src/date_shift.py` before being attributed to model arithmetic.

Output is conversational. Decide what to ticket / fix / spike from the report; the command does not write to disk.

## Running benchmarks

Bench runs come in three shapes — match the shape to the question. See DEBUG.md "Spike First. Sweep Last." for the spike-vs-sweep guidance and "Troubleshooting parallel runs" for shape/OOM postmortems.

| Shape | When to use | Cost |
|---|---|---|
| **Spike / probe** (zero-LLM) | Asking what the runtime/dispatcher does given an input | $0, seconds |
| **Targeted sweep** (1 suite or task subset) | Iterating on a fix, verifying a class of failures resolved | minutes, dollars |
| **Full sweep** (all 4 suites) | Closeout regression check after a fix has stabilized — no other purpose | ~10-15 min, ~$3-5 |

The default during debugging is **targeted**, not full. Re-run only the suite/tasks the change affects until you have evidence it works. Reserve the full sweep for closeouts where you need confidence the change didn't regress unrelated suites.

Local CPU caps at ~10 parallel tasks; Namespace's Team plan (64 vCPU concurrent cap) handles full fan-out in ~10-15 min when you do need it.

### Quick start

```bash
git push                                  # image rebuilds on bench/, rig/, src/, agents/ paths

# Targeted (debugging)
scripts/bench.sh workspace                # one suite, full task set
scripts/bench.sh banking slack            # subset of suites
scripts/bench.sh --fast                   # all suites, grind tasks excluded (iteration cycle)
scripts/bench.sh --grind                  # ALL suites' grind tasks on ONE runner (multi-suite)
scripts/bench.sh --fast workspace         # subset filtering also works
gh workflow run bench-run.yml -f suite=workspace -f tasks="user_task_8 user_task_32"   # specific tasks

# Full (closeout / regression)
scripts/bench.sh                          # all 4 suites in parallel

gh run list --workflow=bench-run.yml --limit 8
uv run --project bench python3 src/fetch_run.py <run-id>     # → runs/<run-id>/
uv run --project bench python3 src/opencode_debug.py --home runs/<run-id>/opencode sessions
```

### What runs where

| Target | Shape | Parallelism | Tasks | Notes |
|---|---|---|---|---|
| `workspace` | 32x64 | -p 40 | 40 | Heaviest — needs 64 GB; ~30 GB peak at -p 34 fast |
| `travel` | 32x64 | -p 20 | 20 | Full parallelism; no fan-out throttle |
| `banking` | 16x32 | -p 16 | 16 | Light |
| `slack` | 32x64 | -p 21 | 21 | Light |
| (no args) | per-target | per-target | all 4 above | Dispatched concurrently |

Parallelism defaults to `task_counts.<suite>` from `bench/grind-tasks.json` — the same source-of-truth file that drives `--fast` / `--grind` carve-outs. Update the JSON if AgentDojo's task count changes.

### One-off / targeted runs

For specific tasks during debug iteration, trigger `bench-run.yml` directly:

```bash
gh workflow run bench-run.yml -f suite=workspace -f tasks=user_task_8
gh workflow run bench-run.yml -f suite=workspace -f tasks="user_task_8 user_task_32"
gh workflow run bench-run.yml -f suite=banking -f tasks=user_task_2 -f trace=true
```

Inputs: `suite`, `tasks`, `planner`, `worker`, `harness`, `parallelism`, `stagger`, `defense`, `trace`, `image_tag`, `shape`.

### Where to run travel

`scripts/bench.sh travel` dispatches travel at 32x64 + -p 20. The historic c-63fe fan-out throttle (-p 5) and `MLLD_HEAP=8g` overrides have been removed — the throttle inflated travel wall to ~1000s without buying anything, and the heap ceiling was a workaround for memory growth that should be fixed at the source. If MCP "Not connected" cascades reappear at full parallelism, file a fresh ticket rather than reinstating the throttle.

### Image freshness

The bench image is composed of three pieces, two of which are pre-built into separate images and `COPY --from`'d into the final bench image:

- **`ghcr.io/mlld-lang/mlld-prebuilt:2.1.0`** — built by `.github/workflows/mlld-prebuild.yml`. Self-skip: re-running with no upstream change is a ~30s no-op. Re-run when mlld@2.1.0 ref moves: `gh workflow run mlld-prebuild.yml`.
- **`ghcr.io/mlld-lang/opencode-prebuilt:dev`** — built by `.github/workflows/opencode-prebuild.yml`. Manual dispatch only. Re-run when adamavenir/opencode#dev changes: `gh workflow run opencode-prebuild.yml`.
- **`ghcr.io/mlld-lang/benchmark-workspace:main`** — bench-image.yml builds this on every push to bench/, rig/, src/, agents/, bench/docker/. Pulls the two prebuilt images, adds bench code + uv venv, pushes. ~1-2 min wall (was ~9 min before the prebuild split).

bench-run.yml inspects each pulled bench image's `mlld.sha` and `clean.sha` Docker labels:

- Compares baked `mlld.sha` against `mlld-lang/mlld:<baked-ref>` HEAD via the GitHub API.
- Compares baked `clean.sha` against the dispatched `github.sha` (clean@main at dispatch time).

If either is stale, bench-run joins an in-flight `bench-image.yml` build whose `head_sha` matches clean@HEAD (or dispatches a new one), waits, repulls, and verifies the post-rebuild image's `clean.sha` matches before continuing. Adds ~1-2 min after a clean push, zero overhead otherwise. (The mlld layer is already prebuilt; bench-image only rebuilds the bench code + venv layers.)

This means: **dispatching `scripts/bench.sh` immediately after a clean push is safe** — bench-run will block until the matching bench-image build completes. You don't need to manually wait for `bench-image.yml`.

**Don't push between dispatch and build completion.** If you dispatch `scripts/bench.sh` at SHA A, then push SHA B before bench-image's build for A finishes, the in-flight build now targets B's SHA and the post-rebuild check at A will mismatch and fail (we hit this 2026-05-05). Either: push everything first then dispatch, or wait for the in-flight build to land before pushing again. The freshness check is a safety mechanism, not a smoothing layer over rapid pushes.

Edge case: if you dispatch `bench-run.yml` while a bench-image build for an *earlier* clean SHA is queued/in-progress (and no build has been triggered yet for the latest push), bench-run won't find a matching in-flight build for clean@HEAD and will dispatch a new one. The post-rebuild verification catches the unlikely case where we still end up with a mismatched `clean.sha` and aborts with an actionable error message.

Recommended discipline for clean/ changes:

1. **Run local canaries first.** `uv run --project bench python3 src/run.py -s <suite> -d defended -t <task_ids> -p <n>` exercises the *committed-or-uncommitted* working tree directly via the local mlld SDK. No image, no wait, no SHA confusion. Pick the specific tasks the change targets — minutes to confirm the fix shape before spending sweep cost.
2. **Push, then dispatch directly.** `scripts/bench.sh <suite>` — bench-run handles freshness automatically. Verify the fetched manifest's `image_sha` matches HEAD afterward as a sanity check (the post-rebuild step inside bench-run already does this for clean.sha, but the manifest cross-check is good practice).
3. **For docs-only commits, use `[skip ci]`** in the commit message so bench-image doesn't rebuild for changes that don't affect runtime. (`paths` in bench-image.yml does some of this; `[skip ci]` is the explicit override.)

### Reading remote results

`src/fetch_run.py <run-id>` unpacks artifacts to `runs/<run-id>/`:

```
runs/<run-id>/
  manifest.json        # suite, defense, planner, worker, elapsed, exit_code, image_sha, mlld_ref
  console.log          # stdout from src/run.py inside the container
  results/             # bench/results/<model>/<suite>/defended.jsonl
  exec_logs/           # bench/.llm — per-task execution logs
  opencode/            # full opencode session data (storage/, log/, opencode.db)
```

Existing transcript debugging works against fetched runs via `opencode_debug.py --home runs/<run-id>/opencode`.

Cross-suite jq summary across a fan-out:

```bash
for d in runs/24920*/; do
  jq -r '"\(.suite)\t\(.elapsed_sec)s\texit=\(.exit_code)"' "$d/manifest.json"
  jq -c 'select(.utility == false) | .task_id' "$d"/results/bench/results/*/*/defended.jsonl 2>/dev/null
done
```

### Discipline

- **Spike before sweep, target before full.** A $0 probe answers runtime/contract questions; a single-suite or single-task sweep verifies a fix. Full sweeps are for closeouts, not iteration. (DEBUG.md "Spike First. Sweep Last.")
- **Push to main, then sweep.** Artifacts under `runs/<id>/` are the canonical record of "this commit produced these numbers."
- **Cite run IDs in STATUS.md "Sweep history".** `runs/<id>/` becomes the artifact for re-fetching transcripts later.
- **Run multiples in parallel when you do go full.** Concurrent Namespace runners cost the same wall-clock as one — fan out for "did this change affect other suites?" closeouts.

## Rules learned the hard way

- **Never use `show` in exe functions during bench runs.** It writes to stdout and corrupts the host's JSON parsing. Use `log` (stderr) or `MLLD_TRACE` instead.
- **Never rename record fields to match MCP parameter names.** The intent compiler maps arg keys to resolved values — the names don't need to match. Field renaming across the MCP boundary destroys StructuredValue metadata.
- **Run worker tests before and after prompt changes.** `mlld rig/tests/workers/run.mld --no-checkpoint` catches regressions in ~50s. If tests pass too easily, the assertions are too weak.
- **Per-task memory ≈ 0.9 GB on workspace at full parallelism (measured 2026-05-05).** Workspace at -p 34 on 32x64 hit 30.3 GB peak / 62.9 GB available (48% utilization, plenty of headroom). Earlier "1.5-2 GB per task" estimates predated the recent mlld memory reduction. Workspace and travel still want 32x64 for headroom; banking and slack are fine on 16x32. `scripts/bench.sh` sets the shape per suite. Memory peaks land in `manifest.json` (`mem_peak_kb` / `mem_total_kb`) per `bench/docker/entrypoint.sh`'s sampler.

## Status, Categories, and Ticket Conventions

`STATUS.md` is the canonical record of current bench results and per-task classification. Read it before reasoning about what's failing, why, and what's worth working on.

### Five categories (per STATUS.md)

| Category | Definition | Has ticket? |
|---|---|---|
| **PASS** | Passes >80% of the time across recent sweeps | No |
| **FLAKY** | Passes <80% of the time. **Only the user marks tasks FLAKY.** | Yes — current theory + work-toward-stabilization |
| **SHOULD-FAIL** | Deterministic security model correctly rejects; 0% pass is the right outcome | No |
| **BAD-EVAL** | Failing because the eval is wrong (asks for one valid reading and demands the other; ignores qualifiers; substring-mismatches semantically correct output). **Only the user marks tasks BAD-EVAL.** | No |
| **OPEN** | Not yet decidedly in any of the above. Anything actively being investigated, anything stochastic that hasn't been promoted, anything the user hasn't reviewed | Yes — current theory + investigation path |

We do NOT keep tickets open for PASS, SHOULD-FAIL, or BAD-EVAL items. STATUS.md is the record. Tickets exist only for OPEN and FLAKY items where there's still investigation or fix work pending.

Promotion in/out of FLAKY and BAD-EVAL is a user-only decision. The agent can move tasks into OPEN with a transcript-grounded theory, can move tasks into PASS when sweep evidence supports >80%, and can move tasks into SHOULD-FAIL when the security-model rejection is documented. The agent does NOT classify into FLAKY or BAD-EVAL on its own — surface the evidence and propose the promotion in conversation.

All 97 AgentDojo tasks count toward the denominator regardless of category. The categories describe what's failing and why; they don't reduce what's measured.

### Ticket conventions for OPEN and FLAKY items

**A. Every OPEN or FLAKY task has an open ticket carrying the current theory.** No silent failures. If a task is failing on the latest sweep and isn't classified PASS / SHOULD-FAIL / BAD-EVAL, there's a `[SUITE-UT<N>]`-titled ticket whose body is the current best theory (transcript-grounded per rule D). If the root cause isn't known yet, the theory is "needs investigation" — file the ticket anyway, don't wait. Multiple tasks failing for the same root cause may share a cluster ticket so long as each task id appears in the title.

**A.1. Actionable fixes get their own tickets, linked to the failure tickets they would close.** A failure ticket is "this test is failing and here's why we think so." A fix ticket is "do X to address it." When the theory points at a concrete change — a prompt addendum, a rig primitive, a runtime fix — file a separate fix ticket with the action in the title and `tk link` it to the failing-test ticket(s) it would resolve. This keeps the work surface (`tk ready`) populated with do-able tasks while preserving the per-task failure record. When a fix lands, the fix ticket closes; the failure ticket only closes when the test verifies green or moves to PASS / SHOULD-FAIL / BAD-EVAL in STATUS.md.

**B. UT-tied tickets carry the task id in the title.** Format: `[SUITE-UT<N>...] short description`. Example: `[BK-UT10] send_money recipient resolved to id field` or `[WS-UT32, WS-UT37] create_file → share_file chaining returns no result handles`. Cluster tickets list all affected ids in the title. Makes `tk ls` greppable by suite/task and makes cross-references visible.

**C. Tickets get updated with transcript analysis on every new sweep.** When a sweep completes and a tracked task either changes status or produces new failure-mode info, add a timestamped note (`tk add-note <id> "..."`) with the run id and the relevant transcript-grounded findings. Don't let tickets drift away from the current behavior. If a fix lands and verifies, note the verifying run id and close. If it lands and doesn't verify, note what changed in the failure shape. If a task moves into PASS / SHOULD-FAIL / BAD-EVAL, close the ticket and reflect the move in STATUS.md.

**D. Diagnoses must be transcript-grounded, not call-sequence guesses.** A failure ticket's "root cause" claim must be backed by reading the planner's actual reasoning — `sqlite3 runs/<id>/opencode/opencode.db "SELECT ... FROM part WHERE session_id=..."` showing the model's stated decisions between tool calls. MCP call sequences + final outputs are insufficient: they show *what* the agent did, not *why* it did it. Single transcript reads have changed diagnoses ~half the time in this project — a planner who looks like it "took the wrong workflow" from MCP calls often shows in the transcript that it tried the right thing first and the framework rejected it. If you don't have a transcript citation in the ticket, the diagnosis is a hypothesis, not a finding. Mark unverified hypotheses explicitly ("UNVERIFIED — call-sequence guess pending transcript pull").

**E. Always report utility against full benchmark denominators.** The canonical numbers are pass-count over the *full* AgentDojo task count (workspace=40, banking=16, slack=21, travel=20 = 97 total). Categories are descriptive (what's failing and why), not prescriptive (what to skip). Don't goalpost-shift to "in-scope" denominators — the comparison number against CaMeL or our own prior sweeps is always against 97.

These conventions mean: every failing task that isn't decisively PASS / SHOULD-FAIL / BAD-EVAL traces to a specific OPEN or FLAKY ticket; every actionable fix has its own ticket linked to the failures it closes; every ticket is current; ticket history is the audit log of what we know about each task; no ticket carries a guess as if it were a finding; and progress numbers stay honest against the full benchmark.

## Deferred: Logging Refactor (ticket c-3edc)

A designed but unstarted refactor of rig's logging stack to lean on the runtime trace subsystem (`--trace effects` via SDK) plus `var session @planner` plus a small curated hook layer. Net effect: `lifecycle.mld` + `runtime.mld @appendLlmCall` + per-wrapper boilerplate shrink; rig gets parent/child LLM-call timing for free; the m-5683 / UT14 bug classes disappear structurally.

Not scheduled. Raise it when any of the following bite: chasing per-worker timing bottlenecks by hand, another lifecycle emission seam getting added manually, shelf-based session state producing an aliasing/null-callback regression, or the bench analyzer wanting a structured call tree. Full plan lives in ticket c-3edc.

## Key Docs

Use `/rig` at session start to load these with instructions to read them all. See `.claude/skills/rig.md` for the full onboarding sequence.

1. `labels-policies-guards.md` — security model narrative
2. `rig/ARCHITECTURE.md` — framework architecture and separation of concerns
3. `bench/ARCHITECTURE.md` — how bench consumes rig
4. `DEBUG.md` — investigation methodology
5. `STATUS.md` — current bench results, per-task classification (canonical state)
6. `HANDOFF.md` — session-to-session context and next steps
