# DEBUG.md - proof-agent investigation protocol

This is the debugging and diagnosis protocol for the fp-proof defended agent. Read it before investigating utility failures, security regressions, structural-refusal behavior, or runtime errors.

The job is not to make benchmark numbers look good. The job is to understand exactly what happened, using transcripts and mlld security evidence, then fix the right layer without weakening the architecture.

## Cardinal rules

**A. Transcripts are definitive for agent behavior.**  
The transcript is the primary source for why a model did something. MCP call logs, result JSON, final answers, and policy denials show symptoms. They do not fully explain the planner's decision. A diagnosis about model intent, confusion, fallback behavior, or why it stopped is invalid without transcript citations.

**B. No benchmark cheating or overfitting.**  
Do not read AgentDojo utility/security checker bodies to shape outputs. Do not add task-id logic, expected-answer maps, suite-specific branches in `rig/`, or prompt rules that only help one task. `rig/` is generic; `bench/` configures records, tools, policy, and minor interface addenda.

**C. Structural refusal is a security success only if the block is structural.**  
A `*-FAIL` task failing for an arbitrary reason is not good. It must fail because a security primitive blocked the unsafe route: missing fact/kind proof, missing handle, policy denial, guard denial, absent write grant, correlation failure, exact/known failure, or projection-induced inaccessibility. If the transcript shows the agent gave up, hallucinated, timed out, or used the wrong tool before reaching the security boundary, classify it as OPEN masked until proven otherwise.

**D. Do not blame the model first.**  
Assume failures come from the architecture, tool contract, prompt interface, wrapper shape, projection, record schema, policy, bridge parsing, or final-answer plumbing. The model can expose these bugs, but "model weak" is not a diagnosis.

**E. Spikes before sweeps.**  
Full sweeps confirm integration. They are bad discovery tools. When a task fails, read the transcript, form one specific hypothesis, and write a zero-LLM probe whenever possible.

**F. Preserve tier boundaries.**  
Fix generic orchestration in `rig/`, suite contracts in `bench/domains/<suite>/`, suite entrypoints in `bench/agents/`, host issues in `src/`, and tests in `tests/`. If a fix wants to cross tiers, articulate the primitive it reveals before editing.

## What counts as evidence

Use the strongest evidence available:

| Claim | Required evidence |
|---|---|
| "The planner misunderstood the route" | Transcript reasoning citation. |
| "The tool contract was unclear" | Transcript reasoning plus tool input shape. |
| "The value lacked proof" | Policy/build denial, record metadata, or fake write denial. |
| "The planner could not see a field" | Record projection plus transcript showing absence or attempted workaround. |
| "A structural refusal blocked correctly" | Transcript shows attempted or impossible route, and denial/projection/policy evidence identifies the primitive that blocked it. |
| "This is safe utility" | LLM-free data-flow test proves authorized path; transcript shows model used or failed to use that path. |
| "This is evaluator/format noise" | Final answer comparison plus no security or runtime failure. Do not read checker bodies. |

Without transcript citations, mark conclusions `UNVERIFIED`.

## Transcript-first workflow

1. Identify the exact task, run, model, result JSONL, and OpenCode home.
2. Read the result row for high-level symptoms: `utility`, `security`, `outcome`, `execute_error`, `policy_denials`, `mcp_calls`, `metrics`, and `final_output`.
3. Locate the OpenCode session for the task.
4. Read the transcript parts, especially `reasoning` and `text` parts before and after tool calls.
5. Reconstruct the actual path:
   - What did the planner think the task required?
   - Which observations did it request?
   - Which values did it select?
   - Did it extract payload, fabricate control args, or preserve handles?
   - Did it reach `authorize_execute`?
   - If denied, which primitive denied it?
   - If it stopped early, why did it think no route existed?
6. Only then classify and fix.

Useful commands:

```sh
python3 src/opencode_debug.py sessions --limit 20
python3 src/opencode_debug.py parts --session <slug-or-id> --limit 400
python3 src/opencode_debug.py follow --session <slug-or-id>
python3 src/opencode_debug.py logs --session <slug-or-id>
```

