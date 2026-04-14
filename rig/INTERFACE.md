# Rig Public Interface

The contract between rig and apps built on it. This is frozen for v2 — changes require explicit architectural review.

## Public Surface

Rig exposes two functions:

### `@rig.build(config)`

Compiles an agent from domain declarations. Returns an agent handle to be passed to `@rig.run`.

Config shape:

```mlld
{
  suite: string,                 // suite name for logging/attribution
  defense: "defended" | "undefended",  // default: "defended"
  model: string,                 // LLM model identifier
  records: @recordCatalog,       // from records.mld
  tools: @toolCatalog,           // from tools.mld
  maxIterations?: number,        // default: 40
  overrides?: {                  // optional narrow overrides
    policy?: @policy,
    prompts?: @promptOverrides
  }
}
```

The agent handle is opaque to the app. It contains compiled routing, compiled policy, display configuration, and prompt templates. Apps should not inspect or modify it.

### Policy synthesis

In defended mode, `@rig.build` synthesizes the policy from the tool catalog — apps do not provide `policy.mld`. Rules generated:

- Default built-in rule set including `no-send-to-unknown`, `no-destroy-unknown`, `no-secret-exfil`, `no-untrusted-destructive`, `no-unknown-extraction-sources`, and `untrusted-llms-get-influenced`
- `operations` reverse-mapping from `tool.operation.risk` labels across the catalog
- `authorizations.authorizable["role:planner"]` populated from tools where `operation.authorizable` is true (the default)
- `authorizations.deny` populated from tools where `operation.authorizable: false` (hard rejection — cannot be authorized even with overrides)
- `no-novel-urls` included conditionally when any tool declares URL-fetch risk

Full synthesis algorithm is specified in `PHASES.md` §Base Policy Synthesis.

### Overrides

`overrides.policy` accepts narrow additive extensions only. Deny lists union. Locked rules from the synthesized policy are preserved. Suite overrides cannot weaken rig defaults — they can only add restrictions.

### `@rig.run(agent, query)`

Runs a single task end-to-end. Returns the final result and debug metadata.

Return shape:

```mlld
{
  text: string,                  // user-facing final answer
  terminal: "complete" | "blocked" | "max_iterations",
  debug: {
    execution_log: [...],        // phase-by-phase log with session IDs
    planner_iterations: [...],   // planner decisions (one entry per iteration)
    phase_events: [...],         // lifecycle events for host attribution
    last_decision: {...}
  }
}
```

Apps typically wrap this:

```mlld
var @result = @rig.run(@agent, @query)
=> { content: @result.text, debug: @result.debug }
```

## Record Catalog

A record catalog is a map of record definitions. Rig reads this to generate state namespaces, display projections, and trust refinement rules.

```mlld
var @recordCatalog = {
  email_msg: @email_msg_record,
  calendar_evt: @calendar_evt_record,
  contact: @contact_record,
  file_entry: @file_entry_record,
  email_payload: @email_payload_record
}
```

Each record definition declares facts vs data, display modes, and optional key/trust refinement. This is existing mlld record syntax — see `~/mlld/mlld/docs/src/atoms/core/31-records--basics.md`.

Apps declare records in `records.mld`. They do not declare derived or extracted variants as separate records — rig generates storage for extract and derive outputs from the planner's inline schemas, not from pre-declared catalog entries.

## Tool Catalog

A tool catalog declares what operations exist and their semantics.

```mlld
var @toolCatalog = {
  // Read tools — resolve records
  search_contacts_by_name: {
    kind: "read",
    mlld: @search_contacts_by_name,
    returns: @contact,             // record family produced
    labels: ["resolve:r", "known"],
    semantics: "Search the user's contact book by name match."
  },

  // Write tools — perform side effects
  send_email: {
    kind: "write",
    mlld: @send_email,
    operation: {
      controlArgs: ["recipients"],        // must have proof-bearing values
      payloadArgs: ["subject", "body"],   // may come from derive/extract or literals
      exactPayloadArgs: ["subject"],      // must appear verbatim in task text
      payloadRecord: @email_payload,      // static payload schema
      risk: ["exfil:send", "comm:w"],
      authorizable: true,
      semantics: "Send an email message to a recipient."
    }
  },

  create_calendar_event: {
    kind: "write",
    mlld: @create_calendar_event,
    operation: {
      controlArgs: [],
      payloadArgs: ["title", "start_time", "end_time", "description", "location"],
      payloadRecord: @calendar_event_payload,
      risk: ["calendar:w"],
      authorizable: true,
      semantics: "Create a new calendar event."
    },
    bind: { participants: [] }            // pre-bound default args
  }
}
```

