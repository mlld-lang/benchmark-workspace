#!/usr/bin/env bash
# Dispatch one or more bench-run.yml workflow_dispatch invocations on
# Namespace.
#
# Usage:
#   scripts/bench.sh                          # all 4 suites in parallel
#   scripts/bench.sh workspace                # just workspace
#   scripts/bench.sh banking slack            # subset
#
# Each invocation triggers a separate Namespace runner. Current shapes
# favor memory headroom over the old exact-64-vCPU packing because MCP
# disconnects in these runs have historically tracked runner memory pressure.
#
# Every benign run executes all user_tasks in the suite (full 97-task
# denominator). No skip list — SHOULD-FAIL and OOS-EXHAUSTED tasks
# stay in scope; they count as failures and their attack-resilience
# is what the security evaluation tests.

set -euo pipefail

WORKFLOW=bench-run.yml

# Per-target shape and parallelism. Each task carries the AgentDojo
# TaskEnvironment + an mlld + MCP process in RAM (~1.5-2 GB at peak).
# Empirical results:
#   - workspace 36 parallel on 8x16  → OOM (run 24922643802/4218)
#   - travel    20 parallel on 8x16  → OOM (run 24922900959)
#   - travel    20 parallel on 16x32 → OOM (run 24923046920)
#   - banking   15 parallel on 8x16  → historically fine, but full 16-task
#     cloud runs later showed MCP errors at the margin.
#   - slack     14 parallel on 8x16  → historically fine (run 24922900581);
#     full 21-task cloud runs OOM after the agentdojo-mcp switch.
#
# Travel mode switching:
#   - Fan-out (workspace in the dispatch set): 16x32 + -p 5. Throttled
#     to keep travel's high-memory tasks from competing with the larger
#     workspace/banking/slack runners.
#   - Solo (workspace absent): 32x64 + -p 20 (full parallelism). 64 GB
#     fits all 20 tasks; c-63fe MCP errors are still possible but the
#     memory headroom mitigates the OOM-driven part of the failure mode.
SHAPE_WORKSPACE=nscloud-ubuntu-22.04-amd64-32x64
SHAPE_TRAVEL_FANOUT=nscloud-ubuntu-22.04-amd64-16x32
SHAPE_TRAVEL_SOLO=nscloud-ubuntu-22.04-amd64-32x64
SHAPE_MEDIUM=nscloud-ubuntu-22.04-amd64-16x32
SHAPE_LARGE=nscloud-ubuntu-22.04-amd64-32x64

dispatch() {
  local label=$1; shift
  printf '→ %-14s ' "$label"
  if gh workflow run "$WORKFLOW" "$@" >/dev/null 2>&1; then
    printf 'dispatched\n'
  else
    printf 'FAILED\n' >&2
    return 1
  fi
}

run_target() {
  case "$1" in
    workspace|w) dispatch workspace -f suite=workspace -f shape="$SHAPE_WORKSPACE" -f parallelism=20 ;;
    banking|b)   dispatch banking   -f suite=banking   -f shape="$SHAPE_MEDIUM" -f parallelism=16 ;;
    slack|s)     dispatch slack     -f suite=slack     -f shape="$SHAPE_LARGE" -f parallelism=21 ;;
    travel|t)
      # c-63fe: MCP server destabilizes under travel's tool load. Fan-out
      # mode throttles to -p 5 (16x32 shape) so travel's high-memory tasks
      # don't compete with the other suites. Solo travel takes 32x64 with
      # -p 20 — 64 GB has the memory headroom even if MCP errors are still
      # expected on some tasks until c-63fe lands.
      #
      # MLLD_HEAP=8g: the local repro showed the mlld Node process
      # spiking to ~5 GB heap during travel; without an explicit limit
      # the default Node heap cap can OOM the process before the
      # container itself OOMs. 8g gives headroom and avoids the
      # spurious MCP-disconnect failure mode while we keep digging
      # into the underlying travel memory growth.
      if "$WORKSPACE_PLANNED"; then
        dispatch travel -f suite=travel -f shape="$SHAPE_TRAVEL_FANOUT" -f parallelism=5  -f heap=8g
      else
        dispatch travel -f suite=travel -f shape="$SHAPE_TRAVEL_SOLO"   -f parallelism=20 -f heap=8g
      fi
      ;;
    *) echo "unknown target: $1" >&2
       echo "valid: workspace banking slack travel" >&2
       exit 1 ;;
  esac
}

if [ $# -eq 0 ]; then
  set -- workspace banking slack travel
fi

# Detect whether workspace is in the planned dispatch set — if it is,
# travel must defer to the conservative shape so the four jobs collectively
# stay under the vCPU concurrency cap.
WORKSPACE_PLANNED=false
for t in "$@"; do
  case "$t" in workspace|w) WORKSPACE_PLANNED=true ;; esac
done

for arg in "$@"; do
  run_target "$arg"
done

echo
echo "Watch:    gh run list --workflow=bench-run.yml --limit 8"
echo "Fetch:    uv run --project bench python3 src/fetch_run.py <run-id>"
echo "Browse:   uv run --project bench python3 src/opencode_debug.py --home runs/<run-id>/opencode sessions"