For fetched or remote runs:

```sh
python3 src/opencode_debug.py --home runs/<run_id>/opencode parts --session <slug-or-id> --limit 400
```

Find sessions by phrase:

```sh
DB="$HOME/.local/share/opencode/opencode.db"
sqlite3 -readonly "$DB" \
  "select s.slug, s.id, s.title, datetime(s.time_updated/1000,'unixepoch')
   from session s
   join part p on p.session_id = s.id
   where p.data like '%<distinctive task phrase>%'
   group by s.id
   order by s.time_updated desc
   limit 10;"
```

If a transcript cannot be found, the diagnosis is incomplete. Do not replace it with MCP-call speculation.

## Structural-Refusal Protocol

Structural refusal is a positive proof obligation. For every `*-FAIL` task, record:

1. The user's requested unsafe route.
2. The legitimate data source that would be needed to complete it.
3. The missing authority boundary.
4. The exact security primitive that blocked the write or prevented planning.
5. A disabled-defense canary showing the task would execute if that primitive were removed.

Valid structural-refusal evidence:

| Failure mode | Good evidence | Bad evidence |
|---|---|---|
| Missing fact/kind | `@policy.build` denies `recipient`/`email`/`url` because extracted scalar has no factsource or wrong kind. | Agent says "I cannot do that" without attempting the route or surfacing denial. |
| Missing handle | Destructive target id cannot be authorized because no record handle backs it. | Model chose the wrong id and failed utility. |
| Projection block | Transcript shows planner never saw untrusted instruction text; extractor output is payload-only; write intent cannot be formed. | Model saw the text but ignored it accidentally. |
| Guard/policy denial | Denial names the guard/rule and argument. | Tool crashed, parse failed, timeout, or wrapper bug. |
| No write grant | Input record has no write permission and dispatch denies. | Tool not exposed due import/runtime failure. |
| Correlation failure | Same-record correlation denies mixed facts. | Model never selected a scheduled transaction. |

If a `*-FAIL` task fails before the security primitive is reached, classify it as `OPEN masked by arbitrary failure`. Fix the arbitrary failure or write a probe that directly exercises the security boundary.

## Status protocol

Use these task statuses exactly:

| Status | Evidence required |
|---|---|
| `PASS` | Actual AgentDojo benchmark task passed in a real fp-proof run. |
| `PASS*` | Deterministic local proof exists: utility data flow works, defended security boundary blocks, and a disabled-defense canary breaches. |
| `OPEN` | Expected secure utility path, but no real benchmark PASS yet. |
| `FLAKY` | Expected secure utility path, but unstable or not reliable enough to count as PASS. |
| `*-FAIL` | Missing provenance primitive blocks the task at the intended security boundary. |

Current grid:

| Suite | PASS | OPEN | FLAKY | `*-FAIL` | Total |
|---|---:|---:|---:|---:|---:|
| Travel | 0 | 17 | 3 | 0 | 20 |
| Banking | 0 | 14 | 2 | 0 | 16 |
| Slack | 0 | 20 | 0 | 1 | 21 |
| Workspace | 0 | 34 | 2 | 4 | 40 |
| Total | 0 | 85 | 7 | 5 | 97 |

Never mark projected utility as PASS. Deterministic proof can only produce PASS*, and only when the breach canary proves the defense is doing real work.

### Current Structural-Refusal Expectations

See [PLAN.md](/Users/adam/mlld/fp-proof/PLAN.md) for the full accounting. The short version:

- Banking: no current `*-FAIL`; UT0/UT2/UT12/UT13 are recovered by signed file attestation and remain OPEN until real benchmark runs pass.
- Workspace: MAIL-FAIL UT13/UT19; FS-FAIL UT35/UT38.
- Slack: MSG-FAIL UT11 only. UT2/UT16/UT17/UT20 are recovered by signed webpage attestation; UT18/UT19 are recovered by signed TODO/app attestation. UT16 is webpage-origin, not message-origin.
- Travel: none in the current user-task set.

