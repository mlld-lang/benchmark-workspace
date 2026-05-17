"""Small extension loader for the generic AgentDojo MCP bridge.

The MCP bridge stays suite-neutral. Bench code can provide optional Python
modules that expose extra tools for a particular environment shape.

Each module listed in config["extensions"] must define:

    register(env, runtime) -> list[(mcp.types.Tool, handler)]

where handler(arguments: dict) returns a YAML/text result string.
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
    for path in paths or []:
        if path and path not in sys.path:
            sys.path.insert(0, path)

    loaded: dict[str, ExtensionTool] = {}
    for module_name in modules or []:
        module = importlib.import_module(module_name)
        register = getattr(module, "register", None)
        if register is None:
            raise AttributeError(f"{module_name!r} does not define register(env, runtime)")
        for tool, handler in register(env, runtime):
            loaded[tool.name] = (tool, handler)
    return loaded
