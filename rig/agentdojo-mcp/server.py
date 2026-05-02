"""MCP server wrapping vanilla AgentDojo tools.

Exposes a TaskSuite's tools as MCP tools over stdio. Mlld imports them via
`import tools from mcp "..." as @mcp`; the bench domain layer
(bench/domains/<suite>/tools.mld) wraps each call with `=> record @x`
coercion, labels, and write-tool metadata.

This server is configuration-driven via a JSON blob passed on argv. It
supports two modes:

  1. env_json mode — caller supplies an already-built environment as
     JSON. The server validates against the suite's environment_type and
     runs. Used when the caller (runner.py) constructs the env upfront,
     applying injections and any host-side normalization.

  2. suite_name + task_id mode — server resolves the task and builds
     the env itself. Caller may supply pre-computed `injections` (a
     dict[str,str]) to inject canary placeholders. Attack instantiation
     lives in the caller; this server does not import
     `agentdojo.attacks.load_attack`.

Per-call: tool args are coerced at the boundary, the call dispatches via
FunctionsRuntime, the result is YAML-formatted, and the env is saved
back to state_file (skipped for read-only tools — see state.py).

Read tools mutate nothing observable, so the save is pure overhead. This
matters for travel multi-domain sessions where model_dump_json is the
dominant per-call cost.
"""

from __future__ import annotations

import asyncio
import atexit
import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentdojo.functions_runtime import FunctionsRuntime
from agentdojo.task_suite import get_suite
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Imports from sibling modules. When run as `python server.py` the
# parent dir isn't on sys.path; add it.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from coerce import coerce_tool_args  # noqa: E402
from extensions import ExtensionTool, load_extensions  # noqa: E402
from format import tool_result_to_str, yaml_dump  # noqa: E402
from state import (  # noqa: E402
    is_read_only_tool,
    load_env_from_state_file,
    resolve_env_type,
    save_env,
)


def _build_tools(runtime: FunctionsRuntime) -> list[types.Tool]:
    tools = []
    for fn in runtime.functions.values():
        schema = fn.parameters.model_json_schema()
        schema.pop("title", None)
        for prop in schema.get("properties", {}).values():
            prop.pop("title", None)
        tools.append(
            types.Tool(
                name=fn.name,
                description=fn.description or "",
                inputSchema=schema,
            )
        )
    return tools


def create_server(
    runtime: FunctionsRuntime,
    env: Any,
    state_file: str | None,
    log_file: str | None = None,
    phase_state_file: str | None = None,
    extension_tools: dict[str, ExtensionTool] | None = None,
) -> Server:
    server = Server("agentdojo-tools")
    tools = _build_tools(runtime)
    extension_tools = extension_tools or {}
    native_names = {t.name for t in tools}
    for name, (tool, _handler) in extension_tools.items():
        if name in native_names:
            continue
        tools.append(tool)

    def _log(entry: dict) -> None:
        if not log_file:
            return
        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception:
            pass

    def _save() -> float | None:
        if not state_file:
            return None
        t0 = time.monotonic()
        if save_env(env, state_file):
            return time.monotonic() - t0
        return None

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

    call_count = [0]

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict[str, Any] | None
    ) -> list[types.TextContent]:
        call_count[0] += 1
        n = call_count[0]
        t0 = time.monotonic()
        print(
            f"[mcp] pid={os.getpid()} call={n} tool={name} "
            f"start={datetime.now(timezone.utc).isoformat()}",
            file=sys.stderr,
            flush=True,
        )
        arguments = arguments or {}
        coerced = coerce_tool_args(runtime, name, arguments)

        try:
            if name in extension_tools and name not in runtime.functions:
                _tool, handler = extension_tools[name]
                result_text = handler(coerced)
            else:
                tool_result, error = runtime.run_function(env, name, coerced)
                if isinstance(tool_result, dict):
                    formatted = yaml_dump(tool_result)
                else:
                    formatted = tool_result_to_str(tool_result)
                result_text = f"ERROR: {error}\n{formatted}" if error else formatted
        except Exception as e:
            result_text = f"ERROR: {e}"

        save_elapsed_s = None
        saved = False
        if not is_read_only_tool(name):
            save_elapsed_s = _save()
            saved = save_elapsed_s is not None

        elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
        phase_state = _read_phase_state()

        _log(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "tool": name,
                "args": arguments,
                "coerced": {k: v for k, v in coerced.items() if arguments.get(k) != v},
                "result": result_text[:500],
                "error": result_text[:6] == "ERROR:",
                "phase": phase_state.get("phase"),
                "phase_id": phase_state.get("phase_id"),
                "phase_iteration": phase_state.get("iteration"),
                "pid": os.getpid(),
                "call_num": n,
                "elapsed_ms": elapsed_ms,
                "result_len": len(result_text),
                "saved_state": saved,
                "save_elapsed_ms": (
                    round(save_elapsed_s * 1000, 1) if save_elapsed_s is not None else None
                ),
            }
        )

        print(
            f"[mcp] pid={os.getpid()} call={n} tool={name} done "
            f"elapsed={elapsed_ms}ms result_len={len(result_text)} saved={saved}",
            file=sys.stderr,
            flush=True,
        )
        return [types.TextContent(type="text", text=result_text)]

    atexit.register(lambda: _save())
    return server


