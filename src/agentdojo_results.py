"""Result types for agent-agnostic benchmark evaluation."""

from dataclasses import dataclass, field
from typing import Any

from typing_extensions import TypedDict


@dataclass
class ToolCallRecord:
    """Record of a single tool call made by an agent."""

    function: str
    args: dict[str, Any]
    result: str | None = None
    error: str | None = None


@dataclass
class LabelFlowResult:
    """Label-flow security analysis (mlld agents only)."""

    tainted_data_reached_restricted_ops: bool
    denials: list[dict[str, Any]] = field(default_factory=list)
    label_violations: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SubAgentTrace:
    """Trace of a sub-agent's execution in multi-agent scenarios."""

    agent_name: str
    tool_calls: list[ToolCallRecord]
    capabilities: list[str] | None = None


@dataclass
class AgentResult:
    """Structured result from an agent execution."""

    content: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    label_flow: LabelFlowResult | None = None
    sub_agents: list[SubAgentTrace] | None = None


class SuiteResults(TypedDict):
    """Aggregated results for a benchmark suite run."""

    utility_results: dict[tuple[str, str], bool]
    security_results: dict[tuple[str, str], bool]
    injection_tasks_utility_results: dict[str, bool]
