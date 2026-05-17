"""Bench-specific extra MCP tools for agentdojo-mcp.

Loaded by `rig/agentdojo-mcp/server.py` when its config specifies:

    "extension_paths": ["<repo>/src"],
    "extensions": ["bench_mcp_extras"]

Provides three helpers that aren't in vanilla AgentDojo:

- `get_email_by_id`        — exact-id email retrieval with full content
- `search_emails_any_sender` — search inbox across senders (vanilla
                                 search_emails requires a sender filter)
- `get_current_datetime`   — date_shift-aware current datetime

Kept separate from the agentdojo-mcp server so the server stays
suite-agnostic.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Callable

from mcp import types

# date_shift lives next to this file. Add this dir to sys.path so the
# import works whether or not the host already added it.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# format helpers live in agentdojo-mcp; add that path so we can reuse
# yaml_dump rather than reimplementing it.
_AGENTDOJO_MCP = _HERE.parent / "rig" / "agentdojo-mcp"
if str(_AGENTDOJO_MCP) not in sys.path:
    sys.path.insert(0, str(_AGENTDOJO_MCP))

from date_shift import REFERENCE_DATE, compute_offset  # noqa: E402
from format import yaml_dump  # noqa: E402


Handler = Callable[[dict[str, Any]], str]


def _make_get_email_by_id(env: Any) -> Handler:
    def handler(args: dict[str, Any]) -> str:
        email_id = str(args.get("email_id", ""))
        emails = getattr(getattr(env, "inbox", None), "emails", None)
        if not isinstance(emails, dict):
            raise ValueError("Inbox emails not available.")
        email = emails.get(email_id)
        if email is None:
            raise ValueError(f"Email with ID '{email_id}' not found.")
        payload = email.model_dump() if hasattr(email, "model_dump") else email
        if isinstance(payload, dict):
            payload.pop("status", None)
        return yaml_dump(payload)

    return handler


def _make_search_emails_any_sender(env: Any) -> Handler:
    def handler(args: dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip().lower()
        emails = getattr(getattr(env, "inbox", None), "emails", None)
        if not isinstance(emails, dict):
            raise ValueError("Inbox emails not available.")
        if not query:
            raise ValueError("Query is required.")

        terms = [t for t in re.split(r"[^a-z0-9]+", query) if len(t) >= 3]
        if not terms:
            terms = [query]

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
            score = 10 if query in haystack else 0
            score += sum(1 for t in terms if t in haystack)
            if score <= 0:
                continue
            payload = dict(payload)
            payload.pop("status", None)
            matches.append((score, str(payload.get("timestamp", "")), payload))

        if not matches:
            raise ValueError("No emails found. Try with a different query.")

        matches.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return yaml_dump([p for _, _, p in matches[:10]])

    return handler


def _make_get_current_datetime() -> Handler:
    def handler(_args: dict[str, Any]) -> str:
        return f"{(REFERENCE_DATE + compute_offset()):%Y-%m-%d} 08:00"

    return handler


def register(env: Any, _runtime: Any) -> list[tuple[types.Tool, Handler]]:
    """Return tool definitions and handlers, gated on env shape.

    Email helpers register only when the env has an inbox. The datetime
    helper is unconditional — every suite gets it.
    """
    tools: list[tuple[types.Tool, Handler]] = []
    has_inbox = hasattr(env, "inbox") and hasattr(env.inbox, "emails")

    if has_inbox:
        tools.append(
            (
                types.Tool(
                    name="get_email_by_id",
                    description="Retrieve a specific email by ID with full content.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "email_id": {
                                "type": "string",
                                "description": "Exact email id to retrieve.",
                            }
                        },
                        "required": ["email_id"],
                    },
                ),
                _make_get_email_by_id(env),
            )
        )
        tools.append(
            (
                types.Tool(
                    name="search_emails_any_sender",
                    description="Search inbox emails across any sender and return matching email metadata.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query to match against sender, subject, and body.",
                            }
                        },
                        "required": ["query"],
                    },
                ),
                _make_search_emails_any_sender(env),
            )
        )

    tools.append(
        (
            types.Tool(
                name="get_current_datetime",
                description="Return the current local datetime in YYYY-MM-DD HH:MM format.",
                inputSchema={"type": "object", "properties": {}},
            ),
            _make_get_current_datetime(),
        )
    )

    return tools
