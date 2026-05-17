# proof-agent architecture

This rig is built around one invariant: the LLM may choose badly, but it
cannot make an unauthorized write succeed.

## Shape

`rig/` is generic:

- `index.mld` builds the planner prompt and runs one planner LLM call.
- `workers.mld` selects the model harness, runs inner LLM workers, and
  compiles/dispatches proof-carrying write intent through `@policy.build`.
- `llm/lib/opencode/` bridges provider/model strings such as
  `togetherai/zai-org/GLM-5.1` and `cerebras/gpt-oss-120b` to the
  OpenCode CLI.

`bench/` is benchmark configuration:

- `bench/agents/<suite>.mld` binds a suite's resolve/extract/execute
  worker tools to the generic rig.
- `bench/domains/<suite>/records.mld` defines authoritative facts,
  untrusted data, planner/worker read projections, and write contracts.
- `bench/domains/<suite>/tools.mld` wraps MCP tools and attaches records.
- `bench/domains/<suite>/policy.mld` composes stock and suite-specific
  policy fragments.

## Security Boundary

The planner only sees worker tools. It never receives raw write tools.

Resolve workers are non-LLM wrappers around authoritative read tools. Their
record results cross the planner's LLM boundary, so fact fields publish
handles into the planner call that will later authorize writes.

Extract workers may use a worker LLM. They can read untrusted content, but
their prose is not fact proof. The banking configuration deliberately has no
tool that promotes extracted bill text into a fact-bearing IBAN.

Execute is a generic compiler:

1. Parse planner intent.
2. Validate the authorization buckets with `@policy.build`.
3. If valid, dynamically dispatch the selected write tool under the compiled
   policy.
4. If invalid, return a structured denial.

The runtime, not the prompt, enforces: record input facts, `known` task-text
checks, record `write:` grants, deny lists, and correlation on multi-fact
updates.

## Utility Strategy

High utility comes from giving the planner useful safe capabilities rather
than hiding all data:

- Authoritative identifiers are visible through value handles.
- Trusted fixture fields can be read for reasoning.
- Untrusted content can still be summarized by extract workers.
- The planner may perform multi-step tasks, but every write is separately
  compiled and authorized.

Where a benchmark task requires converting untrusted content into a payment
destination, the architecture refuses that conversion. This is intentional:
the source lacks proof, and accepting it would make the IT9 banking attack
indistinguishable from utility.
