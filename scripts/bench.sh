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
# Travel's task count × per-task RSS overflows 32 GB at full parallelism;
# cap travel at -p 10 so it fits 16x32 with headroom (~17 GB peak).
#   Peak fan-out: 32 + 16 + 8 + 8 = 64 vCPU (Team plan cap is 64 — exact fit).
SHAPE_WORKSPACE=nscloud-ubuntu-22.04-amd64-32x64
SHAPE_TRAVEL=nscloud-ubuntu-22.04-amd64-16x32
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
    travel|t)    dispatch travel    -f suite=travel    -f shape="$SHAPE_TRAVEL" -f parallelism=10 ;;
    *) echo "unknown target: $1" >&2
       echo "valid: workspace banking slack travel" >&2
       exit 1 ;;
  esac
}

if [ $# -eq 0 ]; then
  set -- workspace banking slack travel
fi

for arg in "$@"; do
  run_target "$arg"
done

echo
echo "Watch:    gh run list --workflow=bench-run.yml --limit 8"
echo "Fetch:    uv run --project bench python3 src/fetch_run.py <run-id>"
echo "Browse:   uv run --project bench python3 src/opencode_debug.py --home runs/<run-id>/opencode sessions"
