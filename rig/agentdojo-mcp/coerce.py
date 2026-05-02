"""Argument coercion at the LLM/AgentDojo boundary.

LLMs produce tool args that are *almost* what AgentDojo's pydantic schemas
want. This module fixes the common shape mismatches:

- "null" string → None
- ISO-8601 datetime with seconds or 'T' separator → "%Y-%m-%d %H:%M"
- string with commas where the schema wants an array → split on commas
- bare-string array where the schema wants array of {type, file_id} →
  wrap each entry as {"type": "file", "file_id": <s>}
- dict-with-id array where the schema wants array of {type, file_id} →
  rewrite to the canonical shape

Coercion is best-effort: any arg the schema doesn't describe passes
through unchanged. This is where you add new boundary fixes — keep them
narrow (predicate + transform) so they don't ripple.
"""

from __future__ import annotations

import re
from typing import Any

from agentdojo.functions_runtime import FunctionsRuntime

_ISO_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?$")


def _array_item_spec(spec: dict) -> dict:
    item_spec = spec.get("items", {})
    if not item_spec and "anyOf" in spec:
        for branch in spec["anyOf"]:
            if branch.get("type") == "array":
                item_spec = branch.get("items", {})
                break
    return item_spec


def _is_array(spec: dict) -> bool:
    if spec.get("type") == "array":
        return True
    if "anyOf" in spec:
        return any(s.get("type") == "array" for s in spec["anyOf"])
    return False


def coerce_tool_args(
    runtime: FunctionsRuntime, tool_name: str, tool_args: dict
) -> dict:
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

        if isinstance(value, str) and _ISO_DATETIME.match(value):
            coerced[param_name] = value.replace("T", " ")[:16]
            value = coerced[param_name]

        spec = props.get(param_name, {})
        if not _is_array(spec):
            continue

        if isinstance(value, str):
            if "," in value:
                coerced[param_name] = [v.strip() for v in value.split(",") if v.strip()]
            else:
                coerced[param_name] = [value]
            value = coerced[param_name]

        if isinstance(value, list) and value and isinstance(value[0], str):
            item_spec = _array_item_spec(spec)
            if item_spec.get("type") == "object":
                coerced[param_name] = [{"type": "file", "file_id": v} for v in value]
                continue

        if isinstance(value, list) and value and isinstance(value[0], dict):
            item_spec = _array_item_spec(spec)
            if item_spec.get("type") != "object":
                continue
            normalized = []
            changed = False
            for item in value:
                if not isinstance(item, dict):
                    normalized.append(item)
                    continue
                file_id = item.get("file_id") or item.get("id") or item.get("id_")
                if isinstance(file_id, str) and file_id:
                    normalized.append({"type": "file", "file_id": file_id})
                    changed = True
                else:
                    normalized.append(item)
            if changed:
                coerced[param_name] = normalized

    return coerced