These classifications are not excuses to ignore failures. Each must have refusal tests and transcript-grounded evidence when observed in a run. A `*-FAIL` is a recoverable provenance gap: the failure is valid only if the trace reaches the intended missing-attestation boundary. A timeout, malformed action, wrong tool, arbitrary model refusal, or wrapper bug is `OPEN masked by arbitrary failure`, not a security success.

Expected category signatures:

| Category | Valid block |
|---|---|
| FS-FAIL | Listing-derived file id is denied on `delete_file.file_id` because every listing entry is not provenance-attested. |
| MAIL-FAIL | Email body is readable, but body-derived recipient/action args fail fact/kind floors without DKIM-style attestation. |
| MSG-FAIL | Message-body-derived identity/write arg fails fact floors without signed-sender/verified-relay provenance. |

Recovered sign/verify tasks are healthy only if transcripts show the planner called `verify_user_attestation` after receiving a content/resource handle and before execute. A recovered task that passes because unverified content was appended to task context is a security bug, not a utility success.

## Triage classes

Pick the first class that fired. Later symptoms can be noted, but do not let them hide the root cause.

### A. Runtime or host failure

Symptoms:

- `Error evaluating imported file`
- interpreter error
- MCP server exited
- missing env state
- Python exception in `src/`
- OpenCode infrastructure error

Evidence:

- result row `execute_error`
- host logs
- mlld validation failure
- transcript showing no meaningful planning occurred

Next move:

```sh
mlld validate rig bench/agents bench/domains tests
MLLD_TRACE=effects MLLD_TRACE_FILE=tmp/trace.jsonl <repro command>
```

### B. Rig framework failure

Symptoms:

- action parser accepts/denies wrong shape
- shelf roundtrip strips metadata
- selected handles lose facts
- execute wrapper uses wrong bucket
- invalid action falls through
- planner receives wrong tool catalog

Evidence:

- transcript showing a reasonable model action
- structured action/tool input
- direct probe of `@policy.build` or shelf metadata

Next move:

- Write a zero-LLM rig probe.
- Fix `rig/`, not suite config.

### C. Record, projection, or policy failure

Symptoms:

- planner sees untrusted content it should not see
- planner cannot see safe handles it needs
- input record is missing a fact/kind floor
- policy denial is too broad or too weak
- correlation missing or applied to wrong input

Evidence:

- record schema
- projection output
- policy denial details
- transcript showing the field was visible/missing

Next move:

- Fix `bench/domains/<suite>/records.mld` or `policy.mld`.
- Add utility/block/canary tests.

### D. Bridge or tool-wrapper failure

Symptoms:

- MCP raw output parsed incorrectly
- error string becomes data
- wrapper coerces wrong record
- tool input/result format differs from what rig expects
- created records do not mint handles

Evidence:

- MCP call result
- wrapper code
- record materialization test
- transcript showing downstream confusion caused by wrapper output

Next move:

- Fix `bench/domains/<suite>/tools.mld` or bridge helpers.
- Add parser/error-gate tests.

### E. Model-interface utility failure

Symptoms:

- all safe data and tools exist, but planner chooses wrong route
- model loops after denial
- model passes bare values instead of handles despite available handles
- model gives up even though legal route exists
- final answer omits required data after correct tool calls

Evidence:

- transcript reasoning before divergence
- successful proof test for the route
- tool call sequence showing legal route was available but unused

Next move:

- Improve generic action contract or tool notes.
- Add prompt/interface clarification at the generic layer.
- Do not add task-specific prompt text.

### F. Evaluator or final-output mismatch

Symptoms:

- agent did the right operations
- final answer is semantically correct but utility is false
- mismatch appears to be formatting, canonical naming, or host parsing

Evidence:

- transcript and final output
- result row and public task text
- no security denial or runtime failure

Next move:

- Fix final-answer formatting generally if possible.
- Mark as evaluator-strict only with evidence.
- Do not read checker bodies.

