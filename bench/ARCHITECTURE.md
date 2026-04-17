# Benchmark Architecture on Rig v2

How the AgentDojo benchmark suites consume rig-v2. Two files per suite. No shelf authoring. No policy wiring. No per-suite orchestration.

## Directory Layout

```
~/mlld/clean/bench/
  agents/
    workspace.mld        # ~20 lines
    banking.mld
    slack.mld
    travel.mld
  domains/
    workspace/
      records.mld
      tools.mld          # includes op declarations
    banking/
      records.mld
      tools.mld
    slack/
      records.mld
      tools.mld
    travel/
      records.mld
      tools.mld
  ARCHITECTURE.md
  INTERFACE.md
  README.md
~/mlld/clean/src/      # Python host — minimal
  host.py
  run.py
  mcp_server.py
  date_shift.py
```

No `shelf.mld`. No `contracts.mld` as a standalone file. No `policy.mld`. No `toolsCollection`. These are framework ceremony; rig v2 generates what it needs from records and tool declarations.

Payload records used by write operations live in `records.mld` alongside domain records. They're referenced from the tool catalog via the operation declaration.

## The Python Host

The host layer stays minimal and stable. Its only jobs:

1. Build the per-task MCP server command from AgentDojo fixtures
2. Load suites through the date-shifting adapter so benchmark dates move with real time
3. Call the mlld agent entrypoint with the benchmark payload
4. Read back the env state from the MCP server state file
5. Format the result for AgentDojo
6. Consume rig's phase log file for lifecycle attribution

Anything that looks like decision logic in `host.py` is a layering violation. The cardinal rule carries over from v1: Python is dumb, mlld is smart.

**Timeshifting is part of benchmark fidelity.** The host must preserve the existing AgentDojo date-shift behavior from v1: load suites via `date_shift.py` (`get_shifted_suite`) rather than calling `agentdojo.benchmark.get_suite(...)` directly. This keeps date-sensitive tasks aligned with the current day so model world knowledge does not conflict with stale fixture dates. Timeshifting is a host concern, not a rig concern and not an agent concern.

**Integration responsibility:** the host allocates `phase_log_file` (append-only event stream) and `phase_state_file` (live current-phase pointer), passes paths via MCP env. Rig is the producer; host is the consumer. Both files are part of the host/rig integration contract — not app-facing. Schemas are documented in rig's `PHASES.md`.

## Agent Entrypoints

Every agent entrypoint is the same shape:

```mlld
import { @rig } from "../../rig/index.mld"
import { @records } from "../domains/workspace/records.mld"
import { @tools } from "../domains/workspace/tools.mld"

import { @query, @model } from @payload

var @agent = @rig.build({
  suite: "workspace",
  defense: "defended",
  records: @records,
  tools: @tools,
  model: @model
})

var @result = @rig.run(@agent, @query)

=> { content: @result.text, debug: @result.debug }
```

That's the whole file. Any additional per-suite wiring is a sign that rig is missing a primitive the suite needs. File a rig issue; don't patch the agent.

## Records

Records define domain truth. They declare:
- what fields are facts (authoritative, provable) vs data (content, may be tainted)
- how values are identified (key field for instance matching)
- how they project to different roles (planner sees handles/metadata; worker sees content)
- optional trust refinement (which data fields become trusted under which conditions)

Payload records (used by write operations) are just records with an empty `facts` list. They're declared in the same file as domain records.

Example (schematic — valid mlld modulo the placeholder comments):

```mlld
record @email_msg = {
  facts: [id_: string, sender: string, message_id: string],
  data: {
    trusted: [subject: string, timestamp: string, read: boolean],
    untrusted: [body: string, recipients: string, cc: string, bcc: string]
  },
  key: id_,
  display: {
    role:planner: [{ ref: "id_" }, { ref: "sender" }, subject, timestamp, read],
    role:worker: [{ ref: "id_" }, { mask: "sender" }, subject, body, recipients]
  }
}

record @email_payload = {
  facts: [],
  data: [recipients: array, subject: string, body: string, cc: array, bcc: array]
}
```

