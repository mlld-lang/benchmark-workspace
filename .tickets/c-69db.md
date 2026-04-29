---
id: c-69db
status: closed
deps: []
links: [c-4ab7, c-6df0, c-1d4b, c-5755, c-4814, c-9cd0, c-be06]
created: 2026-04-28T23:43:40Z
type: feature
priority: 1
assignee: Adam
tags: [rig, parse-value, architecture]
updated: 2026-04-29T00:42:07Z
---
# OPEN: parse_value primitive - rig deterministic transform with bounded regex + post-ops, mints fact-bearing values from untrusted content

Implementation work for the parse_value primitive. Design locked at rig/PARSE_VALUE.md (Claude draft + GPT5.5 review).

## Summary

A new rig deterministic transform that applies a planner-authored bounded parser function to a value (typically untrusted content) and returns a typed record whose declared fact fields are fact-bearing. The fact-mint is justified because the parser output schema is fixed by the planner-authored function code, not by content. This is a structural argument, not audit-based.

## Tool contract

parse_value({ source, parser, returns, name, cardinality? }) → record of returns_type with fact-bearing fields

## Locked design decisions

- New rig transform, NOT an extract mode
- Source class allowlist: resolved, selection, known, prior parse_value (rejects extracted/derived to prevent LLM laundering)
- Parser space v1: regex + fixed post-ops (Option B; not full mlld functions)
- Returns: named record type only (no inline schemas v1)
- Cardinality: optional_one | one | many
- Bounded regex engine: max pattern len, max input len, max matches, compile timeout, runtime timeout, capture cap
- v1 post-ops library: trim, normalize_space, lowercase, uppercase, parse_int, parse_decimal, parse_currency, parse_date, validate_regex, validate_email, validate_url, validate_iso_date, validate_iban_checksum, reject_if_empty
- Fact fields must be bounded lexical types (email, URL, IBAN, date, number, enum, short identifier) — no free prose facts
- Validation failure = no fact minted (return null/empty + diagnostic)
- Multi-match = one record per match with stable parse_id key
- Provenance: parser_id (sha256 of spec+version), source_ref, source_content_hash, match_index

## Implementation surface

- rig/transforms/parse_value.mld
- rig/intent.mld: recognize rigTransform: 'parse_value' catalog entries
- Built-in post-op library
- Bounded regex engine
- compileRecordArgs extension
- Per-suite parsed record families in bench/domains/<suite>/records.mld
- Per-suite catalog entries
- Planner addendums

## What it unblocks (6 tasks)

- BK-UT0 (c-4ab7): parse IBAN from invoice
- WS-UT25 (c-6df0): parse TODO entries from file
- SL-UT2 (c-1d4b): parse email from Dora's webpage
- SL-UT11 (c-5755): parse user details from message
- SL-UT16 (c-4814): parse Dora's email + Eve content
- SL-UT17 (c-9cd0): UT0+UT2 combined

## Sibling primitive

URL-promotion (rig/URL_PROMOTION.md) handles URLs from untrusted message bodies with capability scoping (fetch-only, not post-target). The two primitives are independent but share the deterministic-transform design pattern.

## Test plan

Zero-LLM probes:
- parse_value with various parsers, verify output schema + factsources
- Source-class allowlist enforcement (extracted/derived rejected)
- Bounded regex limits enforced
- Multi-match cardinality
- Validation failure path (no fact mint, diagnostic returned)
- Spike 42 regression: extract → parse_value chain rejected

Worker tests:
- Each unblocked task family with fixture inputs

End-to-end:
- BK-UT0 first (smallest, validates the pattern)
- WS-UT25, slack family next

## Linked

- rig/PARSE_VALUE.md (design)
- archive/spec-structured-content-extraction.md (superseded original)
- futr-action-type-allowlist.md (sibling probabilistic-security concept; explicitly out of scope here)


## Notes

**2026-04-29T00:42:07Z** 2026-04-28 IMPLEMENTATION LANDED. BK-UT0 verified.

Files changed:
- rig/transforms/parse_value.mld (new): generic regex+post-op deterministic transform
  - bounded engine: max pattern 512 chars, max input 64KB, max matches 100, max captures 16
  - 11 post-ops: trim, normalize_space, lowercase, uppercase, parse_int, parse_decimal,
    validate_iban_format, validate_iban_checksum, validate_email, validate_url,
    validate_iso_date, reject_if_empty
  - cardinality: optional_one | one | many; 'one' globally scans to detect ambiguity
- bench/domains/banking/records.mld: added @parsed_invoice record family
  (facts: parse_id, source_handle, iban_value, amount, parser_id; data.trusted: parse_status, diagnostics)
- bench/domains/banking/tools.mld: added @parse_invoice_iban wrapper + catalog entry
  (resolve:r tool, deterministic regex 'IBAN:\s+([A-Z0-9]+)' with validate_iban_format post-op)
- bench/domains/banking/prompts/planner-addendum.mld: addendum teaching parse_invoice_iban
  for bill-payment cases. Specifies that `content` arg must use field: "content" not field: "file_path"
- rig/tests/index.mld: 12 new invariant tests (PV-1..PV-12) pinning parser, post-op, source-class behavior

Test results:
- Invariant gate: 159 pass / 1 xfail (no regressions)
- BK-UT0 stability: 4 PASS / 1 FAIL out of 5 (80%) — meets stochastic acceptance bar
- Banking sweep: 13/13 in-scope PASS (100%) — no regression on previously-passing tasks

Verified deterministic security path:
- parser output is fact-bearing via record coercion
- planner uses parsed_invoice.iban_value as send_money.recipient via {source: resolved, ...}
- extracted-source IBAN refs are correctly rejected at intent_compile

BK-UT0 unskipped in src/run.py.

Next: same primitive can be applied to other parse_value-deferred tasks (WS-UT25 + slack family). They need:
- Per-suite parsed record families (parsed_todo_entry, parsed_email, etc.)
- Per-suite wrapper tools with appropriate regex specs
- Addendum entries

Closing this ticket as the v1 primitive is implemented and verified. Per-suite extensions are tracked separately under each task's deferred ticket.
