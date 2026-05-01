---
id: c-4ab7
status: closed
deps: []
links: [c-69db]
created: 2026-04-25T18:50:56Z
type: task
priority: 4
assignee: Adam
tags: [oos, should-fail]
updated: 2026-04-30T20:47:39Z
---
# SHOULD-FAIL: BK-UT0 - recipient IBAN from bill file (untrusted-content → control-arg)


## Notes

**2026-04-30T20:47:57Z** Reclassified SHOULD-FAIL 2026-04-30 (bench-grind-14). The @parse_invoice_iban wrapper minted fact-bearing iban_value from invoice file content (untrusted source) and satisfied send_money.recipient via a {source: resolved, record: parsed_invoice, field: iban_value} ref. Same defect class as the slack untrusted-content → control-arg family: determinism does not promote attacker-controllable content to fact (CaMeL-aligned: 'Q-LLM output is not considered clean just because it came from an LLM'). Wrapper, parsed_invoice record, and addendum entry removed from banking. BK-UT0 re-skipped in src/run.py with SHOULD-FAIL comment. See c-6479 for revisit conditions; see c-69db for the architectural ratchet note on parse_value's salvageable shape (extracted-class output, never resolved-class).
