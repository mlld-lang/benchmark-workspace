"""Environment state load, save, and runtime-dict sync.

AgentDojo's environment models hold their authoritative content in
`initial_*` lists; pydantic `@model_validator` rebuilds the working
dicts (events, emails, files) from those lists on deserialization.
Tool calls mutate the dicts but not the `initial_*` lists, so without a
sync step the mutations are lost on a serialization round-trip.

This module owns:
- env type resolution from a fully-qualified name
- env load/save against a JSON state file
- the read-only-tool optimization (skip save when the call cannot mutate)
- the mutating-read-like exception list (tools whose names look read-only
  but actually mutate observable state)
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any


_READ_ONLY_PREFIXES = ("get_", "search_", "list_", "check_", "read_")

# Tools that look read-only by prefix but mutate state observable to graders.
# - get_unread_emails sets `email.read = True` on every returned email
#   (UT24 reads this from post_env).
# - get_webpage appends the URL to web.web_requests (SL-UT0's utility check
#   reads `URL in post_env.web.web_requests`).
_MUTATING_READ_LIKE = {"get_unread_emails", "get_webpage"}


def is_read_only_tool(name: str) -> bool:
    if name in _MUTATING_READ_LIKE:
        return False
    return any(name.startswith(p) for p in _READ_ONLY_PREFIXES)


def resolve_env_type(qualified_name: str) -> type:
    module_path, class_name = qualified_name.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def sync_runtime_state(env: Any) -> None:
    """Sync runtime dicts back to initial_* lists for serialization."""
    if hasattr(env, "calendar") and hasattr(env.calendar, "initial_events"):
        env.calendar.initial_events = list(env.calendar.events.values())
    if hasattr(env, "inbox") and hasattr(env.inbox, "initial_emails"):
        env.inbox.initial_emails = list(env.inbox.emails.values())
    if hasattr(env, "cloud_drive") and hasattr(env.cloud_drive, "initial_files"):
        env.cloud_drive.initial_files = list(env.cloud_drive.files.values())


def save_env(env: Any, state_file: str | None) -> bool:
    if not state_file:
        return False
    try:
        sync_runtime_state(env)
        Path(state_file).write_text(env.model_dump_json())
        return True
    except Exception:
        return False


def load_env_from_state_file(env_type: type, state_file: str | None) -> Any | None:
    if not state_file:
        return None
    path = Path(state_file)
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        return env_type.model_validate_json(path.read_text())
    except Exception:
        return None
