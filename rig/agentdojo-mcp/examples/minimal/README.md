# minimal example

The smallest possible record-attachment over agentdojo-mcp.

`records.mld` declares three records (one read row type, one singleton, one write input record). `tools.mld` imports the AgentDojo banking tools via MCP and wraps each call with `exe` + record + labels.

To run this example end-to-end you need a rig agent file that imports `@tools` and calls `@rig.run(...)`. See `clean/bench/agents/banking.mld` for the production version.

The point of this example: showing that record attachment is a mlld-side wrapper concern, not something the MCP server cares about. The same `agentdojo-mcp` server works for any record/policy configuration the wrapping layer wants to apply.
