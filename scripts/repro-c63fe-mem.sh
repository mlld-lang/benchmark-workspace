#!/usr/bin/env bash
# c-8dff: deterministic c-63fe Phase B memory hot-path reproducer.
# Replays UT19's planner tool-call sequence with no LLM calls.
#
# Trace output:
#   /tmp/c63fe-mock-<ts>/mlld-trace.jsonl       per-call event stream
#   /tmp/c63fe-mock-<ts>/run.log                stdout+stderr
#
# Inspect peaks:
#   jq -c 'select(.event=="memory.snapshot")' /tmp/c63fe-mock-*/mlld-trace.jsonl | tail -20
#   grep -E "rss|heap" /tmp/c63fe-mock-*/run.log
#
# Usage:
#   scripts/repro-c63fe-mem.sh                  # default: 12g heap
#   MLLD_HEAP=8g scripts/repro-c63fe-mem.sh     # override

set -eu

CLEAN_ROOT=$(cd "$(dirname "$0")/.." && pwd)
TS=$(date +%s)
OUT=${OUT:-/tmp/c63fe-mock-$TS}
mkdir -p "$OUT"

export MLLD_TRACE=${MLLD_TRACE:-verbose}
export MLLD_TRACE_FILE="$OUT/mlld-trace.jsonl"
export MLLD_TRACE_MEMORY=${MLLD_TRACE_MEMORY:-1}
export MLLD_HEAP=${MLLD_HEAP:-12g}

echo "c-8dff Phase B memory reproducer"
echo "  CLEAN_ROOT: $CLEAN_ROOT"
echo "  OUT:        $OUT"
echo "  HEAP:       $MLLD_HEAP"
echo "  TRACE:      $MLLD_TRACE (memory=$MLLD_TRACE_MEMORY)"
echo

cd "$CLEAN_ROOT"
mlld rig/test-harness/run-ut19-mock.mld --no-checkpoint 2>&1 | tee "$OUT/run.log"

echo
echo "=== Done. Inspect:"
echo "  cat $OUT/run.log"
echo "  jq -c 'select(.event|test(\"memory|phase|rss|heap\"))' $OUT/mlld-trace.jsonl | tail -30"
echo "  ls -la $OUT/"
