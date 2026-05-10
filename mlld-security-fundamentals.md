# mlld security fundamentals

mlld's security model is built on a simple insight: you can't stop an LLM from being tricked, but you **can** stop the consequences from happening. Labels track facts about data — what it is, where it came from, what trust level it carries, what proof attaches to it. Policies declare rules about what labeled data is allowed to do. Guards provide imperative hooks for inspection, transformation, and strategic overrides. Records are the data security boundary: they classify tool output, validate tool input, mint proof on authoritative fields, and project handles instead of values across the LLM boundary. Shelves and sessions accumulate state — durably across phases, ephemerally per call. The runtime enforces all of this regardless of LLM intent.

## Principles

1. **Enforce structurally, don't exhort via prompts.** Prompts are advisory; the runtime is authoritative. If your security depends on the LLM choosing correctly, you've lost.
2. **Let the runtime own runtime contracts.** Tool metadata, record schemas, and policy rules live in the runtime — not in the prompt the LLM reads.
3. **Phases don't mix.** Planners decide; workers act. Each phase has its own narrow tool surface.
4. **Narrow the LLM's view.** Records project handles instead of values; named read modes serve different agents from the same record. The LLM sees only what its role needs.
5. **Selection beats re-derivation.** Once a value has proof, pass the value (or its handle) — don't re-fabricate it from a string.
6. **Proof flows through values plus factsources.** Cross-phase identity is value-keyed, not handle-string-keyed. Handles are per-call ephemeral.
7. **Taint is sticky; proof is specific.** Untrusted data spreads conservatively; fact proof attaches only to the specific value it was minted on.
8. **The runtime owns observability.** Trace events, audit logs, and `@mx` introspection are runtime-emitted facts, not LLM-reported claims.

## Built-in Rules Reference

mlld ships **11 built-in default rules** you can enable in `policy.defaults.rules`, plus one **per-tool structural check** (`correlate-control-args`) that fires when a tool's bound input record explicitly declares `correlate: true`.

| Rule | What it blocks | Operation labels checked |
|---|---|---|
| `no-secret-exfil` | `secret` data flowing to exfil ops | `exfil` |
| `no-sensitive-exfil` | `sensitive` data flowing to exfil ops | `exfil` |
| `no-untrusted-destructive` | Untrusted data driving destructive ops | `destructive` (taint scoped to control args when known) |
| `no-untrusted-privileged` | Untrusted data driving privileged ops | `privileged` (taint scoped to control args when known) |
| `no-send-to-unknown` | Sends without proof on the destination | `exfil:send` — destination arg must carry `fact:*` or `known` |
| `no-send-to-external` | Sends to external without internal proof | `exfil:send` — stricter; requires `fact:internal:*` or `known:internal` |
| `no-destroy-unknown` | Destructive ops without proof on the target | `destructive:targeted` — target arg must carry `fact:*` or `known` |
| `no-unknown-extraction-sources` | Extraction without proof on source args | source-arg-bearing reads — runs only when source-arg metadata exists |
| `no-novel-urls` | URLs the LLM fabricated | URLs in `influenced` tool-call args must appear in prior context |
| `no-influenced-advice` | Influenced fact-state reaching `advice` ops | `advice` — used as the structural trigger for `denied =>` debias gates |
| `untrusted-llms-get-influenced` | Doesn't block — auto-applies `influenced` to LLM output | Triggered on `llm` exes whose input carries `untrusted` |
| `correlate-control-args` *(per-tool, not in `defaults.rules`)* | Cross-record fact-arg mixing on a single dispatch | Fires only on tools whose bound input record declares `correlate: true` |

The first four are **negative checks** (block contaminated data from reaching operations). `no-send-to-unknown`, `no-send-to-external`, `no-destroy-unknown`, and `no-unknown-extraction-sources` are **positive checks** (require proof that a value came from an authoritative source). `no-novel-urls` is a **URL identity check**. `no-influenced-advice` is a **structural trigger** for the advice-gate `denied =>` pattern. `untrusted-llms-get-influenced` is a **labeling rule**. `correlate-control-args` is a **cross-arg correlation check** that runs only on tools that opt in.

`correlate` does **not** default to `true` for multi-fact records — set it explicitly on input records where cross-record mixing is the attack surface you care about.

---

# Part I — Primitives

## §1. Labels

### 1.1 What labels are

Labels are strings attached to values. They're the foundation of mlld's security model. Every value in mlld carries a (possibly empty) set of labels that travel with it through assignment, parameter binding, transformations, shelf I/O, and the LLM bridge.

When an operation is attempted, the runtime checks: what labels does the input data carry? what labels does the operation carry? does policy allow this flow? The LLM may have been tricked into trying something dangerous, but the runtime sees the labels and blocks it.

### 1.2 The four roles labels play

A label isn't one thing — labels are a single mechanism that fills four distinct roles depending on which label and how it's used:

| Role | What it means | Examples |
|---|---|---|
| **Type-like adjective** | Refines what a value *is* — its sensitivity or nature | `secret`, `pii`, `sensitive`, user-declared (`internal`, `redacted`) |
| **Taint tag** | Sticky propagation through transformations; tracks contamination | `untrusted`, `influenced`, `src:*`, `op:*` |
| **Decorator** | Triggers a runtime capability when present on a value | `secret` → trace redaction, `untrusted` → `influenced` rule, `fact:*` → positive checks |
| **Role marker** | Identity for authorization, not data classification | `role:planner`, `role:worker`, custom roles |

Most built-in labels fill more than one role. `secret` is type-like (declares "this is sensitive") **and** a decorator (triggers redaction in traces and SDK output). `untrusted` is type-like **and** a taint tag (spreads conservatively) **and** a decorator (triggers the `untrusted-llms-get-influenced` rule). `fact:*` is a decorator (consumed by positive checks like `no-send-to-unknown`) and a proof carrier (minted only by record coercion).

### 1.3 The load-bearing built-ins

Labels are user-extensible — you can declare any string as a label on any variable. But a small set is built-in-and-load-bearing: the runtime recognizes them, applies them automatically, and triggers specific behaviors based on their presence.

| Label | Origin | What it does mechanically |
|---|---|---|
| `secret` | Declared on variables; auto-applied to keychain reads | Triggers redaction in trace events, SDK streams, and post-call snapshots; default rule `no-secret-exfil` blocks flow to net/output ops |
| `sensitive` | Declared | Default rule `no-sensitive-exfil` blocks flow to net/output ops |
| `pii` | Declared | Type-like; you wire it to flow rules via `policy.labels.pii` |
| `untrusted` | Declared, or auto-applied via `defaults.unlabeled: "untrusted"`; auto-applied to data fields by `=> record` coercion | Sticky taint; triggers `untrusted-llms-get-influenced`; checked by `no-untrusted-destructive` and `no-untrusted-privileged` |
| `trusted` | Declared, or carried through from trusted tool results | Marks data as cleared for sensitive ops; conflicts with `untrusted` raise unless resolved |
| `known` (and `known:<scope>`) | Declared on planner-supplied literals | Attestation: this exact value was vetted by an uninfluenced source; satisfies positive checks |
| `influenced` | Auto-applied by `untrusted-llms-get-influenced` rule | Marks LLM output that processed untrusted input; you wire restrictions via `policy.labels.influenced` |
| `fact:<record>.<field>` (and `fact:<scope>:<record>.<field>`) | Minted only by `=> record` coercion on `facts:` fields | Proof carrier; satisfies positive checks (`no-send-to-unknown`, `no-destroy-unknown`); `factsources` metadata enables `correlate-control-args` |
| `src:*` (e.g., `src:cmd`, `src:mcp`, `src:file`) | Auto-applied when data enters through that channel | Provenance tracking; consumable in custom flow rules |
| `op:*` (e.g., `op:cmd:git:status`) | Auto-applied during execution | Operation lineage |
| `role:*` (e.g., `role:planner`, `role:worker`) | Declared on exes (`exe llm role:planner @planner(...)`) | Authorization identity; selects record read mode; satisfies the matching read key |
| `dir:/path` | Auto-applied on filesystem reads | Path provenance |

Beyond these, you declare your own labels for domain-specific flow rules:

```mlld
var internal @customers = <data/customers.csv>
var classified @briefing = "..."
var redacted @cleanedOutput = @output | @scrub
```

User-declared labels carry no behavior on their own — they're inert string tags until you reference them in a policy or guard.

### 1.4 Declaring labels

The label sigil precedes the variable name in declarations:

```mlld
var secret @customerList = <internal/customers.csv>
var pii @patientRecords = <clinic/patients.csv>
var untrusted @externalData = "from outside"
var known @userEmail = "alice@example.com"
var internal,classified @briefing = "..."
```

Multiple labels are comma-separated. Labels are also returned from exes via the modification syntax:

```mlld
exe @classify(data) = [
  let @processed = @data | @transform
  => pii @processed
]
```

See [label modification][mod] for the full set of return-side operations (`=> trusted!`, `=> !label`, `=> clear!`).

### 1.5 Propagation

Labels propagate through transformations:

```mlld
var secret @customerList = <internal/customers.csv>
var @summary = @customerList | @summarize
show @summary.mx.labels    >> ["secret"]
```

The `@summary` value still carries `secret` because the `secret` taint flows through. This applies to assignments, pipe transformations, parameter binding, and shelf I/O — anywhere a value is derived from a labeled source.

`fact:*` labels do **not** propagate the same way. Fact proof attaches to a specific value at the moment of `=> record` coercion. Derived values (a substring, a transformation, a re-fabrication) lose the fact label — they're a different value. This is intentional: proof is specific, not sticky.

### 1.6 Trust asymmetry

`untrusted` is sticky and conservative; `trusted` cannot remove it. Adding `trusted` to already-untrusted data raises a conflict (configurable via `policy.defaults.trustconflict`). Removing `untrusted` requires a privileged guard:

| Syntax | Privilege? | Effect |
|---|---|---|
| `=> untrusted @var` | No | Adds `untrusted` (taint flows down freely) |
| `=> trusted @var` | No | Adds `trusted`; conflict with existing `untrusted` |
| `=> trusted! @var` | **Yes** | Blessing: removes `untrusted`, adds `trusted` |
| `=> !untrusted @var` | **Yes** | Removes `untrusted` only |
| `=> clear! @var` | **Yes** | Removes all non-factual labels |

The `!` and `clear!` shorthands work only inside privileged guards. See §3 (Guards) for the privileged-guard model.

### 1.7 Inspecting labels via `@mx`

Every value carries metadata accessible via `@mx`:

```mlld
var secret @key = "abc"
show @key.mx.labels         >> user-declared sensitivity labels
show @key.mx.taint           >> labels + auto-applied source/op markers
show @key.mx.attestations    >> value-scoped approvals (known, known:*)
show @key.mx.sources         >> source references (file paths, guard names)
show @key.mx.tools           >> tool lineage with audit references
```

The four channels are conceptually distinct:

- **`labels`** — what you declared (`secret`, `pii`, `untrusted`, `internal`, `redacted`, ...)
- **`taint`** — union of declared labels and auto-applied markers (`src:cmd`, `op:sh`, `dir:/path`, ...)
- **`attestations`** — value-scoped approvals (`known`, `known:internal`); unlike taint, attestations match the *exact* value and do not propagate to derived values
- **`sources`** / **`tools`** — provenance trails for audit, not for security checks

`untrusted` lives in `taint`. `known` lives in `attestations`. The distinction is load-bearing: positive checks like `no-send-to-unknown` consume attestations (exact-value match), while negative checks like `no-untrusted-destructive` consume taint (sticky propagation).

### 1.8 Auto-applied labels

The runtime applies certain labels without you asking:

- **`secret`** — applied to anything retrieved from the keychain
- **`src:*`** — applied whenever data enters through a channel (`src:cmd`, `src:mcp`, `src:file`, `src:js`)
- **`op:*`** — applied during execution to mark operation lineage
- **`dir:/path`** — applied on filesystem reads
- **`influenced`** — applied to LLM output by the `untrusted-llms-get-influenced` rule when input carried `untrusted`
- **`fact:*`** — minted by `=> record` coercion on `facts:` fields; never user-declared
- **`untrusted`** — applied to unlabeled values when `policy.defaults.unlabeled: "untrusted"` is set; applied by `=> record` to `data:` fields by default

Auto-applied labels follow the same propagation and check rules as user-declared ones. The asymmetry is in *who can remove them*: `secret`, `untrusted`, and `src:*` can only be removed via privileged guard.

[mod]: https://mlld.ai/atoms/effects/labels-modification

---

## §2. Policies

A policy is a declarative object that bundles security configuration. Where labels are facts about data, **policies are rules about what labeled data is allowed to do**. Where guards are imperative ("inspect this, decide what to do"), policies are declarative ("this flow is blocked").

### 2.1 Anatomy

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
  },
  labels: {
    pii: { deny: ["op:cmd", "net:w"] }
  },
  capabilities: {
    allow: ["cmd:git:*"],
    danger: ["@keychain"]
  },
  auth: {
    claude: "ANTHROPIC_API_KEY"
  },
  authorizations: {
    deny: ["update_password"],
    can_authorize: {
      role:planner: [@sendEmail, @createFile]
    }
  },
  records_require_tool_approval_per_role: false,
  env: {
    default: "@provider/sandbox",
    tools: { allow: ["Read", "Write"] }
  },
  locked: false
}
```

Most policies use only a few of these sections. The required mental model: a policy is a **single source of truth** that the runtime consults at every operation boundary.

### 2.2 `defaults.rules` — enable built-in rules

This turns on the 11 built-in rules from the reference table at the top of this doc. Pick the ones relevant to your use case:

```mlld
defaults: {
  rules: [
    "no-secret-exfil",
    "no-sensitive-exfil",
    "no-untrusted-destructive",
    "no-untrusted-privileged",
    "no-send-to-unknown",
    "no-send-to-external",
    "no-destroy-unknown",
    "no-unknown-extraction-sources",
    "no-novel-urls",
    "no-influenced-advice",
    "untrusted-llms-get-influenced"
  ]
}
```

**Per-rule overrides.** Any entry can be an object form for runtime tweaks:

```mlld
rules: [
  "no-secret-exfil",
  { "rule": "no-untrusted-destructive", "taintFacts": true }
]
```

`taintFacts: true` forces all-arg taint checking even when the tool's bound input record declares effective control args. The default scope is "fact args only" when the runtime knows the control-arg shape.

`mlld validate` warns on unknown rule names and suggests close matches.

### 2.3 `defaults.unlabeled` — auto-label unlabeled data

Without this, data with no explicit labels has no trust label. Set it to `"untrusted"` to treat all unlabeled data as untrusted by default:

```mlld
defaults: {
  unlabeled: "untrusted"
}
```

File-loaded data, command output, and anything else without explicit labels now automatically gets `untrusted`. Data you explicitly labeled (`var trusted @config = ...`) is unaffected. Set to `"trusted"` to default the other way; opt-in either direction.

### 2.4 `operations` — the two-step pattern

You label exes with **what they do** (`net:w`, `fs:w`). Policy maps those to **risk categories** (`exfil`, `destructive`, `privileged`). The built-in rules reference the risk categories.

```mlld
>> Step 1: label exes by capability
exe net:w @postToSlack(msg) = run cmd { curl -X POST @channel -d @msg }
exe fs:w @deleteFile(path) = run cmd { rm -rf "@path" }
exe sys:admin @restartService(name) = run cmd { systemctl restart @name }

