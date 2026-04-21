"""CLI runner for mlld AgentDojo agent.

Usage:
    uv run --project clean/bench python3 clean/src/run.py -s workspace -t user_task_0 --debug
    uv run --project clean/bench python3 clean/src/run.py -s workspace -p 20
    uv run --project clean/bench python3 clean/src/run.py -s workspace -d defended -p 20
    uv run --project clean/bench python3 clean/src/run.py -s workspace -d defended -a important_instructions -p 20
"""

from __future__ import annotations

import argparse
import fcntl
import sys
import time
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_AGENTDOJO_SRC = REPO_ROOT / "agentdojo" / "src"
if LOCAL_AGENTDOJO_SRC.exists():
    sys.path.insert(0, str(LOCAL_AGENTDOJO_SRC))

from agentdojo.attacks import load_attack
from agentdojo.runner import run_task as run_agentdojo_task

sys.path.insert(0, str(Path(__file__).parent))

from host import MlldAgent, MlldInfrastructureError, AGENT_DIR
from date_shift import get_shifted_suite

BENCHMARK_VERSION = "v1.1.1"
SUITES = ["workspace", "slack", "banking", "travel"]
ATTACKS = [
    "direct", "ignore_previous", "important_instructions", "injecagent",
    "system_message", "tool_knowledge",
]


def _rotate_log(model, suite, defense, attack=None):
    log_dir = AGENT_DIR.parent / "results" / model / suite
    log_dir.mkdir(parents=True, exist_ok=True)
    suffix = defense
    if attack:
        suffix = f"{defense}.atk_{attack}"
    log_path = log_dir / f"{suffix}.jsonl"
    if log_path.exists():
        n = 1
        while (log_dir / f"{suffix}.{n}.jsonl").exists():
            n += 1
        log_path.rename(log_dir / f"{suffix}.{n}.jsonl")


def _log_suffix(defense, attack=None):
    return f"{defense}.atk_{attack}" if attack else defense


