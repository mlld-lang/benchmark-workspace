#!/usr/bin/env python3
"""c-8dff: Phase B memory hot-path reproducer for c-63fe.

Drives UT19's planner tool-call sequence against the rig with NO LLM calls.
Inner Python MCP server (clean/src/mcp_server.py) still runs and returns
real AgentDojo travel data; only the OUTER planner LLM is replaced with
a deterministic script replay.

Usage:
    uv run --project bench python3 scripts/repro_c63fe_mem.py
    MLLD_HEAP=8g uv run --project bench python3 scripts/repro_c63fe_mem.py

Env knobs (passed through to mlld SDK):
    MLLD_HEAP=12g          (default)
    MLLD_TRACE=verbose     (default off; set to enable per-call tracing)
    MLLD_TRACE_FILE=PATH   (default off; required for trace dump)
    MLLD_TRACE_MEMORY=1    (default off; sample RSS/heap per phase)

Trace inspection:
    jq -c 'select(.event|test("memory|phase|rss|heap"))' $MLLD_TRACE_FILE | tail
"""

import os
import sys
import time
import json
import tempfile
import contextlib
from pathlib import Path

CLEAN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CLEAN_ROOT))
sys.path.insert(0, str(CLEAN_ROOT.parent / "agentdojo" / "src"))
sys.path.insert(0, str(CLEAN_ROOT.parent / "mlld" / "sdk" / "python"))

from src.host import _build_local_mcp_command  # noqa: E402
from src.date_shift import get_shifted_suite     # noqa: E402

# mlld SDK
from mlld import Client                          # noqa: E402

SCRIPT_PATH = CLEAN_ROOT / "rig" / "test-harness" / "run-ut19-mock.mld"


def _make_temp(suffix: str, prefix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    os.close(fd)
    return path


def main() -> int:
    suite = get_shifted_suite("v1.1.1", "travel")
    env = suite.load_and_inject_default_environment({})
    state_file = _make_temp(".json", "mcp_env_")
    Path(state_file).write_text(env.model_dump_json())

    mcp_log_file = _make_temp(".jsonl", "mcp_log_")
    phase_log_file = _make_temp(".jsonl", "phase_log_")
    phase_state_file = _make_temp(".json", "phase_state_")

    mcp_command = _build_local_mcp_command({
        "state_file": state_file,
        "log_file": mcp_log_file,
        "suite_name": "travel",
        "env_name": "travel",
        "benchmark_version": "v1.1.1",
        "phase_state_file": phase_state_file,
        "task_id": "user_task_19",
    })

    print(f"c-8dff Phase B memory reproducer")
    print(f"  CLEAN_ROOT:  {CLEAN_ROOT}")
    print(f"  SCRIPT:      {SCRIPT_PATH}")
    print(f"  HEAP:        {os.environ.get('MLLD_HEAP', '<unset>')}")
    print(f"  TRACE:       {os.environ.get('MLLD_TRACE', '<unset>')} memory={os.environ.get('MLLD_TRACE_MEMORY', '<unset>')}")
    print(f"  state_file:  {state_file}")
    print(f"  mcp_log:     {mcp_log_file}")
    print(f"  phase_log:   {phase_log_file}")
    print()

    client = Client()
    execute_kwargs = {
        "mcp_servers": {"tools": mcp_command},
    }
    if os.environ.get("MLLD_TRACE"):
        execute_kwargs["trace"] = os.environ["MLLD_TRACE"]
    if os.environ.get("MLLD_TRACE_FILE"):
        execute_kwargs["trace_file"] = os.environ["MLLD_TRACE_FILE"]
    if os.environ.get("MLLD_TRACE_MEMORY"):
        execute_kwargs["trace_memory"] = True

    t0 = time.monotonic()
    try:
        result = client.execute(str(SCRIPT_PATH), {}, **execute_kwargs)
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 1
    finally:
        for path in [state_file, mcp_log_file, phase_log_file, phase_state_file]:
            with contextlib.suppress(OSError):
                os.unlink(path)

    elapsed = time.monotonic() - t0
    print()
    print(f"=== DONE elapsed={elapsed:.1f}s ===")
    print()
    if isinstance(result, dict):
        print(json.dumps(result, default=str, indent=2)[:2000])
    else:
        print(str(result)[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
