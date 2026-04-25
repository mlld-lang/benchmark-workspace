"""MCP server wrapping AgentDojo tools.

Launched as a subprocess by mlld's `import tools from mcp` mechanism.
Reads a JSON config blob from argv[1] (base64-encoded) containing:
  - env_name: which AgentDojo suite to load
  - task_id: which task's environment to use
  - state_file: path to write serialized env state on shutdown
  - attack: optional attack type
  - injection_task_id: optional injection task index

The server exposes each AgentDojo tool as an MCP tool, handling arg coercion
at the boundary. The mlld script calls tools directly; results get src:mcp
taint automatically.

On shutdown, the server writes the modified env to state_file so the host
can read back side effects (sent emails, created files, etc.) for
AgentDojo's evaluation.

Usage (by mlld):
  import tools from mcp "uv run --project clean/bench python3 clean/src/mcp_server.py <config_b64>"
"""

from __future__ import annotations

import asyncio
import atexit
import base64
import importlib
import json
import os
import re
import signal
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_AGENTDOJO_SRC = REPO_ROOT / "agentdojo" / "src"
if LOCAL_AGENTDOJO_SRC.exists():
    sys.path.insert(0, str(LOCAL_AGENTDOJO_SRC))

from agentdojo.functions_runtime import FunctionReturnType, FunctionsRuntime
from agentdojo.task_suite import get_suite
from date_shift import REFERENCE_DATE, compute_offset
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server


def _prepare_for_yaml(data: Any) -> Any:
    """Convert types that yaml.safe_dump would mangle before serialization.

    - datetime → "YYYY-MM-DD HH:MM" string (prevents mlld JS Date timezone shift)
    - date → "YYYY-MM-DD" string
    - shared_with permission maps → ["email1", "email2"] so records can treat
      each shared email as a separate fact-bearing value
    """
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if k == "shared_with" and isinstance(v, dict) and all(isinstance(vv, str) for vv in v.values()):
                result[k] = list(v.keys())
            else:
                result[k] = _prepare_for_yaml(v)
        return result
    elif isinstance(data, list):
        return [_prepare_for_yaml(item) for item in data]
    elif isinstance(data, datetime):
        return data.strftime("%Y-%m-%d %H:%M")
    elif isinstance(data, date):
        return data.strftime("%Y-%m-%d")
    return data


def _yaml_dump(data: Any) -> str:
    return yaml.safe_dump(_prepare_for_yaml(data), default_flow_style=False)


def tool_result_to_str(tool_result: FunctionReturnType, dump_fn=_yaml_dump) -> str:
    """Format an AgentDojo tool result using the local YAML dumper."""
    if isinstance(tool_result, BaseModel):
        return dump_fn(tool_result.model_dump()).strip()

    if isinstance(tool_result, list):
        rendered: list[Any] = []
        for item in tool_result:
            if type(item) in [str, int, float, bool] or item is None:
                rendered.append(item)
            elif isinstance(item, BaseModel):
                rendered.append(item.model_dump())
            else:
                raise TypeError(f"Not valid type for item tool result: {type(item)}")
        return dump_fn(rendered).strip()

    if isinstance(tool_result, dict):
        return dump_fn(tool_result).strip()

    return str(tool_result)