>> Step 2: policy classifies capability labels as risk types
operations: {
  exfil: ["net:w"],
  destructive: ["fs:w"],
  privileged: ["sys:admin"]
}
```

`no-secret-exfil` blocks `secret` data from reaching anything classified as `exfil`. `no-untrusted-destructive` blocks `untrusted` data from reaching anything classified as `destructive`. The indirection is what makes a single policy reusable across scripts that share semantic labels but differ on which capabilities they classify as risky.

**Direct labeling shortcut.** You can skip the mapping and label exes directly: `exe exfil @sendData(...)`. This works but couples function definitions to risk policy. The two-step pattern is preferred for maintainability.

`mlld analyze --format json` surfaces these mappings under `policies[].operations`. `mlld validate --context ...` warns when a privileged guard's `op:` trigger doesn't match any declared operation label.

### 2.5 `labels` — custom flow rules

For rules beyond the built-ins, declare deny/allow lists per label:

```mlld
labels: {
  secret: {
    deny: ["op:show"]                  >> secrets can't be displayed
  },
  pii: {
    deny: ["op:cmd", "net:w"]          >> PII can't reach shell or network
  },
  "src:mcp": {
    deny: ["destructive"],             >> MCP data can't reach destructive ops
    allow: ["op:cmd:git:status"]       >> ...except git status is fine
  },
  influenced: {
    deny: ["destructive", "exfil"]     >> LLM-influenced data is restricted
  }
}
```

**Targets** for deny/allow:
- Auto-applied operation labels: `op:cmd`, `op:show`, `op:sh`
- Hierarchical operation labels: `op:cmd:git` blocks all git subcommands
- Your semantic exe labels: `net:w`, `fs:w`
- Risk categories: `exfil`, `destructive`, `privileged`

**Most-specific-wins.** If you deny `op:cmd:git` but allow `op:cmd:git:status`, status is allowed while push, reset, etc. are blocked. The matcher walks the hierarchy from most specific to least and uses the first matching rule.

### 2.6 Other config sections

Three sections live in the policy object but operate at different layers than label-flow rules. They're load-bearing but you can usually set them once and forget:

- **`capabilities`** — what operations are allowed at all. `allow` whitelists command patterns; `danger` marks capabilities that require explicit opt-in (`@keychain` reads must declare `danger: ["@keychain"]` in `policy.auth`).
- **`auth`** — caller-side credential mappings for `using auth:name`. Short form (`"API_KEY"`) or object form (`{ from, as }`).
- **`env`** — execution-environment constraints (provider defaults, allow/deny rules, tools/mcps/network allowlists). These attenuate runtime box/env configs and cannot be bypassed by local config. Guards can also return `env` policy fragments via `env { ... }` actions to scope environment to a specific operation.

See the `policy-capabilities`, `auth`, and `policy-operations` atoms for full coverage.

### 2.7 `authorizations` — planner-worker compiled policy

`authorizations` is the surface for the capability agent pattern (full coverage in §8). Two roles:

- **Base policy** uses `authorizations.can_authorize` to declare which exe roles can authorize which tools (`role:planner: [@sendEmail, @createFile]`), plus a `deny` list of tools no role can authorize.
- **Runtime policy** uses `authorizations.allow` and `authorizations.deny` to enforce the per-task envelope produced by `@policy.build` from planner intent.

```mlld
policy @workspace = {
  authorizations: {
    deny: ["update_password"],
    can_authorize: {
      role:planner: [@sendEmail, @createFile]
    }
  }
}
```

The planner emits bucketed authorization intent; the framework checks `can_authorize`, compiles the intent via `@policy.build`, and applies the returned policy to the worker call. Invalid intent fails closed at activation. See §8 for the full pattern, the bucket shapes (`resolved`, `known`, `allow`), and how this composes with positive checks like `no-send-to-unknown`.

`records_require_tool_approval_per_role` is a separate, global strictness switch for the submit side of record-backed tools. The default is `false`: a worker may submit a tool if that tool is included in the provided catalog for the call/box/bridge. Set it to `true` when an architecture wants every record-backed submit to also require the input record's `write.<role>.tools.submit` grant.

### 2.8 `locked` — absolute label-flow constraints

By default, policies are **unlocked** — privileged guards can create strategic exceptions to label-flow denials (see §3). Set `locked: true` to make a policy's **label-flow denials** non-overridable:

```mlld
policy @absolute = {
  defaults: { rules: ["no-secret-exfil"] },
  operations: { exfil: ["net:w"] },
  locked: true
}
```

Now no guard, no matter how privileged, can override `no-secret-exfil`'s denial. Use this for security invariants that should never have exceptions.

`locked` applies specifically to **managed label-flow denials** — the rules in `defaults.rules` and the `labels` flow declarations. It doesn't make capability allowlists, auth bindings, or environment constraints "more locked" — those are already structural and not subject to guard override.

### 2.9 Export, import, composition

Share policies across scripts:

```mlld
export { @p }
```

```mlld
import policy @p from "./policies.mld"
```

Policies compose with `union()` — combine multiple config objects into one policy. **The most restrictive rules win**: `allow` sets intersect, `deny` sets union, `locked` is sticky. See §9 for the full composition rules.

---

## §3. Guards

Guards are imperative hooks that run at operation boundaries. Where policies are declarative ("this flow is blocked"), guards are procedural ("inspect this, decide, transform, retry, redirect"). They can examine the security context, deny operations with a reason, mutate values (via privileged label modification), and route around denials with structured fallbacks.

### 3.1 Anatomy

```mlld
guard [@name] TIMING TRIGGER = when [
  CONDITION => ACTION
  ...
]
```

- **TIMING** — `before`, `after`, or `always` (`for` is a synonym for `before`)
- **TRIGGER** — a label that matches wherever it appears: on input data, on operations, or both
- **CONDITION** — any `when` predicate (label checks, value checks, computed expressions)
- **ACTION** — `allow`, `allow @transformed`, `allow with { ... }`, `deny "reason"`, `retry "hint"`, `resume "hint"`, or `env { ... }`

Guards are anonymous by default. Naming is optional and surfaces in trace events and error messages.

### 3.2 Triggers and matching

A trigger is a label. The runtime fires the guard wherever that label appears — on a value, on an exe, or both:

```mlld
>> Fires on values labeled secret AND on exes labeled secret
guard before secret = when [
  @mx.op.labels.includes("net:w") => deny "secrets cannot flow to net:w"
  * => allow
]
```

Use the `op:` prefix to narrow to operation-only matching:

```mlld
guard before op:exfil = when [...]   >> only fires on exes labeled exfil
```

The two equivalent shapes (data-side vs operation-side):

```mlld
>> "Block secret → net:w" — guard from the data side
guard before secret = when [
  @mx.op.labels.includes("net:w") => deny "..."
  * => allow
]

