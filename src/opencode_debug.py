#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


DEFAULT_DB = Path.home() / ".local/share/opencode/opencode.db"
DEFAULT_LOG_DIR = Path.home() / ".local/share/opencode/log"


@dataclass
class SessionRef:
    id: str
    slug: str
    title: str
    time_created: int
    time_updated: int


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def format_ms(value: int | None) -> str:
    if value is None:
        return "-"
    return datetime.fromtimestamp(value / 1000).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def shorten(value: object, limit: int = 220) -> str:
    if value is None:
        return "null"
    if isinstance(value, str):
        text = value.replace("\n", " ").strip()
    else:
        try:
            text = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
        except TypeError:
            text = repr(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def load_json(text: str) -> dict:
    return json.loads(text)


def fetch_sessions(conn: sqlite3.Connection, limit: int) -> list[SessionRef]:
    rows = conn.execute(
        """
        select id, slug, title, time_created, time_updated
        from session
        order by time_updated desc
        limit ?
        """,
        (limit,),
    ).fetchall()
    return [SessionRef(**dict(row)) for row in rows]


def resolve_session(conn: sqlite3.Connection, query: str | None) -> SessionRef:
    if not query or query == "latest":
        sessions = fetch_sessions(conn, 1)
        if not sessions:
            raise SystemExit("No opencode sessions found.")
        return sessions[0]

    row = conn.execute(
        """
        select id, slug, title, time_created, time_updated
        from session
        where id = ? or slug = ?
        order by time_updated desc
        limit 1
        """,
        (query, query),
    ).fetchone()
    if row:
        return SessionRef(**dict(row))

    rows = conn.execute(
        """
        select id, slug, title, time_created, time_updated
        from session
        where title like ?
        order by time_updated desc
        limit 2
        """,
        (f"%{query}%",),
    ).fetchall()
    if not rows:
        raise SystemExit(f"No session matched '{query}'.")
    if len(rows) > 1:
        choices = ", ".join(f"{row['slug']} ({row['id']})" for row in rows)
        raise SystemExit(f"Ambiguous session '{query}': {choices}")
    return SessionRef(**dict(rows[0]))


def print_sessions(conn: sqlite3.Connection, limit: int) -> None:
    for session in fetch_sessions(conn, limit):
        print(
            f"{session.slug:20}  {session.id}  "
            f"updated={format_ms(session.time_updated)}  "
            f"title={shorten(session.title, 80)}"
        )


def fetch_parts(
    conn: sqlite3.Connection,
    session_id: str,
    limit: int,
    after_ms: int | None = None,
) -> list[sqlite3.Row]:
    if after_ms is None:
        return conn.execute(
            """
            select id, message_id, session_id, time_created, time_updated, data
            from part
            where session_id = ?
            order by time_created desc
            limit ?
            """,
            (session_id, limit),
        ).fetchall()
    return conn.execute(
        """
        select id, message_id, session_id, time_created, time_updated, data
        from part
        where session_id = ? and time_created > ?
        order by time_created asc
        """,
        (session_id, after_ms),
    ).fetchall()


def format_part(row: sqlite3.Row) -> str:
    payload = load_json(row["data"])
    part_type = payload.get("type", "?")
    stamp = format_ms(row["time_created"])
    prefix = f"{stamp}  {row['id']}  {part_type}"

    if part_type == "tool":
        state = payload.get("state", {})
        return (
            f"{prefix}  {payload.get('tool')}  "
            f"status={state.get('status')}  "
            f"input={shorten(state.get('input'))}  "
            f"output={shorten(state.get('output'))}"
        )
    if part_type == "reasoning":
        return f"{prefix}  {shorten(payload.get('text', ''), 320)}"
    if part_type in {"step-start", "step-finish"}:
        bits = []
        if payload.get("reason"):
            bits.append(f"reason={payload['reason']}")
        if payload.get("tokens"):
            bits.append(f"tokens={shorten(payload['tokens'], 120)}")
        if payload.get("cost") is not None:
            bits.append(f"cost={payload['cost']}")
        return f"{prefix}  {'  '.join(bits)}".rstrip()
    return f"{prefix}  {shorten(payload, 320)}"


def print_parts(conn: sqlite3.Connection, session: SessionRef, limit: int) -> None:
    print(f"session={session.slug} ({session.id}) title={shorten(session.title, 120)}")
    rows = list(reversed(fetch_parts(conn, session.id, limit)))
    for row in rows:
        print(format_part(row))


def follow_parts(conn: sqlite3.Connection, session: SessionRef, poll: float) -> None:
    print(f"following session={session.slug} ({session.id})")
    last_seen = 0
    seen_ids: set[str] = set()
    try:
        while True:
            rows = fetch_parts(conn, session.id, limit=500, after_ms=last_seen)
            for row in rows:
                if row["id"] in seen_ids:
                    continue
                print(format_part(row), flush=True)
                seen_ids.add(row["id"])
                last_seen = max(last_seen, row["time_created"])
            time.sleep(poll)
    except KeyboardInterrupt:
        return


def iter_matching_log_lines(log_dir: Path, session_id: str) -> Iterable[tuple[Path, str]]:
    for path in sorted(log_dir.glob("*.log"), reverse=True):
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if session_id in line:
                    yield path, line.rstrip()


def print_logs(session: SessionRef, log_dir: Path, limit: int) -> None:
    matches = list(iter_matching_log_lines(log_dir, session.id))
    if not matches:
        print(f"No log lines found for {session.id} in {log_dir}")
        return
    for path, line in matches[-limit:]:
        print(f"{path.name}: {line}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect OpenCode sessions for clean bench debugging.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to opencode.db")
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR, help="Path to opencode log dir")

    subparsers = parser.add_subparsers(dest="command", required=True)

    sessions = subparsers.add_parser("sessions", help="List recent sessions")
    sessions.add_argument("--limit", type=int, default=10)

    parts = subparsers.add_parser("parts", help="Show recent parts for one session")
    parts.add_argument("--session", default="latest", help="Session id, slug, title fragment, or 'latest'")
    parts.add_argument("--limit", type=int, default=20)

    follow = subparsers.add_parser("follow", help="Poll part rows for a live session")
    follow.add_argument("--session", default="latest", help="Session id, slug, title fragment, or 'latest'")
    follow.add_argument("--poll", type=float, default=1.0, help="Polling interval in seconds")

    logs = subparsers.add_parser("logs", help="Show coarse opencode log lines for one session")
    logs.add_argument("--session", default="latest", help="Session id, slug, title fragment, or 'latest'")
    logs.add_argument("--limit", type=int, default=40)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    conn = connect(args.db)
    try:
        if args.command == "sessions":
            print_sessions(conn, args.limit)
            return 0

        session = resolve_session(conn, args.session)
        if args.command == "parts":
            print_parts(conn, session, args.limit)
            return 0
        if args.command == "follow":
            follow_parts(conn, session, args.poll)
            return 0
        if args.command == "logs":
            print_logs(session, args.log_dir, args.limit)
            return 0
    finally:
        conn.close()

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
