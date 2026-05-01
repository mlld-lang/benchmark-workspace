# clean/ project

Rig v2 framework + AgentDojo benchmark implementation for mlld.

## First Actions

```bash
mlld clean/rig/tests/index.mld --no-checkpoint   # invariant gate (must pass 100%)
mlld rig/tests/workers/run.mld --no-checkpoint   # worker LLM tests (must pass 100%)
tk ready                                          # active work items
```

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
  bench/                  Benchmark (consumes rig, suite-specific)
    ARCHITECTURE.md         How bench consumes rig
    agents/<suite>.mld      Agent entrypoints (~20 lines each)
    domains/<suite>/        Records, tools, bridge per suite
  SCIENCE.md              Working experiment log — task tables, patterns, theories
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

See SCIENCE.md for current results and HANDOFF.md for session context. Use `/rig` at the start of each session to load all required context docs.

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
scripts/bench.sh workspace                # one suite
scripts/bench.sh banking slack            # subset
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
| `workspace` | 32x64 | -p 40 (caps at 36) | 36 active (UT13/19/25/31 oos) | Heaviest — needs 64 GB |
| `travel` (with workspace) | 16x32 | -p 5 | 20 | Throttled: shared 64 vCPU cap + c-63fe |
| `travel` (solo, no workspace) | 32x64 | -p 20 | 20 | Auto-bumped when workspace not in dispatch |
| `banking` | 8x16 | -p 40 (caps at 15) | 15 active (UT0 oos) | Light |
| `slack` | 8x16 | -p 40 (caps at 14) | 14 active (oos UT2/11/16-20) | Light |
| (no args) | per-target | per-target | all 4 above | Peak 64 vCPU — exact Team-plan fit |

### One-off / targeted runs

For specific tasks during debug iteration, trigger `bench-run.yml` directly:

```bash
gh workflow run bench-run.yml -f suite=workspace -f tasks=user_task_8
gh workflow run bench-run.yml -f suite=workspace -f tasks="user_task_8 user_task_32"
gh workflow run bench-run.yml -f suite=banking -f tasks=user_task_2 -f trace=true
```

Inputs: `suite`, `tasks`, `planner`, `worker`, `harness`, `parallelism`, `stagger`, `defense`, `trace`, `image_tag`, `shape`, `heap`.

### Where to run travel

c-63fe: travel's mlld Node process pushes ~5 GB heap, and without an explicit cap the default Node heap limit hits before the container OOMs — surfacing as MCP "Not connected" cascades. We mitigate via `MLLD_HEAP=8g`, which `scripts/bench.sh` already passes for travel dispatches. Two reasonable patterns:

**Travel solo → run on Namespace (default, recommended).**

```bash
scripts/bench.sh travel
# 32x64 + -p 20 + MLLD_HEAP=8g (set automatically). No competition with other suites for the vCPU cap.
```

**Full sweep including travel → split: travel local, others remote.**

When you fan out the full bench surface, travel on the Namespace runner shares the 64 vCPU concurrency cap with workspace and gets throttled to `16x32 + -p 5`. Running travel locally instead gives it the whole machine plus an even bigger heap and avoids the c-63fe failure mode entirely:

```bash
# Terminal 1 — remote: the three other suites in parallel
scripts/bench.sh workspace banking slack

# Terminal 2 — local: travel at full parallelism, ample heap
MLLD_HEAP=12g uv run --project bench python3 src/run.py -s travel -d defended -p 20
```

A 48 GB Mac handles `-p 20` with `MLLD_HEAP=12g` cleanly. Smaller machines: drop to `-p 10` and `MLLD_HEAP=8g`.

If you don't need workspace in the run, prefer pure remote (`scripts/bench.sh travel banking slack`) — simpler, results all land in `runs/<id>/` via `fetch_run.py`.

### Image freshness

The image bakes mlld@2.1.0 + clean@main + agentdojo@mlld-rig. bench-run.yml inspects each pulled image's `mlld.sha` AND `clean.sha` Docker labels:

- Compares baked `mlld.sha` against `mlld-lang/mlld:<baked-ref>` HEAD via the GitHub API.
- Compares baked `clean.sha` against the dispatched `github.sha` (clean@main at dispatch time).

If either is stale, bench-run joins an in-flight `bench-image.yml` build whose `head_sha` matches clean@HEAD (or dispatches a new one), waits, repulls, and verifies the post-rebuild image's `clean.sha` matches before continuing. Adds ~3-4 min after a clean or mlld push, zero overhead otherwise.

This means: **dispatching `scripts/bench.sh` immediately after a clean push is safe** — bench-run will block until the matching bench-image build completes. You don't need to manually wait for `bench-image.yml`.

Edge case: if you dispatch `bench-run.yml` while a bench-image build for an *earlier* clean SHA is queued/in-progress (and no build has been triggered yet for the latest push), bench-run won't find a matching in-flight build for clean@HEAD and will dispatch a new one. The post-rebuild verification catches the unlikely case where we still end up with a mismatched `clean.sha` and aborts with an actionable error message.

Recommended discipline for clean/ changes:

1. **Run local canaries first.** `uv run --project bench python3 src/run.py -s <suite> -d defended -t <task_ids> -p <n>` exercises the *committed-or-uncommitted* working tree directly via the local mlld SDK. No image, no wait, no SHA confusion. Pick the specific tasks the change targets — minutes to confirm the fix shape before spending sweep cost.
2. **Push, then dispatch directly.** `scripts/bench.sh <suite>` — bench-run handles freshness automatically. Verify the fetched manifest's `image_sha` matches HEAD afterward as a sanity check (the post-rebuild step inside bench-run already does this for clean.sha, but the manifest cross-check is good practice).

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
- **Cite run IDs in SCIENCE.md.** `runs/<id>/` becomes the artifact for re-fetching transcripts later.
- **Run multiples in parallel when you do go full.** Concurrent Namespace runners cost the same wall-clock as one — fan out for "did this change affect other suites?" closeouts.

## Rules learned the hard way

- **Never use `show` in exe functions during bench runs.** It writes to stdout and corrupts the host's JSON parsing. Use `log` (stderr) or `MLLD_TRACE` instead.
- **Never rename record fields to match MCP parameter names.** The intent compiler maps arg keys to resolved values — the names don't need to match. Field renaming across the MCP boundary destroys StructuredValue metadata.
- **Run worker tests before and after prompt changes.** `mlld rig/tests/workers/run.mld --no-checkpoint` catches regressions in ~50s. If tests pass too easily, the assertions are too weak.
- **Workspace and travel remote runs need bigger shapes.** Workspace (36 parallel tasks) needs 32x64 (64 GB). Travel (20 parallel tasks) needs 16x32 (32 GB). Both OOM on 8x16 (exit 137). Banking and slack survive 8x16. `scripts/bench.sh` already sets the right shape per target; if you call `bench-run.yml` directly, pass `-f shape=nscloud-ubuntu-22.04-amd64-32x64` for workspace or `-f shape=nscloud-ubuntu-22.04-amd64-16x32` for travel.

## Ticket Conventions

Three rules for benchmark-failure tickets:

**A. Every failing in-scope test has an open ticket carrying the current theory.** No silent failures. If a task is failing on the latest sweep and isn't out-of-scope, there's a `[SUITE-UT<N>]`-titled ticket for it whose body is the current best theory of why it's failing (transcript-grounded per rule D). If the root cause isn't known yet, the theory is "needs investigation" — file the ticket anyway, don't wait. Multiple tasks failing for the same root cause may share a cluster ticket so long as each task id appears in the title.

**A.1. Actionable fixes get their own tickets, linked to the failure tickets they would close.** A failure ticket is "this test is failing and here's why we think so." A fix ticket is "do X to address it." When the theory points at a concrete change — a prompt addendum, a rig primitive, a runtime fix, an OOS classification — file a separate fix ticket with the action in the title (e.g. `Add compose-precision rule for decimal renderings`) and `tk link` it to the failing-test ticket(s) it would resolve. This keeps the work surface (`tk ready`) populated with do-able tasks while preserving the per-task failure record. When a fix lands, the fix ticket closes; the failure ticket only closes when the test verifies green.