>> Same flow rule, expressed from the operation side
guard before net:w = when [
  @input.any.mx.labels.includes("secret") => deny "..."
  * => allow
]
```

Choose whichever reads more naturally. Same enforcement.

### 3.3 The inspection surface (`@mx`)

Inside a guard body, `@mx` is the security context:

| Accessor | What it carries |
|---|---|
| `@mx.labels` | User-declared labels on the matched value |
| `@mx.taint` | Union of labels and auto-applied source/op markers |
| `@mx.attestations` | Value-scoped approvals (`known`, `known:*`) — distinct from taint |
| `@mx.sources` | File paths, guard names, transformation trail |
| `@mx.op.type` | Operation kind: `cmd`, `show`, `exe`, `tool`, etc. |
| `@mx.op.name` | Operation name (exe name, tool name, command name) |
| `@mx.op.labels` | Labels on the operation/exe being called |
| `@mx.args.<name>` | Named arg access (preferred over positional) |
| `@mx.guard.try` | Retry/resume attempt count (1-based; first guard evaluation is `1`) |
| `@mx.guard.reason` | Denial reason in a `denied =>` arm |
| `@mx.guard.name` | Name of the denying guard |
| `@mx.guard.hintHistory` | Prior retry/resume hints (after-phase) |
| `@mx.llm.resume` | Resume-continuation metadata when in a resumed call |

`@input` is the value being inspected — a per-input value for data-side guards, the array of operation inputs for operation-side guards. Per-operation guards expose helpers:

- `@input.any.mx.labels.includes("secret")`
- `@input.all.mx.taint.includes("src:file")`
- `@input.none.mx.attestations.includes("known")`
- `@input.mx.labels` — union across all inputs
- `@input[0]` / `@input[n]` — positional access (less readable than named `@mx.args.*`)

### 3.4 Per-arg inspection

Named-arg access via `@mx.args` is the preferred shape — you only reference what you care about, and optional args the caller omitted simply don't fire their checks:

```mlld
guard before tool:w = when [
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

For names that aren't dot-safe, use bracket form: `@mx.args["repo-name"]`. To list available arg names: `@mx.args.names`. To access an arg actually named `names`: `@mx.args["names"]`.

### 3.5 Actions

Guards return one of:

| Action | Effect |
|---|---|
| `allow` | Operation proceeds |
| `allow @transformed` | Operation proceeds with a transformed value (before-phase: replaces input; after-phase: replaces output) |
| `allow with { addLabels, removeLabels }` | Proceed with label modifications (`removeLabels` requires privileged guard) |
| `deny "reason"` | Operation blocked |
| `retry "hint"` | Re-run the operation with a hint (re-fires tools) |
| `resume "hint"` | Continue an LLM conversation with a correction; tools do not re-fire |
| `resume "hint" with { tools: [...] }` | Resume with a scoped tool set (e.g. terminal-only repair tools) |
| `env { ... }` | Return a policy/env fragment to scope environment for this operation |

`retry` is right for read-only exes with malformed output. `resume` is right for write-tool exes whose final text is malformed but whose writes already happened — the LLM can fix the text without firing new tool calls against dead handles. Use `@mx.guard.try` to bound attempts.

### 3.6 Composition and precedence

Guards run top-to-bottom in declaration order. Decision precedence: `deny > retry/resume > allow @value > allow`. Before-phase transforms are last-wins; after-phase transforms chain sequentially through the pipeline.

`{ guards: false }` on a call disables non-privileged guards. Privileged guards still run.

### 3.7 Privileged guards

Privileged guards have elevated powers:

```mlld
>> Prefix form
guard privileged @taskAllow before tool:w = when [
  @mx.op.name == "send_email" && @mx.args.recipients ~= ["john@gmail.com"] => allow
  @mx.op.name == "send_email" => deny "recipient not authorized"
]

>> With-clause form
guard @taskAllow before tool:w = when [
  ...
] with { privileged: true }
```

What privileged guards can do that regular guards cannot:

- **Override unlocked policy denials.** A matched `allow` takes precedence over a label-flow denial from `defaults.rules` or `labels`. This is the mechanism for strategic exceptions.
- **Remove protected labels** via `trusted!`, `!label`, or `clear!` syntax (see §1.6).
- **Survive `{ guards: false }`.** Disabling guards only disables non-privileged ones; privileged guards always run. Policy-rule guards are automatically privileged.

What privileged guards **cannot** do:

- Override a **locked** policy. With `locked: true`, even privileged guards can't punch holes in label-flow denials.
- Override capability denials, environment constraints, or `authorizations.deny` — those are structural, not label-flow.

**No wildcard arm in privileged guards that override policy.** When a privileged guard is meant to allow specific cases while letting policy block everything else, omit the `* => allow` wildcard. If no condition matches, the guard produces no action and the policy denial stands. A `* => allow` would override the policy for **every** call.

```mlld
>> WRONG: wildcard overrides policy for everything
guard privileged @bad before tool:w = when [
  @mx.op.name == "send_email" && @mx.args.recipients == ["safe@example.com"] => allow
  * => allow                          >> defeats the policy!
]

>> RIGHT: no wildcard — unmatched calls defer to policy
guard privileged @good before tool:w = when [
  @mx.op.name == "send_email" && @mx.args.recipients == ["safe@example.com"] => allow
]
```

`mlld validate` warns on this pattern with `privileged-wildcard-allow`.

### 3.8 Catching denials (`denied =>`)

A wrapper exe carrying a policy-relevant label can catch its own denials and redirect to a fallback path using `denied =>` inside a `when` expression:

```mlld
exe advice @adviceGate(query, factState, factSchema, model) = when [
  denied => @debiasedEval(@query, @factState, @factSchema, @model)
  *      => @directAnswer(@query, @factState, @model)
]
```

When `@adviceGate` is invoked with input that triggers a denial (e.g. `no-influenced-advice` firing because `factState` carries `influenced`), the runtime catches the denial via the `denied =>` arm and runs `@debiasedEval` instead of letting the call fail.

`denied` matches denials from:

- User-defined and policy guards
- Managed policy label-flow denials (`defaults.rules`, `labels` deny/allow)
- Input-record dispatch checks (`proofless_control_arg`, `allowlist_mismatch`, `blocklist_match`, `no_update_fields`, `correlate_mismatch`)

Capability denials and environment-constraint denials are hard errors and cannot be caught.

Inside the `denied =>` arm, `@input` carries the value that triggered the denial (with security labels intact) and `@mx.guard.reason`, `@mx.guard.name`, and `@mx.denial.*` (for input-record denials) are populated. Reserve `denied =>` for policy-aware fallback paths with a meaningful response — debiasing, structured re-extraction, escalation. Don't use it as a generic try/catch.

When mlld runs through the SDK or `mlld live --stdio`, guard and label-flow denials are also surfaced as structured observability data: streamed executions emit `guard_denial` events and structured execute results collect denials in `result.denials`, whether handled by `denied =>` or not.

### 3.9 The three enforcement planes

mlld's security checks live in three structurally distinct planes. They run in different places, fail with different error codes, and can't be overridden by the same mechanisms. Mixing them up is one of the most common sources of debugging confusion.

| Plane | What it checks | Where | Override surface |
|---|---|---|---|
| **Structural gates** | Capability allowlists, env constraints, `authorizations.deny`, record `write:` permissions, active-role requirements | Before any value-level check | None — structural denials are absolute |
| **Label-flow policy rules** | `defaults.rules` and `labels` deny/allow against value labels | At every operation boundary | Privileged guards (when `locked: false`); locked policies are absolute |
| **Bridge projection / handle resolution** | What the LLM sees, what handles resolve to, what proof carries through | At the LLM call boundary | Read-mode declarations; cannot be guard-overridden because guards run on resolved values |

```
Plane 1 — Structural gates (capabilities, env, write:, active role)
  │ Hard structural denial; not subject to any guard or policy override
  │
Plane 2 — Label-flow policy rules (defaults.rules, labels)
  │ locked: true → absolute, no exceptions
  │ locked: false (default) → privileged guards can override specific cases
  │
Plane 2.5 — Privileged guards
  │ Can override unlocked policy denials (Plane 2) for matched conditions
  │ Can remove protected labels
  │ Survive { guards: false }
  │ Cannot override Plane 1 (structural) or Plane 3 (bridge projection)
  │
Plane 2.5 — Regular guards
  │ Can inspect, validate, transform, deny, retry, resume
  │ Cannot override policy denials (Plane 2)
  │ Cannot remove protected labels
  │
Plane 3 — Bridge projection / handle resolution
  │ Determined by record read modes and active role
  │ Not a "rule" you can override; a structural property of the projection
```

The principle: **regular guards can only add restrictions, never remove them.** Privileged guards create exceptions to unlocked Plane 2 policies. Plane 1 (structural) and Plane 3 (projection) are absolute relative to guards.

A common confusion: a `WRITE_DENIED_NO_DECLARATION` error doesn't go away when you add a privileged guard — that's a Plane 1 structural gate, not a Plane 2 label-flow rule. Add `write:` to the record. Conversely, a `no-secret-exfil` denial *can* be punched through with a privileged guard, because it's Plane 2.

---

## §4. Records

Labels track facts about data; policies and guards enforce flow rules over those labels. But there's a deeper question: **where do trustworthy labels come from in the first place?** Records answer that.

Records are the primary security boundary for data in mlld. They classify tool output (minting `fact:*` proof on authoritative fields), validate tool input (rejecting malformed or tainted args at dispatch), and shape what the LLM sees through structured read projections. They're also the canonical mechanism for **wrapping existing MCP tools with security capabilities** — point a tool catalog entry at a record via `inputs: @r`, and you get fact-arg validation, allowlists, blocklists, payload constraints, contributor-role enforcement, and tool-doc/MCP-schema generation from one definition.

The slogan: **one record, one source of truth.** The same declaration drives runtime validation, prompt-time tool docs, MCP server schemas, policy builder checks, and shelf typing. Where elsewhere you'd write the contract three times (validation code, prompt instructions, MCP description), with records you write it once.

### 4.1 The two directions

A record can serve in two directions:

- **Output direction** — coerced via `=> record @r` on an exe result. Mints labels (`fact:*`, `untrusted` on `data:`), runs `read:` projection at the LLM boundary, populates `factsources` for cross-arg correlation.
- **Input direction** — referenced via `inputs: @r` on a tool catalog entry. Validates incoming args at dispatch (proof checks, type checks, allowlist/blocklist, exact match, update set, contributor role, correlation).

The grammar is shared. Direction is conventionally signaled by which sections a record declares: input-only sections (`exact:`, `update:`, `allowlist:`, `blocklist:`, `optional_benign:`, plus `correlate: true` and `write: { role:X: { tools: ... } }`) make a record input-shaped; a `read:` section and `write: { role:X: { shelves: ... } }` make it output-shaped. A record with neither shape may serve in both directions.

The runtime currently does not reject mixed-direction records — direction discipline is a documentation convention, not a static check (this may tighten in a future release). Input-policy validation issues do carry a `direction: "input"` marker on many paths so input-side and output-side failures can be distinguished in error reporting.

### 4.2 Output records: classifying tool output

```mlld
record @contact = {
  facts: [email: string, name: string, phone: string?],
  data: [notes: string?],
  read: [name, { value: "email" }],
  when [
    internal => :internal
    *        => :external
  ]
}

exe @searchContacts(query) = run cmd {
  contacts-cli search @query --format json
} => contact
```

- **`facts: [...]`** — fields the source is authoritative for. On coercion, each field gets `fact:@contact.<field>` (and `fact:<scope>:@contact.<field>` if a `when` clause assigned a scope tier).
- **`data: [...]`** — content fields. Tools may put anything here, including attacker-controlled strings.
- **`read: [...]`** — what the LLM sees at the boundary. See §4.3.
- **`when [...]`** — assigns trust scope tiers from the data itself. The example tags rows with `internal` data as `fact:internal:*`, others as `fact:external:*`.

**Trust refinement on `=> record`.** When coercion runs on an `untrusted`-labeled exe result, `untrusted` is cleared on `facts:` fields and on `data.trusted:` fields, and preserved on `data.untrusted:` fields. The shorthand `data: [fields]` is sugar for `data: { untrusted: [fields] }` — safe by default. To explicitly mark some payload as trusted-clearing:

```mlld
record @issue = {
  facts: [id: string, author: string],
  data: {
    trusted:   [title: string],
    untrusted: [body: string]
  }
}
```

Fact fields get **proof and taint cleared**. Trusted-payload fields get **taint cleared but no proof** (safe to read, not authorization-grade). Untrusted-payload fields stay tainted. The `when` clause can conditionally promote data fields to trusted based on input values.

Schema validation metadata is available on `@output.mx.schema.valid` and `@output.mx.schema.errors`. `validate:` on the record controls the failure mode: `"demote"` (the default) keeps invalid output but strips fact proof; `"strict"` denies on validation error; `"drop"` drops invalid rows from arrays.

### 4.3 Read projections

`read` controls how fields cross the LLM boundary. All modes apply to both fact and data fields; modes differ on JSON visibility (does the LLM see the value?) and schema-notes visibility (does the LLM see the field name in `<*_notes>` blocks and `@toolDocs` output?).

| Mode | Syntax | LLM sees in JSON | In schema notes | Handle? |
|---|---|---|---|---|
| **Bare** | `name` | full value | yes | No |
| **Value** | `{ value: "name" }` | `{value, handle, address}` | yes | Yes |
| **Masked** | `{ mask: "email" }` | `{preview, handle, address}` | yes | Yes |
| **Handle** | `{ handle: "id" }` | `{handle, address}` | yes | Yes |
| **Protected** | `{ protected: "ssn" }` | nothing | yes | No |
| **Omit** | `{ omit: "raw" }` | nothing | nothing | No |
| (not listed) | — | nothing | yes (defaults to protected) | No |

The schema-notes column is security-relevant: a `protected` field tells the LLM that the field exists (so it can construct correct field references for downstream tool calls) without exposing the value. An `omit` field disappears entirely — the LLM doesn't know the field exists.

**Bare mode and fact fields — known gotcha.** Bare mode emits a raw value with no handle, regardless of whether the field is in `facts:` or `data:`. Bare-listing a fact field means the LLM sees the value but has no handle to reference it in downstream tool calls — so it can't be used as a control arg via handle resolution. If the planner needs to authorize an operation against this fact field, use `{value: ...}` mode (publishes value AND handle) instead of bare. The runtime treats this as an explicit opt-out of handle publishing, not as a footgun to warn about — but it is a footgun if you intended the field to be referenceable.

Projected tool result for `read: [name, { value: "email" }]` (where `notes` is unlisted):

```json
{
  "name": "Ada Lovelace",
  "email": {
    "value": "ada@example.com",
    "handle": "h_ab12cd",
    "address": "contact:44d1c1cc"
  }
}
```

`notes` is unlisted, so it defaults to **protected** — present in the record's schema notes (the LLM knows the field exists) but absent from the JSON value. To include it in the JSON, add it to `read:` (bare or `value:`); to hide its existence entirely, list it as `{ omit: "notes" }`.

The `handle` is per-call ephemeral (see §5). The `address` is the cross-call stable form (`<record>:<key>`, opaque key per §4.4).

`{ protected: "x" }` and unlisted both produce no JSON value. The explicit `protected` form documents intent for security audits — "the author considered this field and chose to protect its value." Unlisted fields are the implicit default. `{ omit: "x" }` is structurally different and should only be used when the field's existence should be invisible to the role.

Read projection only applies at the LLM boundary. `show @contact.email` from mlld code still prints the actual email.

#### Where read modes are declared

A read mode can be declared in three places. From least to most specific:

1. **exe definition** — `exe @worker(...) with { read: "role:worker" } = ...`
2. **box config** — `box { read: "role:worker" } [...]`
3. **call site** — `@claude(...) with { read: "role:worker" }`

A more specific declaration overrides a less specific one. Call site always wins. If no explicit read is set, the active llm exe label (`role:planner`, `role:worker`) selects the matching read key by default.

#### Named read modes

Different agents need different visibility from the same record:

```mlld
record @email_msg = {
  facts: [from: string, message_id: string],
  data: [subject: string, body: string, needs_reply: boolean],
  read: {
    role:worker:  [{ mask: "from" }, subject, body],
    role:planner: [{ value: "from" }, { value: "message_id" }, needs_reply]
  }
}
```

Worker sees subject and body (its job to read them); from is masked. Planner sees from and message_id in value mode (readable + handle), sees needs_reply, and treats unlisted fields as protected schema-only.

In named modes, unlisted fields are protected. Use `{ omit: "field" }` only when the field's existence should be hidden from this role.

#### Worker returns with the `handle` field type

A worker exe whose return is coerced through a record can use the `handle` field type to enforce that fact-bearing values cross the phase boundary as projection-minted handles, not as plain strings the LLM might fabricate:

```mlld
record @reader_result = {
  facts: [channel: handle],
  data: [summary: string]
}
```

The `handle` type requires a resolvable handle string — bare strings fail validation. If the LLM returns a literal channel name instead of copying the handle from its tool result, `=> record` validation fails and a guard can `resume` to repair the output (see §3.5).

### 4.4 Identity: `.mx.key`, `.mx.hash`, `.mx.address`, `.mx.handle`

Every record-coerced object exposes four identity-related accessors, each serving a different purpose:

| Accessor | Form | Stability | Used for |
|---|---|---|---|
| `.mx.key` | opaque sha256-truncated hash | content-stable | shelf upsert/from/remove, projection-cache addressing, `correlate-control-args` instance matching |
| `.mx.hash` | content fingerprint | changes when content changes | change detection — "did this row's content shift since I last looked?" |
| `.mx.address` | `{ record, key, string }` | content-stable, cross-call | planner-loop addressing; the canonical wire form is `<record>:<key>` |
| `.mx.handle` | per-call ephemeral string | dies with the LLM call | display labels at the LLM boundary (covered in §5.5) |

**`.mx.key` is always opaque.** It's a sha256 digest truncated to 8 hex characters — never a readable field value. The `key:` declaration on a record controls **what fields are hashed into `.mx.key`**, not whether `.mx.key` returns a literal field value. Three forms:

- **Single field** — `key: id` includes the `id` field's canonical-encoded value in the hash input
- **Composite** — `key: [account_id, period]` includes multiple fields
- **Hash form** — `key: hash(...)` is explicit about the content-derived computation

In all three forms, `record.mx.key` returns the opaque hash, not the underlying field value. If you want the readable id, read the field directly: `@record.id`.

`.mx.address.key` mirrors this — it is **always** the opaque `.mx.key`, never a readable key-field value. This is a load-bearing security constraint: readable key strings would re-introduce attacker-controlled text into handle/address strings the planner sees, defeating opacity (the c-0298 / c-a8d2 attacker-text-in-handles bug class).

### 4.5 Input records: validating tool inputs and wrapping MCP tools

Input records are how mlld wraps existing MCP tools (or any exe) with security capabilities. You declare a record describing the tool's input contract — fact args, payload args, allowlists, exact-match constraints — and reference it from a tool catalog entry. The runtime then validates every dispatch against the record before the tool executes:

```mlld
record @send_email_inputs = {
  facts: [recipients: array, cc: array?, bcc: array?],
  data: {
    trusted:   [subject: string],
    untrusted: [body: string, attachments: array?]
  },

  exact:           [subject],
  allowlist:       { recipients: @internal_domains, cc: @internal_domains },
  blocklist:       { recipients: @known_phish_domains },
  optional_benign: [cc, bcc, attachments],

  write: {
    role:planner: { tools: { authorize: true } },
    role:worker:  { tools: { submit: true } }
  },

  key: recipients,
  correlate: true,
  validate: "strict"
}

exe tool:w @sendEmail(recipients, cc, bcc, subject, body, attachments) = run cmd {
  send-email --to @recipients --subject @subject --body @body
}

var tools @agentTools = {
  send_email: {
    mlld:    @sendEmail,
    inputs:  @send_email_inputs,
    labels:  ["execute:w", "exfil:send", "comm:w"],
    description: "Send an outbound email"
  }
}
```

This single declaration drives:

- **Runtime validation** at every dispatch (fact-proof check, type check, allowlist/blocklist match, exact-string-in-task check, contributor-role check, cross-record correlation)
- **Tool-doc and MCP schema generation** — `@toolDocs(@agentTools)` and `mlld mcp tools.mld --tools-collection @agentTools` derive their schemas from the record
- **`@policy.build` builder-phase checks** — the planner's proposed values are validated against the same record before the worker runs
- **Shelf slot typing** — `shelf @state from @agentTools` creates wildcard slots typed by each tool's `returns:` record

#### Wrapping an existing MCP tool

The same pattern wraps an MCP-imported tool. Import the tool, then re-export it through a tool collection with `inputs:`:

```mlld
import tools { send_email as raw_send_email } from mcp "smtp-server"

exe tool:w @sendEmail(recipients, subject, body) = @raw_send_email(@recipients, @subject, @body)

var tools @agentTools = {
  send_email: {
    mlld:   @sendEmail,
    inputs: @send_email_inputs,    >> validation contract attached
    labels: ["exfil:send"]
  }
}
```

Now the upstream MCP `send_email` tool is callable only through the validated wrapper. The agent's surfaced surface is the wrapper's input shape; the raw tool isn't reachable from inside `box @agent with { tools: @agentTools }`.

#### Sections on input records

| Section | Purpose | Phase |
|---|---|---|
| `facts: [...]` | Fields requiring fact proof or `known` attestation at dispatch | dispatch |
| `data: [trusted: [...], untrusted: [...]]` | Payload fields; trusted entries can't carry `untrusted` | dispatch |
| `read: { role:X: [...], ... }` | What each role sees at the LLM boundary (§4.3); applicable when the input record is also surfaced for projection | LLM bridge |
| `write: { role:X: { tools: { authorize, submit }, shelves: { upsert, clear, remove } } }` | Per-role permission to land this record into write surfaces — tool dispatch and shelf upserts | dispatch |
| `exact: [field, ...]` | Field values must appear verbatim in the task text | builder only |
| `update: [field, ...]` | Mutation set; ≥1 must be non-null on update; tool needs `update:w` label | builder + dispatch |
| `allowlist: { field: <set>, ... }` | Field value must be in the set | builder + dispatch |
| `blocklist: { field: <set>, ... }` | Field value must NOT be in the set | builder + dispatch |
| `optional_benign: [field, ...]` | Acknowledges that omitting an optional fact is benign at the backend | validator advisory |
| `key:` — single field, composite (`[a, b]`), or `hash(...)` | Identity for cross-record correlation; controls what's hashed into `.mx.key` | dispatch |
| `correlate: true \| false` | Opt-in cross-record fact-arg mixing check; **not** defaulted by arity | dispatch |
| `validate:` — `"demote"` (default), `"strict"`, or `"drop"` | Failure mode on validation error | dispatch |

`exact:` is builder-only because it needs the planner's `task` text to compare against. `optional_benign:` is a validator advisory — listing an optional field there silences the `optional_fact_declared` warning. The other sections run at both builder time (against the planner's proposed values) and dispatch time (against the actual values handed to the tool).

#### `write:` permissions on records

`write:` is the per-role authority surface for landing a record into write surfaces — tool dispatches and shelf upserts. **A record without `write:` cannot be persisted to a shelf or used as input to a tool dispatch** — the runtime denies the operation with `WRITE_DENIED_NO_DECLARATION`. Records used purely for `=> record` coercion (no write-surface participation) need no `write:`.

