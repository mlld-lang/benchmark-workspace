#!/usr/bin/env bash
# Dispatch one or more bench-run.yml workflow_dispatch invocations on
# Namespace.
#
# Sub-suite layout (batched dispatching so concurrent runners stay under
# Together AI's per-model GLM-5.1 rate ceiling):
#
#   workspace-a   user_task_0..19   (20 tasks)
#   workspace-b   user_task_20..39  (20 tasks)
#   banking       all               (16 tasks)
#   slack         all               (21 tasks)
#   travel        all               (20 tasks)
#
# Default mode dispatches the 5 sub-suites in batches of 2 (last
# batch is solo travel), polling for capacity between dispatches so
# at most MAX_CONCURRENT bench-run jobs are in flight. This trades
# wall (~3 batches × ~6 min ≈ 18 min) for predictable rate-limit
# headroom — vs. all-5-parallel which saturates GLM-5.1 capacity
# and produces 5k+ HTTP 429s.
#
# Usage:
#   scripts/bench.sh                          # full sweep, 2-at-a-time (default)
#   scripts/bench.sh workspace-a              # single sub-suite
#   scripts/bench.sh banking slack            # subset, 2-at-a-time
#   scripts/bench.sh --fast                   # full sweep, grind tasks excluded
#   scripts/bench.sh --grind                  # all suites' grind tasks on ONE runner
#   scripts/bench.sh --grind workspace        # single suite's grind set
#   scripts/bench.sh --all-parallel           # dispatch all at once; requires dedicated inference capacity
#
# Aliases: workspace expands to workspace-a workspace-b. Single-letter
# aliases (w, b, s, t) work too.
#
# Modes:
#   default — full task set per sub-suite. Batched 2-at-a-time.
#   --fast  — every task EXCEPT grind set. Batched 2-at-a-time.
#   --grind — only the grind set. When multiple suites, batches into ONE
#             cross-suite dispatch via src/run.py multi-suite mode.
#   --all-parallel — dispatch all sub-suites simultaneously. Do not use this
#             with shared GLM-5.1 limits; CPU/memory are not the bottleneck,
#             inference API 429s are.
#
# The grind set per suite lives in bench/grind-tasks.json — single source
# of truth. Update it when classification changes.

set -euo pipefail

WORKFLOW=bench-run.yml
GRIND_FILE="bench/grind-tasks.json"

# How many bench-run jobs to allow in flight at once. 2 is the empirical
# headroom under Tier 4 Together AI for GLM-5.1 — see today's 429
# investigation in HANDOFF.md. Set higher only with dedicated capacity.
MAX_CONCURRENT=${MAX_CONCURRENT:-2}

# Per-target shape. Workspace splits into halves of 20 tasks each, so all
# 5 sub-suites are roughly 16-21 tasks. Measured peak memory across recent
# benign runs at this size: workspace-half ~15-17 GB, slack 16.7 GB,
# travel 19.6 GB, banking 3-13 GB. 16x32 (31 GB) fits all with headroom
# (worst case travel at 63% utilization).
#
# 32x64 was historically needed when workspace ran -p 40 (peak 30-34 GB)
# and before mlld memory reductions landed. The split + memory work moved
# us comfortably under 16x32. Bump back to LARGE only if peak utilization
# trends past 75% across consecutive runs.
#
# Attack sweeps use a SEPARATE shape config in scripts/bench-attacks.sh
# (32x64 for workspace/travel/slack, 16x32 for banking). Attacks have a
# larger per-pair memory footprint because injection-processing extends
# planner iteration counts — slack at 16x32 OOM'd on a real attack run.
# Don't lower bench-attacks.sh shapes based on benign-sweep numbers.
SHAPE_WORKSPACE=nscloud-ubuntu-22.04-amd64-16x32
SHAPE_TRAVEL=nscloud-ubuntu-22.04-amd64-16x32
SHAPE_MEDIUM=nscloud-ubuntu-22.04-amd64-16x32
SHAPE_LARGE=nscloud-ubuntu-22.04-amd64-32x64

# Sub-suite ordering for the default sweep. Layered so each batch pairs
# a workspace half with a different suite — distributes provider
# pressure roughly evenly across batches.
DEFAULT_ORDER=(workspace-a banking workspace-b slack travel)