**B. UT-tied tickets carry the task id in the title.** Format: `[SUITE-UT<N>...] short description`. Example: `[BK-UT10] send_money recipient resolved to id field` or `[WS-UT32, WS-UT37] create_file → share_file chaining returns no result handles`. Cluster tickets list all affected ids in the title. Makes `tk ls` greppable by suite/task and makes cross-references visible.

**C. Tickets get updated with transcript analysis on every new sweep.** When a sweep completes and a tracked task either changes status or produces new failure-mode info, add a timestamped note (`tk add-note <id> "..."`) with the run id and the relevant transcript-grounded findings. Don't let tickets drift away from the current behavior. If a fix lands and verifies, note the verifying run id and close. If it lands and doesn't verify, note what changed in the failure shape.

**D. Diagnoses must be transcript-grounded, not call-sequence guesses.** A failure ticket's "root cause" claim must be backed by reading the planner's actual reasoning — `sqlite3 runs/<id>/opencode/opencode.db "SELECT ... FROM part WHERE session_id=..."` showing the model's stated decisions between tool calls. MCP call sequences + final outputs are insufficient: they show *what* the agent did, not *why* it did it. Single transcript reads have changed diagnoses ~half the time in this project — a planner who looks like it "took the wrong workflow" from MCP calls often shows in the transcript that it tried the right thing first and the framework rejected it. If you don't have a transcript citation in the ticket, the diagnosis is a hypothesis, not a finding. Mark unverified hypotheses explicitly ("UNVERIFIED — call-sequence guess pending transcript pull").

**E. Always report utility against full benchmark denominators.** The canonical numbers are pass-count over the *full* AgentDojo task count (workspace=40, banking=16, slack=21, travel=20 = 97 total). The OOS skip list is a workflow convenience for not re-adjudicating items during local iteration; it does NOT reduce the denominator for any number that gets compared with prior runs, other architectures, or progress baselines. Reporting "12/12 in-scope" when the actual measurement is 12/16 is goalpost movement — it makes session-over-session comparison meaningless and obscures the structural ceiling that OOS tasks impose. Always cite both: `12/16 (75%) — 3 OOS skipped, see tag:oos tickets`. The ceiling discussion belongs in a separate "what's structurally cappable" framing, not in the running utility number.

These rules together mean: every utility=false row in any sweep traces to a specific failure ticket, every actionable fix has its own ticket linked to the failures it closes, every ticket is current, ticket history is the audit log of what we know about each task, no ticket carries a guess as if it were a finding, and progress numbers stay honest against the full benchmark.

## Test prioritization buckets

**No benchmark task is "out of scope".** All 97 AgentDojo tasks are in-scope for the benchmark. The "OOS-*" prefixes below are *internal prioritization buckets* — they describe how we're choosing to spend our attention right now, not what the benchmark is measuring. Every entry counts as a failure against the 97-task denominator regardless of bucket. We use these buckets to keep the work surface focused without losing track of what we're walking past.

Each per-task ticket carries one of these prefixes in its title:

**OPEN: {SUITE}-{ID} - {reason it's open}** — actively investigating; clear path to a fix; not blocked. Lives in `tk ready`. Failing-test tickets stay OPEN until the test verifies green.

**REVIEW: {SUITE}-{ID} - {what needs review}** — needs human decision before next move. Different from CANDIDATE in that REVIEW means "we haven't decided which bucket this belongs in yet." Used sparingly.

**OOS-DEFERRED: {SUITE}-{ID}** — we know how to fix; an architectural primitive is on the roadmap; we're saving the work until other things are complete. Current examples: `summarize_url` primitive (c-1d65 — bounded-worker URL summarization with mechanical source attribution; depends on `no-untrusted-or-unknown-urls-in-output` rule from mlld-dev tracked at c-2923; closes IT1-class ASR on slack UT1/3/4/6/15 and workspace summarize-and-send tasks without utility regression); typed-instruction-channel (c-6479 — only WS-UT25 remains in scope after UT13/UT19 reclassified SHOULD-FAIL; reframed as "typed-grounding-extract" per the simplified deterministic-only design). The fix path is named, the work is sequenced; just not now.

**OOS-EXHAUSTED: {SUITE}-{ID}** — we've tried; further attempts would be benchmark-shaping or overfitting. Examples: eval requires literal `'{k}-th'` substitution where models naturally produce `'1st/2nd/3rd/4th'` (SL-UT14); eval requires `pre_env == post_env` while task wording asks to update (BK-UT9/UT10); linguistic ambiguity where eval picks one valid reading and three sweeps converge on the other (TR-UT11). EXHAUSTED is a documented loss, not a recategorization — it acknowledges that prioritizing a fix would violate Cardinal Rule A.

**OOS-CANDIDATE: {SUITE}-{ID}** — we believe it should be EXHAUSTED but want explicit evidence first. Often stochastic tasks (sweep FAIL, retest PASS) where one more sweep cycle would settle whether the failure mode is structural or noise. CANDIDATE entries are typically NOT in `SKIP_TASKS` so they keep showing up in sweeps and produce evidence.

**SHOULD-FAIL: {SUITE}-{ID}** — the deterministic-security model **correctly rejects** this task. The task delegates action choice (or other security-critical decisions) to untrusted content in a way that no structural invariant can safely permit. Solving it would require **probabilistic / audit-based security** (action-type allowlists, payload schemas, profile authorization, content sanitizers) that we explicitly exclude from the benchmark agent. SHOULD-FAIL is a positive statement about the security model: 0% utility on these tasks is the correct outcome. Future production deployments can opt into probabilistic-security extensions to pass them; the benchmark cannot. See `futr-action-type-allowlist.md` for the canonical example. SHOULD-FAIL entries belong in `SKIP_TASKS` for workflow convenience but count as full failures against the 97 denominator like every other bucket.

**CLOSED: {SUITE}-{ID}** — currently passing.

### Discipline

- Every failing in-scope test belongs in exactly one bucket. EXHAUSTED is reserved for cases where you can show evidence of the eval design or LLM behavior making any fix overfitting.
- Promotion from CANDIDATE → EXHAUSTED requires a transcript-grounded note saying *what* was tried and *why* further attempts would be overfitting.
- Demotion from OPEN → CANDIDATE requires a note saying *what's been tried*.
- Demotion from CANDIDATE → DEFERRED requires identifying the specific architectural primitive that would fix the family, and the named ticket where that primitive is tracked.
- DEFERRED tickets reference the architectural primitive on which they depend. When the primitive lands, the DEFERRED tickets get reopened for verification.
- `SKIP_TASKS` in `src/run.py` is the workflow-convenience skip list. EXHAUSTED and DEFERRED entries are typically there. CANDIDATE entries usually stay visible in sweeps.

These buckets do not change reporting (Convention E still holds — always cite full denominators). They only change what we work on next.

## Deferred: Logging Refactor (ticket c-3edc)

A designed but unstarted refactor of rig's logging stack to lean on the runtime trace subsystem (`--trace effects` via SDK) plus `var session @planner` plus a small curated hook layer. Net effect: `lifecycle.mld` + `runtime.mld @appendLlmCall` + per-wrapper boilerplate shrink; rig gets parent/child LLM-call timing for free; the m-5683 / UT14 bug classes disappear structurally.

Not scheduled. Raise it when any of the following bite: chasing per-worker timing bottlenecks by hand, another lifecycle emission seam getting added manually, shelf-based session state producing an aliasing/null-callback regression, or the bench analyzer wanting a structured call tree. Full plan lives in ticket c-3edc.

## Key Docs

Use `/rig` at session start to load these with instructions to read them all. See `.claude/skills/rig.md` for the full onboarding sequence.

1. `labels-policies-guards.md` — security model narrative
2. `rig/ARCHITECTURE.md` — framework architecture and separation of concerns
3. `bench/ARCHITECTURE.md` — how bench consumes rig
4. `DEBUG.md` — investigation methodology
5. `SCIENCE.md` — experiment log, task tables, failure analysis
6. `HANDOFF.md` — session-to-session context and next steps
