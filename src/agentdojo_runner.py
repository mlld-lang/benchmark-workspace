"""Benchmark runner for agent-agnostic evaluation.

Manages the lifecycle: suite loading → environment setup → MCP server
command construction → agent execution → state readback → grading.
"""

from __future__ import annotations

import base64
import json
import logging
import tempfile
import warnings
from collections.abc import Sequence
from pathlib import Path

from agentdojo_agents_base import AgentEndpoint
from agentdojo.attacks.base_attacks import BaseAttack
from agentdojo.base_tasks import BaseInjectionTask, BaseUserTask
from agentdojo.functions_runtime import FunctionsRuntime, TaskEnvironment
from agentdojo_grading import grade_security, grade_utility
from agentdojo_results import AgentResult, SuiteResults, ToolCallRecord
from agentdojo.task_suite.task_suite import TaskSuite


def _tools_to_json(suite: TaskSuite) -> list[dict]:
    """Build tool JSON schemas from a suite's tools."""
    runtime = FunctionsRuntime(suite.tools)
    tools = []
    for fn in runtime.functions.values():
        schema = fn.parameters.model_json_schema()
        schema.pop("title", None)
        for prop in schema.get("properties", {}).values():
            prop.pop("title", None)
        tools.append({
            "name": fn.name,
            "description": fn.description,
            "parameters": schema,
        })
    return tools


def _qualified_name(cls: type) -> str:
    """Get fully qualified class name for deserialization."""
    return f"{cls.__module__}.{cls.__qualname__}"


def _build_mcp_server_cmd(
    env: TaskEnvironment,
    suite: TaskSuite,
    state_file: str,
    log_file: str,
    benchmark_version: str = "v1.1.1",
) -> str:
    """Build the MCP server launch command with base64-encoded config."""
    config = {
        "env_json": env.model_dump_json(),
        "env_type": _qualified_name(type(env)),
        "suite_name": suite.name,
        "benchmark_version": benchmark_version,
        "state_file": state_file,
        "log_file": log_file,
    }
    config_b64 = base64.b64encode(json.dumps(config).encode()).decode()
    return f"python -m agentdojo.mcp_server {config_b64}"


def _read_tool_log(log_file: str) -> list[ToolCallRecord]:
    """Read tool call records from the MCP server's JSONL log."""
    records = []
    log_path = Path(log_file)
    if not log_path.exists():
        return records

    for line in log_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            records.append(ToolCallRecord(
                function=entry["tool"],
                args=entry["args"],
                result=str(entry.get("result", ""))[:500],
                error=str(entry["error"]) if entry.get("error") else None,
            ))
        except (json.JSONDecodeError, KeyError):
            continue

    return records


def _contact_emails(contact_list: object) -> set[str]:
    if not isinstance(contact_list, list):
        return set()
    emails: set[str] = set()
    for contact in contact_list:
        email = getattr(contact, "email", None)
        if isinstance(email, str) and email:
            emails.add(email)
    return emails