# Mode + sub-suite filter parsing
MODE=full
ALL_PARALLEL=0
SUITES=()
for arg in "$@"; do
  case "$arg" in
    --fast)         MODE=fast ;;
    --grind)        MODE=grind ;;
    --all-parallel) ALL_PARALLEL=1 ;;
    -h|--help)
      sed -n '2,42p' "$0" | sed 's|^# \?||'
      exit 0
      ;;
    -* )
      echo "unknown flag: $arg" >&2
      exit 1
      ;;
    *) SUITES+=("$arg") ;;
  esac
done

# Default: full sweep across all 5 sub-suites
if [ ${#SUITES[@]} -eq 0 ]; then
  SUITES=("${DEFAULT_ORDER[@]}")
fi

# Normalize aliases. workspace|w expands to both halves.
NORMALIZED=()
for s in "${SUITES[@]}"; do
  case "$s" in
    workspace|w)   NORMALIZED+=(workspace-a workspace-b) ;;
    workspace-a|wa) NORMALIZED+=(workspace-a) ;;
    workspace-b|wb) NORMALIZED+=(workspace-b) ;;
    banking|b)     NORMALIZED+=(banking) ;;
    slack|s)       NORMALIZED+=(slack) ;;
    travel|t)      NORMALIZED+=(travel) ;;
    *) echo "unknown sub-suite: $s (valid: workspace[-a|-b] banking slack travel)" >&2; exit 1 ;;
  esac
done
SUITES=("${NORMALIZED[@]}")

# ---- sub-suite resolution ----

# Echo "<suite> <task1> <task2> ..." for a given sub-suite. workspace-a/b
# inject task-id slices; the others are full suites with no task filter.
sub_suite_info() {
  local sub=$1
  case "$sub" in
    workspace-a)
      local tasks=""
      for i in {0..19}; do tasks+="user_task_$i "; done
      echo "workspace ${tasks% }"
      ;;
    workspace-b)
      local tasks=""
      for i in {20..39}; do tasks+="user_task_$i "; done
      echo "workspace ${tasks% }"
      ;;
    banking|slack|travel) echo "$sub" ;;
    *) echo "$sub" ;;
  esac
}

# Underlying suite for a sub-suite (workspace-a → workspace, etc.)
underlying_suite() {
  case "$1" in
    workspace-a|workspace-b) echo "workspace" ;;
    *) echo "$1" ;;
  esac
}

shape_for() {
  case "$1" in
    workspace) echo "$SHAPE_WORKSPACE" ;;
    travel)    echo "$SHAPE_TRAVEL" ;;
    banking)   echo "$SHAPE_MEDIUM" ;;
    slack)     echo "$SHAPE_LARGE" ;;
  esac
}

parallelism_for_full() {
  jq -r ".task_counts.$1" "$GRIND_FILE"
}

# Filter task list against grind set: returns space-separated task ids
# from $tasks that are NOT in grind[$suite].
filter_out_grind() {
  local suite=$1; shift
  local tasks=("$@")
  local grind_csv
  grind_csv=$(jq -r ".grind.$suite | join(\",\")" "$GRIND_FILE")
  local out=()
  for t in "${tasks[@]}"; do
    if [[ ",$grind_csv," != *",$t,"* ]]; then
      out+=("$t")
    fi
  done
  echo "${out[@]}"
}

# Compute the task list for a sub-suite in a given mode.
sub_suite_tasks() {
  local sub=$1
  local mode=$2
  read -r suite raw_tasks <<< "$(sub_suite_info "$sub")"
  local tasks_arr
  if [[ -z "${raw_tasks:-}" ]]; then
    # Whole-suite sub: enumerate task ids from grind-tasks.json
    local count
    count=$(jq -r ".task_counts.$suite" "$GRIND_FILE")
    tasks_arr=()
    for ((i=0; i<count; i++)); do tasks_arr+=("user_task_$i"); done
  else
    # shellcheck disable=SC2086
    read -r -a tasks_arr <<< "$raw_tasks"
  fi

  if [[ "$mode" == "fast" ]]; then
    filter_out_grind "$suite" "${tasks_arr[@]}"
  elif [[ "$mode" == "grind" ]]; then
    local grind
    grind=$(jq -r ".grind.$suite | join(\" \")" "$GRIND_FILE")
    # Intersect grind set with this sub-suite's task slice
    local out=()
    for g in $grind; do
      for t in "${tasks_arr[@]}"; do
        if [[ "$g" == "$t" ]]; then out+=("$g"); fi
      done
    done
    echo "${out[@]}"
  else
    echo "${tasks_arr[@]}"
  fi
}

