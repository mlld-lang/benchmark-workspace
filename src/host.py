"""MlldAgent — MCP-based benchmark host for mlld agents.

Python does four things:
  1. Builds the MCP server command for the per-suite AgentDojo state
  2. Calls the per-suite mlld agent entrypoint under `bench/agents/`
  3. Reads back the modified env from the MCP server's state file
  4. Formats the result for AgentDojo

The mlld agent imports the AgentDojo MCP tools natively
(`import tools from mcp "tools" as @mcp`) and wraps them with the
rig framework's phase labels and security metadata. No tool spec
generation happens in Python.
"""

from __future__ import annotations

import base64
import fcntl
import inspect
import json
import os
import shlex
import sys
import tempfile
import uuid
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agentdojo_results import AgentResult, ToolCallRecord

import mlld as mlld_sdk
from mlld import Client

SRC_DIR = Path(__file__).parent
ROOT_DIR = SRC_DIR.parent
AGENT_DIR = ROOT_DIR / "bench" / "agents"
CLEAN_BENCH_PROJECT_DIR = ROOT_DIR / "bench"


def _agent_entrypoint(env_name: str = "workspace") -> str:
    return str(AGENT_DIR / f"{env_name}.mld")


def _resource_content_to_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if hasattr(value, "model_dump_json"):
        try:
            return value.model_dump_json()
        except Exception:
            pass
    return str(value)


def _attested_resource(
    resource_id: str,
    content: Any,
    *,
    kind: str,
    suite: str,
    task_id: str,
    query: str,
    scope: str,
) -> dict[str, Any]:
    return {
        "id": resource_id,
        "content": _resource_content_to_string(content),
        "signer": "user",
        "findable": False,
        "scope": scope,
        "meta": {
            "type": kind,
            "suite": suite,
            "task": task_id,
            "referenced_in_prompt": resource_id in query,
            "resource": resource_id,
            "scope": scope,
        },
    }


def _collect_attested_resources(env_name: str, task_id: str, query: str, scope: str) -> list[dict[str, Any]]:
    """Register task-start resource attestations for content-origin tasks.

    This is bench configuration, not rig logic: the host has access to the
    benign AgentDojo environment, so it can sign the bytes the user/origin is
    treated as having attested before injected state is applied.
    """
    try:
        from date_shift import get_shifted_suite

        suite = get_shifted_suite("v1.1.1", env_name)
        env = suite.load_and_inject_default_environment({})
        try:
            task = suite.get_user_task_by_id(task_id)
            env = task.init_environment(env)
        except Exception:
            pass
    except Exception:
        return []

    query_text = query or ""
    resources: list[dict[str, Any]] = []

    filesystem = getattr(env, "filesystem", None)
    files = getattr(filesystem, "files", None)
    if isinstance(files, dict):
        for file_path, content in sorted(files.items()):
            file_id = str(file_path)
            if file_id and file_id in query_text:
                resources.append(
                    _attested_resource(
                        file_id,
                        content,
                        kind="file",
                        suite=env_name,
                        task_id=task_id,
                        query=query_text,
                        scope=scope,
                    )
                )

    web = getattr(env, "web", None)
    web_content = getattr(web, "web_content", None)
    if isinstance(web_content, dict):
        for url, content in sorted(web_content.items()):
            url_id = str(url)
            # Slack tasks can discover URLs through signed Slack message refs,
            # so origin-attest the benign web corpus for that suite. Other
            # suites only get prompt-mentioned URLs by default.
            if env_name == "slack" or (url_id and url_id in query_text):
                resources.append(
                    _attested_resource(
                        url_id,
                        content,
                        kind="url",
                        suite=env_name,
                        task_id=task_id,
                        query=query_text,
                        scope=scope,
                    )
                )

    return resources


class MlldInfrastructureError(RuntimeError):
    """Raised when the mlld agent never executed (import crash, OOM, etc.).

    Distinct from RuntimeError so callers can tell an infrastructure failure
    apart from an in-run RuntimeError (rate limit, model error). Run scoring
    must NOT treat infrastructure failures as successful defenses — the agent
    didn't decide anything, so there is no defense to credit.
    """


