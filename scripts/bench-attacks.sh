#!/usr/bin/env bash
# Dispatch the defended attack sweep across all 4 suites in 2 cycles.
#
# Usage:
#   scripts/bench-attacks.sh cycle1     # direct + ignore_previous
#   scripts/bench-attacks.sh cycle2     # important_instructions + injecagent
#   scripts/bench-attacks.sh cycle3     # system_message + tool_knowledge
#   scripts/bench-attacks.sh single <attack_type>   # one attack type, all 4 suites
#
# Capacity math (Personal Business + 7-day double = 320 vCPU concurrent):
#   Per attack type × 4 suites:
#     workspace 32x64 -p 40                      = 32 vCPU
#     travel    32x64 -p 20 heap=8g (solo shape) = 32 vCPU
#     banking   16x32 -p 16                      = 16 vCPU
#     slack     32x64 -p 21                      = 32 vCPU
#                                                  ----
#                                                 112 vCPU per attack type
#   2 attack types in parallel = 224 vCPU. Fits the 320 cap with 96 spare.
#   3 cycles × ~60-90 min each ≈ ~3-4 hr total wall for the attack sweep.
#
# Per-suite shapes were sized empirically:
#   - banking 8x16 / slack 8x16 OOM under benign at full task count (16/21
#     active) after SKIP_TASKS removal — bumped to 16x32 first.
#   - slack 16x32 -p 21 OOM'd on cycle 1 attack take 1 (run 25227133626
#     exit 137 at 47min) — attacks have larger per-pair footprint than
#     benign because injection-processing adds iterations. Bumped to 32x64.
#   - workspace and travel solo at 32x64 already validated by the benign
#     run (run IDs 25222263461 / 25222265101).
#
# Travel runs at the 32x64 *solo* shape with -p 20 even when other suites
# are dispatching alongside, because the 320 vCPU cap accommodates it
# without throttling. MLLD_HEAP=8g preserved for c-63fe headroom.
#
# c-63fe MCP "Not connected" issue was fixed in opencode locally
# (commit d10bb76 picks up the patched binary via OPENCODE_BIN). With that
# fix, the second-large-resolve_batch failure mode should be resolved.

set -euo pipefail

WORKFLOW=bench-run.yml

CYCLE1_ATTACKS=(direct ignore_previous)
CYCLE2_ATTACKS=(important_instructions injecagent)
CYCLE3_ATTACKS=(system_message tool_knowledge)

dispatch_suite_attack() {
  local suite=$1 attack=$2
  local shape parallelism heap=""
  case "$suite" in
    workspace) shape=nscloud-ubuntu-22.04-amd64-32x64; parallelism=40 ;;
    travel)    shape=nscloud-ubuntu-22.04-amd64-32x64; parallelism=20; heap=8g ;;
    banking)   shape=nscloud-ubuntu-22.04-amd64-16x32; parallelism=16 ;;
    # Slack bumped 16x32 → 32x64 after cycle 1 OOM (exit 137 at ~47min).
    # 21 parallel attack pairs × ~1.5–2 GB peak = ~32–42 GB, exceeds the
    # 32 GB cap on 16x32. 64 GB shape gives comfortable headroom.
    slack)     shape=nscloud-ubuntu-22.04-amd64-32x64; parallelism=21 ;;
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
  echo "usage: $0 cycle1 | cycle2 | cycle3 | single <attack_type>" >&2
  echo "  cycle1: ${CYCLE1_ATTACKS[*]}" >&2
  echo "  cycle2: ${CYCLE2_ATTACKS[*]}" >&2
  echo "  cycle3: ${CYCLE3_ATTACKS[*]}" >&2
  exit 1
}

case "${1:-}" in
  cycle1) dispatch_cycle "cycle1" "${CYCLE1_ATTACKS[@]}" ;;
  cycle2) dispatch_cycle "cycle2" "${CYCLE2_ATTACKS[@]}" ;;
  cycle3) dispatch_cycle "cycle3" "${CYCLE3_ATTACKS[@]}" ;;
  single)
    [[ $# -eq 2 ]] || usage
    dispatch_cycle "single" "$2"
    ;;
  *) usage ;;
esac