Operation semantics strings describe what the operation does — creates vs updates vs deletes, whether a grounded target is required. These get surfaced to the planner as tool docs. They must describe operation semantics, not task strategy. "Modify an existing scheduled payment identified by id" is fine. "Prefer this for rent updates" is not.

Tool kinds:
- `read` — returns records. Resolves entities. No side effects.
- `write` — performs side effects. Requires an operation declaration. Subject to compiled authorization.

## Source Class Refs

Every value referenced in planner intent carries an explicit source class. Rig compiles these into the correct authorization bucket and validates against state provenance. The planner never writes `resolved` / `known` / `allow` buckets directly — it writes typed refs, and rig lowers them.

### Ref forms

Structured ref objects for all phase inputs except compose sources (see below).

**Specific value ref (resolves to a single value with factsource):**
```
{ source: "resolved", record: "contact", handle: "h_xyz", field: "email" }
```

**Family ref (whole record family — used as derive sources, resolve tool args expecting collections, compose inputs):**
```
{ source: "resolved", record: "contact" }
```

**Named value ref (field of a named extract/derive result):**
```
{ source: "extracted", name: "event_details", field: "title" }
{ source: "derived", name: "largest_file", field: "filename" }
```

**Named whole-result ref (the entire named result object):**
```
{ source: "extracted", name: "event_details" }
{ source: "derived", name: "largest_file" }
```

**Known literal (user-typed value from task text):**
```
{ source: "known", value: "Meeting follow-up" }
```

**Selection ref (derive-only producer; lowers to backing resolved instance at consumption):**
```
{ source: "selection", backing: { record: "hotel", handle: "h_abc" } }
```

**Tool-level unconstrained (only for tools with no controlArgs):**
```
{ source: "allow" }
```

### Compose sources (string sugar)

The compose-phase `sources` field accepts string namespace sugar as convenience. **This is compose-only and non-canonical.** It cannot appear in execute, resolve, extract, or derive args.

```
"resolved.*"      // all resolved state
"derived.*"       // all derived results
"extracted.*"     // all extracted results
"execution_log"   // attestation log
```

Compose may also use structured refs in sources for precise selection. Prefer structured refs; the string form is shorthand.

**Grammar notes:**
- `source` is authoritative. Rig never infers source class from ref contents.
- `record`, `handle`, `field`, `name` are mandatory components when the source requires them. Missing components are a hard error.
- `source: "selection"` refs are produced by derive workers during output validation. Extract workers cannot produce selection refs (spike 42). The planner cannot author a selection ref from scratch — rig validates that the backing instance existed in the derive input set.

**Rules:**
- `resolved` refs require a handle that resolves to current state with a factsource.
- `known` values are verified against the query text by `@policy.build`.
- `extracted` and `derived` refs provide typed values for payload args only. Cannot fill control args directly.
- `selection` refs are the only path from derive to control-arg proof. Selection is derive-only as a producer. Rig validates the backing ref against the derive source phase's input set.
- `allow` is only valid for tools with no controlArgs. Tools with controlArgs require structured arg refs — the planner cannot bypass per-arg source-class discipline by emitting `allow`. Note: the lower-level `@policy.build` primitive (see `~/mlld/benchmarks/labels-policies-guards.md` §6) accepts `allow: { tool: true }` unconditionally; rig v2's planner-facing contract narrows this. Suites needing unconditional authorization on a controlArgs tool can use `overrides.policy` with the flat form — that's explicit app-level escape, not planner intent.

## Planner Intent Shape