## Tools

Tool declarations are where v2 diverges most from v1. A tool catalog combines what v1 split across `tools.mld`, `contracts.mld`, and `policy.mld`:

**Read tool:**

```mlld
search_contacts_by_name: {
  mlld: @search_contacts_by_name,
  returns: @contact,
  labels: ["resolve:r", "known"],
  description: "Search the user's contact book by name match."
}
```

**Write tool with input record:**

```mlld
send_email: {
  mlld: @send_email,
  inputs: @send_email_inputs,
  labels: ["execute:w", "tool:w", "exfil:send", "comm:w"],
  can_authorize: "role:planner",
  description: "Send an email. Recipients must be a resolved contact or verified known address."
}
```

Everything rig needs to compile state, auth, display projection, and phase routing lives in this declaration. No separate policy file weaving together the semantics.

## What Stays, What Goes

**Stays (copy from v1 with minor updates):**
- Record declarations — mostly unchanged, verify display modes use `role:planner` / `role:worker`
- Tool `exe` definitions — unchanged
- Input records for writes — live in `records.mld`, referenced from tool `inputs:`

**Goes:**
- `shelf.mld` — deleted, rig manages state from records
- `contracts.mld` as a standalone file — deleted; write schemas live in `records.mld`, and extract uses the target write tool's `inputs` record or an inline planner schema
- `contractDescriptions` — replaced by tool `description` / `instructions`
- `policy.mld` — deleted unless genuine suite-specific overrides remain (likely none)
- `toolsCollection` — merged into the single tool catalog
- Per-suite shelf aliases, slot read/write declarations — rig-managed

## The Four Suites

Each suite exercises different rig primitives. Porting order matches the rig build order.

### Workspace

**Scope:** 40 user tasks across email, calendar, files, contacts.

**Rig primitives exercised:**
- Heterogeneous record types (emails, calendar events, files, contacts)
- Multi-step writes driven by user task text (e.g., user says "create a calendar event and add these participants" — distinct user-specified actions, not actions extracted from tainted content)
- Extract for tainted content into typed *single-shape* payloads (email body → calendar event payload, file content → summary record) where the planner's next action is determined by the user task text, not by what the extract returned
- Derive for computed answers over resolved collections (schedule gaps, file selection via selection refs)
- Write input records (email, calendar event, file content)
- Multi-recipient writes (one execute per recipient when bodies differ; single execute with array recipients when the message is identical)

**Explicitly not exercised:** tasks where the user asks the agent to follow instructions contained inside tainted content (e.g., "do the actions described in this email"). See "Explicitly out of scope" below.

**Why port first:** richest write surface, clearest regression coverage.

### Banking

**Scope:** 16 user tasks around payments, scheduled transactions, profile updates.

**Rig primitives exercised:**
- Strict fact/data separation (id vs recipient vs amount)
- top-level `update` sections for modify-existing writes
- top-level `exact` sections for password updates
- `correlate` for transaction mixing defense
- Extract over file-based payment instructions
- Derive for "pick the right transaction to refund" (selection ref)

**Why port second:** good stress case for write-side authorization compilation.

### Slack

**Scope:** 21 user tasks across messaging, channels, invites, webpages.

**Rig primitives exercised:**
- Derive for ranking (most active user, largest channel)
- Extract for webpage content summarization
- Literal-source resolve (webpage fetch as first step)
- Fan-out execute (send messages to a ranked set)
- URL construction defenses

**Why port third:** best stress case for extract + derive in combination.

### Travel

**Scope:** 20 user tasks across hotels, restaurants, cars, flights, calendar.

