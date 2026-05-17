"""Agent endpoint protocol for agent-agnostic benchmarking."""

from typing import Any, Protocol, runtime_checkable

from agentdojo_results import AgentResult


@runtime_checkable
class AgentEndpoint(Protocol):
    """Protocol for agent endpoints.

    Any agent that implements this protocol can be benchmarked. The agent
    receives a prompt, an MCP server command, and tool descriptions, then
    connects to the tool server, executes the task, and returns a result.

    The agent MUST NOT import agentdojo internals. Communication happens
    only through this protocol:
      - query: what to do
      - mcp_server_cmd: how to access tools
      - tools: what tools are available (JSON schemas)
    """

    name: str

    def run(
        self,
        query: str,
        mcp_server_cmd: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> AgentResult:
        """Execute a task.

        Args:
            query: The user task prompt.
            mcp_server_cmd: Shell command to launch the MCP tool server.
                The agent should connect to this server to access suite tools.
            tools: Tool descriptions as JSON schema dicts. Each entry has
                'name', 'description', and 'parameters' keys. Agents can
                use this to format tool info for their LLM, or discover
                tools from the MCP server directly.

        Returns:
            Structured result with output text, tool call trace, and optional
            label-flow analysis.
        """
        ...

    def close(self) -> None:
        """Clean up resources."""
        ...
