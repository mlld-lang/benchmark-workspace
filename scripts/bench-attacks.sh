#!/usr/bin/env bash
# Dispatch the defended attack sweep across all 4 suites in 2 cycles.
#
# Usage:
#   scripts/bench-attacks.sh cycle1     # direct + ignore_previous + important_instructions
#   scripts/bench-attacks.sh cycle2     # injecagent + system_message + tool_knowledge
#   scripts/bench-attacks.sh single <attack_type>   # one attack type, all 4 suites
#
# Capacity math (Personal Business + 7-day double = 320 vCPU concurrent):
#   Per attack type × 4 suites:
#     workspace 32x64 -p 40                      = 32 vCPU
#     travel    32x64 -p 20 heap=8g (solo shape) = 32 vCPU
#     banking   16x32 -p 16                      = 16 vCPU
#     slack     16x32 -p 21                      = 16 vCPU
#                                                  ----
#                                                  96 vCPU per attack type
#   3 attack types in parallel = 288 vCPU. Fits the 320 cap with 32 spare.
#   2 cycles × ~30-40 min each ≈ ~60-80 min total wall for the full attack
#   sweep (vs ~90-120 min on the stock 160 vCPU plan).
#
# Per-suite shapes were sized empirically:
#   - banking 8x16 / slack 8x16 OOM under benign at full task count (16/21
#     active) after SKIP_TASKS removal — bumped to 16x32 for headroom.
#   - workspace and travel solo at 32x64 already validated by the benign
#     run (run IDs 25222263461 / 25222265101).
#
# Travel runs at the 32x64 *solo* shape with -p 20 even when other suites
# are dispatching alongside, because the 320 vCPU cap accommodates it
# without throttling. MLLD_HEAP=8g preserved for c-63fe headroom.

set -euo pipefail

WORKFLOW=bench-run.yml

CYCLE1_ATTACKS=(direct ignore_previous important_instructions)
CYCLE2_ATTACKS=(injecagent system_message tool_knowledge)

dispatch_suite_attack() {
  local suite=$1 attack=$2
  local shape parallelism heap=""
  case "$suite" in
    workspace) shape=nscloud-ubuntu-22.04-amd64-32x64; parallelism=40 ;;
    travel)    shape=nscloud-ubuntu-22.04-amd64-32x64; parallelism=20; heap=8g ;;
    banking)   shape=nscloud-ubuntu-22.04-amd64-16x32; parallelism=16 ;;
    slack)     shape=nscloud-ubuntu-22.04-amd64-16x32; parallelism=21 ;;
    *) echo "unknown suite: $suite" >&2; return 1 ;;
  esac

  local args=(
    -f "suite=$suite"
    -f "attack=$attack"
    -f "shape=$shape"
    -f "parallelism=$parallelism"
    -f "defense=defended"
  )
  [[ -n "$heap" ]] && args+=(-f "heap=$heap")

  printf '→ %-9s × %-23s ' "$suite" "$attack"
  if gh workflow run "$WORKFLOW" "${args[@]}" >/dev/null 2>&1; then
    printf 'dispatched\n'
  else
    printf 'FAILED\n' >&2
    return 1
  fi
}

dispatch_cycle() {
  local cycle=$1; shift
  local attacks=("$@")

  echo "== $cycle: ${attacks[*]} =="
  for attack in "${attacks[@]}"; do
    for suite in workspace travel banking slack; do
      dispatch_suite_attack "$suite" "$attack"
      sleep 0.5  # avoid rapid-fire dispatch race on GH side
    done
  done
  echo
  echo "$((${#attacks[@]} * 4)) jobs dispatched."
  echo "Watch:    gh run list --workflow=$WORKFLOW --limit 12"
  echo "Wait:     until [[ \$(gh run list --workflow=$WORKFLOW --limit 12 --json status -q '[.[] | select(.status == \"completed\")] | length') -eq 12 ]]; do sleep 60; done"
}

usage() {
  echo "usage: $0 cycle1 | cycle2 | single <attack_type>" >&2
  echo "  cycle1: ${CYCLE1_ATTACKS[*]}" >&2
  echo "  cycle2: ${CYCLE2_ATTACKS[*]}" >&2
  exit 1
}

case "${1:-}" in
  cycle1) dispatch_cycle "cycle1" "${CYCLE1_ATTACKS[@]}" ;;
  cycle2) dispatch_cycle "cycle2" "${CYCLE2_ATTACKS[@]}" ;;
  single)
    [[ $# -eq 2 ]] || usage
    dispatch_cycle "single" "$2"
    ;;
  *) usage ;;
esac
