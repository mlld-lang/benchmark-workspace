#!/usr/bin/env bash
# Dispatch one or more bench-run.yml workflow_dispatch invocations on Namespace.
#
# Usage:
#   scripts/bench-all.sh                          # all 5 groups (workspace-a/b + banking + slack + travel)
#   scripts/bench-all.sh workspace-a              # one group
#   scripts/bench-all.sh banking slack            # subset
#   scripts/bench-all.sh workspace                # both halves of workspace
#
# Each invocation triggers a separate Namespace 32x64 runner and runs all
# in-scope tasks in parallel inside that runner. Five groups → 5 runners
# concurrent, ~10-15 min wall time for the full bench surface.
#
# Skip lists (oos/non-gating) are honored automatically: workspace-a/b are
# pre-filtered here; banking/slack/travel rely on src/run.py's SKIP_TASKS
# when no -t is passed.

set -euo pipefail

# Workspace task IDs to run, oos already excluded:
# - skipped from A: UT13, UT19 (instruction-following over untrusted content)
# - skipped from B: UT25 (same), UT31 (non-gating evaluator wording)
WORKSPACE_A=(0 1 2 3 4 5 6 7 8 9 10 11 12 14 15 16 17 18)
WORKSPACE_B=(20 21 22 23 24 26 27 28 29 30 32 33 34 35 36 37 38 39)

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

dispatch_workspace() {
  local label=$1; shift
  local task_args=()
  for n in "$@"; do task_args+=("user_task_$n"); done
  local tasks_str
  tasks_str="${task_args[*]}"
  dispatch "$label" -f suite=workspace -f tasks="$tasks_str"
}

run_target() {
  case "$1" in
    workspace-a|wa) dispatch_workspace workspace-a "${WORKSPACE_A[@]}" ;;
    workspace-b|wb) dispatch_workspace workspace-b "${WORKSPACE_B[@]}" ;;
    workspace)
      dispatch_workspace workspace-a "${WORKSPACE_A[@]}"
      dispatch_workspace workspace-b "${WORKSPACE_B[@]}"
      ;;
    banking|b) dispatch banking -f suite=banking ;;
    slack|s)   dispatch slack   -f suite=slack ;;
    travel|t)  dispatch travel  -f suite=travel ;;
    *) echo "unknown target: $1" >&2
       echo "valid: workspace-a workspace-b workspace banking slack travel" >&2
       exit 1 ;;
  esac
}

if [ $# -eq 0 ]; then
  set -- workspace-a workspace-b banking slack travel
fi

for arg in "$@"; do
  run_target "$arg"
done

echo
echo "Watch:    gh run list --workflow=bench-run.yml --limit 8"
echo "Fetch:    uv run --project bench python3 src/fetch_run.py <run-id>"
echo "Browse:   uv run --project bench python3 src/opencode_debug.py --home runs/<run-id>/opencode sessions"