Every planner decision is one of:

```mlld
// Resolve: ground a record family
{
  phase: "resolve",
  tool: "search_contacts_by_name",
  args: { name: "Sarah Baker" },
  purpose: "resolve the recipient contact"
}

// Extract: coerce tainted content into a typed payload
{
  phase: "extract",
  source: { source: "resolved", record: "email_msg", handle: "h_email123", field: "body" },
  schema: @calendar_event_payload,   // record; typically the write tool's payloadRecord
  name: "event_details",              // name under which the extracted value is stored
  purpose: "extract the event time and location from a meeting invite email"
}

// Derive: compute a derived result from typed inputs
{
  phase: "derive",
  sources: [
    { source: "resolved", record: "calendar_evt" },
    { source: "resolved", record: "contact" }
  ],
  goal: "find the time gap between the previous event end and the target event start",
  schema: {
    target_event_start: "string",
    prior_event_end: "string",
    gap_minutes: "number"
  },
  name: "schedule_gap",
  purpose: "compute the schedule gap"
}

// Execute: perform one write with typed source-class args
{
  phase: "execute",
  operation: "send_email",
  args: {
    recipients: { source: "resolved", record: "contact", handle: "h_xyz", field: "email" },
    subject: { source: "known", value: "Meeting follow-up" },
    body: { source: "derived", name: "email_body", field: "text" }
  },
  purpose: "send the follow-up email"
}

// Compose: render the final answer
{
  phase: "compose",
  sources: ["resolved.*", "derived.*", "extracted.*", "execution_log"],
  purpose: "tell the user the email was sent"
}

// Blocked: halt with reason
{
  phase: "blocked",
  reason: "multiple calendar events match 'dental check-up'; clarification needed"
}
```

## Worker Return Shapes

Workers return clean attestation via `->` or canonical record return via `=>`.

### Resolve worker

```mlld
-> {
  status: "resolved",
  record_type: "contact",
  count: 1,
  handles: [@contacts.mx.handles]
}
```

Or canonical return when the planner needs to inspect the record:

```mlld
=> @grounded as record @contact
```

### Extract worker

```mlld
-> {
  status: "extracted",
  schema_name: "calendar_event_payload",
  name: "event_details",
  provenance: "extracted",
  preview_fields: [...]
}
```

The typed payload is stored under `extracted.<name>` (rig-internal state; app doesn't reference it).

### Derive worker

```mlld
-> {
  status: "derived",
  schema_name: "schedule_gap",
  name: "schedule_gap",
  provenance: "derived",
  selection_refs: [...]
}
```

Selection refs, if produced, are validated by rig before being included. The planner receives attested selection refs it can use in subsequent execute args.

### Execute worker

```mlld
-> {
  status: "sent" | "denied" | "error",
  tool: "send_email",
  result_handles?: [...],
  summary: "email sent to h_abc"
}
```

### Compose worker

```mlld
=-> @composedText
```

Same value to both `->` (planner) and `=>` (mlld caller).

## State Model

Rig manages state internally from declarations. Apps never read or write state paths directly — the planner references values through typed refs, and rig resolves them.

- Resolved records are stored keyed by handle/instance key, typed by record.
- Extract outputs are stored under planner-provided names with extracted provenance.
- Derive outputs are stored under planner-provided names with derived provenance.
- Framework state (execution log, last write) is rig-internal.

State is always read display-projected at LLM boundaries per role. The planner sees `role:planner` display on records; workers see `role:worker`.

## Host Integration

Rig emits phase lifecycle events to the host via environment-configured log files (set by the host before run). Apps do not configure this.

Events:
- `phase_start`: iteration, worker type (resolve/extract/derive/execute/compose), planner session ID
- `phase_end`: worker session ID, outcome, summary
- `planner_iteration`: iteration number, decision shape

The benchmark host uses these to attribute MCP calls to phases and track planner lifecycle. See `PHASES.md` for the exact emission contract.

## Versioning

This interface is frozen for rig v2. Additions (new phase types, new ref components, new tool kinds) are non-breaking. Removals or semantic changes require a v3.
