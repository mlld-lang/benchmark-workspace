# Benchmark Suite Interface

What a suite has to provide to rig v2. Two files. That's it.

## `domains/<suite>/records.mld`

Declares the domain records. Each record describes:
- `facts` — authoritative fields (trust-bearing after resolve)
- `data` — content fields (may be tainted; split into `trusted` and `untrusted` if needed)
- `key` — identifier field for instance matching
- `display` — per-role display projections

Every record used in the suite goes here, including payload records used by write operations. Payload records are just records with `facts: []`.

```mlld
>> domains/workspace/records.mld

record @email_msg = {
  facts: [id_: string, sender: string, message_id: string],
  data: {
    trusted: [subject: string, timestamp: string, read: boolean],
    untrusted: [body: string, recipients: string, cc: string, bcc: string]
  },
  key: id_,
  display: {
    role:planner: [{ ref: "id_" }, { ref: "sender" }, subject, timestamp, read],
    role:worker: [{ ref: "id_" }, { mask: "sender" }, subject, body]
  }
}

record @calendar_evt = {
  facts: [id_: string, start_time: string, end_time: string],
  data: [title: string, description: string, location: string, participants: string],
  key: id_,
  display: {
    role:planner: [{ ref: "id_" }, title, start_time, end_time],
    role:worker: [{ ref: "id_" }, title, description, start_time, end_time, location]
  }
}

record @email_payload = {
  facts: [],
  data: [recipients: array, subject: string, body: string, cc: array, bcc: array]
}

record @calendar_event_payload = {
  facts: [],
  data: [title: string, start_time: string, end_time: string, description: string, participants: string, location: string]
}

var @records = {
  email_msg: @email_msg,
  calendar_evt: @calendar_evt,
  email_payload: @email_payload,
  calendar_event_payload: @calendar_event_payload
}

export { @records, @email_msg, @calendar_evt, @email_payload, @calendar_event_payload }
```

Export individual records plus the `@records` catalog map.

## `domains/<suite>/tools.mld`

Declares tool functions (exes) and the tool catalog. Read tools return record families. Write tools declare `inputs: @record` and express input policy through that record's top-level sections.

```mlld
>> domains/workspace/tools.mld

import { @mcp } from "../../mcp-bridge.mld"
import {
  @email_msg, @calendar_evt, @email_payload, @calendar_event_payload
} from "./records.mld"

>> ==== Read tools ====

exe resolve:r, tool:r @search_emails(query) = [
  => @mcp.searchEmails(@query)
] => email_msg

exe resolve:r, tool:r @get_day_calendar_events(day) = [
  => @mcp.getDayCalendarEvents(@day)
] => calendar_evt

>> ==== Write tools ====

exe execute:w, exfil:send, comm:w, tool:w @send_email(recipients: array, subject, body, attachments: array, cc: array, bcc: array) = [
  => @mcp.sendEmail(@recipients, @subject, @body, @attachments, @cc, @bcc)
]

exe execute:w, calendar:w, tool:w @create_calendar_event(title, start_time, end_time, description, participants: array, location) = [
  => @mcp.createCalendarEvent(@title, @start_time, @end_time, @description, @participants, @location)
]

>> ==== Tool catalog ====

var @tools = {
  search_emails: {
    mlld: @search_emails,
    returns: @email_msg,
    labels: ["resolve:r", "known"],
    description: "Search the user's inbox by query string."
  },

  get_day_calendar_events: {
    mlld: @get_day_calendar_events,
    returns: @calendar_evt,
    labels: ["resolve:r", "known"],
    description: "Retrieve all calendar events for a specific day."
  },

  send_email: {
    mlld: @send_email,
    inputs: @send_email_inputs,
    labels: ["execute:w", "tool:w", "exfil:send", "comm:w"],
    can_authorize: "role:planner",
    description: "Send an email message to one or more recipients."
  },

  create_calendar_event: {
    mlld: @create_calendar_event,
    inputs: @create_calendar_event_inputs,
    labels: ["execute:w", "tool:w", "calendar:w"],
    can_authorize: "role:planner",
    description: "Create a new calendar event.",
    bind: { participants: [] }
  }
}

export { @tools }
```

