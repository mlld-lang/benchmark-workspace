"""Optional extension loading for agentdojo-mcp.

Configuration can specify:

    "extension_paths": ["/abs/path/to/src"],
    "extensions": ["bench_mcp_extras"]

Each module listed in `extensions` must export:

    def register(env, runtime) -> list[(types.Tool, handler)]

where `handler(arguments: dict) -> str` returns the YAML-formatted result
text (the server wraps it in a TextContent before responding). Extension
tools merge into the MCP tool surface alongside AgentDojo's native tools.

This is the mechanism for adding suite-aware helpers (`get_email_by_id`,
`get_current_datetime`, etc.) without making agentdojo-mcp suite-aware.
The extension module owns its own assumptions about the env's shape.

Search paths from `extension_paths` are prepended to `sys.path` before
import, so an extension module can live anywhere the host wants — it
doesn't need to be installed as a package.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any, Callable

from mcp import types

ExtensionHandler = Callable[[dict[str, Any]], str]
ExtensionTool = tuple[types.Tool, ExtensionHandler]


def load_extensions(
    modules: list[str],
    paths: list[str],
    env: Any,
    runtime: Any,
) -> dict[str, ExtensionTool]:
    """Load extension modules; return {tool_name: (Tool, handler)}.

    Tools registered by later modules override earlier ones if names
    collide. AgentDojo's native tools always win — the server merges
    extensions under native, not over.
    """
    for path in paths or []:
        if path not in sys.path:
            sys.path.insert(0, path)

    result: dict[str, ExtensionTool] = {}
    for mod_path in modules or []:
        mod = importlib.import_module(mod_path)
        register = getattr(mod, "register", None)
        if register is None:
            raise AttributeError(
                f"extension module {mod_path!r} has no register(env, runtime)"
            )
        for tool, handler in register(env, runtime):
            result[tool.name] = (tool, handler)
    return result
