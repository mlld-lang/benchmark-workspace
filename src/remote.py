"""Launch a bench run on a Namespace-hosted GitHub Actions runner.

Wraps `gh workflow run bench-run.yml`. Prints the resolved run URL and id, then
waits for completion (unless --detach is passed). Pair with `src/fetch_run.py`
to retrieve artifacts.

Usage:
    uv run --project bench python3 src/remote.py -s workspace
    uv run --project bench python3 src/remote.py -s workspace -t user_task_8 user_task_32
    uv run --project bench python3 src/remote.py -s banking --image-tag sha-abc1234
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time

SUITES = ["workspace", "slack", "banking", "travel"]
WORKFLOW = "bench-run.yml"
DEFAULT_SHAPE = "nscloud-ubuntu-22.04-amd64-32x64"


def gh(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True, **kwargs)


def latest_run_id(workflow: str, since_iso: str) -> str | None:
    proc = gh("run", "list", "--workflow", workflow, "--limit", "5",
              "--json", "databaseId,createdAt,event,status")
    if proc.returncode != 0:
        return None
    runs = json.loads(proc.stdout or "[]")
    candidates = [r for r in runs if r.get("createdAt", "") >= since_iso
                  and r.get("event") == "workflow_dispatch"]
    if not candidates:
        return None
    candidates.sort(key=lambda r: r["createdAt"], reverse=True)
    return str(candidates[0]["databaseId"])


def main() -> int:
    p = argparse.ArgumentParser(description="Launch a bench run on Namespace via GH Actions")
    p.add_argument("-s", "--suite", choices=SUITES, required=True)
    p.add_argument("-t", "--task", nargs="+", default=None,
                   help="Specific user task ids (default: full suite, oos skipped)")
    p.add_argument("--planner", default="")
    p.add_argument("--worker", default="")
    p.add_argument("--harness", choices=["", "opencode", "claude"], default="")
    p.add_argument("-p", "--parallel", type=int, default=40)
    p.add_argument("--stagger", type=float, default=10.0)
    p.add_argument("--defense", choices=["defended", "undefended"], default="defended")
    p.add_argument("--trace", action="store_true",
                   help="Enable MLLD_TRACE=effects")
    p.add_argument("--image-tag", default="main",
                   help="Image tag to pull (e.g., main, sha-abc1234)")
    p.add_argument("--shape", default=DEFAULT_SHAPE,
                   help="Namespace runner shape label")
    p.add_argument("--detach", action="store_true",
                   help="Return immediately after dispatch (default: wait for completion)")
    args = p.parse_args()

    inputs = [
        f"suite={args.suite}",
        f"tasks={' '.join(args.task) if args.task else ''}",
        f"planner={args.planner}",
        f"worker={args.worker}",
        f"harness={args.harness}",
        f"parallelism={args.parallel}",
        f"stagger={args.stagger}",
        f"defense={args.defense}",
        f"trace={'true' if args.trace else 'false'}",
        f"image_tag={args.image_tag}",
        f"shape={args.shape}",
    ]
    cmd = ["gh", "workflow", "run", WORKFLOW]
    for inp in inputs:
        cmd += ["-f", inp]

    print(f"$ {' '.join(shlex.quote(p) for p in cmd)}")
    since_iso = subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                               capture_output=True, text=True).stdout.strip()
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        return proc.returncode

    print()
    print("Resolving run id...", flush=True)
    run_id = None
    for _ in range(15):
        time.sleep(2)
        run_id = latest_run_id(WORKFLOW, since_iso)
        if run_id:
            break
    if not run_id:
        print("WARN: could not resolve run id automatically. Find it via:")
        print(f"  gh run list --workflow {WORKFLOW} --limit 5")
        return 1

    repo = subprocess.run(["gh", "repo", "view", "--json", "url", "-q", ".url"],
                          capture_output=True, text=True).stdout.strip()
    url = f"{repo}/actions/runs/{run_id}" if repo else f"(run id: {run_id})"

    print(f"RUN_ID={run_id}")
    print(f"URL: {url}")
    print()
    print("Fetch results when done:")
    print(f"  uv run --project bench python3 src/fetch_run.py {run_id}")
    print()

    if args.detach:
        return 0

    print("Waiting for run to complete (Ctrl-C to detach)...")
    watch = subprocess.run(["gh", "run", "watch", run_id, "--exit-status"])
    return watch.returncode


if __name__ == "__main__":
    sys.exit(main())
