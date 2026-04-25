#!/usr/bin/env bash
# Dispatch one or more bench-run.yml workflow_dispatch invocations.
#
# Usage:
#   scripts/bench.sh                          # all 4 suites in parallel (Namespace)
#   scripts/bench.sh workspace                # just workspace
#   scripts/bench.sh banking slack            # subset
#   PUZL=1 scripts/bench.sh                   # use puzl.cloud runners (trial)
#
# Each invocation triggers a separate runner. By default, dispatches to
# bench-run.yml (Namespace runners with per-shape sizing). Set PUZL=1 to
# dispatch to bench-run-puzl.yml (puzl.cloud runners with per-runner
# sizing in their console — no shape arg passed).
#
# Skip lists (oos/non-gating) are honored by src/run.py's SKIP_TASKS
# when no -t is passed.

set -euo pipefail

# Workflow + sizing knobs differ between providers. Namespace needs an
# explicit -f shape per dispatch. puzl.cloud sizes runners in its
# console and ignores the shape arg, so we don't pass it. puzl-Business
# allows up to 48 vCPU / 96 GB per job which fits everything — no
# throttling, no fan-out math required.
if [ -n "${PUZL:-}" ]; then
  WORKFLOW=bench-run-puzl.yml
  USE_SHAPES=false
else
  WORKFLOW=bench-run.yml
  USE_SHAPES=true
fi

# Per-target shape and parallelism. Each task carries the AgentDojo
# TaskEnvironment + an mlld + MCP process in RAM (~1.5-2 GB at peak).
# Empirical results:
#   - workspace 36 parallel on 8x16  → OOM (run 24922643802/4218)
#   - travel    20 parallel on 8x16  → OOM (run 24922900959)
#   - travel    20 parallel on 16x32 → OOM (run 24923046920)
#   - banking   15 parallel on 8x16  → fine
#   - slack     14 parallel on 8x16  → fine (run 24922900581)
#
# Travel mode switching:
#   - Fan-out (workspace in the dispatch set): 16x32 + -p 5. Throttled
#     for both the 64 vCPU concurrency cap and c-63fe MCP destabilization.
#   - Solo (workspace absent): 32x64 + -p 20 (full parallelism). 64 GB
#     fits all 20 tasks; c-63fe MCP errors are still possible but the
#     memory headroom mitigates the OOM-driven part of the failure mode.
SHAPE_WORKSPACE=nscloud-ubuntu-22.04-amd64-32x64
SHAPE_TRAVEL_FANOUT=nscloud-ubuntu-22.04-amd64-16x32
SHAPE_TRAVEL_SOLO=nscloud-ubuntu-22.04-amd64-32x64
SHAPE_LIGHT=nscloud-ubuntu-22.04-amd64-8x16

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

# Build the shape arg list — empty when sizing is handled by the runner
# provider (puzl).
shape_arg() {
  $USE_SHAPES && printf -- '-f shape=%s' "$1" || true
}

run_target() {
  case "$1" in
    workspace|w)
      # shellcheck disable=SC2046
      dispatch workspace -f suite=workspace $(shape_arg "$SHAPE_WORKSPACE")
      ;;
    banking|b)
      # shellcheck disable=SC2046
      dispatch banking -f suite=banking $(shape_arg "$SHAPE_LIGHT")
      ;;
    slack|s)
      # shellcheck disable=SC2046
      dispatch slack -f suite=slack $(shape_arg "$SHAPE_LIGHT")
      ;;
    travel|t)
      # c-63fe: MCP server destabilizes under travel's tool load. On
      # Namespace, fan-out mode throttles to -p 5 (16x32 shape) because
      # of the 64 vCPU concurrency cap; solo mode runs -p 20 on 32x64.
      # On puzl, no throttling — runners are 48x96, no aggregate cap.
      if $USE_SHAPES && "$WORKSPACE_PLANNED"; then
        dispatch travel -f suite=travel -f shape="$SHAPE_TRAVEL_FANOUT" -f parallelism=5
      elif $USE_SHAPES; then
        dispatch travel -f suite=travel -f shape="$SHAPE_TRAVEL_SOLO" -f parallelism=20
      else
        dispatch travel -f suite=travel -f parallelism=20
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
echo "Watch:    gh run list --workflow=$WORKFLOW --limit 8"
echo "Fetch:    uv run --project bench python3 src/fetch_run.py <run-id>"
echo "Browse:   uv run --project bench python3 src/opencode_debug.py --home runs/<run-id>/opencode sessions"
