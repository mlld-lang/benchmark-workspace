#!/usr/bin/env python3
"""Run scripted-LLM tests against the clean/tests framework.

Wraps ``tests/scripted-index.mld`` with an MCP server command wired up
the same way ``scripts/repro_workspace_list_files.py`` and friends do —
AgentDojo Python env builds the env-json, ``_build_local_mcp_command``
spawns the MCP bridge, and the mlld SDK runs the index with
``mcp_servers={'tools': <cmd>}`` so domain ``tools.mld`` files import
cleanly.

Usage:
    uv run --project bench python3 tests/run-scripted.py
    uv run --project bench python3 tests/run-scripted.py --suite travel

Env knobs:
    MLLD_HEAP=12g
    MLLD_TIMEOUT_S=600
    MLLD_TRACE=effects|verbose
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

CLEAN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CLEAN_ROOT))
sys.path.insert(0, str(CLEAN_ROOT.parent / "mlld" / "sdk" / "python"))

from mlld import Client  # noqa: E402
from src.date_shift import get_shifted_suite  # noqa: E402
from src.host import _build_local_mcp_command  # noqa: E402

# Default task-id seeds the AgentDojo env per suite. These pick a task
# whose initial environment matches what the demo scripted-suite expects.
DEFAULT_TASK_ID = {
    "workspace": "user_task_26",
    "travel": "user_task_19",
    "banking": "user_task_2",
    "slack": "user_task_1",
}


def _make_temp(suffix: str, prefix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    os.close(fd)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="workspace",
                        choices=sorted(DEFAULT_TASK_ID),
                        help="bench suite whose MCP env to wire up (default: workspace)")
    parser.add_argument("--task-id", default=None,
                        help="override the default task-id used to seed the env")
    parser.add_argument("--index", default=str(CLEAN_ROOT / "tests" / "scripted-index.mld"),
                        help="path to the scripted index to run")
    args = parser.parse_args()

    suite_name = args.suite
    task_id = args.task_id or DEFAULT_TASK_ID[suite_name]

    suite = get_shifted_suite("v1.1.1", suite_name)
    env = suite.load_and_inject_default_environment({})
    state_file = _make_temp(".json", "mcp_env_")
    Path(state_file).write_text(env.model_dump_json())

    mcp_log_file = _make_temp(".jsonl", "mcp_log_")
    phase_state_file = _make_temp(".json", "phase_state_")

    mcp_command = _build_local_mcp_command({
        "state_file": state_file,
        "log_file": mcp_log_file,
        "suite_name": suite_name,
        "env_name": suite_name,
        "benchmark_version": "v1.1.1",
        "phase_state_file": phase_state_file,
        "task_id": task_id,
    })

    print(f"clean/tests scripted runner")
    print(f"  suite:      {suite_name}")
    print(f"  task_id:    {task_id}")
    print(f"  index:      {args.index}")
    print()

    client = Client()
    timeout_s = int(os.environ.get("MLLD_TIMEOUT_S", "600"))
    execute_kwargs = {
        "mcp_servers": {"tools": mcp_command},
        "timeout": timeout_s,
    }
    if os.environ.get("MLLD_TRACE"):
        execute_kwargs["trace"] = os.environ["MLLD_TRACE"]
    if os.environ.get("MLLD_TRACE_FILE"):
        execute_kwargs["trace_file"] = os.environ["MLLD_TRACE_FILE"]

    t0 = time.monotonic()
    exit_code = 0
    result = None
    try:
        result = client.execute(args.index, {"suite": suite_name}, **execute_kwargs)
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        exit_code = 1
    finally:
        for path in (state_file, mcp_log_file, phase_state_file):
            with contextlib.suppress(OSError):
                os.unlink(path)

    elapsed = time.monotonic() - t0

    # `show` calls become effects with type='both'; rig's diagnostic
    # `log` calls (and similar) come through as type='stderr'. Route
    # accordingly so the wrapper output is clean: user-facing report
    # on stdout, diagnostics on stderr.
    fails_marker = None
    if result is not None:
        for effect in getattr(result, "effects", []) or []:
            content = getattr(effect, "content", None)
            etype = getattr(effect, "type", None)
            if content is None:
                continue
            # The marker line carries the wrapper's exit-code signal;
            # parse it but don't print it (it's noise in the report).
            if "__SCRIPTED_STATUS__:" in content:
                for token in content.split():
                    if token.startswith("fails="):
                        try:
                            fails_marker = int(token.split("=", 1)[1])
                        except ValueError:
                            pass
                continue
            text = content if content.endswith("\n") else content + "\n"
            stream = sys.stderr if etype == "stderr" else sys.stdout
            stream.write(text)

    sys.stdout.write(f"\n=== DONE elapsed={elapsed:.1f}s ===\n")

    if fails_marker is None and result is not None:
        # Marker missing — the script didn't reach the summary line.
        # Treat as failure so silent breakages don't pass.
        exit_code = 1
    elif fails_marker and fails_marker > 0:
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
