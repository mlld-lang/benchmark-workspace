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

Declares tool functions (exes) and the tool catalog. Read tools produce records. Write tools carry operation declarations that reference payload records from `records.mld`.

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
    kind: "read",
    mlld: @search_emails,
    returns: @email_msg,
    labels: ["resolve:r", "known"],
    semantics: "Search the user's inbox by query string."
  },

  get_day_calendar_events: {
    kind: "read",
    mlld: @get_day_calendar_events,
    returns: @calendar_evt,
    labels: ["resolve:r", "known"],
    semantics: "Retrieve all calendar events for a specific day."
  },

  send_email: {
    kind: "write",
    mlld: @send_email,
    operation: {
      controlArgs: ["recipients"],
      payloadArgs: ["subject", "body", "attachments", "cc", "bcc"],
      exactPayloadArgs: ["subject"],
      payloadRecord: @email_payload,
      risk: ["exfil:send", "comm:w"],
      authorizable: true,
      semantics: "Send an email message to one or more recipients."
    }
  },

  create_calendar_event: {
    kind: "write",
    mlld: @create_calendar_event,
    operation: {
      controlArgs: [],
      payloadArgs: ["title", "start_time", "end_time", "description", "participants", "location"],
      payloadRecord: @calendar_event_payload,
      risk: ["calendar:w"],
      authorizable: true,
      semantics: "Create a new calendar event."
    },
    bind: { participants: [] }
  }
}

export { @tools }
```

Export only `@tools`. The tool catalog is the entire tool surface rig needs.

## Tool Declaration Fields

### For every tool

- `kind: "read" | "write"` — which phase handles it
- `mlld: @<exe_name>` — the mlld exe that invokes it
- `semantics: "..."` — short operation description for planner-facing op docs. Describes what the tool does, not when to use it.

### For read tools

- `returns: @<record>` — the record family produced. Required.
- `labels: [...]` — security labels applied (`resolve:r`, `known`, `untrusted`, etc.)

### For write tools

- `operation: { ... }` — required:
  - `controlArgs: [...]` — arg names that must have proof-bearing values. When a control arg is array-typed (e.g., `recipients: array`), rig checks proof per array element — every element must have its own resolved/known/selection proof.
  - `payloadArgs: [...]` — arg names that take user/derived/extracted content
  - `updateArgs: [...]` — optional; arg names for modify operations (rejects no-change updates)
  - `exactPayloadArgs: [...]` — optional; payload args that must appear verbatim in task text
  - `payloadRecord: @<record>` — optional; static schema for payload coercion at execute boundary
  - `risk: [...]` — risk category labels (`exfil:send`, `destructive:targeted`, etc.)
  - `correlateControlArgs: true` — optional; require all control args to share source record instance
  - `authorizable: true | false` — optional; default `true`; `false` means the tool cannot be authorized at all (absolute deny)
  - `semantics: "..."` — same as above

- `bind: { argname: value }` — optional; pre-bind default values for args the planner doesn't need to authorize

## Array-Typed Args and Multi-Recipient Writes

When a tool accepts an array-typed arg (e.g., `recipients: array` on `send_email`):

**Record author rules:**
- The payload record field type must match the tool exe signature exactly. If the tool declares `recipients: array`, the `payloadRecord` declares `recipients: array`. Mismatched types produce a build-time error.
- Array fields declare their element type where meaningful (e.g., `recipients: array` as strings is the default; structured array element types can be specified as the suite matures).

**Dispatch rules:**
- For array-typed control args, rig checks proof **per element**. Every element must have its own resolved, known, or selection ref — validated independently.
- For array-typed payload args, `@cast` validates each element against the record's element type.

**Planner usage patterns:**
- Identical message, multiple recipients: single execute with `recipients: ["a@x", "b@x"]`. Both elements need proof; bodies are identical.
- Personalized messages per recipient: one execute per recipient with `recipients: ["a@x"]` (single-element array) and a distinct body. This is a planner pattern for tasks requiring personalization — not a framework constraint.

The framework supports both patterns via the same tool signature. Which one a task uses is a planner decision, not a framework configuration.

## What Suites Do NOT Provide

- No `shelf.mld` — rig manages state from records
- No standalone `contracts.mld` — write payloads are records referenced from tool ops; read-side extract/derive uses the target write's `payloadRecord` or inline planner schemas
- No `policy.mld` — risk compilation is derived from tool operation metadata
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
- Every record referenced in `payloadRecord` is defined in `records.mld`
- `controlArgs` and `payloadArgs` together cover every arg name the tool exe declares
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