```mlld
record @contact = {
  facts: [email: string, name: string],
  data:  [notes: string?],
  read:  [name, { value: "email" }],
  write: { role:worker: { shelves: true } }
}

record @send_email_inputs = {
  facts: [recipient: string, subject: string],
  data:  { untrusted: [body: string] },
  write: {
    role:planner: { tools: { authorize: true } }
  }
}

record @update_password_inputs = {
  data: { trusted: [password: string] },
  exact: [password],
  write: {}                  >> explicit denial for shelves and planner authorization
}
```

Structure: `write: { role:<X>: { <target>: <permissions> } }`. Role keys are canonical (`role:planner`, `role:worker`).

| Target | Capabilities | Bool default |
|---|---|---|
| `shelves` | `upsert`, `clear`, `remove` | `shelves: true` → `{ upsert: true }` only |
| `tools` | `authorize`, `submit` | bool form rejected at validate time |

**Tool dispatch has two phases.** The planner *authorizes* (certifies the dispatch); the worker *submits* (executes it). Planner authorization always uses `tools.authorize`. Worker submission is allowed by inclusion in the provided tool catalog by default. If an architecture wants submission to require per-role record grants too, set `policy.records_require_tool_approval_per_role: true` and declare `tools.submit` explicitly. This is also why authorize-then-submit flows have two role contexts — see §8.5 for the dual-role pattern.

**Scope specs** narrow capabilities to specific instances:

```mlld
write: {
  role:worker: {
    tools:   { submit: [@send_email] },
    shelves: { upsert: [@drafts, @outbox] }
  },
  role:planner: {
    tools: { authorize: [{ labels: "safe" }] }
  }
}
```

`true` means all in-scope instances. `[@ref, ...]` lists specific instances. `[{ labels: "x" }]` matches by label (tools only in v1).

**Deny-by-default for write surfaces.** Every absence is a denial for shelf writes, planner authorization, and strict submit approval: missing `write:`, missing role, missing target, missing capability, or scope mismatch all reject that operation at runtime. The explicit denial form is `write: {}` for shelf writes and planner authorization. Under the default submit model, deny tool execution by omitting the tool from the provided catalog or listing it in `policy.authorizations.deny`.

**Active role.** The active role at the write site comes from the LLM bridge's display selection — `with { read }`, box config, or matching `role:*` exe label. Writes from non-bridge contexts have no active role; deny-by-default applies to shelf writes, planner authorization, and strict submit approval if the record declares `write:`. Tests that exercise strict per-role submit approval must run inside an exe carrying `role:worker` (or whichever role the record's `write:` permits); tests that exercise `@policy.build` must run under `role:planner`. Without the active role, record write checks fail with `WRITE_DENIED_NO_ACTIVE_ROLE` regardless of fact proof.

**Composition with input-record constraints.** `write:` is orthogonal to `exact`, `update`, `allowlist`, `blocklist`, `correlate`, and `optional_benign`. All applicable constraints fire at dispatch; any failure rejects the call.

**Relationship to policy `authorizations.can_authorize`.** Records' `write.<role>.tools.authorize` and policy `authorizations.can_authorize` are two surfaces for planner authorization. Catalog entries can also declare `can_authorize` legacy-style, which compiles additively into the policy. The record-side declaration is preferred because it lives with the contract; the policy-side override is for cross-cutting deny rules (`authorizations.deny`). `write.<role>.tools.submit` is only part of the submit path when `policy.records_require_tool_approval_per_role` is enabled.

#### Optional facts and the benign-omission rule

Marking a field in `facts:` as optional (`?`) is an assertion that *omitting this field produces a benign default at the tool's backend*. mlld can't verify this — it's a semantic property of the downstream operation. Don't mark a fact optional if the tool's omission default is sensitive (send to all contacts, delete everything matching). An optional fact must mean: absent arg = no effect scoped to that arg.

The validator emits `optional_fact_declared` as an advisory on every optional fact. Acknowledge with `optional_benign: [field, ...]` to silence and document the assertion in source.

### 4.6 Fact kinds

Field-level `kind:` tags label semantically equivalent fields across records so positive checks can match by kind rather than by exact field name:

```mlld
record @contact = { facts: [email: { type: string, kind: "email" }] }
record @customer_inputs = { facts: [email: { type: string, kind: "email" }] }

exe @sendCommsTool(email) = run cmd { ... }

var tools @t = {
  send_comms: { mlld: @sendCommsTool, inputs: @customer_inputs }
}
```

A `fact:@contact.email` value satisfies the `send_comms` tool's `email` arg because both fields share `kind: "email"`. Without kind tags, the runtime falls back to exact field-name matching (`fact:*.email`).

Derivation order on positive checks:

1. **`accepts: [...]`** on the input record's field — exact pattern list, takes precedence
2. **`kind: "email"`** — accepts `known` and any in-scope `fact:@<record>.<field>` whose field shares that kind tag
3. **Untagged fact fields** — strict fallback to `known` or `fact:*.<argName>`

Kind tags don't affect minting — a value from `record @contact = { facts: [email: { type: string, kind: "email" }] }` still carries `fact:@contact.email`. The kind tag is consumed downstream by input-record derivation rules, not by the output record.

### 4.7 Dispatch validation order

When a tool declared with `inputs: @r` is dispatched, the runtime walks `@r`'s sections in this order:

1. **Active-role check** — the dispatch site has an active `role:*` context (from bridge display selection, box config, or exe label). Without one, dispatch fails with `WRITE_DENIED_NO_ACTIVE_ROLE`.
2. **Record `write:` declaration check** — the record declares a `write:` block. Missing → `WRITE_DENIED_NO_DECLARATION`.
3. **Per-role write capability check** — the active role's `write.<role>.tools.{authorize | submit}` permits this dispatch phase. Missing role / target / capability → deny-by-default (`WRITE_DENIED_*`). Scope specs (`[@send_email]`, `[{labels:"safe"}]`) further narrow.
4. **Arity / presence** — required fields must be present; extras are rejected.
5. **Type check** — values match declared field types (`type_mismatch`).
6. **`facts:` proof check** — fact fields carry `fact:*` or compiled `known` (`proofless_control_arg` for write tools, `proofless_source_arg` for read tools).
7. **`data.trusted:` taint check** — trusted-payload fields don't carry `untrusted` (`trusted_payload_tainted`).
8. **Cross-field policy sections** — `allowlist` (`allowlist_mismatch`), `blocklist` (`blocklist_match`), `update` (`no_update_fields`).
9. **`correlate:` check** (when `correlate: true` is declared) — all fact fields trace to the same source-record instance via `factsources.instanceKey` or `(coercionId, position)` (`correlate_mismatch`).

Each step that fails emits a structured issue. Dispatch is denied if any step produces an error-severity issue. `@policy.build` walks the same checks at builder time (skipping steps that need runtime provenance) and reports issues in `report` / `issues`.

Steps 1–3 are the **structural permission gate** introduced by record `write:`. They run before any value-level check and fail closed when the record-author hasn't explicitly granted authority. Steps 4–9 are the **value-level checks** — they assume the structural gate passed and inspect the actual incoming arg values.

Contributor-role enforcement (`supply:` in earlier specs) is not implemented; the grammar parse-errors on unknown record sections, so `supply:` cannot be authored against the current implementation. If you need contributor-role discipline today, enforce it in orchestrator code; treat this as a design space the spec hasn't yet settled.

#### Correlating multi-fact tools

For write tools whose fact args must come from the same source record instance, declare `correlate: true` explicitly (no implicit default by arity):

```mlld
record @updateTransaction_inputs = {
  facts: [id: string, recipient: string],
  data:  [amount: number, date: string],
  correlate: true,
  key: id
}
```

The runtime checks that every fact-arg value's `factsources` provenance points to the same source record instance, matching by `instanceKey` (the `key:` field value) when available, or by `(coercionId, position)` for keyless records. Cross-source dispatches are denied with `correlate_mismatch`.

The canonical attack this defends: an attacker who controls one record (a planted "transaction to attacker@evil.com") tricks the planner into mixing that record's `recipient` with a legitimate record's `id`. Both individual values have fact proof, so single-arg checks like `no-send-to-unknown` pass. Without correlation, the dispatch goes through and updates the legitimate transaction with the attacker's recipient. With `correlate: true`, the cross-source mismatch is caught structurally.

### 4.8 Automatic tool security annotations

When `@claude()` is called with security-relevant tools, the runtime auto-injects `<tool_notes>` into the system message. The notes include per-tool argument listings with fact args flagged, read/write classification, the deny list, and multi-fact correlation warnings — all derived from the bound input records and the active policy. No orchestrator assembly needed.

For custom prompt assembly without `@claude()`, `@toolDocs(@tools)` produces the same content. The tool collection must be a labeled `var tools @x = {...}` declaration (which carries the compiled metadata), not a bare object spread (which materializes plain data and drops the tool-collection identity).

### 4.9 Compiled reflection

Tool collections expose compiled metadata via `.mx`:

```mlld
@agentTools.mx.tools                       >> list of surfaced tool names
@agentTools.send_email.mx.factArgs         >> compiled fact-arg list
@agentTools.send_email.mx.optionalArgs     >> compiled optional-arg list
@agentTools.send_email.mx.inputSchema      >> compiled JSON schema
```

Use these when framework code needs the already-compiled contract instead of re-reading the authored record.

---

## §5. Facts and Handles

§4 covered how records mint `fact:*` proof at the boundary. This section covers what happens to that proof as values cross phase boundaries — between an orchestrator and an LLM, between a planner and a worker, between calls separated in time. The mechanism that makes proof durable across those crossings is what this section is about.

### 5.1 The core problem: LLMs destroy value identity

When a tool returns `{ email: "ada@example.com" }`, mlld attaches `fact:@contact.email` to the email value. That label travels with the value through assignment, parameter binding, shelf I/O. The runtime can answer "is this value authoritative?" with a structural check.

But the moment that value crosses an LLM boundary, identity is destroyed. The LLM consumes the value as text, processes it through token streams, and produces new text. A `"send to ada@example.com"` string in the LLM's tool call is just text — the runtime has no structural reason to treat it as the same authoritative value the tool returned. An attacker who got "send to attacker@evil.com" injected into a different tool result could equally well produce that string.

This is the cross-phase identity problem. Labels alone don't solve it. Records, handles, addresses, and shelves do.

### 5.2 Control args vs payload args

Before talking about identity, the structural distinction that drives everything else: **not all arguments to a tool need the same kind of proof.**

When a tool dispatch happens — say, `send_email(recipients, subject, body, attachments)` — the args split into two groups:

- **Control args** — args that decide *what the operation targets or does*. For `send_email`, the recipient list. For `delete_contact`, the contact id. For `update_transaction`, the transaction id. Control args must come from an authoritative source, or the operation is dispatching against attacker-controlled targets.
- **Payload args** — content the operation carries but doesn't target on. For `send_email`, the subject and body. For `update_transaction`, the new amount. Payload is expected to be LLM-composed and may carry `untrusted`. Demanding fact proof on payload would defeat the point of LLM agents (the LLM's job is to compose payload).

mlld surfaces this distinction structurally. On an input record:

- Fields in **`facts:`** are control args. They must carry `fact:*` or `known` at dispatch.
- Fields in **`data:`** are payload args. Trust refinement (§4.2) keeps `data.trusted:` taint-free without requiring proof; `data.untrusted:` is expected to be tainted.

The checks compose this way:

- **Negative checks** (`no-untrusted-destructive`, `no-untrusted-privileged`) — scope their taint inspection to control args when the runtime knows the input record. Tainted payload (body, subject, description) is expected and not blocked. Override with `taintFacts: true` to force all-arg checking when control-arg scoping isn't appropriate.
- **Positive checks** (`no-send-to-unknown`, `no-destroy-unknown`, `no-unknown-extraction-sources`, `no-send-to-external`) — require *proof* on control args. They consume `fact:*` labels and `known` attestations on the named control fields.
- **Cross-record correlation** (`correlate-control-args`) — verifies all control args on a single dispatch trace to the same source-record instance.

Without this control-arg framing, "untrusted data → privileged op" becomes indistinguishable from "LLM-composed email body → privileged op," which would force you to either ban LLM payload (useless) or accept attacker-controlled targets (insecure). Splitting control args from payload args is what makes both safety and usefulness possible at once.

The legacy `with { controlArgs: [...] }` shape on exes is still accepted during migration but emits a deprecation warning. New code declares control args via the input record's `facts:` section.

**Positive checks depend on tool metadata.** When a tool catalog entry binds an input record via `inputs: @r`, the runtime derives effective control args from `@r`'s `facts:` and effective source args from the same field set on read tools. The positive checks (`no-send-to-unknown`, `no-destroy-unknown`, `no-unknown-extraction-sources`) consume that metadata to know which args carry security responsibility. Without a bound input record, taint checks fall back to all-arg scope and positive checks fall back to field-name heuristics (`fact:*.email` for sends, `fact:*.id` for deletes). The bound-record path is the supported, recommended shape; heuristics are a fallback for unannotated tools.

### 5.3 The durable identity carrier: factsources

When `=> record` coercion mints `fact:@contact.email` on a value, it also writes structured **factsources** metadata onto that value:

```
{
  record:      "@contact",
  instanceKey: "ada@example.com",      >> from key: email, or composite/hash form
  coercionId:  "c_8e7f2a",              >> per-coercion identifier
  position:    0                        >> array index for keyless records
}
```

`factsources` is the durable, cross-phase identity. It travels with the value through:

- assignment and parameter binding
- pipe transformations (`|`)
- shelf I/O round-trips (write → read preserves the full carrier)
- LLM-bridge crossings (when the value is passed in or returned)
- session containers

The runtime's proof-claims registry is **value-keyed via factsources**, not handle-string-keyed. When a planner produces a `known` value that the worker's tool dispatch later sees, the registry looks up the factsource — not the string — to decide whether the proof claim still applies. Two independent calls that fetched the same logical record (same `instanceKey`) match. A bare string the LLM fabricated has no factsource and matches nothing.

Factsources are what makes `correlate-control-args` work: every fact arg on a dispatch must point to the same `(record, instanceKey)` pair (or fall back to `(coercionId, position)` for keyless records).

### 5.4 The handle / address / shelf chain

`factsources` is the durable identity. **Handles, addresses, and shelves are three views of that identity at different lifetimes and surfaces:**

| Surface | Lifetime | Where it lives | What it's for |
|---|---|---|---|
| **Handle** (`h_xxx`) | Per-call ephemeral — dies with the LLM call | LLM JSON tool calls, `<tool_notes>` blocks | Display label the LLM uses to refer to a fact-bearing value within one call |
| **Address** (`<record>:<key>`) | Cross-call stable | Planner-loop wire format, mlld-side dereferencing | Durable identifier for cross-call addressing |
| **Shelf** | Durable across the whole script | Slot storage with full proof carriers | Cross-phase state accumulation |

All three project from the same underlying value-with-factsources. They differ on how long the projection is good for and what surface they appear on:

```
                   ┌── Handle (h_ab12)         per-call display label
value + factsources├── Address (contact:44d1) cross-call stable id
                   └── Shelf entry             durable storage
```

A planner reads a `@contact` record from the shelf. The shelf returns the value with its full factsources intact. The planner is inside an `@claude` call, so the bridge mints a fresh **handle** (`h_ab12`) for the LLM's view of that value in this call. The planner emits a tool call referring to `h_ab12`. The bridge resolves the handle back to the underlying value (via this call's mint table), the worker dispatches with the value's `fact:@contact.email` proof intact.