def _resolve_type(qualified_name: str) -> type:
    module_path, class_name = qualified_name.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _coerce_tool_args(runtime: FunctionsRuntime, tool_name: str, tool_args: dict) -> dict:
    """Fix common LLM mistakes at the boundary between LLM output and AgentDojo schemas."""
    fn = runtime.functions.get(tool_name)
    if fn is None:
        return tool_args

    schema = fn.parameters.model_json_schema()
    props = schema.get("properties", {})
    coerced = dict(tool_args)

    for param_name, value in coerced.items():
        if value == "null":
            coerced[param_name] = None
            continue

        # Normalize datetime strings: strip seconds, replace T with space
        # (AgentDojo expects "%Y-%m-%d %H:%M")
        if isinstance(value, str) and re.match(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?$", value):
            coerced[param_name] = value.replace("T", " ")[:16]
            value = coerced[param_name]

        spec = props.get(param_name, {})
        is_array = spec.get("type") == "array"
        if not is_array and "anyOf" in spec:
            is_array = any(s.get("type") == "array" for s in spec["anyOf"])

        if is_array and isinstance(value, str):
            if "," in value:
                coerced[param_name] = [v.strip() for v in value.split(",") if v.strip()]
            else:
                coerced[param_name] = [value]

        if is_array and isinstance(value, list) and value and isinstance(value[0], str):
            item_spec = spec.get("items", {})
            if not item_spec and "anyOf" in spec:
                for s_opt in spec["anyOf"]:
                    if s_opt.get("type") == "array":
                        item_spec = s_opt.get("items", {})
            if item_spec.get("type") == "object":
                coerced[param_name] = [{"type": "file", "file_id": v} for v in value]

        if is_array and isinstance(value, list) and value and isinstance(value[0], dict):
            item_spec = spec.get("items", {})
            if not item_spec and "anyOf" in spec:
                for s_opt in spec["anyOf"]:
                    if s_opt.get("type") == "array":
                        item_spec = s_opt.get("items", {})
            if item_spec.get("type") == "object":
                normalized_items = []
                changed = False
                for item in value:
                    if not isinstance(item, dict):
                        normalized_items.append(item)
                        continue
                    file_id = item.get("file_id") or item.get("id") or item.get("id_")
                    if isinstance(file_id, str) and file_id:
                        normalized_items.append({"type": "file", "file_id": file_id})
                        changed = True
                    else:
                        normalized_items.append(item)
                if changed:
                    coerced[param_name] = normalized_items

    return coerced


def _extra_tools(env: Any) -> list[types.Tool]:
    tools: list[types.Tool] = []
    if hasattr(env, "inbox") and hasattr(env.inbox, "emails"):
        tools.append(types.Tool(
            name="get_email_by_id",
            description="Retrieve a specific email by ID with full content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "Exact email id to retrieve."
                    }
                },
                "required": ["email_id"]
            },
        ))
        tools.append(types.Tool(
            name="search_emails_any_sender",
            description="Search inbox emails across any sender and return matching email metadata.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to match against sender, subject, and body."
                    }
                },
                "required": ["query"]
            },
        ))
    tools.append(types.Tool(
        name="get_current_datetime",
        description="Return the current local datetime in YYYY-MM-DD HH:MM format.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ))
    return tools


def _build_tools(runtime: FunctionsRuntime, env: Any) -> list[types.Tool]:
    """Convert AgentDojo runtime functions to MCP Tool definitions."""
    tools = []
    for fn in runtime.functions.values():
        schema = fn.parameters.model_json_schema()
        schema.pop("title", None)
        for prop in schema.get("properties", {}).values():
            prop.pop("title", None)
        tools.append(types.Tool(
            name=fn.name,
            description=fn.description or "",
            inputSchema=schema,
        ))
    tools.extend(_extra_tools(env))
    return tools


def _sync_runtime_state(env: Any) -> None:
    """Sync runtime dicts back to initial_* lists for serialization.

    AgentDojo models use @model_validator to rebuild events/emails/files
    dicts from initial_* lists on deserialization. Runtime mutations
    (create_event, send_email, create_file, etc.) modify the dicts but
    not the initial_* lists, so they'd be lost in a round-trip.

    Also syncs contact_list — send_email auto-adds new contacts for
    unknown recipients, and this mutation must survive serialization.
    """
    if hasattr(env, 'calendar') and hasattr(env.calendar, 'initial_events'):
        env.calendar.initial_events = list(env.calendar.events.values())
    if hasattr(env, 'inbox') and hasattr(env.inbox, 'initial_emails'):
        env.inbox.initial_emails = list(env.inbox.emails.values())
    if hasattr(env, 'cloud_drive') and hasattr(env.cloud_drive, 'initial_files'):
        env.cloud_drive.initial_files = list(env.cloud_drive.files.values())


def create_server(
    runtime: FunctionsRuntime,
    env: Any,
    env_type: type,
    state_file: str | None,
    log_file: str | None = None,
    phase_state_file: str | None = None,
) -> Server:
    """Create an MCP server wrapping AgentDojo tools.

    After each tool call that modifies state, the env is serialized to state_file
    so the host can read back side effects.
    """
    server = Server("agentdojo-tools")
    tools = _build_tools(runtime, env)

    def _log(entry: dict):
        if log_file:
            try:
                with open(log_file, "a") as f:
                    f.write(json.dumps(entry, default=str) + "\n")
            except Exception:
                pass

    def _save_state():
        if state_file:
            try:
                # Sync runtime state to initial_* lists so model_validate_json()
                # reconstructs correctly (pydantic validators rebuild from initial_*)
                _sync_runtime_state(env)
                Path(state_file).write_text(env.model_dump_json())
            except Exception as e:
                print(f"Failed to save state: {e}", file=sys.stderr)

    def _read_phase_state() -> dict[str, Any]:
        if not phase_state_file:
            return {}
        try:
            path = Path(phase_state_file)
            if not path.exists() or path.stat().st_size == 0:
                return {}
            data = json.loads(path.read_text())
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return tools

    _call_count = [0]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
        _call_count[0] += 1
        call_num = _call_count[0]
        t0 = time.monotonic()
        print(f"[mcp-heartbeat] pid={os.getpid()} call={call_num} tool={name} start={datetime.now(timezone.utc).isoformat()}", file=sys.stderr, flush=True)
        arguments = arguments or {}
        coerced = _coerce_tool_args(runtime, name, arguments)
        try:
            if name == "get_email_by_id":
                email_id = str(coerced.get("email_id", ""))
                emails = getattr(getattr(env, "inbox", None), "emails", None)
                if not isinstance(emails, dict):
                    raise ValueError("Inbox emails not available.")
                email = emails.get(email_id)
                if email is None:
                    raise ValueError(f"Email with ID '{email_id}' not found.")
                payload = email.model_dump() if hasattr(email, "model_dump") else email
                if isinstance(payload, dict):
                    payload.pop("status", None)
                result_text = _yaml_dump(payload)
            elif name == "search_emails_any_sender":
                query = str(coerced.get("query", "")).strip().lower()
                emails = getattr(getattr(env, "inbox", None), "emails", None)
                if not isinstance(emails, dict):
                    raise ValueError("Inbox emails not available.")
                if not query:
                    raise ValueError("Query is required.")

                query_terms = [term for term in re.split(r"[^a-z0-9]+", query) if len(term) >= 3]
                if not query_terms:
                    query_terms = [query]

                matches: list[tuple[int, str, dict[str, Any]]] = []
                for email in emails.values():
                    payload = email.model_dump() if hasattr(email, "model_dump") else email
                    if not isinstance(payload, dict):
                        continue
                    text_parts: list[str] = []
                    for field in ("sender", "subject", "body"):
                        value = payload.get(field)
                        if isinstance(value, str):
                            text_parts.append(value.lower())
                    for field in ("recipients", "cc", "bcc"):
                        value = payload.get(field)
                        if isinstance(value, list):
                            text_parts.extend(str(item).lower() for item in value)
                    haystack = "\n".join(text_parts)
                    if not haystack:
                        continue
                    score = 0
                    if query in haystack:
                        score += 10
                    score += sum(1 for term in query_terms if term in haystack)
                    if score <= 0:
                        continue
                    payload = dict(payload)
                    payload.pop("status", None)
                    matches.append((score, str(payload.get("timestamp", "")), payload))

                if not matches:
                    raise ValueError("No emails found. Try with a different query.")

                matches.sort(key=lambda item: (item[0], item[1]), reverse=True)
                result_text = _yaml_dump([payload for _, _, payload in matches[:10]])
            elif name == "get_current_datetime":
                result_text = f"{(REFERENCE_DATE + compute_offset()):%Y-%m-%d} 08:00"
            else:
                tool_result, error = runtime.run_function(env, name, coerced)
                if isinstance(tool_result, dict):
                    formatted = _yaml_dump(tool_result)
                else:
                    formatted = tool_result_to_str(tool_result, dump_fn=_yaml_dump)
                if error:
                    result_text = f"ERROR: {error}\n{formatted}"
                else:
                    result_text = formatted
        except Exception as e:
            result_text = f"ERROR: {e}"

        phase_state = _read_phase_state()
        _log({
            "ts": datetime.now(timezone.utc).isoformat(),
            "tool": name,
            "args": arguments,
            "coerced": {k: v for k, v in coerced.items() if arguments.get(k) != v},
            "result": result_text[:500],
            "error": bool("ERROR" in result_text[:6]),
            "phase": phase_state.get("phase"),
            "phase_id": phase_state.get("phase_id"),
            "phase_iteration": phase_state.get("iteration"),
        })
        _save_state()

        elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
        print(f"[mcp-heartbeat] pid={os.getpid()} call={call_num} tool={name} done elapsed={elapsed_ms}ms result_len={len(result_text)}", file=sys.stderr, flush=True)
        return [types.TextContent(type="text", text=result_text)]

    # Also save state on shutdown
    atexit.register(_save_state)

    return server


async def main():
    if len(sys.argv) < 2:
        print("Usage: mcp_server.py <config_b64> | --config-file <path>", file=sys.stderr)
        sys.exit(1)

    # Linux's MAX_ARG_STRLEN caps a single argv element at 128KB. AgentDojo
    # serializes the full TaskEnvironment into env_json, which can blow past
    # that. The host writes the JSON config to a temp file and passes its
    # path; we read either form.
    if sys.argv[1] == "--config-file" and len(sys.argv) >= 3:
        config = json.loads(Path(sys.argv[2]).read_text())
    else:
        config = json.loads(base64.b64decode(sys.argv[1]))
    benchmark_version = config.get("benchmark_version", "v1.1.1")
    state_file = config.get("state_file")
    suite_name = config.get("suite_name") or config.get("env_name")

    sys.path.insert(0, str(Path(__file__).parent))
    get_shifted_suite = None
    try:
        from date_shift import get_shifted_suite as _get_shifted_suite
        get_shifted_suite = _get_shifted_suite
    except ImportError:
        pass

    suite = None
    runtime = None
    env_type = None
    env = None

    if "env_json" in config:
        if not suite_name:
            print("suite_name required when using env_json mode", file=sys.stderr)
            sys.exit(1)
        suite = get_shifted_suite(benchmark_version, suite_name) if get_shifted_suite else get_suite(benchmark_version, suite_name)
        runtime = FunctionsRuntime(suite.tools)
        env_type = _resolve_type(config["env_type"])
        env = env_type.model_validate_json(config["env_json"])
    else:
        env_name = config.get("env_name") or config.get("suite_name")
        if not env_name:
            print("env_name or suite_name required when not using env_json mode", file=sys.stderr)
            sys.exit(1)
        suite = get_shifted_suite(benchmark_version, env_name) if get_shifted_suite else get_suite(benchmark_version, env_name)

        task_id = config.get("task_id")
        attack_name = config.get("attack")
        injection_task_id = config.get("injection_task_id")

        task = suite.user_tasks.get(task_id)
        if task is None:
            print(f"Task {task_id} not found", file=sys.stderr)
            sys.exit(1)

        runtime = FunctionsRuntime(suite.tools)
        env_type = suite.environment_type

        if state_file:
            state_path = Path(state_file)
            if state_path.exists() and state_path.stat().st_size > 0:
                try:
                    env = env_type.model_validate_json(state_path.read_text())
                except Exception as e:
                    print(f"Failed to load seeded state from {state_file}: {e}", file=sys.stderr)

        if env is None:
            if attack_name and injection_task_id:
                from agentdojo.attacks import load_attack

                class _FakeAgent:
                    name = "mcp-server"
                attack = load_attack(attack_name, suite, _FakeAgent())
                injection_task = suite.injection_tasks.get(injection_task_id)
                if injection_task:
                    injections = attack.attack(task, injection_task)
                else:
                    injections = {}
                env = suite.load_and_inject_default_environment(injections)
            else:
                env = suite.load_and_inject_default_environment({})

    log_file = config.get("log_file")
    phase_state_file = config.get("phase_state_file")
    server = create_server(runtime, env, env_type, state_file, log_file, phase_state_file)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
