---
id: c-5af8
status: open
deps: []
links: []
created: 2026-05-02T21:01:27Z
type: bug
priority: 2
assignee: Adam
tags: [perf, cloud, bench, oom, agentdojo-mcp, migration]
---
# Cloud bench OOM regression after agentdojo-mcp migration (UNVERIFIED)

Bench-run cloud sweeps after the agentdojo-mcp migration (commits bd4665a → be2c8d0)
OOM-killed (exit 137) on three of three completed suites: workspace, banking,
slack. Travel was still in_progress at investigation time; expected to OOM
similarly. All three failed within ~2 minutes of starting the benign sweep,
before any task completed (banking got 1/16 done; workspace 0/40 done).

Local 8-parallel banking on the same code completed cleanly (12/16 PASS,
parent RSS peak 146 MB). So the OOM is not a code regression that affects
small loads — it's specific to cloud-shape memory limits at full parallelism.

Cloud runs:
  - workspace 40-parallel on 32x64 (64 GB) → OOM at ~3 min  (run 25261078977)
  - banking   16-parallel on 8x16  (16 GB) → OOM at ~2 min  (run 25261079445)
  - slack     14-parallel on 8x16  (16 GB) → OOM at ~2 min  (run 25261079982)

CLAUDE.md previously documented these shapes as "fine" for the same
parallelism. Something in the migration shifted per-task memory enough
to push them over.

## Architectural change in scope

The migration replaced the bench-side runtime path in three layered changes:

1. **MCP server** (commit bd4665a + 000cf64). clean/src/mcp_server.py was a
   single 553-LOC file that also imported the agentdojo fork via sys.path.
   The new path uses clean/rig/agentdojo-mcp/server.py (vanilla agentdojo
   from PyPI). It loads:
     - server.py
     - coerce.py
     - format.py
     - state.py
     - extensions.py
   plus, for every suite (after migration), it imports clean/src/bench_mcp_extras.py
   which itself imports date_shift + format. Where the legacy server inlined
   the workspace helpers (get_email_by_id, search_emails_any_sender,
   get_current_datetime), the new path always loads bench_mcp_extras even
   when the suite has no email tools (the helpers gate on env shape; the
   module still imports).

2. **Vendored runner** (commit 8eb9ea9). agentdojo.runner / .results /
   .grading / .judge / .ground_truth / .agents.base moved from the fork
   into clean/src/agentdojo_*.py. Same code, byte-for-byte; only the import
   path changed. agentdojo.attacks / .task_suite / .functions_runtime /
   .base_tasks now resolve to vanilla PyPI 0.1.35 instead of the fork.

3. **Default flip** (commit be2c8d0). All suites now route through the
   new MCP server by default (was previously opt-in via AGENTDOJO_MCP_NEW).

## Theories (UNVERIFIED — investigate per Cardinal Rule D)

### Theory 1: per-MCP-process memory increased under the new server
Each task spawns its own MCP server subprocess. If each new-server process
uses more RAM than each legacy-server process, 16 banking tasks × delta
exceeds the 16 GB shape. Plausible mechanisms:

- Extension loading (load_extensions → import bench_mcp_extras → import
  date_shift) imports the entire date_shift module (heavy regex
  pre-compilation, ~700 LOC including utility-checker patches). The legacy
  server already imported date_shift at top-level — same module weight in
  principle, but module identity differs (legacy imported once at parent;
  new server imports per subprocess).