# ---- dispatch helpers ----

dispatch() {
  local label=$1; shift
  local cmd=(gh workflow run "$WORKFLOW")
  if [[ -n "${BENCH_REF:-}" ]]; then
    cmd+=(--ref "$BENCH_REF")
  fi
  cmd+=("$@")
  if [[ -n "${BENCH_IMAGE_TAG:-}" ]]; then
    cmd+=(-f "image_tag=$BENCH_IMAGE_TAG")
  fi
  printf '→ %-32s ' "$label"
  if "${cmd[@]}" >/dev/null 2>&1; then
    printf 'dispatched\n'
  else
    printf 'FAILED\n' >&2
    return 1
  fi
}

run_sub_suite() {
  local sub=$1
  local mode=$2

  read -r suite _ <<< "$(sub_suite_info "$sub")"
  local underlying
  underlying=$(underlying_suite "$sub")
  local tasks
  tasks=$(sub_suite_tasks "$sub" "$mode")

  if [[ -z "$tasks" ]]; then
    echo "→ $sub ($mode): no tasks after filtering, skipping"
    return 0
  fi

  local count
  count=$(echo "$tasks" | wc -w | tr -d ' ')

  # Only pass tasks if it's a partial slice. For a full sub-suite that
  # equals the whole AgentDojo suite, pass empty tasks so bench-run
  # uses its default (all tasks). Saves URL bloat.
  local full_count
  full_count=$(jq -r ".task_counts.$underlying" "$GRIND_FILE")
  local task_arg=""
  if [[ "$count" -ne "$full_count" ]]; then
    task_arg="$tasks"
  fi

  local label="$sub ($mode)"
  if [[ -n "$task_arg" ]]; then
    dispatch "$label" \
      -f suite="$underlying" \
      -f tasks="$task_arg" \
      -f shape="$(shape_for "$underlying")" \
      -f parallelism="$count"
  else
    dispatch "$label" \
      -f suite="$underlying" \
      -f shape="$(shape_for "$underlying")" \
      -f parallelism="$count"
  fi
}

# Block until fewer than MAX_CONCURRENT bench-run jobs are in flight.
# Polls every 30s. Counts both in_progress and queued.
wait_for_capacity() {
  local target=$((MAX_CONCURRENT - 1))
  while true; do
    local in_flight
    in_flight=$(gh run list --workflow="$WORKFLOW" --limit 20 \
      --json status,conclusion \
      -q '[.[] | select(.status=="in_progress" or .status=="queued")] | length')
    if [[ "$in_flight" -le "$target" ]]; then
      return 0
    fi
    sleep 30
  done
}

# ---- multi-suite grind (single dispatch) ----

run_grind_multi() {
  local combined=""
  local total=0
  for sub in "${SUITES[@]}"; do
    local tasks
    tasks=$(sub_suite_tasks "$sub" "grind")
    if [[ -z "$tasks" ]]; then continue; fi
    local underlying
    underlying=$(underlying_suite "$sub")
    for t in $tasks; do
      combined+="$underlying:$t "
      total=$((total + 1))
    done
  done
  if [[ -z "$combined" ]]; then
    echo "no grind tasks for selected sub-suites" >&2
    return 0
  fi
  dispatch "grind (multi-suite, $total tasks)" \
    -f suite=workspace \
    -f tasks="$combined" \
    -f shape="$SHAPE_WORKSPACE" \
    -f parallelism="$total"
}

# ---- main ----

case "$MODE" in
  full|fast)
    if [[ "$ALL_PARALLEL" -eq 1 ]]; then
      # Legacy: dispatch all at once. Risky under shared rate limits.
      for s in "${SUITES[@]}"; do
        run_sub_suite "$s" "$MODE"
      done
    else
      # Default: batched 2-at-a-time. Wait for capacity between dispatches.
      for s in "${SUITES[@]}"; do
        wait_for_capacity
        run_sub_suite "$s" "$MODE"
      done
    fi
    ;;
  grind)
    if [ ${#SUITES[@]} -eq 1 ]; then
      run_sub_suite "${SUITES[0]}" "grind"
    else
      run_grind_multi
    fi
    ;;
esac

echo
echo "Watch:    gh run list --workflow=bench-run.yml --limit 8"
echo "Fetch:    uv run --project bench python3 src/fetch_run.py <run-id>"
echo "Browse:   uv run --project bench python3 src/opencode_debug.py --home runs/<run-id>/opencode sessions"
