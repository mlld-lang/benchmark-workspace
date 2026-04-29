# parse_value — Deterministic Parser Primitive

**Status**: design locked (Claude draft + GPT5.5 review). Ready for implementation.
**Replaces**: `archive/spec-structured-content-extraction.md` (overfit on per-format wrapper tools).
**Implementation ticket**: see linked ticket for the build work.
**Sibling primitive**: URL-promotion (parse_value + capability scoping for fetch-only URLs).

## What it is

A new rig deterministic transform that applies a planner-authored bounded parser function to a value (typically untrusted content) and returns a typed record whose declared fact fields are fact-bearing.

`parse_value` is **not** an extract mode. Extract remains LLM-based and produces payload-only `extracted` outputs. parse_value is pure deterministic parsing and may mint fact-bearing record fields because its output schema is fixed by the parser code, not by the content.

## Tool contract

```
parse_value({
  source,        // required: where to read the value from
  parser,        // required: parser specification
  returns,       // required: named record type
  name,          // required: planner-state storage/display name
  cardinality?   // optional: "optional_one" | "one" | "many"
})
```

### `source`

Source class allowlist:
- `resolved` — fact-bearing values, including prior parse_value output
- `selection` — derive-validated selection refs
- `known` — task-text literals
- prior parse_value result (chained deterministic transforms)

Rejected:
- `extracted` — would create `extract → parse_value → resolved` LLM laundering path
- `derived` — same laundering risk

This source allowlist is the load-bearing security invariant. Without it, the LLM-bounded primitives (extract, derive) would have an escape hatch to mint fact-bearing values via parse_value.

### `parser`

v1 parser space: regex + fixed post-ops. No arbitrary mlld functions yet.

```json
{
  "kind": "regex",
  "pattern": "IBAN:\\s*([A-Z0-9]+)",
  "flags": ["multiline"],
  "captures": { "iban_value": 1 },
  "post": {
    "iban_value": [
      { "op": "trim" },
      { "op": "validate", "rule": "iban_checksum" }
    ]
  }
}
```

### `returns`

**Named record type only** for v1. No inline fact schemas. The record is declared in `bench/domains/<suite>/records.mld` (or rig if a parser shape is shared across suites). Fact fields must be bounded lexical types — see "Fact-field constraints" below.

### `cardinality`

- `optional_one` — zero or one match; missing match returns null/empty record + diagnostic
- `one` — exactly one match required; ambiguity blocks
- `many` — array of records, one per match, each with stable `parse_id` key

## Bounded regex engine

Planner-authored regex introduces ReDoS surface. Hard limits in v1:

- max pattern length (e.g., 512 chars)
- max input length (e.g., 64 KB)
- max matches returned (`many` mode caps to e.g. 100)
- compile-time timeout (e.g., 50ms)
- runtime timeout per match (e.g., 100ms)
- capture count cap (e.g., 16)

Either use a regex engine with built-in limits (e.g. RE2-style) or wrap stdlib regex with the above guards.

## v1 built-in post-ops

A fixed library of named post-operations applied per-capture after regex match:

| Op | Effect |
|---|---|
| `trim` | strip leading/trailing whitespace |
| `normalize_space` | collapse internal whitespace runs to single space |
| `lowercase` / `uppercase` | case normalization |
| `parse_int` | string → integer; fail = no fact mint |
| `parse_decimal` | string → decimal number |
| `parse_currency` | parse "$1,234.56" / "€1.234,56" → number + currency code |
| `parse_date` | parse ISO 8601 + named common formats → ISO date |
| `validate_regex` | pattern check; fail = no fact mint |
| `validate_email` | RFC-shaped email validation; fail = no fact mint |
| `validate_url` | scheme + host validation; fail = no fact mint |
| `validate_iso_date` | strict ISO 8601 |
| `validate_iban_checksum` | mod-97 IBAN checksum |
| `reject_if_empty` | empty string = no fact mint |

No arbitrary mlld/JS functions in v1. Adding a new op requires per-op design + test.

## Fact-field constraints

Parsed fact fields **must be bounded lexical values** with type/format validation. Free prose belongs in `data`, not `facts`.

Allowed fact field kinds:
- email
- URL
- IBAN
- date (ISO)
- number (int/decimal)
- enum (one of declared values)
- short identifier (e.g., regex `^[A-Za-z0-9_-]{1,64}$`)

Disallowed as facts:
- arbitrary free text
- multi-line content
- structured objects (those are data fields)

This prevents broad attacker-supplied prose from becoming "trusted" via a careless parse.

## Output and provenance

parse_value output is stored as proof-bearing records in `state.resolved[<returns_type>]`. Each record carries explicit provenance:

```json
{
  "provenance": "parsed",
  "parser_id": "sha256(<parser spec + version>)",
  "source_ref": { "record": "...", "handle": "...", "field": "..." },
  "source_content_hash": "sha256(<the value parsed>)",
  "match_index": 0
}
```

Factsources on each fact field include:
- parser id and version
- source record handle and field
- match index (for `many` mode)
- source content hash (for replay/audit)

The planner uses normal resolved refs:

```json
{ "source": "resolved", "record": "parsed_iban", "handle": "h_x", "field": "iban_value" }
```

## What "resolved" now means

This intentionally broadens "resolved" from "authoritative lookup" to "proof-bearing value." The proof claim parse_value mints is:

> "deterministically extracted from this source by this parser"

It does NOT claim:

> "the source value is legitimate"

Same boundary as any deterministic-extraction primitive. If the source content is attacker-controlled (compromised page, fake invoice), parse_value faithfully extracts whatever attacker structural content matches the parser. That's content-author trust, not parser failure.

## Important guardrails (per GPT5.5 review)

1. **Validation failure → no fact minted.** Return null/empty record + diagnostic data. The planner sees the failure and decides what to do (re-parse, block, etc.).
2. **Unknown parser output fields rejected.** Parser outputs must declare their captures up front; extra fields are not silently added to the record.
3. **Multi-match → one record instance per match.** Each gets a stable `parse_id` derived from `(parser_id, source_ref, match_index)`.
4. **Records feeding multi-control-arg writes need a key.** `parsed_iban.iban_value` reaching `send_money.recipient` while `parsed_iban.amount` reaches `send_money.amount` should be enforceable as same-instance via existing `correlate-control-args`. The record's `parse_id` (or another key) makes this work.

## Architecture-fit notes

This narrowly updates `rig/ARCHITECTURE.md`:

- The current rule "extract/derive scalars cannot reach control args except via selection refs" remains true. parse_value is neither extract nor derive; it is a third class of resolve-phase transform with its own provenance.
- The current "tainted instruction following is out of scope" language in `bench/ARCHITECTURE.md` narrows: deterministic structural rows (e.g., TODO entries with `name:`, `task:`, `deadline:` fields) can become facts via parse_value. Operation choice still must come from the clean user task or an explicit profile, not from arbitrary prose inside the file.

## Use cases (deterministic-deferred unlocks)

| Suite/task | Application |
|---|---|
| BK-UT0 | Parse IBAN from `bill-december-2023.txt` (regex + iban_checksum validation) |
| WS-UT25 | Parse TODO entries from meeting-minutes file (regex with named captures: name, task, deadline_date) |
| SL-UT2 | Parse email from Dora's webpage (validate_email post-op) |
| SL-UT11 | Parse user details from Bob→Alice message body |
| SL-UT16 | Parse Dora's email + interpret Eve's blog content for feedback |
| SL-UT17 | Combined: read URL + parse email (UT2 family) |

URL-promotion is the sibling primitive for tasks where URLs come from untrusted message bodies and need fetch-only capability scoping (SL-UT4, UT6, UT15, UT20).

## Threat model

Threats addressed by parse_value:

| Threat | How it's blocked |
|---|---|
| Prose injection in untrusted content | Parser only matches structural fields; injected prose like "ignore instructions" returns no match |
| Attacker-injected schema fields | Output captures are fixed by parser spec; extra fields rejected |
| LLM laundering via extract→parse_value | Source allowlist rejects `extracted`/`derived` sources |
| ReDoS via planner regex | Bounded regex engine with hard limits |
| Free-text fact pollution | Fact fields must be bounded lexical types |

Threats NOT addressed (and not expected to be):

- **Data substitution**: attacker controls the source structure such that the parser matches the attacker's value (e.g., replaces IBAN in invoice). Defense requires separate trust root (known-payee, signed source).
- **Parser misauthoring**: planner writes a buggy regex that matches the wrong field. Output is deterministic but wrong. Mitigation: schema validation post-ops (e.g., iban_checksum) before fact-mint.

## Implementation surface

### Rig

- `rig/transforms/parse_value.mld` — deterministic dispatcher
- `rig/intent.mld` — recognize `rigTransform: "parse_value"` catalog entries
- Built-in post-op library (fixed catalog)
- Bounded regex engine wrapping (limits enforced)
- Output coercion through existing `=> record` path with parsed-provenance factsources
- `compileRecordArgs` extension for parse_value's arg shape

### Bench, per suite

- Per-suite parsed record declarations in `bench/domains/<suite>/records.mld`
- Catalog entries with `rigTransform: "parse_value"` and `recordArgs` shape
- Planner addendum: "when target values for control args appear in untrusted content, use parse_value with an appropriate parser. Parser must be deterministic (regex + post-ops only)."

### Worker tests

- Zero-LLM: parse_value with various parsers, verify output schema, factsources, source-class
- Negative: extracted/derived sources rejected
- Negative: malformed regex (length, complexity) rejected
- Worker tests: extract assignees from TODO file, extract email from webpage, extract IBAN from bill — verify each chains correctly into downstream control-arg use

## Acceptance criteria

- All 6 currently-deferred parse_value-family tasks pass utility in defended mode (BK-UT0, WS-UT25, SL-UT2, UT11, UT16, UT17)
- 0% ASR on existing injection tasks for those tasks
- No regression on currently-passing tasks
- Source-class firewall remains intact (`extracted` scalars still cannot reach control args; only parse_value-output facts on declared bounded types do)
- Worker tests pin the parse_value chain shape for each task family
- Spike 42 invariant preserved (`extract` → `parse_value` source rejection)