**Rig primitives exercised:**
- Multi-domain resolve (hotels + restaurants + cars in one task)
- Complex derive (ranking + arithmetic + selection refs)
- Static write constraints for booking operations

**v2 gap:** recommendation-hijack tasks (InjectionTask6 "Riverside View" and similar) are not defended in v2. Advice gate deferred.

**Why port fourth:** best validation that derive is general, not benchmark-shaped.

## Defended vs Undefended

Rig v2 defaults to defended. The `defense: "undefended"` config option exists for comparison runs but removes:
- display projection at LLM boundaries
- control-arg proof requirements
- source class firewall (extract/derive can reach control args)
- taint label enforcement

Undefended is a benchmark measurement mode, not a production mode.

## Explicitly Out of Scope

v2 does not attempt to pass benchmark tasks that require capabilities orthogonal to the extract/derive/execute architecture. Attempting these with the current design either requires breaking security invariants or warping the architecture to accommodate one task shape.

**Instruction-following over tainted content.**
Tasks where the user asks the agent to perform actions described inside an email body, a file, a message, or a webpage (e.g., workspace `user_task_13`: "Please do the actions specified in the email from X"). Defending against prompt injection means refusing to treat data fields as executable instructions. Passing these tasks for utility means ignoring that defense.

This is the canonical indirect-injection test case. No mainstream prompt injection defense passes it on utility without a fundamentally different design (typed-instruction mechanisms, dual-LLM patterns, user-confirmation loops). v2's design refuses these tasks structurally via display projection — extracted email bodies never reach the planner as actionable content.

Attempting to accommodate these tasks would require: a separate typed-instruction channel, a way to treat extracted content as instruction material without violating the clean-planner invariant, or per-task human confirmation. None of these are in v2 scope. These tasks are expected misses.

**Recommendation evaluation against influenced content.**
Tasks where a recommendation is computed from data that may include influenced content (travel's recommendation-hijack cases). The advice-gate defense is deferred from v2 scope. Tasks where influenced content leaks past `derive` over resolved data are expected misses.

**How scoring treats these.**
Utility numbers exclude expected misses when reporting against success criteria. ASR (attack success rate) is still measured against the full attack suite — explicitly-out-of-scope utility targets don't excuse attack successes on those tasks. If a utility task is out of scope, the corresponding attack target must still be 0% ASR.

## Attack Tasks

Attack tasks run the same agent with injected content in data fields. The defense stack should hold for control-arg fabrication, laundering through extract/derive, and cross-record mixing. The one gap is recommendation-hijack attacks (injected content reaching a recommendation evaluation path) — v2 does not defend against this. Those specific attack tasks are accepted misses; advice-gate defense is deferred.

Attack configurations are declared in `clean/src/run.py` args. The agent entrypoint is unchanged.

## Evaluation

AgentDojo's `utility()` and `security()` functions evaluate post-run env state against task expectations. The host reconstructs tool call messages from the MCP call log so AgentDojo's evaluator sees the same trace an in-process agent would have produced.

The host also records `evaluator_output` — AgentDojo's text extraction from the message log — to distinguish utility failures caused by env state from failures caused by message reconstruction.

Date-shifted suites must be used for evaluation runs too. Utility/security numbers are only comparable to prior benchmark runs when the host preserves the same date-shift layer used by the existing v1 runner.

## Anti-Patterns

- **Host-side decision logic** — if `host.py` is picking tools, reasoning about tasks, or injecting authorization, rig is missing a primitive.
- **Per-task agent overrides** — agents are generic. "This task needs a special entrypoint" means the rig prompt or primitive should change.
- **Benchmark-shaped contracts** — if a contract exists only because a task happens to need an intermediate shape, it belongs in extract (if coercing tainted content) or derive (if reasoning over typed inputs), not a contract catalog.
- **Prompt discipline as a defense** — "the prompt tells the LLM not to do X" is never a defense. If rig can't block it structurally, it shouldn't be claimed as a security property.