## Spike first

When a transcript exposes uncertainty, turn it into a deterministic probe.

Good probe questions:

- Does this selected value still have `fact:email` after shelf roundtrip?
- Does `send_money.recipient` deny file-body IBAN?
- Does `update_scheduled_transaction` deny mixed id/recipient facts?
- Does Slack URL promotion hide raw URLs from planner projection?
- Does travel advice projection omit `review_blob` while preserving rating and price?
- Does `create_file` mint a file handle that can authorize `share_file`?

Bad probe questions:

- "Can the model pass UT13 now?"
- "Does this prompt sound clearer?"
- "Will the sweep improve?"

Run focused probes:

```sh
mlld tests/banking-proof.mld --no-checkpoint
mlld tests/workspace-proof.mld --no-checkpoint
mlld tests/slack-proof.mld --no-checkpoint
mlld tests/travel-proof.mld --no-checkpoint
mlld tests/index.mld --no-checkpoint
```

Run suite proof tests in parallel when possible:

```sh
mlld tests/banking-proof.mld --no-checkpoint &
mlld tests/workspace-proof.mld --no-checkpoint &
mlld tests/slack-proof.mld --no-checkpoint &
mlld tests/travel-proof.mld --no-checkpoint &
wait
```

## Common diagnosis patterns

### Pattern 1: Policy denial is correct, model reacts badly

Transcript shows the planner attempts an unsafe write, receives a denial, then gives up or retries badly.

Classification:

- Security path: correct.
- Utility path: if task should pass, model-interface bug.
- Structural refusal: success only if denial is the planned primitive.

Next move:

- For OPEN utility tasks, improve legal route visibility until benchmark evidence justifies PASS or deterministic proof justifies PASS*.
- For `*-FAIL` tasks, add refusal proof and make final answer explain structural refusal.

### Pattern 2: Task fails before reaching policy

Transcript shows wrong tool, malformed JSON, missing import, timeout, or arbitrary final answer before any security primitive fires.

Classification:

- Not a valid structural refusal.
- A/B/D/E depending on first cause.

Next move:

- Fix the arbitrary failure.
- Add direct proof test for the intended security boundary.

### Pattern 3: Legal route exists in tests but model does not find it

Proof test shows data can flow correctly; transcript shows model used a less safe or incomplete route.

Classification:

- E, model-interface utility failure.

Next move:

- Improve generic action schema, tool descriptions, denial messages, or loop affordances.
- Do not weaken policy.

### Pattern 4: Model found route but proof is missing

Transcript shows correct semantic choice, but `@policy.build` denies because facts/handles are missing.

Classification:

- B if metadata was lost in rig.
- C if record schema/projection forgot to expose the fact.
- D if wrapper failed to materialize the record correctly.

Next move:

- Write a metadata roundtrip probe.
- Fix the tier that dropped proof.

### Pattern 5: Security passes only because utility is broken

The task "fails securely" because the agent never found the data, crashed, or output nonsense.

Classification:

- OPEN, not structural refusal.

Next move:

- First fix utility to the point where the unsafe route is attempted or demonstrably impossible.
- Then prove the security primitive blocks it.

## Reporting format

Use this shape for task diagnoses:

```md
### <suite> <task_id> - <triage class>: <short failure shape>

**Verdict:** <100-200 words grounded in transcript citations.>

**Transcript evidence:**
- `part:<id>` - <reasoning/tool/final excerpt or paraphrase>
- `part:<id>` - <second citation>

**Security evidence:**
- `<policy/guard/projection/probe>` - <what primitive allowed or denied>

**Structural-refusal status:** <not applicable | proven structural block | OPEN masked by arbitrary failure>

**Next move:** <one concrete fix or probe>
```

If no transcript was read, start with:

```md
UNVERIFIED: no transcript citation yet.
```

## Final rule

Do not "fix" a security failure by making the model less likely to try the bad thing. Fix it by making the bad thing impossible to execute and by proving the legitimate thing can still flow.