- Vanilla agentdojo's pydantic models may differ from fork's in ways that
  affect env-state memory (Banking/Workspace/Slack/Travel envs). The fork
  removed agent_pipeline/* but did not modify env classes, so this should
  be a wash; not yet checked empirically.
- New server's state.save_env runs sync_runtime_state on every non-readonly
  call, same as legacy. No structural change there.

### Theory 2: parent process (run.py) memory grew due to vendored imports
run.py now imports agentdojo_runner which imports agentdojo_grading,
agentdojo_results, agentdojo_judge, agentdojo_ground_truth — all live in
clean/src/. Previously these came from the fork via sys.path. Local peak
RSS for parent was 146 MB at 8-parallel; would need a 16-parallel run to
stress-test. Unlikely to be the dominant factor.

### Theory 3: import-cost amplification under uv-run-per-task
Each MCP server is spawned via 'uv run --project bench python3 server.py'.
uv re-resolves the project's dependency tree on each invocation. With 16
suites × 2 (uv shim + python child) = 32 processes at import time
simultaneously. The new server's import graph is larger (5 sibling modules
vs the legacy's single file). Import-time memory and CPU spikes could
trigger an OOM peak even when steady-state is fine.

### Theory 4: 16 vs 15 active banking tasks
CLAUDE.md scripts/bench.sh comment says "banking 15 parallel on 8x16 → fine".
Banking has 16 tasks. After migration we may run 16 active where before
something filtered to 15. Need to verify by reading run.py's task selection
logic and comparing pre/post migration parallel counts. If we're spawning
exactly 1 more task than before, that ~6.7% extra memory pressure could
explain the edge OOM.

### Theory 5: vanilla AgentDojo PyPI 0.1.35 envs are larger than fork's
The fork (~/mlld/agentdojo, mlld-rig branch) was based on PyPI 0.1.35 with
additions but not env-class modifications I checked. To rule out: dump
post-init env JSON size for one banking task under fork vs vanilla.

## Mitigations available without diagnosis

- Bump banking shape: nscloud-ubuntu-22.04-amd64-8x16 → 16x32. CLAUDE.md
  already does this for travel/workspace; banking stayed at 8x16 because
  it was historically the smallest-RAM suite.
- Reduce parallelism: -p 14 instead of -p 16 (drops one task, restoring
  the historical 'fine' margin).
- Bump slack shape similarly: 8x16 → 16x32, or drop -p to 13.

Either gets us green sweeps without root-causing the regression. Worth
filing the root-cause investigation separately so we don't lose the
question.

## How to verify (proposed sequence)

1. Run banking on cloud with AGENTDOJO_MCP_LEGACY=all set in the docker run
   command (requires bench-run.yml input + container env passthrough). If
   that passes at 16-parallel on 8x16, the regression is in the new MCP
   server, not the vendored runner.
2. Run banking on cloud with new MCP server but at -p 14. If that passes,
   the regression is at-the-margin and can be backed out by either bumping
   shape or shaving parallelism.
3. Compare per-task peak RSS locally between legacy and new server paths.
   ps -o rss for each child python process; track max over a single banking
   task. Report delta.
4. If delta is real and significant, profile the new server's startup with
   tracemalloc — confirm whether bench_mcp_extras imports are the source.

## What this ticket is NOT

This is not a regression in correctness: 8/8 UT0 verdicts matched between
legacy and new paths in local validation, and local 8-parallel banking
produces the expected utility numbers (12/16 PASS).

## Affected runs (preserve as evidence)

- 25261078977 workspace — runs/25261078977/
- 25261079445 banking   — runs/25261079445/
- 25261079982 slack     — (not yet fetched)
- 25261080471 travel    — in progress at filing time


## Notes

**2026-05-02T21:29:06Z** 2026-05-02 investigation: local A/B measured MCP server startup/idle RSS with identical env configs and found no new-server growth: banking 166.6MB legacy vs 165.5MB new; slack 166.1MB vs 165.4MB; workspace 168.4MB vs 167.9MB; travel 167.8MB vs 167.8MB. Full host-path stub runs point instead at concurrent mlld worker RSS. Banking -p16 --stagger 2 peaked 20.5GB new vs 17.8GB legacy; top processes were mlld workers, not Python MCP servers. Dropping banking to -p14 without a heap cap still peaked 19.8GB, so parallelism alone is not enough. MLLD_HEAP is effective: banking -p16 --stagger 2 new peaked 14.0GB with 2g and 10.4GB with 1536m; slack -p14 new peaked 20.7GB uncapped, 17.2GB with 2g, 12.7GB with 1536m; workspace -p40 with 1536m stayed under 29.3GB before the 180s sampler timeout. Implemented scripts/bench.sh mitigation to pass heap=1536m for workspace/banking/slack benign dispatches, leaving travel's 8g override unchanged. Interpretation: agentdojo-mcp made a marginal cloud shape tip over under real staggered worker overlap, but the actionable resource owner is V8/mlld worker headroom rather than the Python MCP server.

**2026-05-03T15:01:56Z** 2026-05-03 cloud follow-up: all-suite cloud rerun showed the 1536m heap cap was only a partial mitigation, not the right sizing model. workspace, banking, travel exited 0, but workspace still had MCP-error tasks (UT26/UT27/UT35/UT15) and banking UT12 had MCP errors. Slack ran full 21-way parallelism on the 8x16 shape and OOMed with exit 137 at 156s before any task completed. Since historical MCP errors have consistently correlated with OOM/memory pressure, revised scripts/bench.sh away from heap-capping workspace/banking/slack as the primary lever: workspace now runs on 32x64 at -p20, banking on 16x32 at -p16, slack on 32x64 at -p21. Travel keeps its existing 8g heap override and shape behavior because its long tasks can exceed the default V8 ceiling independently of runner-level OOM.

**2026-05-03T15:38:08Z** 2026-05-03 corrected investigation: reran the comparison against the true prior implementation (~/mlld/agentdojo fork) instead of only clean's legacy/new server toggle. In fresh worktrees, with stub planner/worker and --stagger 2 to isolate process-tree memory, the old fork vs current agentdojo-mcp delta is modest: banking -p16 peaked ~8.6GB old vs ~9.4GB current; slack -p21 peaked ~10.5GB old vs ~11.1GB current. MCP server idle RSS is effectively unchanged (~166-168MB per suite), and static banking/slack env JSON + tool schema payload sizes are identical between fork and vanilla AgentDojo. So the migration appears to have reduced memory margin, but it does not explain the 18-20GB local peaks or cloud OOMs by itself.

Found a meaningful mlld-side amplifier while reproducing: AuditLogIndex bulk-read <project>/.llm/sec/audit.jsonl to recover write labels. The main checkout had accumulated multi-GB audit logs (bench/.llm/sec/audit.jsonl ~3.0GB, .llm/sec/audit.jsonl ~1.0GB), so each parallel mlld worker could allocate huge memory before doing real work. Patched mlld to append write events to a compact .llm/sec/audit-writes.jsonl sidecar, prefer that for descriptor recovery, and cap historical full-audit fallback reads at 16MB (MLLD_AUDIT_INDEX_MAX_BYTES override). After patch, contaminated main banking -p16 dropped from ~17.9-20.5GB to ~9.44GB; contaminated main slack -p21 exits 0 at ~12.90GB. Focused AuditLogger/AuditLogIndex vitest tests and npm run build passed.

Interpretation: heap-capping was masking pressure, not fixing root cause. The old-vs-new AgentDojo architecture likely costs ~0.5-0.8GB at suite fanout in stub runs; the large observed jump came from mlld's audit index behavior plus dirty/shared state growth. Cloud real-LLM runs can still exceed local stub peaks, so scripts/bench.sh remains revised toward larger shapes/lower competing fanout rather than relying on a 1536m heap cap.