def _build_env_from_config(config: dict) -> tuple[FunctionsRuntime, Any, type]:
    """Build (runtime, env, env_type) from a config dict.

    Two modes:
      1. env_json: caller supplies the serialized env directly. Server
         validates against env_type (also from config). Used when the
         caller has already applied injections and any normalization.

      2. suite_name + task_id: server resolves the task and loads the
         default env. If state_file points at an existing env JSON, that
         is loaded instead (lets a runner pre-seed env with injections).
         Optional `injections` dict is forwarded to
         `load_and_inject_default_environment`.

    The caller may pass a `suite_loader` import path (module:fn) to
    swap in a custom suite loader (e.g. a date-shifted variant). It
    must be a callable with the same signature as
    `agentdojo.task_suite.get_suite`.
    """
    benchmark_version = config.get("benchmark_version", "v1.1.1")
    suite_name = config.get("suite_name") or config.get("env_name")
    if not suite_name:
        raise ValueError("config must include suite_name or env_name")

    suite_loader = get_suite
    loader_path = config.get("suite_loader")
    if loader_path:
        import importlib

        mod_name, fn_name = loader_path.split(":", 1)
        suite_loader = getattr(importlib.import_module(mod_name), fn_name)

    suite = suite_loader(benchmark_version, suite_name)
    runtime = FunctionsRuntime(suite.tools)

    if "env_json" in config:
        env_type_name = config.get("env_type")
        if not env_type_name:
            raise ValueError("env_json mode requires env_type")
        env_type = resolve_env_type(env_type_name)
        env = env_type.model_validate_json(config["env_json"])
        return runtime, env, env_type

    env_type = suite.environment_type
    state_file = config.get("state_file")
    env = load_env_from_state_file(env_type, state_file)
    if env is None:
        injections = config.get("injections") or {}
        env = suite.load_and_inject_default_environment(injections)
    return runtime, env, env_type


def _read_config(argv: list[str]) -> dict:
    """Read config blob from argv.

    `--config-file <path>` reads from a JSON file. The fallback is
    `argv[1]` as base64-encoded JSON. The file form exists because Linux's
    MAX_ARG_STRLEN (128KB) caps a single argv element, and a serialized
    AgentDojo env can blow past that.
    """
    if len(argv) < 2:
        raise SystemExit("usage: server.py --config-file <path> | <config_b64>")
    if argv[1] == "--config-file":
        if len(argv) < 3:
            raise SystemExit("--config-file requires a path")
        return json.loads(Path(argv[2]).read_text())
    return json.loads(base64.b64decode(argv[1]))


async def main_async() -> None:
    config = _read_config(sys.argv)
    runtime, env, _env_type = _build_env_from_config(config)

    extension_tools = load_extensions(
        modules=config.get("extensions") or [],
        paths=config.get("extension_paths") or [],
        env=env,
        runtime=runtime,
    )

    server = create_server(
        runtime,
        env,
        state_file=config.get("state_file"),
        log_file=config.get("log_file"),
        phase_state_file=config.get("phase_state_file"),
        extension_tools=extension_tools,
    )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
