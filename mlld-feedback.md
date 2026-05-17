# mlld feedback from fp-proof

This file records mlld friction and ergonomic/security opportunities discovered while building the AgentDojo proof agent. These are not blockers for the current repo, but they would make future defended-agent work faster and less error-prone.

## 1. Durable cross-call references should be first-class

The proof agent currently uses `from_history` refs plus a bridge that converts allowed fact-bearing history values into scoped known claims. It works, but it is compensating for the fact that LLM handles are per-call.

Desired direction:

- shelf/address-backed values as the default cross-call reference surface;
- simple syntax for "planner may refer to this fact field later";
- `@policy.build` accepting those addresses directly and producing worker-fresh handles.

This would remove most of the custom `bridgeResolvedAuthorization` logic.

## 2. Strict planner-worker dispatch should be easier to scaffold

The safe shape is:

- outer execute helper is `role:worker`;
- inner compile helper is `role:planner`;
- policies set `records_require_tool_approval_per_role: true`;
- records declare both authorize and submit grants.

This is easy to get subtly wrong. A template/helper around the canonical pattern would help. Error messages should explicitly say whether failure occurred in planner authorize or worker submit.

## 3. URL capability refs deserve a primitive

Slack needed opaque URL refs:

- raw URL found in message body should not be planner-visible authority;
- direct fetch should require task-known URL;
- ref fetch should use a private capability created by the runtime/tool wrapper;
- destination URL writes need separate provenance.

The proof version uses local helper code and temp-file storage. The clean version had a more principled URL capability shelf. mlld could make this a reusable pattern: `url_ref` record + hidden capability store + fetch-by-ref helper + no-novel-url guard.

## 4. `known` ergonomics need sharp affordances

`known` is semantically narrow: exact user-task text from an uninfluenced source. It would help to have helper APIs that:

- validate a proposed value against task text before building the full policy;
- explain which element of an array failed;
- produce standardized denial reasons;
- make it hard to confuse worker-discovered values with task-known values.

The current `known_not_in_task` signal is useful, but agents often need a small diagnostic wrapper around it.

## 5. Fact-source refs are powerful but stringly

Bridge configuration currently names allowed fact sources as strings like `"\@contact.email"` or `"\@file_entry.id_"`. This is compact but fragile.

Better options:

- typed references to record fields;
- validation that every configured fact-source ref names an existing record and fact field;
- a helper that derives allowed source refs from tool input records and output records where possible.

## 6. Running an individual suite test file is misleading

In this repo, `mlld tests/slack-proof.mld --no-checkpoint` validates/imports but does not run assertions because the actual runner is `tests/index.mld`. It exits successfully with no output.

Potential improvement:

- a native test convention where a suite file can both export a suite and run itself when invoked directly;
- or a validator warning when an invoked file defines suites but has no top-level execution.

## 7. Denial handling scope remains easy to misuse

The same-scope `when [ denied => ... ]` rule is important, but easy to forget. The test template documents it, but mlld could improve ergonomics with:

- clearer error messages when a denial escapes an unexpected scope;
- a helper for "run this operation and return structured denial";
- docs showing guard/policy denial test patterns next to guard syntax.

## 8. JS/Python interop needs proof-preservation linting

JS helpers are useful for deterministic parsing, ranking, and aggregation. They are also the easiest place to accidentally erase metadata.

Helpful improvements:

- lint warnings when `.mx` metadata is inspected without `.keep`;
- examples showing safe native-object returns versus JSON-string round trips;
- a "metadata lost here" trace event when values cross a host boundary.

## 9. Policy/build diagnostics are good but could be more action-oriented

For agent development, the most useful report is:

- tool;
- arg;
- expected proof;
- actual labels/factsources/trust;
- whether the value came from `known`, `resolved`, or direct args;
- exact repair suggestion.

The proof rig has to surface these in transcripts. mlld could standardize a compact human-readable denial envelope.

## 10. Advice/influence should have a reusable recipe

`@noInfluencedAdvice` exists, but agent builders need a canonical pattern:

- role-specific advice projection;
- no-tool advice worker;
- denied fallback that strips influenced derived/extracted entries;
- deterministic tests showing review prose is omitted and unsafe advice canary breaches.

This should be a documented recipe rather than something each rig rediscovers.

## 11. Output URL validation should be packaged

The proof rig has a generic outbound payload URL guard. This works, but feels like a reusable security fragment:

- scan common payload fields and arrays;
- block novel outbound URLs for exfil sends;
- distinguish task-known destination URL from payload-contained URL;
- provide a standard denial code.

`@urlDefense` covers part of this at dataflow level; agent writers still need a simple write-payload guard recipe.

## 12. Sign/verify verified-resource flow needs a canonical agent pattern

The sign/verify primitive is powerful enough to recover file, webpage, and TODO/app authority without semantic prompt defenses, but manual agent loops need a lot of glue:

- explicitly register task-start resources;
- expose read tools that return only verification-required selectors/refs before verification;
- expose a planner-callable `verify_user_attestation` wrapper that re-reads internally and calls `@sigVerify.value`;
- scope signature ids per task/run to avoid parallel canary collisions;
- canonicalize harmless transport differences such as trailing whitespace before signing and verifying text resources;
- preserve safe history refs through redacted history, including stringified JSON wrapper args;
- append only verified content to the execute task context;
- keep `@sigVerify.value` out of the agent tool catalog.

This deserves a first-class recipe or helper module. The recipe should also make transcript auditing easy: a recovered task should show `read -> verify_user_attestation -> execute`, and a failed verification should produce a compact denial reason such as `content_hash_mismatch` rather than a generic policy failure.

## 13. Cloud benchmark ergonomics could be smoother

The proof repo has scripts around `gh workflow run`, image freshness, artifact fetching, and opencode transcript inspection. This is mostly host-side, but a small mlld/bench harness standard would help:

- emit run manifest with model, suite, attack, branch, image tag, and artifact paths;
- standardize transcript/session ids in JSONL result rows;
- provide one command to fetch and inspect latest failed sessions.

The important lesson: benchmark scores are not enough. Transcript access is part of the security workflow.
