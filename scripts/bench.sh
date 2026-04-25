#!/usr/bin/env bash
# Dispatch one or more bench-run.yml workflow_dispatch invocations on Namespace.
#
# Usage:
#   scripts/bench.sh                          # all 4 suites in parallel
#   scripts/bench.sh workspace                # just workspace
#   scripts/bench.sh banking slack            # subset
#
# Each invocation triggers a separate Namespace runner. All 4 fan out at
# once on Team plan (workspace 32x64 + others 8x16 = 56 vCPU, fits under
# the 64 vCPU cap). Wall time ~10-15 min for the full bench surface.
#
# Skip lists (oos/non-gating) are honored by src/run.py's SKIP_TASKS
# when no -t is passed.

set -euo pipefail

# Per-target shape and parallelism. Each task carries the AgentDojo
# TaskEnvironment + an mlld + MCP process in RAM (~1.5-2 GB at peak).
# Empirical results:
#   - workspace 36 parallel on 8x16  → OOM (run 24922643802/4218)
#   - travel    20 parallel on 8x16  → OOM (run 24922900959)
#   - travel    20 parallel on 16x32 → OOM (run 24923046920)
#   - banking   15 parallel on 8x16  → fine
#   - slack     14 parallel on 8x16  → fine (run 24922900581)
#
# Travel parallelism is also throttled (c-63fe): MCP server destabilizes
# at higher concurrency with travel's 28-tool surface. Even with no
# container OOM, ~50% of tool calls fail with "Not connected". Run with
# -p 5 (fan-out) or -p 10 (solo) until c-63fe is fixed.
#
# Two modes:
#   - Fan-out (workspace alongside others): travel constrained to 16x32
#     and -p 5 so total fits Team's 64 vCPU cap (32+16+8+8 = 64).
#   - Solo travel (workspace not in the dispatch set): bump to 32x64 +
#     -p 10. Less aggressive than the suite size would allow because of
#     c-63fe.
SHAPE_WORKSPACE=nscloud-ubuntu-22.04-amd64-32x64
SHAPE_TRAVEL_FANOUT=nscloud-ubuntu-22.04-amd64-16x32
SHAPE_TRAVEL_SOLO=nscloud-ubuntu-22.04-amd64-32x64
SHAPE_LIGHT=nscloud-ubuntu-22.04-amd64-8x16

dispatch() {
  local label=$1; shift
  printf '→ %-14s ' "$label"
  if gh workflow run bench-run.yml "$@" >/dev/null 2>&1; then
    printf 'dispatched\n'
  else
    printf 'FAILED\n' >&2
    return 1
  fi
}

run_target() {
  case "$1" in
    workspace|w) dispatch workspace -f suite=workspace -f shape="$SHAPE_WORKSPACE" ;;
    banking|b)   dispatch banking   -f suite=banking   -f shape="$SHAPE_LIGHT" ;;
    slack|s)     dispatch slack     -f suite=slack     -f shape="$SHAPE_LIGHT" ;;
    travel|t)
      # c-63fe: MCP server destabilizes under travel's tool load — even
      # without OOM-kill, ~50% of tool calls fail with "Not connected".
      # Keep parallelism low while the ticket is open.
      if "$WORKSPACE_PLANNED"; then
        dispatch travel -f suite=travel -f shape="$SHAPE_TRAVEL_FANOUT" -f parallelism=5
      else
        dispatch travel -f suite=travel -f shape="$SHAPE_TRAVEL_SOLO"   -f parallelism=10
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