def _normalize_post_environment_for_grading(
    suite_name: str,
    pre_env: TaskEnvironment,
    post_env: TaskEnvironment,
) -> TaskEnvironment:
    """Drop benign derived contact entries before strict grading.

    Both workspace and travel inboxes rebuild `contact_list` from email history
    when a serialized environment is loaded (Inbox._create_contact_list runs
    after model_validate_json). After sending an email or calendar invite to a
    new recipient, the deserialization step adds a contact entry even though
    the task's semantic side effects are only the new email/event itself.
    Strict utilities such as `check_new_email()` / `check_new_event()` reject
    the extra `iterable_item_added` diff, so grading ignores benign new contacts
    that correspond to recipients of newly-sent emails.
    """
    if suite_name not in ("workspace", "travel"):
        return post_env

    pre_inbox = getattr(pre_env, "inbox", None)
    post_inbox = getattr(post_env, "inbox", None)
    if pre_inbox is None or post_inbox is None:
        return post_env

    pre_contacts = _contact_emails(getattr(pre_inbox, "contact_list", None))
    post_contacts = getattr(post_inbox, "contact_list", None)
    post_contact_emails = _contact_emails(post_contacts)
    new_contact_emails = post_contact_emails - pre_contacts
    if not new_contact_emails or not isinstance(post_contacts, list):
        return post_env

    pre_emails = getattr(pre_inbox, "emails", None)
    post_emails = getattr(post_inbox, "emails", None)
    if not isinstance(pre_emails, dict) or not isinstance(post_emails, dict):
        return post_env

    new_email_ids = set(post_emails) - set(pre_emails)
    benign_contacts: set[str] = set()
    for email_id in new_email_ids:
        email = post_emails.get(email_id)
        if email is None:
            continue
        status = getattr(email, "status", None)
        status_value = getattr(status, "value", status)
        if status_value != "sent":
            continue
        for field_name in ("recipients", "cc", "bcc"):
            values = getattr(email, field_name, None)
            if not isinstance(values, list):
                continue
            for value in values:
                if isinstance(value, str) and value in new_contact_emails:
                    benign_contacts.add(value)

    if not benign_contacts:
        return post_env

    post_inbox.contact_list = [
        contact
        for contact in post_contacts
        if getattr(contact, "email", None) not in benign_contacts
    ]
    return post_env


def run_task(
    suite: TaskSuite,
    agent: AgentEndpoint,
    user_task: BaseUserTask | BaseInjectionTask,
    injection_task: BaseInjectionTask | None,
    injections: dict[str, str],
    benchmark_version: str = "v1.1.1",
) -> tuple[bool, bool, AgentResult]:
    """Run a single task with an agent.

    Returns:
        (utility, security, agent_result) where security is True if no
        injection task was provided.
    """
    # Load and inject environment
    env = suite.load_and_inject_default_environment(injections)
    if isinstance(user_task, BaseUserTask):
        env = user_task.init_environment(env)

    pre_env = env.model_copy(deep=True)

    # Get prompt
    if isinstance(user_task, BaseUserTask):
        prompt = user_task.PROMPT
    else:
        prompt = user_task.GOAL

    # Set up temp files for MCP server state exchange
    state_fd, state_file = tempfile.mkstemp(suffix=".json")
    log_fd, log_file = tempfile.mkstemp(suffix=".jsonl")

    try:
        # Write initial state so the server has it even if no tools are called
        Path(state_file).write_text(env.model_dump_json())

        mcp_cmd = _build_mcp_server_cmd(env, suite, state_file, log_file, benchmark_version)

        # Build tool schemas for the agent
        tools_json = _tools_to_json(suite)

        # Run the agent
        result = agent.run(query=prompt, mcp_server_cmd=mcp_cmd, tools=tools_json)

        # Read back post-environment from MCP server state file
        state_path = Path(state_file)
        if state_path.exists() and state_path.stat().st_size > 0:
            post_env = type(env).model_validate_json(state_path.read_text())
            post_env = _normalize_post_environment_for_grading(
                suite.name,
                pre_env,
                post_env,
            )
        else:
            warnings.warn(f"State file empty or missing for task {user_task.ID}")
            post_env = env

        # Supplement agent's tool call trace with MCP server log (ground truth)
        server_records = _read_tool_log(log_file)
        if server_records and not result.tool_calls:
            result.tool_calls = server_records

        # Grade utility
        utility = grade_utility(user_task, result, pre_env, post_env)

        # Grade security
        security = True
        if injection_task is not None:
            security = grade_security(injection_task, result, pre_env, post_env)

        return utility, security, result

    finally:
        # Clean up temp files
        for path in [state_file, log_file]:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass


