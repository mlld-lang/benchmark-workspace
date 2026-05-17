"""Transport normalization at the mlld/AgentDojo boundary.

This module is intentionally narrow. It adapts timestamp literals from common
ISO syntax to AgentDojo's pydantic datetime format, but it does not repair
planner/model argument shapes. Arrays must already be arrays, object args must
already be objects, and missing values must be represented structurally rather
than as strings.
"""

from __future__ import annotations

import re
from agentdojo.functions_runtime import FunctionsRuntime

_ISO_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?$")


def coerce_tool_args(
    runtime: FunctionsRuntime, tool_name: str, tool_args: dict
) -> dict:
    fn = runtime.functions.get(tool_name)
    if fn is None:
        return tool_args

    coerced = dict(tool_args)

    for param_name, value in coerced.items():
        if isinstance(value, str) and _ISO_DATETIME.match(value):
            coerced[param_name] = value.replace("T", " ")[:16]

    return coerced
