#!/usr/bin/env bash
# Entrypoint for bench remote runs.
#
# Reads env vars set by the GH Actions workflow, runs src/run.py, and bundles
# results + opencode transcripts into /artifacts/ for the workflow's upload step.
#
# Required env: RUN_ID, SUITE
# Optional env: TASKS (space-separated), PLANNER, WORKER, HARNESS, PARALLELISM,
#               STAGGER, DEFENSE, MLLD_TRACE, IMAGE_SHA, MLLD_REF
#
# Provider keys (passed through from workflow secrets):
#   CEREBRAS_API_KEY, TOGETHER_API_KEY

set -uo pipefail

: "${RUN_ID:?RUN_ID env required}"
: "${SUITE:?SUITE env required}"

ARTIFACTS="${ARTIFACTS_DIR:-/artifacts}"
mkdir -p "$ARTIFACTS"

cd /workspace/clean

# Build src/run.py args from env
ARGS=(-s "$SUITE" -d "${DEFENSE:-defended}")
if [[ -n "${TASKS:-}" ]]; then
  read -ra task_arr <<< "$TASKS"
  ARGS+=(-t "${task_arr[@]}")
fi
[[ -n "${PLANNER:-}" ]] && ARGS+=(--planner "$PLANNER")
[[ -n "${WORKER:-}" ]] && ARGS+=(--worker "$WORKER")
[[ -n "${HARNESS:-}" ]] && ARGS+=(--harness "$HARNESS")
ARGS+=(-p "${PARALLELISM:-40}")
[[ -n "${STAGGER:-}" ]] && ARGS+=(--stagger "$STAGGER")

if [[ -n "${MLLD_TRACE:-}" ]]; then
  export MLLD_TRACE_FILE="$ARTIFACTS/trace.jsonl"
fi

START_TS=$(date +%s)
echo "[bench-remote] RUN_ID=$RUN_ID SUITE=$SUITE TASKS=${TASKS:-<all>} parallel=${PARALLELISM:-40}"
echo "[bench-remote] image_sha=${IMAGE_SHA:-unknown} mlld_ref=${MLLD_REF:-unknown}"
echo "[bench-remote] diagnostics:"
echo "[bench-remote]   /workspace contents: $(ls /workspace 2>&1 | tr '\n' ' ')"
echo "[bench-remote]   /workspace/agentdojo/src exists? $(test -d /workspace/agentdojo/src && echo yes || echo NO)"
echo "[bench-remote]   /workspace/agentdojo/src/agentdojo/runner.py exists? $(test -f /workspace/agentdojo/src/agentdojo/runner.py && echo yes || echo NO)"
echo "[bench-remote]   /workspace/clean/.mlld-sdk -> $(readlink /workspace/clean/.mlld-sdk 2>/dev/null || echo MISSING)"
echo "[bench-remote] $ uv run --project bench python3 src/run.py ${ARGS[*]}"
echo

uv run --project bench python3 src/run.py "${ARGS[@]}" 2>&1 | tee "$ARTIFACTS/console.log"
RUN_STATUS=${PIPESTATUS[0]}

END_TS=$(date +%s)

# Manifest for fetch_run.py to summarize without re-parsing console
python3 - "$ARTIFACTS/manifest.json" <<EOF
import json, os, sys
out = sys.argv[1]
manifest = {
    "run_id": os.environ["RUN_ID"],
    "suite": os.environ["SUITE"],
    "tasks": os.environ.get("TASKS", ""),
    "planner": os.environ.get("PLANNER", ""),
    "worker": os.environ.get("WORKER", ""),
    "harness": os.environ.get("HARNESS", ""),
    "parallelism": os.environ.get("PARALLELISM", "40"),
    "defense": os.environ.get("DEFENSE", "defended"),
    "started_at": ${START_TS},
    "ended_at": ${END_TS},
    "elapsed_sec": ${END_TS} - ${START_TS},
    "exit_code": ${RUN_STATUS},
    "image_sha": os.environ.get("IMAGE_SHA", "unknown"),
    "mlld_ref": os.environ.get("MLLD_REF", "unknown"),
}
with open(out, "w") as f:
    json.dump(manifest, f, indent=2)
EOF

# Bundle artifacts
tar czf "$ARTIFACTS/results.tgz" -C /workspace/clean bench/results 2>/dev/null \
  && echo "[bench-remote] packed results.tgz" \
  || echo "[bench-remote] WARN: no bench/results to pack"

tar czf "$ARTIFACTS/exec-logs.tgz" -C /workspace/clean bench/.llm 2>/dev/null \
  && echo "[bench-remote] packed exec-logs.tgz" \
  || echo "[bench-remote] note: no bench/.llm dir (skipping)"

if [[ -d "$HOME/.local/share/opencode" ]]; then
  tar czf "$ARTIFACTS/transcripts.tgz" -C "$HOME/.local/share" opencode 2>/dev/null \
    && echo "[bench-remote] packed transcripts.tgz" \
    || echo "[bench-remote] WARN: transcript pack failed"
else
  echo "[bench-remote] note: no opencode dir (claude harness or no sessions)"
fi

echo "[bench-remote] done RUN_ID=$RUN_ID exit=$RUN_STATUS"
exit "$RUN_STATUS"
