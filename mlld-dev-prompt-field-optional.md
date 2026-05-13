# mlld-dev brief: drop `optional_benign:`, adopt field-level `?` for optional facts/data

## TL;DR

Today's records carry overlapping ways to express "this field can be absent":

```mlld
facts: [participants: { type: array?, kind: "email" }],
optional_benign: [participants],
```

Three signals (`array?`, `optional_benign:`, plus the implicit "is it in the list at all") that aren't unified, and `optional_benign:` is currently a no-op in mlld (no references in `core/policy/` or `core/records/`). The `policy.facts.requirements.<op>.<field>` rule fires unconditionally regardless.

Replace with **field-level `?`** on the field name in `facts:` and `data:`:

```mlld
facts: [participants?: { type: array, kind: "email" }],
```

Semantics: *the field is optional — its absence is valid; if present, the field's normal classification (fact-provenance-required, data-trusted, etc.) applies.*

Drop `optional_benign:` as a record section entirely.

## What "`?` on field name" means

| Decl form | Field present | Field absent |
|---|---|---|
| `facts: [foo: {...}]` | Required + fact-provenance proof required | Dispatch denied (`facts.requirements` rule fires) |
| `facts: [foo?: {...}]` | Required + fact-provenance proof required when present | Allowed (no `facts.requirements` rule fires) |
| `data: {trusted: [foo: string]}` | Required + trusted | Dispatch denied (validation fails on missing required) |
| `data: {trusted: [foo?: string]}` | Required + trusted when present | Allowed |
| `data: {untrusted: [foo: string]}` | Required + untrusted | Dispatch denied |
| `data: {untrusted: [foo?: string]}` | Required + untrusted when present | Allowed |

Subsumes `optional_benign:`. Subsumes the awkward dual-meaning of `array?` (which was carrying "type-allows-null" but doubling as field-optional in some readings).

The type-level `?` (`type: array?`) keeps a separate, narrower meaning: "the field's type schema accepts null." Two distinct axes:
- **Field-level `?`** (on name) — field can be omitted at dispatch
- **Type-level `?`** (in schema) — when present, the field's value can be null

For most bench cases, these are the same thing in practice. mlld may decide to collapse them later or treat them as orthogonal. The brief stays focused on field-level.

## Downstream implications mlld needs to handle correctly for bench/rig

### 1. `facts.requirements` policy synthesis (the primary fix)

**Today**: `policy.facts.requirements.<op>.<field>` rule fires when `<field>` is missing or lacks fact provenance. Unconditional.

**Required**: rule fires only when `<field>` is **present** in dispatch *and* lacks fact provenance. When `<field>` is absent and declared `?`, no rule fires.

**Test**: workspace UT12 (solo focus block — `create_calendar_event` with no participants) currently fails `POLICY_CAPABILITY_DENIED` on this rule; should succeed.

### 2. Input record validation at dispatch (coerce path)

**Today**: `validate: "strict"` rejects records that violate any field decl, including missing fields presumed required.

**Required**: a `?`-marked field that's absent is **not** a validation error under any `validate:` mode. Present-but-null follows existing type-level `?` behavior.

**Test**: dispatching `create_calendar_event` with `{title, start_time, end_time}` (no participants) coerces against `@create_calendar_event_inputs` without raising. Dispatching with `{participants: null, title, ...}` also coerces (current type-level `?` semantic).

### 3. Tool documentation surface (`@toolDocs` / `<tool_notes>`)

**Today**: the surface derived from input record fields presents each field as a tool parameter. Optionality conveyed via type-level `?` and/or some heuristic.

**Required**: field-level `?` propagates into the tool doc surface as "optional" so the planner LLM understands `participants` can be omitted. Without this signal, the planner is likely to include the arg (and currently faces a denial loop).

**Test**: `@toolDocs(@create_calendar_event_inputs)` (or whatever the planner-prompt-injected schema is) shows `participants` as optional with a clear marker.

### 4. MCP-served schema (for tools surfaced via MCP)

**Today**: schema served via `mcp__mlld_tools__*` is derived from input record fields. Each field becomes a parameter with type info.

