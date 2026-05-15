#!/usr/bin/env bash
# Dispatch the defended attack sweep across the 5 sub-suites in batches of 2.
#
# Sub-suite layout (same as scripts/bench.sh):
#
#   workspace-a   user_task_0..19   (20 tasks)   32x64
#   workspace-b   user_task_20..39  (20 tasks)   32x64
#   banking       all               (16 tasks)   16x32
#   slack         all               (21 tasks)   32x64
#   travel        all               (20 tasks)   32x64
#
# Workspace splits the same way as the benign sweep so attack runs stay
# under the per-runner memory + per-model rate limit. Slack and travel
# keep 32x64 because attack runs add planner iterations (injection
# processing) that pushed slack OOM at 16x32 historically (run
# 25227133626 exit 137 at 47min). Banking stays 16x32.
#
# Usage:
#   scripts/bench-attacks.sh                    # full matrix: 6 attacks × 5 sub-suites = 30 jobs
#   scripts/bench-attacks.sh cycle1             # direct + ignore_previous (10 jobs)
#   scripts/bench-attacks.sh cycle2             # important_instructions + injecagent (10 jobs)
#   scripts/bench-attacks.sh cycle3             # system_message + tool_knowledge (10 jobs)
#   scripts/bench-attacks.sh single <attack>    # one attack × all 5 sub-suites (5 jobs)
#   scripts/bench-attacks.sh single <attack> <suite>  # narrow to one sub-suite (1 job)
#
# Capacity math:
#   Full matrix = 30 dispatches. At MAX_CONCURRENT=2 = 15 batches.
#   Each batch ~8-12 min wall (attack runs are longer than benign because
#   planner navigates poisoned content with more iterations). Total wall
#   ~2-3 hr for the full matrix. Fits an overnight window.
#
# Rate-limit posture: matches scripts/bench.sh — at most 2 bench-run
# jobs in flight simultaneously, polling for capacity between dispatches.
# Avoids the 5k+ HTTP 429s a 4+ way fan-out would generate against
# Together AI's per-model GLM-5.1 capacity.
#
# Pre-flight: c-63fe MCP "Not connected" issue was fixed in opencode
# (commit d10bb76). With that in the prebuilt opencode binary the
# second-large-resolve_batch failure mode should be resolved.

set -euo pipefail

WORKFLOW=bench-run.yml
GRIND_FILE="bench/grind-tasks.json"
MAX_CONCURRENT=2

# Per-sub-suite shape. Workspace-a/b stay at 32x64 because attacks
# concentrate planner iterations and we want headroom; benign runs
# can fit 16x32 but attacks are not yet measured at that shape.
SHAPE_LARGE=nscloud-ubuntu-22.04-amd64-32x64
SHAPE_MEDIUM=nscloud-ubuntu-22.04-amd64-16x32

ATTACK_CYCLES_1=(direct ignore_previous)
ATTACK_CYCLES_2=(important_instructions injecagent)
ATTACK_CYCLES_3=(system_message tool_knowledge)
ATTACK_FULL=(direct ignore_previous important_instructions injecagent system_message tool_knowledge)

SUB_SUITES=(workspace-a workspace-b banking slack travel)

# ---- sub-suite mapping (mirrors scripts/bench.sh) ----

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
    banking|slack|travel) echo "$1" ;;
    *) echo "" ;;
  esac
}

underlying_suite() {
  case "$1" in
    workspace-a|workspace-b) echo "workspace" ;;
    *) echo "$1" ;;
  esac
}

shape_for() {
  case "$1" in
    workspace-a|workspace-b|slack|travel) echo "$SHAPE_LARGE" ;;
    banking) echo "$SHAPE_MEDIUM" ;;
  esac
}

parallelism_for() {
  local sub=$1
  case "$sub" in
    workspace-a|workspace-b) echo 20 ;;
    banking) jq -r ".task_counts.banking" "$GRIND_FILE" ;;
    slack)   jq -r ".task_counts.slack" "$GRIND_FILE" ;;
    travel)  jq -r ".task_counts.travel" "$GRIND_FILE" ;;
  esac
}