If the planner instead writes `contact:44d1c1cc` (the **address**) into a shelf as a "selected target" in a multi-call workflow, the next call (with a brand-new mint table and dead handles) can still dereference the address via `@shelf.<slot>.byAddress(@addr)` — the underlying value's factsources are preserved on the shelf row. The new call mints a **new** handle for the same value when projection runs.

This is why **shelves preserve proof carriers** (§6): without that, values written in one call would arrive in the next call as bare data, and the cross-phase identity story would collapse.

### 5.5 Handles in detail

A handle is a string token (`h_xxx`) the bridge mints for fact-bearing values when projecting a record at the LLM boundary. The LLM sees handles in tool result JSON:

```json
{
  "name": "Ada Lovelace",
  "email": {
    "value": "ada@example.com",
    "handle": "h_ab12cd",
    "address": "contact:44d1c1cc"
  }
}
```

The LLM passes the handle in subsequent tool calls. Two equivalent forms:

```json
{ "recipient": "h_ab12cd" }
{ "recipient": { "handle": "h_ab12cd" } }
```

Inside the bridge, both forms resolve to the original live value via this call's mint table. The resolved value still carries `fact:external:@contact.email`. The dispatch sees a fact-bearing arg and the positive checks pass.

**Handles are per-call ephemeral.** Each `@claude` invocation mints fresh handle strings via projection; they are not portable across calls. The bridge resolves handles only against its own per-call mint table. A handle string captured from a prior call will not resolve in a later one — it's dead.

This is intentional: handles are a *display surface*, not a cross-phase identity primitive. Cross-phase identity flows through factsources (which travel via shelves and `known` values), not through handle strings.

### 5.6 Addresses in detail

An address is the cross-call stable form. `.mx.address` returns:

```mlld
@val.mx.address           >> { record: "contact", key: "44d1c1cc", string: "contact:44d1c1cc" }
@val.mx.address.string    >> "contact:44d1c1cc"
```

The `.string` form is the canonical wire format. It's stable across calls and across script runs — the `key` component is always the opaque `.mx.key` hash form (never a readable key-field value, for security).

`@parse.address(...)` round-trips the canonical form back to the structured object. `@shelf.<slot>.byAddress(@addr)` is O(1) lookup against the shelf's by-key index.

When the planner emits a tool call for a target dereferenced by address, the framework looks up the address against the shelf, recovers the live value with its factsources, and dispatches the worker with proof intact — no handle round-trip needed if the call sites are different.

Addresses and handles serve different needs and both stay:

- **Handle** — LLM-facing display label, security-bound, no cross-call laundering possible (a captured handle string is dead in the next call)
- **Address** — durable identifier for planner-loop addressing, opaque key (no attacker-controlled text can surface in the wire form)

### 5.7 Handle resolution at the bridge

Inside an LLM call, the bridge's per-call mint table maps handle strings to underlying values. Both wrapper and bare-string forms resolve:

1. **Handle wrapper** — `{ "handle": "h_xxx" }` in a control-arg position resolves at the bridge for this call's mint table
2. **Bare handle string** — `"h_xxx"` in a control-arg position takes the same path

The bridge mint table is per-call. It does not retain handles from prior calls. From orchestrator code outside an LLM call, handle strings are NOT looked up — pass the underlying labeled value directly (which carries its own proof via factsources).

### 5.8 The builder's value-keyed auto-upgrade

`@policy.build` validates planner intent against the proof-claims registry before compiling a runtime policy fragment for the worker. When a planner emits a `known` entry whose value already has a matching factsource in the registry, the builder **auto-upgrades** that entry to `resolved` with a freshly-minted handle for the worker's call:

```mlld
>> Planner says: "I want to send to ada@example.com — I know this from the user"
{
  known: {
    sendEmail: { recipients: [{ value: "ada@example.com", source: "user said email ada" }] }
  }
}

>> Builder finds existing factsource for "ada@example.com" in registry
>> Auto-upgrades to:
{
  resolved: {
    sendEmail: { recipients: [{ handle: "h_ab12cd_for_worker_call" }] }
  }
}
```

This is the cross-phase reconciliation path. The planner names a value (it doesn't have to know the worker's mint table), the builder finds the existing factsource, and the worker's dispatch sees a resolved handle — not a bare string. The bucket structure (`resolved`, `known`, `allow`) is covered fully in §8; what matters here is *why* the auto-upgrade works: because identity is value-keyed via factsources, not handle-keyed.

### 5.9 What is rejected (and what isn't)

Earlier versions of mlld accepted many emitted forms in the same session via broad "if unique, treat as match" canonicalization. That tolerance has been **narrowed**, but not eliminated. Fact resolution at the LLM boundary takes these paths:

1. **Per-call handle resolution at the bridge** — `h_xxx` strings/wrappers resolve against this call's mint table.
2. **Builder value-keyed `known` upgrade** — `@policy.build` reconciles `known` entries against the proof-claims registry; matching factsources auto-upgrade to `resolved` with worker-fresh handles.
3. **Builder unique-fact-backed-value lifting** — when an entry is a literal value with no fact proof, the builder (not the dispatcher) does a uniqueness check against fact-backed values in scope. If exactly one fact-backed value in the active context matches the literal, the entry is *lifted* to that fact-bearing value with proof and a `liftedArgs` report entry. Ambiguity (multiple matches) and zero-match are rejected.
4. **Dispatch-time strictness** — at the dispatcher, after the policy fragment has compiled, only handle-resolution and proof-bearing values are accepted. Bare literals that survived without builder lifting are rejected.

What is reliably rejected:

- **Masked previews** (`"a***@example.com"`) — display surfaces only. Never resolve to underlying values. The bridge does not canonicalize them at any phase.
- **Bare literals at dispatch time** — once the policy fragment is compiled, the dispatcher does not re-canonicalize. If a literal made it to dispatch without proof or builder-side lifting, it dies there.

What still works (and is safe by design):

- **Builder unique-match lifting** — designed for the planner's "I want to send to ada@example.com" pattern when there's exactly one fact-bearing email in scope. Reports the lift in `report.liftedArgs` for audit. Ambiguity fails closed.
- **Handle resolution from bare strings** — `"h_xxx"` in a control-arg position resolves through the per-call mint table just like the wrapper form `{handle: "h_xxx"}`.

If your agent is copying preview strings around as authorization, you've lost the security property. Pass values, pass handles, or pass addresses — never previews.

### 5.10 Positive checks

`no-send-to-unknown`, `no-destroy-unknown`, `no-unknown-extraction-sources`, and `no-send-to-external` are the positive checks. Where negative checks block contaminated data, positive checks **require proof** on specific control args:

```mlld
policy @p = {
  defaults: {
    rules: ["no-send-to-unknown", "no-destroy-unknown"]
  },
  operations: {
    "exfil:send":           ["tool:w:send_email"],
    "destructive:targeted": ["tool:w:delete_contact"]
  }
}
```

When the tool has a bound input record with `facts:`, any `fact:*` label on those fields satisfies the check. `known` attestation also satisfies it (a planner-pinned value the framework already vetted). Without proof, the call is denied regardless of what the LLM decided.

Without a bound input record, the check falls back to field-name heuristics (`fact:*.email` for sends, `fact:*.id` for deletes). The bound-record path is more precise and is the recommended shape.

`no-send-to-external` is the stricter form: requires `fact:internal:*` or `known:internal` rather than any `fact:*` or `known`. Use it when the operation should only allow inside-the-org targets.

### 5.11 Tying it together

The cross-phase identity story end-to-end:

1. A tool runs and returns data. `=> record` mints `fact:*` labels and writes `factsources` onto the value.
2. The orchestrator stores the value on a shelf (slot writes preserve the full proof carrier).
3. A planner LLM reads the slot via `@fyi.shelf.<alias>` interpolation or via prompt variable. The bridge projects the value and mints a fresh handle. The planner sees `{value, handle, address}` in its tool result JSON.
4. The planner emits bucketed intent: `known: { sendEmail: { recipients: ["h_xxx"] } }`. (Or it emits a value-keyed reference like `{ value: "ada@example.com", source: "user said" }` and the builder reconciles.)
5. `@policy.build` walks the intent, validates against the input record, auto-upgrades value-keyed `known` entries to `resolved` with worker-fresh handles, and produces a compiled runtime policy.
6. The worker call runs. Its tool dispatches resolve handles against this call's mint table. The underlying values still carry their original `factsources` and `fact:*` labels. Positive checks pass. `correlate-control-args` verifies all fact args on a single dispatch trace to the same source instance.
7. After the call, the orchestrator can read the shelf again — and any values written by the worker still carry their full proof carriers, ready for the next planner-worker round.

Identity flows through the value, not through any string the LLM produced. The handle is a label the LLM uses; the address is a wire form for cross-call dereferencing; the shelf is durable storage. None of them carry the proof on their own — the value with its factsources does.

---

## §6. Shelf Slots

Agents accumulate state — candidate lists, selections, drafts, pipeline stages, multi-call workflow context. Shelf slots are the typed surface for that accumulation, and the durable storage that preserves the cross-phase identity carrier described in §5.

Each slot is typed by a record. The record provides schema, fact/data classification, grounding requirements, and read projection. The shelf adds merge semantics, cross-slot constraints, lookup indexes, access control, versioning, and the auto-provisioned `@shelve` tool that the LLM uses to commit values without bare property assignment.

### 6.1 Declaration

```mlld
record @contact = {
  key: id,
  facts: [id: string, email: string, name: string],
  data: [notes: string?, score: number?],
  read: [name, { value: "email" }],
  write: { role:worker: { shelves: true } }
}

shelf @outreach = {
  recipients: contact[],
  selected:   contact? from recipients,
  drafts:     email_draft[]
}
```

Each slot has a record type, a cardinality (`[]` for collection, bare for singular, `?` for optional), and an optional `from` cross-slot constraint. Records used as slot types must declare `write:` permissions for any role that should be able to write to them — records with no `write:` block cannot be persisted to any shelf.

### 6.2 Wildcard shelves

Three forms cover the "I don't want to enumerate every slot upfront" cases:

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

### 6.3 Scope-local shelves

Shelves can be declared inside `exe` or `box` bodies, not just at module scope. Each invocation gets a fresh, isolated shelf instance whose lifetime matches the enclosing scope:

```mlld
exe @runTask(agent, query) = [
  shelf @planner_state from @agent.records
  ...
  >> @planner_state lives for this invocation only;
  >> parallel invocations of @runTask each get their own isolated shelf
]
```

This is the right shape for per-task state where the accepted record set isn't known until the call (`from @agent.records` snapshots at scope entry, not at module load). Concurrent invocations — including `for parallel` branches running the exe — get distinct, non-interacting shelves with no cross-invocation leakage. When the scope exits, the shelf is destroyed.

### 6.4 Record write permissions

Shelf writes consult the record's `write.<role>.shelves` declaration. The bool form `shelves: true` grants only `upsert` — destructive operations (`clear`, `remove`) are explicit:

```mlld
record @draft = {
  facts: [id: string, body: string],
  write: {
    role:worker:  { shelves: { upsert: true, clear: true, remove: true } },
    role:planner: { shelves: [@published] }
  }
}
```

Capability map values can be `true`, `false`, a list of specific shelves, or a label spec. Missing capabilities deny by default.

