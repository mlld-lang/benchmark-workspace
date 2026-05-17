# mlld-friciton.md

This file tracks dogfooding friction that did not block the proof-agent work but would make mlld security agents easier to build, debug, or audit.

## Verified Resource Flow

- The safest shape for file/web/app recovery was: read returns only `verification_required`, planner calls `verify_user_attestation`, verifier re-reads internally, `@sigVerify.value` gates content exposure. This pattern works, but it requires hand-written wrappers in each suite. A standard helper or recipe would reduce mistakes.
- `mintUserValueHandle` correctly refuses downstream-of-untrusted scope, but the error led us through a false start before we settled on internal re-read plus `sigVerify.value`. Documentation should explicitly describe this as the right pattern for verifying untrusted resource reads.
- Text content can pick up transport-only trailing whitespace differences between host-side Python data and mlld-visible values. We added trailing-whitespace canonicalization before sign/verify. A recommended canonicalization recipe would make this choice consistent.

## Tool Argument Shape

- mlld recursive wrappers expose a single `request` string often enough that models put nested JSON inside strings. If that nested JSON contains `from_history`, the runtime must parse it before dispatch or MCP schema validation sees a raw object in a string field.
- The rig now has deterministic tests for stringified history refs in observe and execute arguments. This feels like a common enough agent failure mode to deserve a built-in parser/helper or clearer wrapper schema guidance.

## Cloud And Local Drift

- Cloud freshness checks compare the benchmark branch and remote mlld sha, but local mlld fixes can still be unpushed. The result is a confusing state where local canaries pass and cloud canaries keep failing with an already-fixed mlld bug.
- A run manifest that prints benchmark branch, mlld ref, mlld sha, dirty/local status if available, model, suite, task list, and result artifact path would shorten this diagnosis.

## Debugging

- The decisive evidence is always in transcripts: tool sequence, arguments, verification result, and policy denial reason. Scores alone can hide arbitrary failures, especially for SHOULD-FAIL tasks that must fail at the intended primitive boundary.
- It would help if `verify_user_attestation`-style flows had a standardized compact trace: selected resource id, storage id, verified boolean, failure reason, and whether content was ever appended to execution context.
