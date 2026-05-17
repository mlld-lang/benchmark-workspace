"""YAML output formatting for AgentDojo tool results.

Tool results are serialized to YAML before being returned to the LLM. This
module owns the small set of pre-serialization fixups needed to make
AgentDojo output compose cleanly with mlld's record system.

- `datetime` → "YYYY-MM-DD HH:MM" string. Prevents the JS Date timezone
  shift mlld would otherwise apply on the round-trip.
- `date` → "YYYY-MM-DD" string. Same reason.
- `shared_with` permission maps → list of email strings. Lets records
  treat each shared email as its own fact-bearing value.
- `allow_unicode=True`. Without it `safe_dump` escapes non-ASCII bytes,
  and any *_for_<family> tool that returns name→value dicts will produce
  a phantom state entry under the escaped name (see c-c4a4).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import yaml
from pydantic import BaseModel

from agentdojo.functions_runtime import FunctionReturnType


def _prepare_for_yaml(data: Any) -> Any:
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if (
                k == "shared_with"
                and isinstance(v, dict)
                and all(isinstance(vv, str) for vv in v.values())
            ):
                result[k] = list(v.keys())
            else:
                result[k] = _prepare_for_yaml(v)
        return result
    if isinstance(data, list):
        return [_prepare_for_yaml(item) for item in data]
    if isinstance(data, datetime):
        return data.strftime("%Y-%m-%d %H:%M")
    if isinstance(data, date):
        return data.strftime("%Y-%m-%d")
    return data


def yaml_dump(data: Any) -> str:
    return yaml.safe_dump(
        _prepare_for_yaml(data),
        default_flow_style=False,
        allow_unicode=True,
    )


def tool_result_to_str(tool_result: FunctionReturnType) -> str:
    if isinstance(tool_result, BaseModel):
        return yaml_dump(tool_result.model_dump()).strip()

    if isinstance(tool_result, list):
        rendered: list[Any] = []
        for item in tool_result:
            if type(item) in (str, int, float, bool) or item is None:
                rendered.append(item)
            elif isinstance(item, BaseModel):
                rendered.append(item.model_dump())
            else:
                raise TypeError(f"Not valid type for item tool result: {type(item)}")
        return yaml_dump(rendered).strip()

    if isinstance(tool_result, dict):
        return yaml_dump(tool_result).strip()

    return str(tool_result)