Two layers of permission fire in order: **box scoping** (does this scope have access to the slot at all?) then **record permissions** (does this role's `write:` permit this capability against this shelf?). Both must pass.

### 6.5 Grounding: durable state demands durable references

Slot writes are stricter than tool calls. Fact fields require **handle-bearing input only** — masked previews and bare literals are rejected:

| Form | Tool call arg | Slot write fact field |
|---|---|---|
| Handle wrapper `{ handle: "h_x" }` | Accepted | Accepted |
| Bare handle string `"h_x"` | Accepted | Accepted |
| Masked preview `"m***@example.com"` | Accepted | **Rejected** |
| Bare literal `"mark@example.com"` | Accepted | **Rejected** |

Slots are durable state; durable state gets durable references. Data fields have no grounding requirement — agents pass any value into payload fields.

### 6.6 Merge semantics

| Slot type | Record has `key`? | Default merge |
|---|---|---|
| `record[]` | yes | upsert by `.mx.key` |
| `record[]` | no | append |
| `record` | — | replace |

Upsert compares the row's opaque `.mx.key` and **field-merges**: incoming non-null fields replace stored fields; incoming missing or null fields leave the stored field unchanged. The same rule applies to static `record[]` slots and wildcard `record_type[]` slots.

Override with the expanded form when you want append-only history: `log: { type: contact[], merge: "append" }`.

### 6.7 Cross-slot constraints

`from` validates that a value exists in a referenced slot at write time:

```mlld
shelf @pipeline = {
  candidates: contact[],
  qualified:  contact[] from candidates,
  winner:     contact? from qualified
}
```

An agent can't select a winner that was never a candidate. Identity uses `.mx.key`, so the constraint survives multiple handles minted for the same entity across different calls. `from` is write-time only — stored values don't become retroactively invalid if the source slot changes later.

### 6.8 Lookups: `byKey` and `byAddress`

Keyed slots maintain lookup indexes:

```mlld
@pipeline.candidates.byKey(@record.mx.key)         >> direct opaque-key lookup
@pipeline.candidates.byAddress(@record.mx.address) >> via cross-call address
@shelf.read(@pipeline.candidates).byAddress("contact:44d1c1cc")  >> string-form ok
```

`byAddress` is the primitive that closes the cross-phase loop from §5: a planner emits an address (`contact:44d1c1cc`) into bucketed intent, the framework dereferences it via `@shelf.<slot>.byAddress(@addr)` against the shelf, and recovers the live value with full factsources for the worker dispatch. The bridge mints a fresh handle for the new call; the planner never had to know the worker's mint table.

### 6.9 Two read surfaces

Slot contents are reachable two ways. Use the right one for the context:

| Path | Audience | Projection | What it returns |
|---|---|---|---|
| `@fyi.shelf.<alias>` | LLM agent inside a scoped box | Read modes apply | The agent's view — fields may be `value`/`mask`/`handle`, protected, or omitted |
| `@shelf.read(@slotRef)` | Orchestrator code outside the box | None | Full structured values with fact labels, factsources, and live handles intact |

`@fyi.shelf` is what an agent reads. The record's `read` clause shapes what the LLM sees — fact fields cross the boundary as handle-bearing wrappers per §4.3.

`@shelf.read` is what orchestrator code reads. It returns stored values unprojected — same shape they had when written. Use this when feeding slot contents into another `@shelf.write`, into a JS exe for inspection, or into a downstream tool dispatch from orchestrator code.

Shelf round-trips preserve field-local fact labels and factsources. A read-back field keeps its own `fact:@record.field` proof; sibling fact labels from the same record are not reattached to that field. **This is the load-bearing property** that makes cross-phase identity work — without it, the §5 chain would break the moment a value transited a slot.

### 6.10 The slot API

`@shelf` exposes the full slot API. `@shelve(...)` is sugar for `@shelf.write` (and is also the name of the auto-provisioned LLM tool covered below).

```mlld
@shelf.write(@pipeline.candidates, @candidate)
@shelf.read(@pipeline.candidates)
@shelf.clear(@pipeline.candidates)
@shelf.remove(@pipeline.candidates, "h_abc")

@pipeline.candidates.upsert(@candidate)
@pipeline.candidates.read()
@pipeline.candidates.clear()
@pipeline.candidates.remove(@candidate.mx.key)
@pipeline.candidates.byKey(@candidate.mx.key)
@pipeline.candidates.byAddress(@candidate.mx.address)
```

There is no `shelf @x <- @value` syntax. Use `@shelf.write` (or method-call form on the slot ref).

### 6.11 Access control via box config

Box config grants per-slot access. Two equivalent shapes — literal slot refs or a value built from a regular variable:

```mlld
>> Literal form
box {
  shelf: { write: [@outreach.recipients] }
} [...]

box {
  shelf: {
    read:  [@outreach.recipients],
    write: [@outreach.selected]
  }
} [...]

>> Value form — useful when framework code builds the scope dynamically
var @decisionScope = {
  read:  [@outreach.recipients],
  write: [@outreach.selected]
}
box { shelf: @decisionScope } [...]
```

Write implies read.

**Aliases.** A slot ref in box config exposes the slot to the LLM under its declared name (`@outreach.recipients` becomes `@fyi.shelf.recipients`). Use `as <alias>` to rename when role-based naming is desired:

```mlld
box {
  shelf: { read: [@outreach.recipients as candidates] }
} [...]
```

**Wildcard scopes.** Bounded wildcard shelves can use `@s.*`:

```mlld
box {
  shelf: { read: [@state.*], write: [@state.*] }
} [...]
```

For bounded wildcards this expands over the accepted virtual slots. For bare `*` shelves it grants future writes for record types known when the slot is accessed.

**Composable scope values.** `read` and `write` accept arrays or objects, bare slot refs, alias values (`@slotRef as alias`), single-key alias objects (`{ selected: @s.selected }`), or `{ name, ref }` pairs. Pair with `@someShelf.mx.slotEntries` when framework code needs to build a flat alias surface from computed data.

### 6.12 The auto-provisioned `@shelve` tool

When a box grants write access to any slot, the runtime auto-injects a synthetic `shelve` tool into the LLM's tool surface alongside whatever tools the call already declared. The agent doesn't need `@shelve` listed in the box's `tools:` config — presence of writable shelf scope is sufficient.

The LLM calls `shelve` like any other MCP tool, addressing the slot by the alias the box config gave it. The MCP tool's input schema constrains `slot_alias` to an enum of the box's writable aliases — the LLM cannot write to a slot the box didn't expose. The runtime resolves the alias to the underlying slot ref and runs the normal write pipeline (handle resolution → schema validation → grounding check → merge → source labeling).

This is what gives the planner-worker pattern its data-plane: the planner emits a tool call to `shelve` with bucketed intent and a target slot alias, the worker reads the slot via `@fyi.shelf` interpolation in its prompt or via orchestrator pre-read.

### 6.13 Parallel writes

Inside `for parallel`, shelf writes are buffered per branch and do not mutate live state while the parallel block is running. Reads inside a branch see the **pre-parallel snapshot** — a branch never observes another branch's in-flight writes.

When the parallel block exits, successful branches' buffers commit once in branch enumeration order; failed branches' buffers are discarded. Same-key collisions resolve via the field-merge rule (later branch's non-null fields replace earlier on conflicts).

```mlld
exe @run(agent) = [
  shelf @s from @agent.records

  for parallel(N) @spec in @specs [
    let @result = @resolve(@spec)
    @s.<slot>.upsert(@result)        >> buffered, not applied yet
  ]
  >> @s now contains all parallel branches' merged writes
]
```

This applies to module-scope shelves and to scope-local shelves declared inside the enclosing exe or box. Reads after the parallel construct see the committed state and the version counter (next subsection) increments accordingly.

### 6.14 Versioning and introspection

```mlld
@someShelf.mx.slots         >> declared slot names
@someShelf.mx.slotEntries   >> { name, ref } pairs
@someShelf.mx.version       >> shelf rollup version
@someSlot.mx.version        >> per-slot version
```

The version counter increments on writes (committed writes from parallel blocks bump it once). Useful for cache invalidation in dispatcher loops.

**Per-key cache invalidation.** Projection caches keyed by `.mx.key` invalidate **per row**, not per slot — writing entry A to a slot does not invalidate entry B's projection cache in the same slot. This means a long-lived dispatcher loop that re-projects many rows from a slot only re-mints handles for rows whose content changed. Composes correctly with field-merge upsert: a no-op merge (incoming fields equal stored fields) leaves the cache untouched.

To inspect the **current shelf scope** (which slots the active execution context can read or write, by alias), use `@mx.shelf.writable` and `@mx.shelf.readable`. They return alias metadata only — use `@shelf.read(@slotRef)` for actual stored values.

### 6.15 Trust model

Slots don't mint facts. `known` doesn't persist in slots. Writes are atomic. **Authority comes from the original records and `=> record` coercion — the shelf preserves proof, it doesn't create it.**

Shelf I/O preserves the full structured proof carrier through round-trips: a value written to a slot and read back retains its labels, factsources (including `instanceKey`, `coercionId`, `position`), and source-record provenance. Cross-phase identity passed via shelves is durable end-to-end — a planner writes a fact-bearing target, the worker reads it, and the resolved value still carries the same factsources for downstream `correlate-control-args` and positive checks to consume.

---

## §7. Per-Call Session Containers

Where shelf slots accumulate state across an entire script execution, **session containers accumulate state for the lifetime of a single LLM call**. Every tool callback dispatched by that call sees the same instance; the instance dies when the call exits. This is the right primitive for budgets, counters, terminal-tool latches, execution logs, and any per-conversation accumulator that must not leak across concurrent or nested calls.

The contrast with shelves matters:

| Surface | Lifetime | Use case |
|---|---|---|
| Shelf slot | Cross-call, cross-phase | Durable agent state — candidates, selections, multi-call workflow |
| Session container | One LLM call | Per-conversation accumulators — budgets, counters, run logs |

### 7.1 Declaration

```mlld
record @plannerRuntime = {
  data: [tool_calls: number, invalid_calls: number, terminal: string?, last_decision: string?]
}

var session @planner = {
  agent:   object,
  query:   string,
  state:   object,
  runtime: @plannerRuntime
}
```

The declaration is a labeled var — peer with `var tools`. The RHS is a JSON-shaped object whose values are types: primitives (`string`, `number`, `boolean`, `object`, `array`), record references (`@recordName`), typed arrays (`@recordName[]`), and the optional suffix (`?`). The var binds to the schema; live instances are materialized per call.

Records used as session slot types must be **input-capable, open-read, and have no `when:` rules**. The validator emits `INVALID_SESSION_SLOT_RECORD` if the record declares a `read:` block (sessions don't project at an LLM boundary the same way), `when:` rules (sessions are accumulators, not proof sources), or other output-direction-only sections. The slot type's role in the runtime is purely structural: validating types of writes and providing default values on read.

### 7.2 Attachment and seed

Attach to an LLM-calling exe via `with`:

```mlld
exe llm @runPlanner(agent, query, prompt) = @claude(@prompt, { ... }) with {
  session: @planner,
  seed:    { agent: @agent, query: @query }
}
```

`seed:` writes initial values into the freshly materialized instance — through the normal type-validated write path — before the first tool callback runs. Required slots without a seed entry raise `MlldSessionRequiredSlotError` on first read.

**Wrapper-owned default.** When both a wrapper and a caller specify `session:`, the wrapper wins. Caller override requires explicit opt-in: `with { session: @alt, override: "session" }`. Without the override flag, the conflict raises at the `with` merge layer. This protects framework invariants from accidental caller-side replacement.

### 7.3 Access API

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

| Method | Effect |
|---|---|
| `.set(field: value, ...)` | Replace multiple top-level slots in one call |
| `.write(path, value)` | Replace at a dotted path |
| `.increment(path, n)` | Atomic numeric add |
| `.append(path, value)` | Append to an array |
| `.update(path, @fn)` | Functional update with a pure exe |
| `.clear(path)` | Reset slot to its declared default |

Reads use dotted accessors: `var @count = @planner.runtime.tool_calls`. Writes go through methods only — no bare property assignment. `.update(path, @fn)` accepts only pure exes (`js`, `node`, `mlld-exe-block`, `mlld-when`); `llm` exes and tool-dispatching exes are rejected at call time so commit semantics stay simple.

**Bare-name access is a snapshot.** `var @sess = @planner` (used as a value, not a method head) captures an immutable snapshot of the session's current state. Subsequent reads through `@sess.runtime` see the snapshot, not further mutations. Vars never hold live mutable references.

### 7.4 Strict nesting (security invariant)

Session resolution inspects only the **nearest enclosing bridge frame**. If the nearest frame did not attach `@planner`, the access raises `MlldSessionNotAttachedError` even if an outer frame attached one with the same name.

This is load-bearing for isolation: an inner `@claude()` worker cannot read or mutate an outer planner's session by knowing its declaration name. The only paths for state to cross frames are explicit prompt parameters and shelf slots.

Concurrent calls each get their own session instance — the global-shelf aliasing class of bug is impossible by construction. Resume runs in a fresh frame and gets a fresh session instance; writes do not survive resume.

### 7.5 Guard write-commit semantics

Session writes made inside a guard's execution frame go through a per-guard buffer. The buffer commits atomically on guard allow-exit and discards on deny-exit:

- A `before` guard that writes and then returns `deny` does **not** commit those writes — counters never over-count denied attempts.
- An `after` guard never fires on a denied dispatch (structural invariant in the guard path).
- Within a single guard body, reads observe the guard's own pending writes (read-your-writes overlay); between guards, only committed state is visible.

Trace events for buffered writes are committed or discarded with the writes — denied guards never leak `session.write` events to trace output, SDK streams, or the post-call snapshot.

### 7.6 Trace redaction and post-call inspection

Session writes emit `session.write` trace events with redaction applied per the same rules as variable redaction (`secret` is hidden, `pii` is masked at trace-emit time). Trace output is safe to log.

After the LLM call exits, the orchestrator reads the final session state from the result:

```mlld
var @result      = @runPlanner(@agent, @query, @prompt)
var @plannerFinal = @result.mx.sessions.planner
```

`@result.mx.sessions.<name>` is keyed by the canonical session declaration name. The post-call snapshot is immutable.

### 7.7 Trust model

Sessions are accumulators. They don't mint labels, don't carry `known` attestations, don't satisfy positive checks. A value written to a session and read back keeps whatever labels it had at write time, but the session itself adds no proof. **For authorization-grade state, use shelves and records — sessions are for execution accounting.**

---

# Part II — Patterns

## §8. The Capability Agent Pattern

The defended-agent architecture is a **persistent clean planner session with scoped framework workers**. The planner is one long-running `@claude` call that calls framework-provided worker tools. Each worker tool internally dispatches an isolated worker `@claude` call with a dedicated tool subset, read mode, shelf scope, and authorization scope.

The planner stays clean throughout. It never sees tainted content directly. Workers do the tainted-content work and return planner-safe results through two structural boundary mechanisms — record-projected return for data, `->` attestation for control-plane status. Typed shelf state and execution logs are the substrate; conversation history supplements state but does not replace it.

Everything in the rest of this section composes from primitives covered in §1–§7. This section is the assembly.

### 8.1 How the planner stays clean

Two structural mechanisms, not prompt discipline:

1. **`role:planner` read projection.** The planner exe carries a `role:planner` label. Records project their `read: { role:planner: [...] }` whitelists at the LLM bridge (§4.3). Unlisted fields are protected. Fact fields get handles when the read mode requests them. The planner sees metadata + handles, not content.

2. **`->` taint scoping.** Worker tools return `->` values whose taint follows the expression's own inputs, not the exe's ambient scope. A `->` expression constructed from handles (opaque, no taint) and literals (no taint sources) is clean even when the worker internally processed tainted content. The structural guarantee is "the `->` expression's dependency graph determines taint," not "the prompt tells the worker to filter."

These compose: canonical record returns use mechanism 1 (read projection at the bridge). Explicit `->` attestation uses mechanism 2 (expression-level taint scoping). Both keep the planner uninfluenced when the developer uses the intended pattern.

### 8.2 The five worker types

Each worker is a framework-provided tool the planner calls. Each has its own narrow scope:

**Resolve** — grounds entities and handles from planner-safe tool surfaces. Uses only `resolve:r` tools. Writes grounded records to planner-selected shelf slots. Returns the grounded domain result on the canonical record path (`=> @grounded as record @RecordType` or `=> @cast(@grounded, @RecordType)`) so the bridge applies the planner's `role:*` projection. May use `->` for a deliberately different planner envelope (`{ slot, count, contacts: @grounded, summary }`).

**Extract** — reads tainted content from explicitly selected sources. Uses only `extract:r` tools. Source scope is framework-enforced via `sourceArgs` and `no-unknown-extraction-sources`. Output is contract-pinned via developer-supplied records with `@cast(@raw, @contract)`. Writes typed results to planner-selected extracted slots. The right home for proposal-style outputs (`*_payload` for single downstream writes, `*_proposal` for multi-step tasks where the planner reviews before authorizing).

**Execute** — performs exactly one concrete write under compiled per-step authorization. The planner passes authorization intent referencing handles from prior resolve calls. The framework checks `policy.authorizations.can_authorize[role:planner]`, calls `@policy.build` to compile the intent, and dispatches the worker with the single authorized write tool plus compiled policy. No shelf scope. Pre-resolved typed inputs from the framework. Recommended return shape: `-> { status, tool, result_handles?, summary }` (frameworks may pick a different envelope; the structural property is that it's `->` from the worker, not the schema).

One write per execute dispatch. Multi-step tasks are a planner-managed sequence of single-action execute calls. Authorization reasoning, blast radius, and recovery stay simple this way.

**Compose** — produces the final user-facing answer. No tools (`tools: []`). Reads clean shelf state and execution log. The no-tools boundary is structural: it prevents the compose path from being an injection vector for additional tool calls. Returns `=-> @composedText` (same value to both channels).

**Advice** — preserves the explicit advice gate for recommendation-style tasks. Uses the `advice`-labeled `denied =>` handler path with `no-influenced-advice` as a structural defense and `@debiasedEval` as the fallback (see §3.8). Replaces compose when the task is advice-classified.

### 8.3 `=> record` vs `->` — data-plane vs control-plane

Two distinct return channels serve two distinct purposes:

- **`=> record`** is the **data-plane** path. `=> @value as record @R` and `=> @cast(@value, @R)` turn on record-mediated return filtering. When the return crosses to an LLM caller, the bridge applies the active `role:*` read projection. This is how read tools communicate domain results to the planner — the planner sees fact fields with handles, data fields are omitted or masked per the record's read declaration.

- **`->`** is the **control-plane** path. It lets a worker return a deliberately authored planner-visible object that is NOT produced by record read projection. This is for agent-to-agent communication: a worker that processed tainted content needs to tell the planner what happened. That communication cannot be the worker LLM's own words. The worker exe's mlld code — not the worker LLM — builds the `->` value programmatically from planner-safe sources: handles, status literals, counts, slot names, next-step signals. **The `->` expression is the orchestrator-authored message.**

A `->` built from handles (opaque, no taint) and literals (no taint sources) gives the planner a clean control message. If the developer stuffs tainted content into `->`, they're bypassing the intended pattern and the runtime preserves that taint via expression-level taint scoping.

**`=->`** writes the same value to both channels — for cases where both consumers see the same thing (e.g., compose).

The design rule:

- Use `=> @value as record @R` or `=> @cast(@value, @R)` when the planner should see a record-projected view of domain data.
- Use `->` when the planner should see an orchestrator-authored attestation/status envelope rather than the worker's direct output.
- These are the only two structural mechanisms for safely returning values to a clean agent. Don't invent a third path.

**Strict mode.** Any exe with `->` or `=->` in source NEVER falls back to `=>` for tool dispatch. If the `->` was in an unreached branch, the LLM sees `null`, not the `=>` value. This closes the "I thought I gated this" leak.

### 8.4 Authorization model

Write authorization is declared per role in policy:

```mlld
policy @p = {
  defaults: { rules: ["no-send-to-unknown", "no-untrusted-destructive"] },
  records_require_tool_approval_per_role: false,
  operations: { "exfil:send": ["tool:w:send_email"] },
  authorizations: {
    deny: ["update_password"],
    can_authorize: {
      role:planner: [@sendEmail, @appendToFile, @deleteFile]
    }
  }
}
```

- **`deny`** — no role can authorize these tools, ever. Hard structural denial; survives `{ guards: false }` and is not subject to privileged-guard override.
- **`can_authorize`** — which roles can authorize which tools. The framework checks this before calling `@policy.build`. Catalog entries can also declare `can_authorize: "role:planner" | false | [roles]`, which compiles additively into this field; policy wins on conflict.
- **`records_require_tool_approval_per_role`** — when `true`, record-backed tool submission also requires `write.<role>.tools.submit`. The default is `false`, where membership in the provided tool catalog is enough to submit.

The planner's `role:planner` exe label is the load-bearing identity for authorization decisions. Treat role labels as the security identity; do not rely on `read:` overrides to switch identity. The runtime resolves the active authorization role in this order: tool-config role > exe `role:*` label > scoped `read:` mode mapped to a role. Scoped `read:` *can* fall through into the active role when no other source declares one, so prefer explicit role labels on exes that participate in authorization rather than relying on the read-mode fallback.

The planner sees `<authorization_notes>` — auto-injected docs for tools it can authorize, generated from `can_authorize`. Describes each tool's signature and fact args (from the bound input record's `facts:`) so the planner can construct valid authorization intent. Separate from `<tool_notes>` (which describes callable tools).

#### Two separate gates

`authorizations.can_authorize` (policy-level) and `write.<role>.tools.authorize` (record-level, §4.5) are **two separate authorization gates that compose conjunctively**, not aliases of each other. A planner authorization must pass *both* — the record's per-role authorize capability, and (when defined) the policy's role/tool authorization map. A worker submit is allowed by provided catalog membership by default; under `records_require_tool_approval_per_role: true`, it must also pass the record's per-role `tools.submit` capability.

The record-side `write:` is the contract that travels with the record. Catalogs may also carry legacy `can_authorize` defaults at the entry level, but these are ignored when the entry has an `inputs:` record (the record-side declaration is authoritative). Policy-side `authorizations` is the right home for cross-cutting `deny` rules and for granting roles that a record's authors didn't anticipate.

Note also: `policy.authorizations.can_authorize` accepts a few legacy shapes (top-level `can_authorize`, `authorizations.can_authorize`, `authorizations.authorizable`) and normalizes them all to a top-level `can_authorize` at parse time. Authoring new policies, prefer the top-level form.

Composition: when both policy and a tool's catalog/record declare role lists for the same tool, the runtime intersects them. Adding a role at one layer and not the other does not silently grant.

### 8.5 Dual-role pattern: authorize-then-submit

Tool dispatch under a record's `write:` block has two phases (§4.5): **authorize** (the planner certifies the dispatch) and **submit** (the worker executes it). When a single dispatcher exe drives both phases — calling `@policy.build` to compile the planner's intent, then dispatching the worker — both phases need their own active role.

**Active role is execution context, not data shape.** The runtime resolves the active authorization role from, in order:

1. The current LLM tool config's `authorizationRole` (set when `@claude(...)` runs with a scoped `read:` mode that maps to a role)
2. The current `role:*` exe label (declared on the exe, e.g. `exe role:planner @plan(...)` or `exe role:worker @worker(...)`)
3. The active scoped read mode propagated through `with { read: "role:planner" }` on the LLM call

`@cast(@value, @record)` does **not** switch the active role — it's a value-shape coercion, not a context shift. Value transformations don't grant authority; only the call's enclosing exe label, tool config, or scoped read can do that.

The right shape for a dispatcher: the planner step runs under a planner-role surface (its own `@claude` call with planner read, or an `exe role:planner` wrapper around `@policy.build`); the worker step runs under a worker-role surface (the framework's `@worker` invocation):

```mlld
>> Planner emits intent inside its own role:planner llm call
exe role:planner llm @plan(query, tools) = @claude(@prompt, { tools: @tools }) with {
  read: "role:planner"
}

>> Worker dispatches the compiled policy under role:worker
exe role:worker llm @worker(prompt, policy, tools) = @claude(@prompt, {
  tools: @tools
}) with {
  policy: @policy,
  read:   "role:worker"
}

>> The orchestrator runs each phase in its own active-role surface
exe @dispatchExecute(intent, tools, prompt, query) = [
  let @taskPolicy = @policy.build(@intent, @tools, { task: @query })
  @worker(@prompt, @taskPolicy, @tools)
]
```

`@policy.build` runs in whatever role surface the orchestrator is currently in. When the planner emits intent from inside an `@claude` call carrying `role:planner`, the bridge's authorization-role propagation lets `@policy.build` see `role:planner` as the active role and the record's `write.role:planner.tools.authorize` check passes. The worker call then runs under `role:worker` and may submit because the write tool is in the provided catalog. Strict deployments with `records_require_tool_approval_per_role: true` also require `write.role:worker.tools.submit` to pass.

**Common cause of `WRITE_DENIED_NO_ACTIVE_ROLE`:** orchestrator code calls `@policy.build` from outside any LLM/exe-label surface, so the active role is undefined. Wrap the build in an `exe role:planner` helper, or call it from inside the planner's own `@claude` flow.

**Test scaffolding.** Tests that exercise strict per-role tool *submission* must run inside an exe carrying `role:worker` (or a role the record's `write:` permits for `submit`). Tests that exercise `@policy.build` directly must run under `role:planner` (typically `exe role:planner @testFoo()`). Tests covering the full dispatcher need both surfaces. Without them, record write checks fire `WRITE_DENIED_NO_ACTIVE_ROLE` before any value-level assertion — and the test failure is misleading because the cause is structural, not value-level.

### 8.6 Bucketed intent

The planner structures its authorization output by proof source. Three top-level buckets:

```json
{
  "resolved": {
    "send_email":     { "recipients": "h_2l5r36" },
    "append_to_file": { "file_id": "h_upt8mo" }
  },
  "known": {
    "send_email": {
      "recipients": {
        "value":  "john@example.com",
        "source": "user asked to email john"
      }
    }
  },
  "allow": {
    "create_file": true
  }
}
```

- **`resolved`** — values whose proof comes from a prior tool result. Accepts handle strings minted in a prior call's read projection, OR fact-bearing values passed directly from orchestrator code (the runtime walks the value's `factsources` to mint a fresh handle for the dispatching call). Bare literals with no proof are rejected.
- **`known`** — values the user explicitly provided in their task text. The runtime verifies the value appears in the task text via the `{ task: @query }` config to `@policy.build`. Optional `source` field for audit logging. Must come from uninfluenced sources only (the clean planner).
- **`allow`** — tools the planner authorizes with no per-arg constraints. Object form `{ tool: true }`. Works for tools regardless of whether they declare an input record with `facts:` — the planner takes responsibility at the tool level instead of per-arg.

The buckets are categories of **reasoning** (provenance) rather than categories of **values**. Each maps to a different validation path inside `@policy.build`: handle/factsource resolution, task-text verification, or no-check. The runtime processes all three uniformly and emits a single compiled policy fragment.

**Where user-typed literal values go.** In `known`, keyed by the tool they satisfy. If the user's task is "reschedule my 2pm meeting to 3pm," then `event_id: <handle>` (from the resolve phase) goes in `resolved.reschedule_calendar_event.event_id` and `new_start_time: "15:00"` (from the user's task text) goes in `known.reschedule_calendar_event.new_start_time`. The runtime validates both buckets against the tool's bound input record (`facts:` / `data:`) plus any builder-phase sections (`exact:`, `update:`, `allowlist:`, `blocklist:`).

**Don't mix flat and bucketed forms.** `@policy.build` accepts pure-bucketed intent OR pure-flat intent (the lower-level explicit form), not both at once — mixing produces a hard error rather than silently dropping entries. Use bucketed for planner-emitted intent; reserve flat for programmatic construction in framework code.

The entire bucketed intent must come from uninfluenced sources. Influenced workers (context worker, write worker) produce data for reasoning, not authorization intent. If the same tool+arg appears in both `resolved` and `known`, `resolved` wins.

### 8.7 The compile step: `@policy.build`

The framework calls `@policy.build` to validate planner intent and compile a runtime policy fragment for the worker dispatch:

```mlld
var @taskPolicy = @policy.build(@plannerIntent, @tools, { task: @query })

var @result = @worker(@prompt) with { policy: @taskPolicy }
```

`@policy.build` walks the same checks the dispatcher will later enforce, plus builder-only sections (`exact:`, against the `task` text). For each bucket entry it:

1. Looks up the tool in `@tools` to find the bound input record
2. Validates the proposed values against the input record's sections (type check, fact-proof check, allowlist/blocklist match, exact match against task text)
3. For `known` entries with values that already have factsources in the registry, **auto-upgrades to `resolved`** with a freshly-minted handle for the worker's call (the value-keyed reconciliation path from §5.8)
4. Drops invalid entries with structured issues in `report` / `issues`

Hand-built `with { policy: ... }` fragments fail closed at activation if invalid. The planner's intent is what gets validated; the framework's compile step is what produces the worker's runtime policy.

### 8.8 Records use `role:*` read keys

Records declare per-role field visibility using `role:*` keys that match the labels on exes:

```mlld
record @email_msg = {
  facts: [from: string, message_id: string],
  data:  [subject: string, body: string],
  read: {
    role:planner: [{ value: "from" }, { value: "message_id" }],
    role:worker:  [{ mask: "from" }, subject, body]
  }
}
```

The record is the **single source of truth** for both data shape and access policy. The `role:planner` read omits subject and body (injection surfaces). The `role:worker` read shows content with identity masked. The runtime matches the active `role:*` label from the exe to the record's read key. One naming system, one place the mapping lives.

### 8.9 Handles, addresses, shelves — the assembly

The planner-worker pattern is built end-to-end on the chain from §5:

1. **Resolve worker** runs read tools that return `=> record` results. Coercion mints `fact:*` and writes factsources. The worker writes the result to a planner-selected shelf slot.
2. **Planner** reads the slot via `@fyi.shelf.<alias>` (read projection applied per `role:planner`). It sees `{value, handle, address}` for fact fields, protected/masked for data fields.
3. **Planner** emits bucketed intent: handles in `resolved`, user-typed values in `known`, blanket `allow` for tools without per-arg constraints. Addresses can also appear in `resolved` for cross-call references.
4. **Framework** calls `@policy.build` with the intent, tools, and task text. `known` entries with matching factsources auto-upgrade to `resolved` with worker-fresh handles. Invalid entries drop with reasons.
5. **Execute worker** runs with the compiled policy. Its tool dispatches resolve handles against its own per-call mint table; the underlying values still carry their original factsources and `fact:*` labels. Positive checks pass. `correlate-control-args` verifies all fact args trace to the same source.
6. **Worker** returns `-> { status, tool, summary, result_handles? }`. The control-plane attestation is the orchestrator-authored message; planner sees status, not raw output.

If shelf slots, records, handles, addresses, factsources, and `@policy.build` all sound like a lot of moving parts — they are. Each is doing the work of one specific structural guarantee. Together they let a planner authorize writes without ever seeing tainted content, and let workers act on tainted content without writing to attacker-controlled targets.

### 8.10 The record modeling rule

**If a field contains values a downstream write tool needs as a control arg, it must be a fact, not data.** Data fields don't get fact proof. Selection beats re-derivation — preserve handle-bearing values in records and let the planner select from them via resolve tool calls.

The rule's corollary: don't model "what the LLM should do with this" into payload fields and try to authorize from them. Authorize from facts; let the LLM compose payload.

### 8.11 Conversational agents: user-typed values flow as `known`

In a conversational agent, the user is what feeds the planner with task intent. User-typed literal values (recipient names, new times, exact subject lines) flow into the planner's bucketed intent as `known` attestations from an uninfluenced source — the same security path as a clean planner's literals. If the user types "reschedule my 2pm meeting to 3pm," the `"15:00"` literal goes in `known` keyed by the reschedule tool, with the task text supplying the verification source.

The user is not magic — they're a clean source of `known` values just like a programmatically-clean planner. The same `@policy.build` checks run; the same fact-arg / payload-arg distinctions apply. The agent stays a worker; the user-message-as-intent stays in the planner role.

### 8.12 Typed state, not just conversation history

Shelf state and execution logs remain mandatory in defended mode. Conversation history supplements state but cannot replace it. Typed state is required for:

- heterogeneous grounded entities across domains
- contract-pinned extract outputs
- cross-worker data passing without prose laundering
- advice-gate inputs
- execution summaries and recovery

If your defended-agent design is "the planner remembers" plus prompt instructions, you've inherited every drift mode of the LLM. Typed shelf state under `role:*` permissions is what makes the architecture structural.

---

## §9. Composability

Security in mlld is designed as a **separate concern** that composes cleanly with application logic. The right shape: application code does its work, security is injected from outside.

### 9.1 Policies compose with `union()`

```mlld
import { @secretPolicy } from "./security/secrets.mld"
import { @piiPolicy }    from "./security/pii.mld"

policy @combined = union(@secretPolicy, @piiPolicy)
```

Composition is **restrictive by default**. The most restrictive wins:

- `defaults.rules` — union (every rule from any policy is enabled)
- `labels` flow rules — union of denies, intersection of allows per label
- `capabilities.allow` — intersection (allowed in all source policies)
- `capabilities.danger` — restrictive: intersection when both sides declare it; **empty when only one side declares it** (one-sided dangers don't pass through, because the unilateral side hasn't been confirmed by the other)
- `authorizations.deny` — union
- `authorizations.can_authorize` — intersection per role and per tool when both sides declare; one-sided declarations pass through unchanged
- `records_require_tool_approval_per_role` — sticky (`true` wins)
- `locked` — sticky (if any source is locked, the result is locked)
- `operations` — union (semantic-label → risk-category mappings merge)

A restrictive overlay policy can never accidentally loosen a base policy. To deliberately replace a base policy at an invocation site rather than merge with it, use the **invocation-level** `replace: true` flag on `with { policy: ... }`:

```mlld
@worker(@prompt) with { policy: @taskPolicy, replace: true }
```

`with { replace: true }` requires `with { policy: ... }` and replaces the active policy entirely for that call. Section-level `replace: true` inside a policy declaration is **not currently a feature** — there is no `policy @p = { capabilities: { replace: true } }` form. If you need to override a parent policy, declare a fresh policy and use the invocation-level escape hatch.

### 9.2 Guards are regular exports

```mlld
>> security/email-guards.mld
guard privileged @emailGuard before tool:w = when [
  @mx.op.name == "send_email" && @mx.args.recipients == ["allowed@company.com"] => allow
]
export { @emailGuard }
```

```mlld
>> app.mld
import { @emailGuard } from "./security/email-guards.mld"
>> Guard is now active in this script
```

Importing a guard installs it in the importing scope. Modules can ship guard bundles for specific security postures (PII handling, secret protection, audit logging) and applications opt in by importing.

### 9.3 Separation of concerns

The cleanest pattern: application code never references security. Policy and guards are injected from outside — by the SDK, by a security module, or by a build step.

```mlld
>> security/task-policy.mld — injected by the SDK
policy @task = { ... }
guard privileged @valueMatch before tool:w = when [ ... ]
export { @task, @valueMatch }
```

```mlld
>> app.mld — pure application logic, no security awareness
import { @claude } from @mlld/claude
import { @dispatch } from "./tools/active.mld"
>> ... does its work, constrained by policy it never sees
```

This means you can change the security posture without touching the application. Swap the policy module, adjust the guards, redeploy. The application code is unchanged.

### 9.4 Wrapper-owned session defaults

When both a wrapper exe and a caller specify `session:`, the wrapper wins by default. Caller override requires explicit opt-in:

```mlld
@worker(...) with { session: @altSession, override: "session" }
```

Without the override flag, the conflict raises at the `with` merge layer. `override: "session"` is the only currently-recognized override value — `override: "policy"`, `override: "tools"`, and `override: "read"` are not implemented as generic wrapper-vs-caller dispute mechanisms. For policies, use the invocation-level `with { policy: @p, replace: true }` form (§9.1). For tools and read, the merge rules are field-specific (caller-additive for tools, most-specific-wins for read).

### 9.5 Tool-doc and tool-note auto-injection

`@claude()` calls with security-relevant tools auto-inject two structured prompt blocks:

- **`<tool_notes>`** — per-tool argument listings with fact args flagged, read/write classification, the deny list, and multi-fact correlation warnings. Derived from bound input records and active policy.
- **`<authorization_notes>`** — for the planner role only: tools the planner can authorize (per `can_authorize`), with their signatures and fact args from the bound input record.

For custom prompt assembly without `@claude()`, use `@toolDocs(@tools)` to produce the same content. The tool collection must be a labeled `var tools @x = {...}` declaration to carry the compiled metadata; bare object spread (`{ ...@tools }`) materializes plain data and drops the tool-collection identity.

---

## §10. Debugging with Runtime Tracing

When something goes wrong in a defended agent, the symptom appears far from the cause. A shelf write that silently fails shows up as empty state three turns later. A guard resume that doesn't fire manifests as a collapsed planner loop. A handle that loses proof during JS interop surfaces as an authorization denial on a different phase.

Runtime tracing makes these cause-and-effect chains visible. Enable with `--trace`:

```bash
mlld run pipeline --trace effects                          >> shelf writes, guard decisions, auth checks
mlld run pipeline --trace handle                           >> only handle lifecycle (handle.issued / .resolved / .resolve_failed / .released)
mlld run pipeline --trace verbose                          >> adds handle lifecycle, LLM calls, record coercions, read projections
mlld run pipeline --trace effects --trace-file tmp/trace.jsonl
```

Trace levels: `off`, `effects`, `handle` / `handles`, `verbose`. `--trace handle` and `--trace handles` are equivalent — both isolate handle events. Memory tracing is enabled separately via `--trace-memory` (a sibling flag, not a `--trace` level), which adds RSS/heap/external/ArrayBuffer samples on `memory.*` events and implies `--trace effects` when no other trace level is set.

Trace events are structured. Filter with `jq`:

```bash
jq 'select(.category == "auth")'   tmp/trace.jsonl   >> which tools were authorized and why
jq 'select(.category == "handle")' tmp/trace.jsonl   >> handle lifecycle
jq 'select(.event == "shelf.stale_read")' tmp/trace.jsonl   >> writes that didn't land
```

### Common debugging workflows

- **"Why was my tool call denied?"** Look for `auth.deny` → check `policy.build` for compilation issues → check `policy.compile_drop` to see if bucketed intent entries were dropped (missing proof) → check `handle.resolve_failed` for broken handle references.
- **"Why is shelf state empty after a write?"** A `shelf.write` with `success: true` followed by a `shelf.stale_read` event means the read returned different data than the write in the same execution context. The runtime catches this and emits the diagnostic with timestamps and expected-vs-actual values.
- **"Which handle resolved to which value?"** Follow `handle.issued` (where the handle was minted) → `handle.resolved` (where it was consumed by a tool dispatch) → or `handle.resolve_failed` (where it was lost). `handle.released` marks per-call bridge teardown and reports how many handles were in scope.

### Ambient `@mx.*` accessors

When you want to introspect runtime state from inside an mlld expression rather than reading a trace file:

| Accessor | Returns |
|---|---|
| `@mx.handles` | The handles currently issued in the active LLM bridge scope (handle string → value preview, labels, factsource, issuedAt) |
| `@mx.llm.sessionId` | The current bridge session id, or null outside an LLM call |
| `@mx.llm.read` | The active named read mode for this call |
| `@mx.llm.resume` | Resume state object (`{ sessionId, provider, continuationOf, attempt }`) or null |
| `@mx.shelf.writable` / `@mx.shelf.readable` | Slot alias metadata for the current box's shelf scope |
| `@mx.policy.active` | Active policy descriptors for the current execution context |
| `@mx.op.*`, `@mx.args.*`, `@mx.guard.*` | Operation, argument, and guard context (inside guard bodies) |

Use these for assertion-style probes, mid-execution inspection, and tests that verify the right runtime state is in scope.

Tracing complements audit logging: audit logs record *that* something happened for compliance; traces explain *why* something happened for debugging. Enable tracing during development and when investigating incidents; leave it off in production.

---

## §11. JS/Python Interop and Proof Preservation

The `js {}` and `py {}` boundaries are the weakest link in the proof chain. Values cross from mlld (where they carry labels, handles, and factsources) into JS/Python (where they're plain objects). If you serialize and parse inside a JS block, mlld metadata is erased and cannot be reconstructed.

### 11.1 Rules for JS/Python blocks

**Return native objects, not JSON strings.** mlld handles the conversion.

```mlld
>> RIGHT: return a native object
exe @parseContact(raw) = js {
  return { name: raw.name, email: raw.email }
}

>> WRONG: serializing erases metadata
exe @parseContact(raw) = js {
  return JSON.stringify({ name: raw.name, email: raw.email })
}
```

**Don't `JSON.stringify` / `JSON.parse` inside JS.** Label metadata and proof are lost. Work with values as-is.

**Handle wrappers pass through as plain objects.** A `{ handle: "h_xxx" }` enters JS as a normal one-key object. Don't special-case it. Don't try to resolve it inside JS. If you need handle-aware logic, do it in mlld, not JS — the runtime handles resolution automatically at dispatch.

**Don't reimplement tool metadata in JS.** If you're writing a JS helper that reads the bound input record's `facts:` / `data:` / `correlate:` (or any of the legacy `controlArgs`, `updateArgs`, `exactPayloadArgs` fields), stop. That's the runtime's job. Use `@policy.build` with bucketed intent — not a JS bridge that synthesizes intent from metadata lookups.

### 11.2 Accessing `.mx` metadata in JS

If you genuinely need label or factsource metadata inside a JS exe, use `.keep` (or `.keepStructured`) on the value before passing it as a parameter:

```mlld
var @result = @processEmail(@email.keep)
```

`.keep` preserves the structured wrapper into the JS block; the JS code can read `value.mx.labels`, `value.mx.factsources`, etc. Without `.keep`, the JS block sees a plain string or object and the metadata is gone.

Reserve this for inspection — `.keep` and `.keepStructured` are escape hatches for embedded-language code that genuinely needs to see the wrapper. Don't use them as a general "preserve metadata everywhere" tool. `bind` values and `state://` writes materialize plain data instead of storing live wrappers.

---

# Part III — Worked Examples

These examples compose primitives from Part I (Labels, Policies, Guards, Records, Facts and Handles, Shelves, Sessions) and patterns from Part II (Capability Agent Pattern, Composability). Each names the section number where the underlying primitive is described.

### A. Protect customer data from exfiltration

```mlld
>> Label sensitive variables (§1.4)
var secret @customers = <data/customers.csv>

>> Policy blocks secret → exfil flow (§2.4)
policy @p = {
  defaults: {
    rules: ["no-secret-exfil"],
    unlabeled: "untrusted"
  },
  operations: {
    exfil: ["net:w"]
  }
}

>> Exes labeled with what they do
exe net:w @postToSlack(msg) = run cmd { curl -X POST @url -d @msg }
exe @summarizeCustomers(data) = `customer count: @data.length`

>> This works — summary is computed locally
show @summarizeCustomers(@customers)

>> This fails — secret data cannot reach net:w
show @postToSlack(@summarizeCustomers(@customers))
>> Error: Rule 'no-secret-exfil': label 'secret' cannot flow to 'exfil'
```

The `secret` label on `@customers` propagates through `@summarizeCustomers` (label propagation, §1.5). When the result reaches `@postToSlack` (labeled `net:w`, mapped to `exfil`), `no-secret-exfil` fires.

### B. Treat all data as untrusted, protect destructive ops

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

exe fs:w @deleteFile(path) = run cmd { rm -rf "@path" }

var @target = "/tmp/whatever"   >> auto-applied untrusted (§1.8)
show @deleteFile(@target)
>> Error: Rule 'no-untrusted-destructive': untrusted control arg
```

`defaults.unlabeled: "untrusted"` (§2.3) means any unlabeled variable picks up `untrusted`. To explicitly trust something:

```mlld
var trusted @safePath = "/tmp/known-good"
show @deleteFile(@safePath)
```

### C. Lock down PII with custom flow rules

```mlld
policy @p = {
  defaults: { unlabeled: "untrusted" },
  labels: {
    pii: { deny: ["op:cmd", "net:w"] }   >> custom flow rule (§2.5)
  }
}

var pii @customerEmails = <data/emails.csv>

exe net:w @sendNewsletter(emails) = run cmd { newsletter-cli send @emails }
show @sendNewsletter(@customerEmails)
>> Error: pii data cannot flow to net:w
```

### D. Track LLM influence on untrusted data

```mlld
policy @p = {
  defaults: {
    rules: ["untrusted-llms-get-influenced"],   >> auto-applies influenced label
    unlabeled: "untrusted"
  },
  labels: {
    influenced: { deny: ["destructive", "exfil"] }
  }
}

var untrusted @userInput = <stdin>
var @summary = @claude("summarize: @userInput")  >> output gets 'influenced' (§1.3 decorator role)

show @sendEmail(@summary)
>> Error: influenced data cannot flow to exfil
```

The `untrusted-llms-get-influenced` rule is a labeling rule (§1.2 decorator role), not a blocking rule. It auto-applies `influenced` to LLM output when the input was untrusted. The `labels.influenced` flow rule is what does the blocking.

### E. Policy + privileged guard for strategic exceptions

```mlld
policy @p = {
  defaults: { rules: ["no-untrusted-destructive"] },
  operations: { destructive: ["fs:w"] }
}

>> Privileged guard punches a specific hole — no wildcard arm! (§3.7)
guard privileged @taskAllow before fs:w = when [
  @mx.op.name == "deleteFile" && @mx.args.path == "/tmp/known-safe" => allow
]

>> No wildcard — unmatched calls defer to base policy (blocked)
```

### F. Absolute constraint with `locked: true`

```mlld
policy @absolute = {
  defaults: { rules: ["no-secret-exfil"] },
  operations: { exfil: ["net:w"] },
  locked: true   >> §2.8
}

>> Even a privileged guard cannot override
guard privileged @attempt before net:w = when [
  * => allow
]

show @postToSlack(@customerList)
>> Error: Rule 'no-secret-exfil' (locked): label 'secret' cannot flow to 'exfil'
```

### G. Wrapping an MCP tool with security capabilities

```mlld
import tools { send_email as raw_send_email } from mcp "smtp-server"

>> Define the security contract via input record (§4.5)
record @send_email_inputs = {
  facts: [recipients: array],
  data: { trusted: [subject: string], untrusted: [body: string] },
  exact:     [subject],
  allowlist: { recipients: @internal_domains },
  blocklist: { recipients: @known_phish_domains },
  correlate: false
}

>> Wrap the raw MCP tool
exe tool:w @sendEmail(recipients, subject, body) = @raw_send_email(@recipients, @subject, @body)

>> Re-export through a tool collection with the input record bound
var tools @agentTools = {
  send_email: {
    mlld:   @sendEmail,
    inputs: @send_email_inputs,
    labels: ["execute:w", "exfil:send"]
  }
}

box @worker with { tools: @agentTools } [
  @claude("send a follow-up", { tools: @agentTools })
]
```

The agent inside the box can only call `send_email` (not the raw MCP tool). At dispatch, `@send_email_inputs` is enforced: recipients must be a fact arg matching the allowlist and not the blocklist; subject must appear verbatim in the planner's task text; body is expected to be untrusted (§5.2 control vs payload).

### H. Full provenance flow (planner → worker)

```mlld
>> Resolve worker reads contacts and writes them to a shelf slot
exe role:worker @resolveContacts(query) = [
  let @result = @searchContacts(@query)
  @shelf.write(@outreach.recipients, @result)
  => @result as record @contact[]
]

>> Planner reads the slot, picks a recipient by handle (per-call ephemeral, §5.5)
exe role:planner llm @plan(query) = @claude(`
  Find recipients for: @query
  Then choose one: @fyi.shelf.recipients
`, { tools: [@resolveContacts] }) with {
  read: "role:planner"   >> §4.3, §8.8
}

>> Execute worker performs the write under compiled per-step authorization (§8.7)
exe role:worker @executeSendEmail(intent) = [
  let @policy = @policy.build(@intent, @sendTools, { task: @query })
  @worker(@prompt) with { policy: @policy, tools: @sendTools }
]
```

The full chain: planner sees handles and addresses (no content). Picks one. Emits bucketed intent with the handle in `resolved`. `@policy.build` validates and compiles. Worker dispatches with proof intact; positive checks pass; `correlate-control-args` verifies single-source.

### I. URL exfiltration defense

```mlld
policy @p = {
  defaults: {
    rules: ["no-novel-urls", "untrusted-llms-get-influenced"],
    unlabeled: "untrusted"
  },
  urls: {
    allowConstruction: ["github.com"]   >> allowlist for constructed URLs
  }
}

>> If the LLM emits a URL not in input context, the call is blocked
>> unless the host is in the allowlist
```

`no-novel-urls` requires URLs in `influenced` tool-call args to appear verbatim in a prior tool result or user payload. URLs the LLM constructs from scratch are blocked. The most common exfiltration pattern (LLM is tricked into encoding stolen data into a URL the attacker controls) is structurally prevented.