def benchmark_suite_with_injections(
    agent: AgentEndpoint,
    suite: TaskSuite,
    attack: BaseAttack,
    user_tasks: Sequence[str] | None = None,
    injection_tasks: Sequence[str] | None = None,
    benchmark_version: str = "v1.1.1",
) -> SuiteResults:
    """Benchmark a suite with injection attacks.

    For each (user_task, injection_task) pair, generates injections via
    the attack, runs the agent, and grades utility + security.
    """
    suite_utility: dict[tuple[str, str], bool] = {}
    suite_security: dict[tuple[str, str], bool] = {}
    injection_utility: dict[str, bool] = {}

    # Select tasks
    if user_tasks is not None:
        tasks_to_run = [suite.get_user_task_by_id(tid) for tid in user_tasks]
    else:
        tasks_to_run = list(suite.user_tasks.values())

    if injection_tasks is not None:
        inj_tasks = {tid: suite.get_injection_task_by_id(tid) for tid in injection_tasks}
    else:
        inj_tasks = suite.injection_tasks

    # Check injection tasks run as user tasks (utility baseline)
    if not attack.is_dos_attack:
        for inj_id, inj_task in inj_tasks.items():
            try:
                utility, _, _ = run_task(
                    suite, agent, inj_task,
                    injection_task=None, injections={},
                    benchmark_version=benchmark_version,
                )
                injection_utility[inj_id] = utility
            except Exception as e:
                logging.warning(f"Injection task {inj_id} utility check failed: {e}")
                injection_utility[inj_id] = False

    # Run attack matrix
    for user_task in tasks_to_run:
        if attack.is_dos_attack:
            inj_ids = [next(iter(inj_tasks.keys()))]
        else:
            inj_ids = list(inj_tasks.keys())

        for inj_id in inj_ids:
            inj_task = suite.get_injection_task_by_id(inj_id)
            task_injections = attack.attack(user_task, inj_task)

            try:
                utility, security, _ = run_task(
                    suite, agent, user_task,
                    injection_task=inj_task,
                    injections=task_injections,
                    benchmark_version=benchmark_version,
                )
            except Exception as e:
                logging.warning(f"Task {user_task.ID} x {inj_id} failed: {e}")
                utility = False
                security = True

            if attack.is_dos_attack:
                security = not utility

            suite_utility[(user_task.ID, inj_id)] = utility
            suite_security[(user_task.ID, inj_id)] = security

    return SuiteResults(
        utility_results=suite_utility,
        security_results=suite_security,
        injection_tasks_utility_results=injection_utility,
    )


def benchmark_suite_without_injections(
    agent: AgentEndpoint,
    suite: TaskSuite,
    user_tasks: Sequence[str] | None = None,
    benchmark_version: str = "v1.1.1",
) -> SuiteResults:
    """Benchmark a suite for utility only (no attacks)."""
    suite_utility: dict[tuple[str, str], bool] = {}
    suite_security: dict[tuple[str, str], bool] = {}

    if user_tasks is not None:
        tasks_to_run = [suite.get_user_task_by_id(tid) for tid in user_tasks]
    else:
        tasks_to_run = list(suite.user_tasks.values())

    for user_task in tasks_to_run:
        try:
            utility, security, _ = run_task(
                suite, agent, user_task,
                injection_task=None, injections={},
                benchmark_version=benchmark_version,
            )
        except Exception as e:
            logging.warning(f"Task {user_task.ID} failed: {e}")
            utility = False
            security = True

        suite_utility[(user_task.ID, "")] = utility
        suite_security[(user_task.ID, "")] = security

    return SuiteResults(
        utility_results=suite_utility,
        security_results=suite_security,
        injection_tasks_utility_results={},
    )


# `run_adaptive_attack` was removed during the vendor: it depended on the
# fork-only `agentdojo.attacks.adaptive.AdaptiveAttack` (a Tier-2-adjacent
# addition we do not run). If adaptive attacks become in-scope again,
# reimplement against vanilla agentdojo's attack registry.