Export only `@tools`. The tool catalog is the entire tool surface rig needs.

## Tool Declaration Fields

### For every tool

- `mlld: @<exe_name>` — the mlld exe that invokes it
- `labels: [...]` — routing and risk labels (`resolve:r`, `extract:r`, `execute:w`, `tool:r`, `tool:w`, `calendar:w`, `exfil:send`, etc.)
- `description: "..."` — short planner-facing operation description
- `instructions: "..."` — optional extra usage guidance
- `bind: { argname: value }` — optional; pre-bind default values for args the planner doesn't need to supply

### For read tools

- `returns: @<record>` — the record family produced. Required.

### For write tools

- `inputs: @<record>` — required input record. Facts define proof-bearing control args. Data defines payload args. Top-level policy sections on the record (`exact`, `update`, `allowlist`, `blocklist`, `optional_benign`, `correlate`, `validate`) replace the old legacy write metadata.
- `can_authorize: "role:planner" | false | { ... }` — optional planner-authorization surface. `false` hard-denies the tool.

## Array-Typed Args and Multi-Recipient Writes

When a tool accepts an array-typed arg (e.g., `recipients: array` on `send_email`):

**Record author rules:**
- The input-record field names and types must match the tool exe signature exactly, except for args supplied via `bind`.
- Array fields declare their element type where meaningful.

**Dispatch rules:**
- For array-typed fact fields, rig checks proof **per element**. Every element must have its own resolved, known, or selection ref — validated independently.
- For array-typed data fields, record coercion validates each element against the field type.

**Planner usage patterns:**
- Identical message, multiple recipients: single execute with `recipients: ["a@x", "b@x"]`. Both elements need proof; bodies are identical.
- Personalized messages per recipient: one execute per recipient with `recipients: ["a@x"]` (single-element array) and a distinct body. This is a planner pattern for tasks requiring personalization — not a framework constraint.

The framework supports both patterns via the same tool signature. Which one a task uses is a planner decision, not a framework configuration.

## What Suites Do NOT Provide

- No `shelf.mld` — rig manages state from records
- No standalone `contracts.mld` — write schemas live in the input record referenced by `inputs:`; read-side extract/derive uses a write tool's input record or an inline planner schema
- No `policy.mld` — risk compilation is derived from tool labels and input-record policy sections
- No `toolsCollection` — the tool catalog is both the routing source and the auth source
- No per-suite orchestration overrides
- No planner prompt customization for domain-specific behavior

If a suite seems to need one of these, the abstraction is wrong. File a rig issue.

## Optional Overrides

Some suites legitimately need narrow overrides. These go in the agent entrypoint config, not separate files:

```mlld
var @agent = @rig.build({
  suite: "travel",
  defense: "defended",
  records: @records,
  tools: @tools,
  model: @model,
  overrides: {
    policy: {
      authorizations: { deny: ["cancel_reservation_all"] }
    }
  }
})
```

Overrides should be true policy overrides (deny-list extensions, non-default risk labels). Not workflow hints, not prompt tweaks, not slot customization.

## Validation

A suite is well-formed when:

- Every tool listed in `@tools` has a matching exe import
- Every record referenced by `inputs:` or `returns:` is defined in `records.mld`
- Every exe parameter is covered by an input-record field or `bind`
- `mlld validate <suite dir>` passes
- A trivial run completes end-to-end: `mlld <agent_entrypoint.mld> --payload '{"query": "ping"}'`

Rig v2's `@rig.build` validates the config at build time and throws with a clear error if anything is off. The error message points at the specific tool or record with the problem.

## Migration from v1

Porting a v1 suite to v2 is mostly deletion:

1. **Copy records.mld** — may need display mode updates (`role:planner`/`role:worker`). Add payload records from v1's `contracts.mld` here.
2. **Build tools.mld** — merge v1's `tools.mld` + `contracts.mld` write payload references + `policy.mld` risk labels into one tool catalog.
3. **Delete** `shelf.mld`, standalone `contracts.mld`, `policy.mld`, any read-side contract declarations.
4. **Shrink agent entrypoint** to the ~20-line shape.

Expect each suite to drop ~60% of its line count. The remaining code is genuinely domain-specific.