# ---- dispatch ----

dispatch_attack() {
  local sub=$1 attack=$2
  read -r suite raw_tasks <<< "$(sub_suite_info "$sub")"
  local underlying
  underlying=$(underlying_suite "$sub")

  local args=(
    -f "suite=$underlying"
    -f "attack=$attack"
    -f "shape=$(shape_for "$sub")"
    -f "parallelism=$(parallelism_for "$sub")"
    -f "defense=defended"
  )

  # workspace-a/b inject task slice; the others run all suite tasks
  if [[ -n "${raw_tasks:-}" ]]; then
    args+=(-f "tasks=$raw_tasks")
  fi

  local ref_args=()
  if [[ -n "${BENCH_REF:-}" ]]; then
    ref_args=(--ref "$BENCH_REF")
  fi

  printf '→ %-13s × %-23s ' "$sub" "$attack"
  if gh workflow run "$WORKFLOW" "${ref_args[@]}" "${args[@]}" >/dev/null 2>&1; then
    printf 'dispatched\n'
  else
    printf 'FAILED\n' >&2
    return 1
  fi
}

# Block until fewer than MAX_CONCURRENT bench-run jobs are in flight.
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

dispatch_matrix() {
  local label=$1; shift
  local attacks=("$@")

  local total=$((${#attacks[@]} * ${#SUB_SUITES[@]}))
  echo "== $label: ${attacks[*]} (${#SUB_SUITES[@]} sub-suites × ${#attacks[@]} attacks = $total jobs, batched 2-at-a-time) =="

  local count=0
  for attack in "${attacks[@]}"; do
    for sub in "${SUB_SUITES[@]}"; do
      wait_for_capacity
      dispatch_attack "$sub" "$attack"
      count=$((count + 1))
    done
  done
  echo
  echo "$count jobs dispatched."
  echo "Watch:    gh run list --workflow=$WORKFLOW --limit 30"
  echo "Wait:     until [[ \$(gh run list --workflow=$WORKFLOW --limit 30 --json status -q '[.[] | select(.status == \"completed\")] | length') -ge $count ]]; do sleep 60; done"
}

dispatch_single_narrow() {
  local attack=$1 sub=$2
  for valid in "${SUB_SUITES[@]}"; do
    if [[ "$sub" == "$valid" ]]; then
      dispatch_attack "$sub" "$attack"
      return 0
    fi
  done
  echo "unknown sub-suite: $sub (valid: ${SUB_SUITES[*]})" >&2
  return 1
}

usage() {
  echo "usage: $0 [cycle1 | cycle2 | cycle3 | single <attack> [sub-suite]]" >&2
  echo "  (no args)         full matrix: ${ATTACK_FULL[*]} × ${SUB_SUITES[*]}" >&2
  echo "  cycle1            ${ATTACK_CYCLES_1[*]}" >&2
  echo "  cycle2            ${ATTACK_CYCLES_2[*]}" >&2
  echo "  cycle3            ${ATTACK_CYCLES_3[*]}" >&2
  echo "  single <attack>   one attack × all 5 sub-suites" >&2
  echo "  single <attack> <sub>  narrow to one sub-suite (no batching)" >&2
  exit 1
}

case "${1:-}" in
  ""|full)  dispatch_matrix "full" "${ATTACK_FULL[@]}" ;;
  cycle1)   dispatch_matrix "cycle1" "${ATTACK_CYCLES_1[@]}" ;;
  cycle2)   dispatch_matrix "cycle2" "${ATTACK_CYCLES_2[@]}" ;;
  cycle3)   dispatch_matrix "cycle3" "${ATTACK_CYCLES_3[@]}" ;;
  single)
    case $# in
      2) dispatch_matrix "single $2" "$2" ;;
      3) dispatch_single_narrow "$2" "$3" ;;
      *) usage ;;
    esac
    ;;
  -h|--help) usage ;;
  *) usage ;;
esac