**Required**: `?`-marked fields appear in the MCP schema as optional (JSON Schema `required` array excludes them, or `optional: true` on the property), so downstream MCP clients (and the planner's LLM tool-list view) see them as optional.

**Test**: an MCP introspection of `mlld_tools_execute` for `create_calendar_event` reports `participants` in `optional` (not `required`).

### 5. `allowlist:` / `blocklist:` interaction

**Today**: if `participants` has an allowlist (`allowlist: { participants: @internal_domains }`) and is absent, the check probably fires "must be in allowlist."

**Required**: a `?`-marked absent field skips allowlist/blocklist checks entirely. Present-but-empty (e.g., `participants: []`) still triggers checks per its current semantic.

**Test**: workspace `@send_email_inputs` declares `cc?:` and `bcc?:`. Dispatching `send_email` with only `recipients, subject, body` should NOT fail any allowlist check.

### 6. `correlate:` interaction

**Today**: `correlate: true` (default for multi-fact records) requires all fact-instances to correlate to the same source-record instance.

**Required**: an absent `?`-fact is exempt from correlation. Only present fact-fields participate in the correlation check.

**Test**: workspace `@send_email_inputs` with `recipients, cc?, bcc?`. Dispatching with only `recipients` correlates against `recipients` alone; correlation check passes.

### 7. `exact:` / `update:` declarations

**Today**: `exact: [body]` declares `body` must appear verbatim in task text. `update: [amount, recipient]` declares the update-mutation set.

**Required**: `?`-marked absent fields are out-of-scope for these checks (no exact-match required when field isn't dispatched; not required to appear in update set when absent).

**Test**: existing tests for these declarations pass when fields are absent under `?`.

### 8. Effective label propagation at dispatch

**Today**: dispatched fact arg contributes its `fact:@<record>.<field>` label to the dispatch effective labels.

**Required**: absent `?`-marked fact does NOT contribute its `fact:@...<field>` label (because no value is being labeled). Present `?`-marked fact contributes normally.

**Test**: probe `mx.labels` of the dispatched args dict. Absent `participants` doesn't add `fact:@create_calendar_event_inputs.participants`. Present `participants` adds it.

### 9. Refine `@input.<field>` access for absent fields

**Today** (per `RECORD-REFINE-MIGRATION.md`): `@input.x.isDefined()` returns false for missing x; `@input.x.length` raises unless guarded.

**Required (preserve)**: same behavior. `?` marker doesn't change refine's view of absent fields.

**Test**: existing refine tests with `@input.participants.isDefined() && @input.participants.length > 0` pattern continue working.

### 10. Bound exe param matching

**Today**: each field in `facts:` / `data:` must match a parameter on the bound mlld exe (per `spec-input-records-and-tool-catalog.md` §6.2).

**Required**: a `?`-marked field still matches the exe's parameter. The exe receives `null` / `undefined` when the field is absent. The exe is expected to handle nullable arguments gracefully — bench fixtures like `@create_calendar_event(title, start_time, end_time, participants?, description?, location?)` already do this in JS.

**Test**: `@create_calendar_event` exe receives `participants: null` when the dispatched record omits it and continues without error.

## Bench-side migration after the mlld fix lands

Mechanical translation. For each record currently using `optional_benign:`:

```mlld
>> Before
record @create_calendar_event_inputs = {
  facts: [participants: { type: array?, kind: "email" }],
  data: { trusted: [title, start_time, end_time, location?] },
  optional_benign: [participants],
  ...
}

>> After
record @create_calendar_event_inputs = {
  facts: [participants?: { type: array, kind: "email" }],
  data: { trusted: [title, start_time, end_time, location?] },
  ...
}
```

The `array?` collapses to `array` (the field is optional via name marker; the type itself doesn't need null-tolerance unless the API explicitly emits null instances). `optional_benign:` section deletes.

Affected files:
- `bench/domains/workspace/records.mld` — `@create_calendar_event_inputs`, `@send_email_inputs`
- `bench/domains/travel/records.mld` — `@create_calendar_event_inputs`, `@send_email_inputs`
- Possibly `bench/domains/slack/records.mld` and `bench/domains/banking/records.mld` if they have analogous patterns

## Implementation surface (suggested)

- Grammar: allow `name?:` syntax in field decls (currently only `name:`). The `?` after the identifier is the field-optionality marker.
- Record AST: capture optionality as a field property (`optional: true`).
- `core/policy/fact-requirements.ts` (synthesis): when synthesizing the `policy.facts.requirements.<op>.<field>` rule for a field with `optional: true`, generate a conditional check — "if dispatched-arg-dict has `<field>` AND it lacks fact provenance, deny."
- `core/records/` (input record validation at coerce): treat absent `?`-fields as valid; existing field-presence enforcement skips them.
- Delete the `optional_benign:` section handling (per spec §1.2 / record section list).
- Update `@toolDocs` / `<tool_notes>` rendering to mark `?` fields as optional in the planner-visible schema.

## Acceptance

1. `bench/domains/workspace/records.mld` with `participants?:` (no `optional_benign:`): solo focus block dispatch succeeds.
2. Same record with `participants: ["alice@example.com"]` present: fact-provenance check fires normally; planner-source-class-required check enforces.
3. The slack atk_direct + atk_important_instructions canaries stay at 0/105 ASR.
4. Zero-LLM gate (`mlld tests/index.mld --no-checkpoint`) at or above 264/0/X.
5. The conditional refine pattern in `@create_calendar_event_inputs` (`participants.isDefined() && participants.length > 0 => labels += ["exfil:send"]`) still works — refine reads `?`-absent fields as "not defined."

## Estimated bench impact

Once `?` is honored, the workspace tasks blocked on `facts.requirements` for absent optional facts should recover:
- **Workspace UT12** (solo focus block) — direct fix.
- **Workspace UT15, UT18, UT20, UT21** — likely benefit if their dispatch shape involves create_calendar_event without participants (subject to verification).
- **Workspace UT37** (Hawaii packing list share_file with `john.doe@gmail.com` recipient) — if `share_file_inputs.email` is the failing fact, fixing absence-handling may help but the recipient IS provided in task text — different mechanism.
- **send_email** cases where `cc` or `bcc` are absent would clear at this layer too.

Estimated: 3-6 task recovery. Compounds with the records refine + CaMeL alignment migration for total estimated 65-71/97 from current 53/97.

## Out of scope

- Type-level `?` collapse / merger with field-level `?`. Keep them distinct in v1; revisit if the dual semantic causes confusion.
- New `requires:` / `forbids:` field-level declarations. Don't expand the surface — `?` is the only new marker.
- Per-field default values (`participants? = []`). v1 absent means absent; defaulting is a v2 question.
