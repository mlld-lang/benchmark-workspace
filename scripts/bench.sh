#!/usr/bin/env bash
# Dispatch one or more bench-run.yml workflow_dispatch invocations on
# Namespace.
#
# Usage:
#   scripts/bench.sh                          # all 4 suites, full task set (default)
#   scripts/bench.sh workspace                # one suite, full task set
#   scripts/bench.sh banking slack            # subset of suites, full task set
#   scripts/bench.sh --fast                   # all suites, GRIND tasks excluded
#   scripts/bench.sh --fast workspace slack   # subset of suites, fast only
#   scripts/bench.sh --grind                  # ALL suites' grind tasks on ONE runner
#                                             # (multi-suite mode; single dispatch)
#   scripts/bench.sh --grind workspace        # one suite's grind tasks (single dispatch)
#
# Modes:
#   default — every task in every selected suite. One dispatch per suite.
#   --fast  — every task EXCEPT grind set. One dispatch per suite. Iteration
#             cycle wall is bound by the slowest PASS task, not by the slow
#             SHOULD-FAIL/OOS tail. Use this when iterating on prompts /
#             runtime changes that don't affect grind classification.
#   --grind — only the grind set. When multiple suites are selected, batches
#             into ONE dispatch via src/run.py multi-suite mode (one runner
#             instead of N). Use this when you want to verify SHOULD-FAILs
#             still fail correctly, or for security analysis where the
#             security-constrained tasks are isolated from PASS noise.
#
# The grind set per suite lives in bench/grind-tasks.json — single source of
# truth. Update it when classification changes (see CLAUDE.md "Test
# prioritization buckets").
#
# Each invocation triggers a separate Namespace runner unless --grind is
# selected for multiple suites (then one runner via multi-suite mode).

set -euo pipefail

WORKFLOW=bench-run.yml
GRIND_FILE="bench/grind-tasks.json"

# Per-target shape. Travel + workspace need 64GB headroom at full -p 20;
# banking + slack are lighter and fit on 16x32. The fast/grind splits use
# the same shapes — task count drops but per-task memory is unchanged.
SHAPE_WORKSPACE=nscloud-ubuntu-22.04-amd64-32x64
SHAPE_TRAVEL=nscloud-ubuntu-22.04-amd64-32x64
SHAPE_MEDIUM=nscloud-ubuntu-22.04-amd64-16x32
SHAPE_LARGE=nscloud-ubuntu-22.04-amd64-32x64

# Mode + suite filter parsing
MODE=full
SUITES=()
for arg in "$@"; do
  case "$arg" in
    --fast)  MODE=fast ;;
    --grind) MODE=grind ;;
    -h|--help)
      sed -n '2,30p' "$0" | sed 's|^# \?||'
      exit 0
      ;;
    -* )
      echo "unknown flag: $arg" >&2
      exit 1
      ;;
    *) SUITES+=("$arg") ;;
  esac
done

if [ ${#SUITES[@]} -eq 0 ]; then
  SUITES=(workspace banking slack travel)
fi

# Normalize aliases (workspace|w, banking|b, slack|s, travel|t)
NORMALIZED=()
for s in "${SUITES[@]}"; do
  case "$s" in
    workspace|w) NORMALIZED+=(workspace) ;;
    banking|b)   NORMALIZED+=(banking) ;;
    slack|s)     NORMALIZED+=(slack) ;;
    travel|t)    NORMALIZED+=(travel) ;;
    *) echo "unknown suite: $s (valid: workspace banking slack travel)" >&2; exit 1 ;;
  esac
done
SUITES=("${NORMALIZED[@]}")

dispatch() {
  local label=$1; shift
  printf '→ %-32s ' "$label"
  if gh workflow run "$WORKFLOW" "$@" >/dev/null 2>&1; then
    printf 'dispatched\n'
  else
    printf 'FAILED\n' >&2
    return 1
  fi
}

shape_for() {
  case "$1" in
    workspace) echo "$SHAPE_WORKSPACE" ;;
    travel)    echo "$SHAPE_TRAVEL" ;;
    banking)   echo "$SHAPE_MEDIUM" ;;
    slack)     echo "$SHAPE_LARGE" ;;
  esac
}