def _resolve_mcp_script(config: dict[str, Any]) -> Path:
    """Pick which MCP server to launch.

    Routes every suite to `rig/agentdojo-mcp/server.py` (vanilla
    agentdojo, suite-agnostic, with bench_mcp_extras for domain
    helpers).
    """
    return ROOT_DIR / "rig" / "agentdojo-mcp" / "server.py"


def _build_local_mcp_command(config: dict[str, Any]) -> str:
    """Launch the local MCP bridge with an explicit JSON config blob.

    AgentDojo's current runner hands the agent an `agentdojo.mcp_server`
    command in env-json mode. We rewrite that onto the local benchmark MCP
    bridge so mlld still gets the extra workspace helper tools, date-shift
    behavior, and phase-state attribution hooks.

    Linux execve has a per-arg cap of ~128KB (MAX_ARG_STRLEN). AgentDojo's
    env_json can exceed that for large suites, so the config is written to
    a temp file and passed by path instead of base64-on-argv.
    """
    script_resolved = _resolve_mcp_script(config)
    if script_resolved.parent.name == "agentdojo-mcp":
        config = {
            **config,
            "extension_paths": [str(SRC_DIR)],
            "extensions": ["bench_mcp_extras"],
        }
    cfg_fd, cfg_path = tempfile.mkstemp(suffix=".json", prefix="mcp_cfg_")
    with os.fdopen(cfg_fd, "w") as f:
        json.dump(config, f)
    project_dir = shlex.quote(str(CLEAN_BENCH_PROJECT_DIR))
    script_path = shlex.quote(str(script_resolved))
    return f"uv run --project {project_dir} python3 {script_path} --config-file {shlex.quote(cfg_path)}"


