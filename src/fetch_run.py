"""Fetch a remote bench run's artifacts to runs/<run_id>/.

Usage:
    uv run --project bench python3 src/fetch_run.py 12345678901
    uv run --project bench python3 src/fetch_run.py 12345678901 --out /tmp/run

After fetch, browse opencode transcripts with:
    uv run --project bench python3 src/opencode_debug.py \\
        --home runs/<run_id>/opencode sessions
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = REPO_ROOT / "runs"


def gh_download(run_id: str, dest: Path) -> int:
    """Pull artifacts from GitHub's artifact API via `gh run download`."""
    dest.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["gh", "run", "download", run_id, "-D", str(dest)],
    )
    return proc.returncode


def extract_tar(path: Path, dest: Path) -> None:
    if not path.exists():
        return
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "r:gz") as tf:
        tf.extractall(dest)


def summarize(out: Path) -> None:
    manifest_path = out / "manifest.json"
    if manifest_path.exists():
        with manifest_path.open() as f:
            m = json.load(f)
        print()
        print(f"Suite:       {m.get('suite')}")
        print(f"Defense:     {m.get('defense')}")
        print(f"Tasks:       {m.get('tasks') or '<full suite>'}")
        print(f"Planner:     {m.get('planner') or '<default>'}")
        print(f"Worker:      {m.get('worker') or '<default>'}")
        print(f"Parallelism: {m.get('parallelism')}")
        print(f"Elapsed:     {m.get('elapsed_sec')}s   Exit: {m.get('exit_code')}")
        print(f"Image SHA:   {m.get('image_sha')}")
        print()

    results_dir = out / "results"
    if results_dir.exists():
        for jsonl in sorted(results_dir.rglob("defended.jsonl")):
            with jsonl.open() as f:
                rows = [json.loads(line) for line in f if line.strip()]
            passed = sum(1 for r in rows if r.get("utility") is True)
            failed = sum(1 for r in rows if r.get("utility") is False)
            errors = sum(1 for r in rows if r.get("utility") is None)
            total = len(rows)
            try:
                rel = jsonl.relative_to(out)
            except ValueError:
                rel = jsonl
            print(f"{rel}: {passed} pass / {failed} fail / {errors} infra-err  (n={total})")


def main() -> int:
    p = argparse.ArgumentParser(description="Fetch a remote bench run")
    p.add_argument("run_id", help="GitHub Actions run id (printed by src/remote.py)")
    p.add_argument("--out", type=Path, default=None,
                   help="Output directory (default: runs/<run_id>/)")
    args = p.parse_args()

    out = args.out or (RUNS_DIR / args.run_id)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Fetching {args.run_id} → {out.relative_to(REPO_ROOT) if out.is_relative_to(REPO_ROOT) else out}")
    rc = gh_download(args.run_id, out)
    if rc != 0:
        print("ERROR: gh run download failed", file=sys.stderr)
        return rc

    # GH download nests under <out>/<artifact-name>/ — flatten if there's a single dir
    nested = list(out.iterdir())
    if len(nested) == 1 and nested[0].is_dir() and nested[0].name.startswith("bench-"):
        inner = nested[0]
        for item in inner.iterdir():
            shutil.move(str(item), str(out / item.name))
        inner.rmdir()

    # Unpack tarballs
    extract_tar(out / "results.tgz", out / "results")
    extract_tar(out / "exec-logs.tgz", out / "exec_logs")
    extract_tar(out / "transcripts.tgz", out / "_unpacked")
    nested_oc = out / "_unpacked" / "opencode"
    if nested_oc.exists():
        if (out / "opencode").exists():
            shutil.rmtree(out / "opencode")
        shutil.move(str(nested_oc), str(out / "opencode"))
    if (out / "_unpacked").exists():
        shutil.rmtree(out / "_unpacked", ignore_errors=True)

    # Inner-worker opencode db (workers run under their own opencode home)
    inner_tgz = out / "inner-worker-transcripts.tgz"
    if inner_tgz.exists():
        extract_tar(inner_tgz, out / "_inner_unpacked")
        nested_inner = out / "_inner_unpacked" / "opencode"
        if nested_inner.exists():
            if (out / "opencode-inner").exists():
                shutil.rmtree(out / "opencode-inner")
            shutil.move(str(nested_inner), str(out / "opencode-inner"))
        if (out / "_inner_unpacked").exists():
            shutil.rmtree(out / "_inner_unpacked", ignore_errors=True)

    summarize(out)

    if (out / "opencode" / "opencode.db").exists() or (out / "opencode" / "opencode-dev.db").exists():
        print()
        print("Browse transcripts:")
        print(f"  uv run --project bench python3 src/opencode_debug.py "
              f"--home {out.relative_to(REPO_ROOT) if out.is_relative_to(REPO_ROOT) else out}/opencode sessions")

    return 0


if __name__ == "__main__":
    sys.exit(main())