# Default parallelism = task count for the suite. The fast/grind helpers
# already pass len(tasks) explicitly. Per-task memory after the recent
# mlld memory reduction is ~0.9 GB on workspace (measured 30.3 GB peak
# at -p 34 on 32x64 / 62.9 GB available — 48% utilization, plenty of
# headroom for the full suite at -p 40).
parallelism_for() {
  jq -r ".task_counts.$1" "$GRIND_FILE"
}

# Compute fast tasks for a suite = all tasks - grind tasks. Returns a
# space-separated list of user_task_N ids.
fast_tasks_for() {
  local suite=$1
  local count
  count=$(jq -r ".task_counts.$suite" "$GRIND_FILE")
  local grind_csv
  grind_csv=$(jq -r ".grind.$suite | join(\",\")" "$GRIND_FILE")
  local fast=()
  local i
  for ((i=0; i<count; i++)); do
    local tid="user_task_$i"
    if [[ ",$grind_csv," != *",$tid,"* ]]; then
      fast+=("$tid")
    fi
  done
  echo "${fast[@]}"
}

grind_tasks_for() {
  local suite=$1
  jq -r ".grind.$suite | join(\" \")" "$GRIND_FILE"
}

run_full() {
  local suite=$1
  dispatch "$suite (full)" \
    -f suite="$suite" \
    -f shape="$(shape_for "$suite")" \
    -f parallelism="$(parallelism_for "$suite")"
}

run_fast() {
  local suite=$1
  local tasks
  tasks=$(fast_tasks_for "$suite")
  if [[ -z "$tasks" ]]; then
    echo "→ $suite (fast): no fast tasks (entire suite is grind?)" >&2
    return 0
  fi
  # Parallelism = task count so the fast set runs fully parallel rather
  # than batched against the full-suite parallelism cap. Per src/run.py
  # the ThreadPoolExecutor caps max_workers at len(tasks) regardless,
  # but passing task count makes the intent explicit and means workspace
  # fast (34 tasks) doesn't get throttled to its full-sweep -p 20.
  local count
  count=$(echo "$tasks" | wc -w | tr -d ' ')
  dispatch "$suite (fast)" \
    -f suite="$suite" \
    -f tasks="$tasks" \
    -f shape="$(shape_for "$suite")" \
    -f parallelism="$count"
}

run_grind_single_suite() {
  local suite=$1
  local tasks
  tasks=$(grind_tasks_for "$suite")
  if [[ -z "$tasks" ]]; then
    echo "→ $suite (grind): empty grind set, skipping"
    return 0
  fi
  local count
  count=$(echo "$tasks" | wc -w | tr -d ' ')
  dispatch "$suite (grind)" \
    -f suite="$suite" \
    -f tasks="$tasks" \
    -f shape="$(shape_for "$suite")" \
    -f parallelism="$count"
}

# Multi-suite grind: build one cross-suite tasks string (suite:task_id form)
# and dispatch ONE bench-run that uses src/run.py multi-suite mode. The
# `suite` input is required by the workflow but is just a default for any
# unqualified tasks — every task here is qualified.
run_grind_multi() {
  local combined=""
  local total=0
  for suite in "${SUITES[@]}"; do
    local tasks
    tasks=$(grind_tasks_for "$suite")
    if [[ -z "$tasks" ]]; then
      continue
    fi
    for t in $tasks; do
      combined+="$suite:$t "
      total=$((total + 1))
    done
  done
  if [[ -z "$combined" ]]; then
    echo "no grind tasks for selected suites" >&2
    return 0
  fi
  dispatch "grind (multi-suite, $total tasks)" \
    -f suite=workspace \
    -f tasks="$combined" \
    -f shape="$SHAPE_WORKSPACE" \
    -f parallelism="$total"
}

case "$MODE" in
  full)
    for s in "${SUITES[@]}"; do
      run_full "$s"
    done
    ;;
  fast)
    for s in "${SUITES[@]}"; do
      run_fast "$s"
    done
    ;;
  grind)
    if [ ${#SUITES[@]} -eq 1 ]; then
      run_grind_single_suite "${SUITES[0]}"
    else
      run_grind_multi
    fi
    ;;
esac

echo
echo "Watch:    gh run list --workflow=bench-run.yml --limit 8"
echo "Fetch:    uv run --project bench python3 src/fetch_run.py <run-id>"
echo "Browse:   uv run --project bench python3 src/opencode_debug.py --home runs/<run-id>/opencode sessions"