def _decode_runner_mcp_command(mcp_server_cmd: str) -> dict[str, Any] | None:
    """Extract AgentDojo's base64 config payload from the runner command."""
    try:
        parts = shlex.split(mcp_server_cmd)
        if not parts:
            return None
        payload = parts[-1]
        data = json.loads(base64.b64decode(payload))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _parse_iso_ts(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _has_target_signal(patch: dict | None) -> bool:
    if not isinstance(patch, dict):
        return False
    trusted = patch.get("trusted")
    created_refs = patch.get("created_refs")
    write_context = patch.get("write_context")
    comparison_data = patch.get("comparison_data")
    if isinstance(trusted, dict) and trusted:
        return True
    if isinstance(created_refs, dict) and created_refs:
        return True
    if isinstance(write_context, dict) and write_context:
        return True
    return comparison_data is not None


def _has_successful_write(patch: dict | None) -> bool:
    if not isinstance(patch, dict):
        return False
    results = patch.get("execution_results")
    if not isinstance(results, list):
        return False
    return any(isinstance(entry, dict) and entry.get("status") == "succeeded" for entry in results)


def _build_phase_metrics(debug_info: dict | None, phase_events: list[dict], mcp_calls: list[dict], final_output: str) -> dict:
    debug_info = debug_info if isinstance(debug_info, dict) else {}
    step_history = debug_info.get("step_history")
    if not isinstance(step_history, list):
        step_history = []
    planner_steps = debug_info.get("planner_steps")
    if not isinstance(planner_steps, list):
        planner_steps = []

    phase_counts = Counter()
    planner_iterations = 0
    for event in phase_events:
        if not isinstance(event, dict):
            continue
        if event.get("event") == "phase_start" and isinstance(event.get("phase"), str):
            phase_counts[event["phase"]] += 1
        if event.get("event") in {"planner_step", "planner_iteration"}:
            planner_iterations += 1

    if not phase_counts:
        for entry in step_history:
            if isinstance(entry, dict) and isinstance(entry.get("kind"), str):
                phase_counts[entry["kind"]] += 1

    if planner_iterations == 0:
        planner_iterations = len(planner_steps) if planner_steps else debug_info.get("iteration_count", 0)

    open_phases: dict[str, dict] = {}
    phase_intervals: list[dict] = []
    for index, event in enumerate(phase_events):
        if not isinstance(event, dict):
            continue
        phase_id = event.get("phase_id")
        if not isinstance(phase_id, str) or not phase_id:
            phase_name = event.get("phase") if isinstance(event.get("phase"), str) else "unknown"
            phase_id = f"{phase_name}:{index}"
        tag = event.get("event")
        if tag == "phase_start":
            open_phases[phase_id] = {
                "phase": event.get("phase") if isinstance(event.get("phase"), str) else "unknown",
                "start_ts": _parse_iso_ts(event.get("ts")),
                "start_index": index,
            }
        elif tag == "phase_end":
            start = open_phases.pop(phase_id, None)
            if not start:
                continue
            phase_intervals.append({
                "phase": start["phase"],
                "start_ts": start["start_ts"],
                "end_ts": _parse_iso_ts(event.get("ts")),
                "start_index": start["start_index"],
                "end_index": index,
            })

    phase_intervals.sort(key=lambda item: (item["start_ts"] is None, item["start_ts"], item["start_index"]))

    mcp_calls_by_phase = Counter()
    mcp_tools_by_phase: dict[str, Counter] = defaultdict(Counter)
    unattributed = 0
    for call in mcp_calls:
        if not isinstance(call, dict):
            continue
        phase_name = "unattributed"
        explicit_phase = call.get("phase")
        if isinstance(explicit_phase, str) and explicit_phase:
            phase_name = explicit_phase
        call_ts = _parse_iso_ts(call.get("ts"))
        if phase_name == "unattributed" and call_ts is not None:
            for interval in phase_intervals:
                start_ts = interval["start_ts"]
                end_ts = interval["end_ts"]
                if start_ts is None or end_ts is None:
                    continue
                if start_ts <= call_ts <= end_ts:
                    phase_name = interval["phase"]
                    break
        if phase_name == "unattributed":
            unattributed += 1
        mcp_calls_by_phase[phase_name] += 1
        tool_name = call.get("tool")
        if isinstance(tool_name, str) and tool_name:
            mcp_tools_by_phase[phase_name][tool_name] += 1

    compose_index = next(
        (idx for idx, entry in enumerate(step_history)
         if isinstance(entry, dict) and entry.get("kind") == "compose"),
        len(step_history),
    )
    pre_compose = step_history[:compose_index]
    found_target_before_final_answer = any(
        isinstance(entry, dict) and _has_target_signal(entry.get("state_patch"))
        for entry in pre_compose
    )
    successful_write_before_final_answer = any(
        isinstance(entry, dict) and _has_successful_write(entry.get("state_patch"))
        for entry in pre_compose
    )
    object_like_final_output = (
        isinstance(final_output, str)
        and final_output.lstrip().startswith("{")
        and '"content"' in final_output[:200]
    )
    compose_reached = phase_counts.get("compose", 0) > 0 or compose_index < len(step_history)

    return {
        "planner_iterations": planner_iterations,
        "step_history_count": len(step_history),
        "phase_counts": dict(phase_counts),
        "phase_event_count": len(phase_events),
        "mcp_calls_by_phase": dict(mcp_calls_by_phase),
        "mcp_tools_by_phase": {
            phase: dict(counter)
            for phase, counter in mcp_tools_by_phase.items()
        },
        "unattributed_mcp_calls": unattributed,
        "found_target_before_final_answer": found_target_before_final_answer,
        "successful_write_before_final_answer": successful_write_before_final_answer,
        "compose_reached": compose_reached,
        "object_like_final_output": object_like_final_output,
    }


def _extract_session_ids(
    debug_info: dict | None,
    phase_events: list[dict] | None = None,
) -> tuple[str | None, list[str]]:
    debug_info = debug_info if isinstance(debug_info, dict) else {}
    phase_events = phase_events if isinstance(phase_events, list) else []
    execution_log = debug_info.get("execution_log")
    if not isinstance(execution_log, list):
        execution_log = []

    first_planner_session_id = None
    session_ids: list[str] = []
    seen: set[str] = set()

    def remember(session_id: str | None) -> None:
        if isinstance(session_id, str) and session_id and session_id not in seen:
            seen.add(session_id)
            session_ids.append(session_id)

    for entry in phase_events:
        if not isinstance(entry, dict):
            continue
        planner_session_id = entry.get("planner_session_id")
        if (
            first_planner_session_id is None
            and isinstance(planner_session_id, str)
            and planner_session_id
        ):
            first_planner_session_id = planner_session_id
        remember(planner_session_id)
        remember(entry.get("worker_session_id"))

    for entry in execution_log:
        if not isinstance(entry, dict):
            continue
        planner_session_id = entry.get("planner_session_id")
        if (
            first_planner_session_id is None
            and isinstance(planner_session_id, str)
            and planner_session_id
        ):
            first_planner_session_id = planner_session_id
        remember(planner_session_id)
        remember(entry.get("worker_session_id"))
        remember(entry.get("session_id"))

    top_level_session = first_planner_session_id or (session_ids[0] if session_ids else None)
    return top_level_session, session_ids


def _parse_best_json_object(raw_output: str) -> dict | None:
    if not isinstance(raw_output, str):
        return None
    decoder = json.JSONDecoder()
    best = None
    best_score = -1
    start = raw_output.find("{")
    while start != -1:
        try:
            parsed, _end = decoder.raw_decode(raw_output[start:])
            if isinstance(parsed, dict):
                score = 0
                if "content" in parsed:
                    score += 4
                if isinstance(parsed.get("debug"), dict):
                    score += 3
                if "worker" in parsed:
                    score += 1
                score += min(len(parsed), 4)
                if score > best_score:
                    best = parsed
                    best_score = score
        except json.JSONDecodeError:
            pass
        start = raw_output.find("{", start + 1)
    return best


def _unwrap_content_object(value: str) -> str:
    """Recursively unwrap object-like `{"content": ...}` strings when models leak them."""
    content = value if isinstance(value, str) else str(value)
    for _ in range(3):
        stripped = content.lstrip()
        if not stripped.startswith("{") or '"content"' not in stripped[:400]:
            break
        parsed = None
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = _parse_best_json_object(stripped)
        if not isinstance(parsed, dict) or "content" not in parsed:
            break
        next_content = str(parsed.get("content", content))
        if next_content == content:
            break
        content = next_content
    return content


def _is_provider_auth_error(content: str | None) -> bool:
    if not isinstance(content, str):
        return False
    lowered = content.lower()
    return (
        "not logged in" in lowered
        or "please run /login" in lowered
        or "login required" in lowered
        or "authentication required" in lowered
        or "not authenticated" in lowered
    )


def _is_request_timeout_error(content: str | None) -> bool:
    if not isinstance(content, str):
        return False
    lowered = content.lower()
    return "request timeout after" in lowered or "timed out after" in lowered


def _is_provider_rate_limit_error(content: str | None) -> bool:
    if not isinstance(content, str):
        return False
    lowered = content.lower()
    return (
        "rate limit" in lowered
        or "rate_limit" in lowered
        or "too many requests" in lowered
        or "statuscode\":429" in lowered
        or "status code: 429" in lowered
    )


def _provider_auth_error_from_llm_calls(entries: list[dict] | None) -> str | None:
    if not isinstance(entries, list):
        return None
    for entry in reversed(entries):
        if not isinstance(entry, dict):
            continue
        for candidate in (entry.get("raw"), entry.get("parsed")):
            if _is_provider_auth_error(candidate):
                return str(candidate)
    return None


def _provider_rate_limit_error_from_llm_calls(entries: list[dict] | None) -> str | None:
    if not isinstance(entries, list):
        return None
    for entry in reversed(entries):
        if not isinstance(entry, dict):
            continue
        for candidate in (entry.get("raw"), entry.get("parsed")):
            if _is_provider_rate_limit_error(candidate):
                return str(candidate)
    return None


@contextmanager
def _locked_log_path(log_path: Path):
    lock_path = log_path.with_name(f"{log_path.name}.lock")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


class MlldAgent:
    """AgentDojo agent backed by mlld. Full loop in mlld via MCP tools."""

    name = "claude-3-5-sonnet-20241022"

    _MODEL_NAMES = {
        "sonnet": "claude-3-5-sonnet-20241022",
        "haiku": "claude-3-5-haiku-20241022",
        "opus": "claude-opus-4-5",
    }
    _SDK_SOURCE_PATH = str(Path(inspect.getfile(mlld_sdk)).resolve())

    def __init__(
        self,
        *,
        model: str = "sonnet",
        fast_model: str | None = None,
        harness: str | None = None,
        working_dir: str | None = None,
        timeout: float = 900.0,
        debug: bool = False,
        env_name: str = "workspace",
        defense: str = "undefended",
        attack: str | None = None,
        injection_task_id: str | None = None,
        run_log_path: str | None = None,
    ):
        self._model = model
        self._fast_model = fast_model
        self._harness = harness
        self.name = self._MODEL_NAMES.get(model, model)
        self._working_dir = working_dir or str(ROOT_DIR)
        self._timeout = timeout
        self._debug = debug
        self._env_name = env_name
        self._defense = defense
        self._attack = attack
        self._injection_task_id = injection_task_id
        self._run_log_path = Path(run_log_path).expanduser() if run_log_path else None
        heap = os.environ.get("MLLD_HEAP", None)
        heap_snapshot_near_limit = os.environ.get("MLLD_HEAP_SNAPSHOT_NEAR_LIMIT")
        heap_snapshot_count = None
        if heap_snapshot_near_limit:
            try:
                heap_snapshot_count = int(heap_snapshot_near_limit)
            except ValueError as error:
                raise ValueError("MLLD_HEAP_SNAPSHOT_NEAR_LIMIT must be a positive integer") from error
            if heap_snapshot_count <= 0:
                raise ValueError("MLLD_HEAP_SNAPSHOT_NEAR_LIMIT must be a positive integer")
        self._client = Client(
            timeout=self._timeout,
            working_dir=self._working_dir,
            heap=heap,
            heap_snapshot_near_limit=heap_snapshot_count,
        )

    def run(
        self,
        query: str,
        mcp_server_cmd: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> AgentResult:
        runner_mcp_config = _decode_runner_mcp_command(mcp_server_cmd) or {}

        state_file = runner_mcp_config.get("state_file")
        if not isinstance(state_file, str) or not state_file:
            state_fd, state_file = tempfile.mkstemp(suffix=".json", prefix="mcp_env_")
            os.close(state_fd)
            runner_mcp_config["state_file"] = state_file

        mcp_log_file = runner_mcp_config.get("log_file")
        if not isinstance(mcp_log_file, str) or not mcp_log_file:
            log_fd, mcp_log_file = tempfile.mkstemp(suffix=".jsonl", prefix="mcp_log_")
            os.close(log_fd)
            runner_mcp_config["log_file"] = mcp_log_file

        runner_mcp_config.setdefault("suite_name", self._env_name)
        runner_mcp_config.setdefault("env_name", self._env_name)
        runner_mcp_config.setdefault("benchmark_version", "v1.1.1")

        phase_fd, phase_log_file = tempfile.mkstemp(suffix=".jsonl", prefix="phase_log_")
        os.close(phase_fd)
        llm_log_fd, llm_call_log_file = tempfile.mkstemp(suffix=".jsonl", prefix="llm_call_log_")
        os.close(llm_log_fd)
        phase_state_fd, phase_state_file = tempfile.mkstemp(suffix=".json", prefix="phase_state_")
        os.close(phase_state_fd)
        exec_log_fd, execution_log_file = tempfile.mkstemp(suffix=".jsonl", prefix="exec_log_")
        os.close(exec_log_fd)
        runner_mcp_config["phase_state_file"] = phase_state_file

        task_id = getattr(self, "_current_task_id", "user_task_0")
        attestation_scope = f"{self._env_name}:{task_id}:{self._injection_task_id or 'benign'}:{uuid.uuid4().hex}"
        attested_resources = _collect_attested_resources(self._env_name, task_id, query, attestation_scope)
        mcp_command = _build_local_mcp_command(runner_mcp_config)

        payload = {
            "query": query,
            "model": self._model,
            "defense": self._defense,
            "env_name": self._env_name,
            "task_id": task_id,
            "phase_log_file": phase_log_file,
            "phase_state_file": phase_state_file,
            "llm_call_log_file": llm_call_log_file,
            "execution_log_file": execution_log_file,
            "log_llm_calls": bool(self._debug),
            "attestation_scope": attestation_scope,
            "attested_resources": attested_resources,
        }
        if self._fast_model:
            payload["worker_model"] = self._fast_model
        if self._harness:
            payload["harness"] = self._harness
        if tools is not None:
            payload["tool_count"] = len(tools)

        if self._debug:
            print(
                f"[mlld] running {_agent_entrypoint(self._env_name)}:"
                f" env={self._env_name} defense={self._defense}"
                f" model={self._model} task={task_id}",
                file=sys.stderr,
            )

        task_log = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "log_entry_id": uuid.uuid4().hex,
            "task_id": task_id,
            "injection_task_id": self._injection_task_id,
            "query": query,
            "model": self._model,
            "defense": self._defense,
            "attack": self._attack,
            "sdk_path": self._SDK_SOURCE_PATH,
            "outcome": None,
            "final_output": None,
        }

        execute_error_str: str | None = None
        trace_level = os.environ.get("MLLD_TRACE")
        trace_file_path = os.environ.get("MLLD_TRACE_FILE")
        try:
            if self._debug:
                print(f"[mlld] python sdk: {self._SDK_SOURCE_PATH}", file=sys.stderr)
                if trace_level:
                    print(f"[mlld] trace: level={trace_level} file={trace_file_path}", file=sys.stderr)
            execute_kwargs = {
                "timeout": self._timeout,
                "mcp_servers": {"tools": mcp_command},
            }
            if trace_level:
                execute_kwargs["trace"] = trace_level
            if trace_file_path:
                execute_kwargs["trace_file"] = trace_file_path
            if os.environ.get("MLLD_TRACE_MEMORY"):
                execute_kwargs["trace_memory"] = True
            result = self._client.execute(
                _agent_entrypoint(self._env_name),
                payload,
                **execute_kwargs,
            )
            raw_output = (result.output or "").strip()
            denials = result.denials if hasattr(result, "denials") else []

            if self._debug:
                for eff in (result.effects or []):
                    if eff.type == "stderr" and eff.content:
                        for line in eff.content.strip().split("\n"):
                            print(f"  {line}", file=sys.stderr)
        except Exception as e:
            err_str = str(e)
            execute_error_str = err_str
            task_log["execute_error"] = err_str[:2000]
            if self._debug:
                print(f"[mlld] execute error: {err_str[:500]}", file=sys.stderr)
            raw_output = ""
            denials = []

        if self._debug:
            print(f"[mlld] raw output: {raw_output[:500]}", file=sys.stderr)
            if denials:
                for d in denials:
                    print(f"[mlld] DENIAL: {d}", file=sys.stderr)

        mcp_log_entries = []
        phase_events = []
        llm_call_entries = []
        try:
            mcp_log_path = Path(mcp_log_file)
            if mcp_log_path.exists() and mcp_log_path.stat().st_size > 0:
                mcp_log_entries = _load_jsonl(mcp_log_path)
                task_log["mcp_calls"] = mcp_log_entries
                if self._debug:
                    for entry in mcp_log_entries:
                        err = " ERROR" if entry.get("error") else ""
                        print(f"[mcp] {entry.get('tool','?')}({json.dumps(entry.get('args',{}))[:60]}){err}", file=sys.stderr)
            phase_log_path = Path(phase_log_file)
            if phase_log_path.exists() and phase_log_path.stat().st_size > 0:
                phase_events = _load_jsonl(phase_log_path)
                task_log["phase_events"] = phase_events
            llm_log_path = Path(llm_call_log_file)
            if llm_log_path.exists() and llm_log_path.stat().st_size > 0:
                llm_call_entries = _load_jsonl(llm_log_path)
                task_log["llm_calls"] = llm_call_entries
        except Exception:
            pass
        finally:
            try:
                os.unlink(phase_log_file)
            except OSError:
                pass
            try:
                os.unlink(llm_call_log_file)
            except OSError:
                pass
            try:
                os.unlink(phase_state_file)
            except OSError:
                pass
            try:
                os.unlink(execution_log_file)
            except OSError:
                pass

        nothing_fired = (
            not raw_output
            and not mcp_log_entries
            and not llm_call_entries
            and not phase_events
        )
        if execute_error_str is not None and nothing_fired:
            task_log["outcome"] = "infrastructure_error"
            task_log["final_output"] = None
            task_log["utility"] = None
            task_log["security"] = None
            self._last_task_log = task_log
            self._last_log_entry_id = task_log["log_entry_id"]
            if self._run_log_path:
                log_path = self._run_log_path
            else:
                log_dir = AGENT_DIR.parent / "results" / self._model / self._env_name
                log_dir.mkdir(parents=True, exist_ok=True)
                suffix = self._defense
                if self._attack:
                    suffix = f"{self._defense}.atk_{self._attack}"
                log_path = log_dir / f"{suffix}.jsonl"
            self._last_log_path = log_path
            with _locked_log_path(log_path):
                with open(log_path, "a") as f:
                    f.write(json.dumps(task_log, default=str) + "\n")
            raise MlldInfrastructureError(
                f"mlld agent did not run (no MCP/LLM calls, no output): "
                f"{execute_error_str[:500]}"
            )

        provider_auth_error = None
        if _is_provider_auth_error(execute_error_str):
            provider_auth_error = execute_error_str
        elif _is_provider_auth_error(raw_output):
            provider_auth_error = raw_output
        else:
            provider_auth_error = _provider_auth_error_from_llm_calls(llm_call_entries)

        if provider_auth_error:
            task_log["execute_error"] = str(provider_auth_error)[:2000]
            task_log["outcome"] = "infrastructure_error"
            task_log["final_output"] = None
            task_log["utility"] = None
            task_log["security"] = None
            self._last_task_log = task_log
            self._last_log_entry_id = task_log["log_entry_id"]
            if self._run_log_path:
                log_path = self._run_log_path
            else:
                log_dir = AGENT_DIR.parent / "results" / self._model / self._env_name
                log_dir.mkdir(parents=True, exist_ok=True)
                suffix = self._defense
                if self._attack:
                    suffix = f"{self._defense}.atk_{self._attack}"
                log_path = log_dir / f"{suffix}.jsonl"
            self._last_log_path = log_path
            with _locked_log_path(log_path):
                with open(log_path, "a") as f:
                    f.write(json.dumps(task_log, default=str) + "\n")
            raise MlldInfrastructureError(
                f"Provider authentication failed before the agent could run cleanly: "
                f"{str(provider_auth_error)[:500]}"
            )

        provider_runtime_error = None
        if _is_request_timeout_error(execute_error_str):
            provider_runtime_error = execute_error_str
        elif _is_provider_rate_limit_error(execute_error_str):
            provider_runtime_error = execute_error_str
        elif _is_provider_rate_limit_error(raw_output):
            provider_runtime_error = raw_output
        else:
            provider_runtime_error = _provider_rate_limit_error_from_llm_calls(llm_call_entries)

        if provider_runtime_error:
            task_log["execute_error"] = str(provider_runtime_error)[:2000]
            task_log["outcome"] = "infrastructure_error"
            task_log["final_output"] = None
            task_log["utility"] = None
            task_log["security"] = None
            self._last_task_log = task_log
            self._last_log_entry_id = task_log["log_entry_id"]
            if self._run_log_path:
                log_path = self._run_log_path
            else:
                log_dir = AGENT_DIR.parent / "results" / self._model / self._env_name
                log_dir.mkdir(parents=True, exist_ok=True)
                suffix = self._defense
                if self._attack:
                    suffix = f"{self._defense}.atk_{self._attack}"
                log_path = log_dir / f"{suffix}.jsonl"
            self._last_log_path = log_path
            with _locked_log_path(log_path):
                with open(log_path, "a") as f:
                    f.write(json.dumps(task_log, default=str) + "\n")
            raise MlldInfrastructureError(
                f"Provider/runtime did not complete the agent run cleanly: "
                f"{str(provider_runtime_error)[:500]}"
            )

        content = "Task completed."
        output = None
        try:
            output = json.loads(raw_output)
        except json.JSONDecodeError:
            output = _parse_best_json_object(raw_output)

        if isinstance(output, dict):
            content = str(output.get("content", raw_output))
            debug_info = output.get("debug")
            if isinstance(debug_info, dict):
                task_log["debug"] = debug_info
                for key in ("execution_log", "planner_iterations", "last_decision"):
                    value = debug_info.get(key)
                    if value is not None:
                        task_log[key] = value
                if not phase_events:
                    fallback_phase_events = debug_info.get("phase_events")
                    if isinstance(fallback_phase_events, list):
                        phase_events = fallback_phase_events
                        task_log["phase_events"] = fallback_phase_events
                session_id, session_ids = _extract_session_ids(debug_info, phase_events)
                if session_id:
                    task_log["session_id"] = session_id
                if session_ids:
                    task_log["session_ids"] = session_ids
            if output.get("blocked"):
                task_log["blocked"] = True
            task_log["outcome"] = "response"
        else:
            content = raw_output if raw_output else "Task completed."
            task_log["outcome"] = "unparseable"

        content = _unwrap_content_object(content)

        if "hit your limit" in content.lower() or "rate limit" in content.lower():
            raise RuntimeError(f"Rate limited: {content[:200]}")

        task_log["final_output"] = content[:2000]
        task_log["policy_denials"] = len(denials) if denials else 0
        task_log["total_steps"] = len(mcp_log_entries)
        task_log["metrics"] = _build_phase_metrics(task_log.get("debug"), phase_events, mcp_log_entries, content)
        if self._run_log_path:
            log_path = self._run_log_path
        else:
            log_dir = AGENT_DIR.parent / "results" / self._model / self._env_name
            log_dir.mkdir(parents=True, exist_ok=True)
            suffix = self._defense
            if self._attack:
                suffix = f"{self._defense}.atk_{self._attack}"
            log_path = log_dir / f"{suffix}.jsonl"
        self._last_task_log = task_log
        self._last_log_entry_id = task_log["log_entry_id"]
        self._last_log_path = log_path
        with _locked_log_path(log_path):
            with open(log_path, "a") as f:
                f.write(json.dumps(task_log, default=str) + "\n")

        tool_calls = [
            ToolCallRecord(
                function=str(entry.get("tool", "")),
                args=entry.get("args", {}) if isinstance(entry.get("args"), dict) else {},
                result=str(entry.get("result", ""))[:500] or None,
                error=str(entry.get("result", ""))[:500] if entry.get("error") else None,
            )
            for entry in mcp_log_entries
        ]

        return AgentResult(
            content=content,
            tool_calls=tool_calls,
            metadata=task_log,
        )

    def update_verdict(self, utility: bool, security: bool) -> None:
        """Patch the last JSONL log entry with utility/security verdicts.

        Refuses to overwrite an infrastructure_error outcome — see b-e8e4.
        Late callers should not be able to upgrade a non-run into a graded run.
        """
        if (
            not hasattr(self, "_last_log_path")
            or not hasattr(self, "_last_task_log")
            or not hasattr(self, "_last_log_entry_id")
        ):
            return
        if self._last_task_log.get("outcome") == "infrastructure_error":
            return
        self._last_task_log["utility"] = utility
        self._last_task_log["security"] = security
        log_path = self._last_log_path
        try:
            with _locked_log_path(log_path):
                if not log_path.exists():
                    return
                lines = [line for line in log_path.read_text().splitlines() if line.strip()]
                for idx in range(len(lines) - 1, -1, -1):
                    entry = json.loads(lines[idx])
                    if entry.get("log_entry_id") == self._last_log_entry_id:
                        lines[idx] = json.dumps(self._last_task_log, default=str)
                        break
                else:
                    return

                tmp_path = log_path.with_name(
                    f".{log_path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
                )
                tmp_path.write_text("\n".join(lines) + "\n")
                tmp_path.replace(log_path)
        except Exception:
            pass

    def close(self) -> None:
        self._client.close()