@contextmanager
def _locked_path(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _prepare_run_log(model, suite, defense, attack=None):
    log_dir = AGENT_DIR.parent / "results" / model / suite
    log_dir.mkdir(parents=True, exist_ok=True)
    suffix = _log_suffix(defense, attack)
    canonical_path = log_dir / f"{suffix}.jsonl"
    lock_path = log_dir / f"{suffix}.lock"

    with _locked_path(lock_path):
        numeric_runs = []
        for path in log_dir.glob(f"{suffix}.*.jsonl"):
            serial = path.name[len(f"{suffix}."):-len(".jsonl")]
            if serial.isdigit():
                numeric_runs.append(int(serial))
        next_serial = max(numeric_runs, default=0) + 1

        if canonical_path.exists() and not canonical_path.is_symlink():
            archive_path = log_dir / f"{suffix}.{next_serial}.jsonl"
            canonical_path.rename(archive_path)
            next_serial += 1
        elif canonical_path.is_symlink():
            canonical_path.unlink()

        run_log_path = log_dir / f"{suffix}.{next_serial}.jsonl"
        run_log_path.touch(exist_ok=False)
        canonical_path.symlink_to(run_log_path.name)
        return run_log_path


def _make_agent(model, debug, suite_name, defense, attack=None, injection_task_id=None, run_log_path=None, harness=None):
    return MlldAgent(
        model=model,
        harness=harness,
        debug=debug,
        env_name=suite_name,
        defense=str(defense),
        attack=attack,
        injection_task_id=injection_task_id,
        run_log_path=str(run_log_path) if run_log_path else None,
    )


def _run_task(suite_name, task, model, debug, defense, run_log_path, harness=None):
    agent = _make_agent(model, debug, suite_name, defense, run_log_path=run_log_path, harness=harness)
    agent._current_task_id = task.ID
    suite = get_shifted_suite(BENCHMARK_VERSION, suite_name)
    t0 = time.time()
    try:
        utility, security, _result = run_agentdojo_task(
            suite, agent, task, injection_task=None, injections={},
            benchmark_version=BENCHMARK_VERSION,
        )
        agent.update_verdict(utility, security)
        elapsed = time.time() - t0
        return task.ID, utility, security, None, elapsed
    except MlldInfrastructureError as e:
        elapsed = time.time() - t0
        return task.ID, None, None, f"INFRASTRUCTURE: {e}", elapsed
    except Exception as e:
        elapsed = time.time() - t0
        return task.ID, None, None, str(e), elapsed
    finally:
        agent.close()


def _run_attack_task(suite_name, user_task, injection_task, model, debug, defense, attack_name, run_log_path, harness=None):
    agent = _make_agent(model, debug, suite_name, defense,
                        attack=attack_name, injection_task_id=injection_task.ID,
                        run_log_path=run_log_path, harness=harness)
    agent._current_task_id = user_task.ID
    suite = get_shifted_suite(BENCHMARK_VERSION, suite_name)
    case_id = f"{user_task.ID}×{injection_task.ID}"

    class _FakeAgent:
        name = "claude-3-5-sonnet-20241022"
    attack = load_attack(attack_name, suite, _FakeAgent())
    try:
        injections = attack.attack(user_task, injection_task)
    except Exception:
        injections = {}

    try:
        utility, security, _result = run_agentdojo_task(
            suite, agent, user_task, injection_task=injection_task, injections=injections,
            benchmark_version=BENCHMARK_VERSION,
        )
        agent.update_verdict(utility, security)
        return case_id, user_task.ID, injection_task.ID, utility, security, None
    except MlldInfrastructureError as e:
        # Infrastructure failure — never claim a security verdict for a
        # non-run. See b-e8e4. Returning None/None lets the summary skip
        # this case from ASR computation instead of crediting it.
        return case_id, user_task.ID, injection_task.ID, None, None, f"INFRASTRUCTURE: {e}"
    except Exception as e:
        return case_id, user_task.ID, injection_task.ID, None, None, str(e)
    finally:
        agent.close()


def _run_benign(args, suite, tasks):
    run_log_path = _prepare_run_log(args.model, args.suite, args.defense)
    n = min(args.parallel, len(tasks))
    print(
        f"Running {args.suite} benign suite ({len(tasks)} tasks, {n} parallel,"
        f" defense={args.defense})..."
    )
    start = time.time()

    utility_results = {}
    errors = {}

    stagger = getattr(args, 'stagger', 2.0)
    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = {}
        for i, task in enumerate(tasks):
            futures[pool.submit(_run_task, args.suite, task, args.model, args.debug, args.defense, run_log_path, getattr(args, 'harness', None))] = task
            if stagger > 0 and i < len(tasks) - 1:
                time.sleep(stagger)
        done_count = 0
        rate_limited = False
        task_times = {}
        for future in as_completed(futures):
            task_id, utility, security, error, task_elapsed = future.result()
            utility_results[task_id] = utility
            task_times[task_id] = task_elapsed
            done_count += 1
            status = "PASS" if utility else "FAIL"
            time_str = f" ({task_elapsed:.0f}s)" if task_elapsed else ""
            if error:
                errors[task_id] = error
                status = f"ERROR: {error[:60]}"
                if "rate limit" in error.lower():
                    rate_limited = True
            print(f"  [{done_count}/{len(tasks)}] {task_id}: {status}{time_str}")
            if rate_limited:
                print("\nRate limited — cancelling remaining tasks.")
                pool.shutdown(wait=False, cancel_futures=True)
                break

    elapsed = time.time() - start
    # None signals infrastructure error — exclude from utility scoring entirely.
    graded = {tid: v for tid, v in utility_results.items() if v is not None}
    infra_failures = sorted(tid for tid, v in utility_results.items() if v is None)
    passed = sum(1 for v in graded.values() if v)
    total = len(graded)
    pct = (100 * passed / total) if total else 0.0
    avg_time = sum(task_times.values()) / len(task_times) if task_times else 0
    print(f"\nUtility: {passed}/{total} ({pct:.1f}%) in {elapsed:.1f}s wall, {avg_time:.0f}s avg/task")
    if infra_failures:
        print(f"Infrastructure errors (excluded from utility): {len(infra_failures)}")

    if errors:
        for tid, err in sorted(errors.items()):
            print(f"  {tid}: {err}")

    failed = sorted(tid for tid, v in graded.items() if not v)
    if failed:
        print(f"\nFailed ({len(failed)}): {', '.join(failed)}")


def _run_attacks(args, suite):
    run_log_path = _prepare_run_log(args.model, args.suite, args.defense, attack=args.attack)
    user_tasks = list(suite.user_tasks.values())
    injection_tasks = list(suite.injection_tasks.values())

    if args.task:
        user_tasks = [t for t in user_tasks if t.ID in args.task]
    if args.injection_task:
        injection_tasks = [t for t in injection_tasks if t.ID in args.injection_task]

    class _FakeAgent:
        name = "claude-3-5-sonnet-20241022"
    attack = load_attack(args.attack, suite, _FakeAgent())

    cases = []
    for ut in user_tasks:
        for it in injection_tasks:
            try:
                attack.attack(ut, it)
            except Exception:
                continue
            cases.append((ut, it))

    n = min(args.parallel, len(cases))
    print(
        f"Running {args.suite} attack suite: {args.attack} ({len(cases)} cases, {n} parallel,"
        f" defense={args.defense})..."
    )
    start = time.time()

    results = []
    errors = {}

    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = {
            pool.submit(
                _run_attack_task, args.suite, ut, it,
                args.model, args.debug, args.defense, args.attack, run_log_path, getattr(args, 'harness', None)
            ): (ut, it)
            for ut, it in cases
        }
        done_count = 0
        rate_limited = False
        for future in as_completed(futures):
            case_id, ut_id, it_id, utility, security, error = future.result()
            results.append({
                "case": case_id, "user_task": ut_id, "injection_task": it_id,
                "utility": utility, "security": security,
            })
            done_count += 1

            if error:
                errors[case_id] = error
                print(f"  [{done_count}/{len(cases)}] {case_id}: ERROR {error[:60]}")
                if "rate limit" in error.lower():
                    rate_limited = True
            elif security is True:
                print(f"  [{done_count}/{len(cases)}] {case_id}: BREACHED (utility={utility})")
            if rate_limited:
                print("\nRate limited — cancelling remaining tasks.")
                pool.shutdown(wait=False, cancel_futures=True)
                break

    elapsed = time.time() - start
    # Drop infrastructure errors (security=None) from ASR scoring entirely.
    # See b-e8e4: a crashed run reports security=False (attack didn't succeed
    # because no agent ran), which would inflate the defense rate.
    graded = [r for r in results if r["security"] is not None]
    infra_count = len(results) - len(graded)
    total = len(graded)
    attacks_succeeded = sum(1 for r in graded if r["security"])
    utility_preserved = sum(1 for r in graded if r["utility"])

    asr = 100 * attacks_succeeded / total if total else 0
    utility_pct = 100 * utility_preserved / total if total else 0

    print(f"\n{'='*60}")
    print(f"Attack: {args.attack} | Defense: {args.defense} | {total} cases in {elapsed:.1f}s")
    if infra_count:
        print(f"  ({infra_count} infrastructure errors excluded from scoring)")
    print(f"{'='*60}")
    print(f"  ASR (attack success rate):     {attacks_succeeded}/{total} ({asr:.1f}%)")
    print(f"  Utility under attack:          {utility_preserved}/{total} ({utility_pct:.1f}%)")

    if attacks_succeeded > 0:
        print(f"\nBreached cases ({attacks_succeeded}):")
        for r in sorted(graded, key=lambda r: r["case"]):
            if r["security"]:
                print(f"  {r['case']} (utility={r['utility']})")

    print(f"\nPer injection task:")
    for it in injection_tasks:
        it_results = [r for r in graded if r["injection_task"] == it.ID]
        it_breached = sum(1 for r in it_results if r["security"])
        it_total = len(it_results)
        if it_total:
            print(f"  {it.ID}: ASR {it_breached}/{it_total} ({100*it_breached/it_total:.0f}%) — {it.GOAL[:80]}")


def main():
    parser = argparse.ArgumentParser(description="Run mlld AgentDojo agent")
    parser.add_argument("-s", "--suite", choices=SUITES, default="workspace")
    parser.add_argument("-t", "--task", nargs="+", help="Run specific user task(s)")
    parser.add_argument("--injection-task", nargs="+", help="Run specific injection task(s) when using --attack")
    # Default dev model is GLM 5.1 via Together AI. clean/rig/runtime.mld
    # routes togetherai/* models through the opencode harness by default.
    parser.add_argument("--model", default="togetherai/zai-org/GLM-5.1")
    parser.add_argument("--harness", choices=["claude", "opencode"],
                        help="LLM harness override; if omitted, runtime picks from --model")
    parser.add_argument("-p", "--parallel", type=int, default=20)
    parser.add_argument("--stagger", type=float, default=5.0,
                        help="Seconds between launching parallel tasks (default: 2.0)")
    parser.add_argument("-d", "--defense", default="undefended",
                        help="Defense level: undefended (default) or defended (authorization bundles)")
    parser.add_argument("-a", "--attack", choices=ATTACKS,
                        help="Run attack suite")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    suite = get_shifted_suite(BENCHMARK_VERSION, args.suite)

    if args.attack:
        _run_attacks(args, suite)
        return

    if args.task and len(args.task) == 1:
        task_id = args.task[0]
        task = suite.user_tasks.get(task_id) or suite.injection_tasks.get(task_id)
        if task is None:
            print(f"Task '{task_id}' not found in {args.suite}")
            sys.exit(1)
        run_log_path = _prepare_run_log(args.model, args.suite, args.defense)
        agent = _make_agent(args.model, args.debug, args.suite, args.defense, run_log_path=run_log_path, harness=getattr(args, 'harness', None))
        agent._current_task_id = task_id
        try:
            print(
                f"Running {task_id} (defense={args.defense}):"
                f" {task.PROMPT[:80]}..."
            )
            try:
                utility, security, _result = run_agentdojo_task(
                    suite, agent, task, injection_task=None, injections={},
                    benchmark_version=BENCHMARK_VERSION,
                )
            except MlldInfrastructureError as e:
                # No agent run happened — refuse to claim a verdict. b-e8e4.
                print(f"INFRASTRUCTURE ERROR: {e}")
                sys.exit(2)
            agent.update_verdict(utility, security)
            # AgentDojo's `security` field for benign tasks is vacuously True
            # (its docstring: "The security is always True"). For attack runs
            # `security=True` means the attack achieved its goal (breach).
            # Single-task path is benign-only here, so don't print it at all —
            # it would be misleading either way. Just report utility.
            status = "PASS" if utility else "FAIL"
            print(f"Utility: {status}")
        finally:
            agent.close()
    elif args.task:
        tasks = []
        for tid in args.task:
            task = suite.user_tasks.get(tid) or suite.injection_tasks.get(tid)
            if task is None:
                print(f"Task '{tid}' not found in {args.suite}")
                sys.exit(1)
            tasks.append(task)
        _run_benign(args, suite, tasks)
    else:
        tasks = list(suite.user_tasks.values())
        _run_benign(args, suite, tasks)


if __name__ == "__main__":
    main()
