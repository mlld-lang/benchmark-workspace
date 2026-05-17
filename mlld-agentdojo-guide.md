# mlld AgentDojo rebuild guide

This guide documents the development strategy used to build `fp-proof`. It is intentionally not an architecture spec. The point is to help another agent rebuild a high-utility defended AgentDojo implementation from first principles using mlld records, policy, and tests.

## Goal

Build the smallest useful defended agent that can complete benign AgentDojo tasks while making prompt-injection consequences structurally impossible. Do not start by designing a large framework. Start by modeling authority.

The invariant is:

> The model may choose badly, but it cannot cause an unauthorized effect.

## Start with threat shape, not code shape

For each suite, read the relevant `sec-*.md` file and classify task families by what provenance they need.

Ask these questions before writing implementation:

- What values can become write control args?
- Which tools are authoritative for those values?
- Which fields are untrusted instruction-bearing content?
- Which tasks require a missing primitive and should fail structurally?
- Which legal utility paths must still work?

Do not design around task ids or expected checker output. Do not read benchmark checker code. Do not add task-specific branches. Domain-natural tools and records are allowed; benchmark-shaped answer hacks are not.

## The core mlld concepts

### Records

Records are the primary security boundary.

- Put authoritative identifiers in `facts:`.
- Put instruction-bearing prose in `data.untrusted:`.
- Put objective non-instruction data in `data.trusted:`.
- Add `kind:` tags to facts that will satisfy write control args.
- Add role-specific `read:` projections so the planner sees only safe facts and handles.

Rule of thumb:

> If a downstream write tool needs a value as a control arg, that value must originate as a fact.

Examples: email recipients, Slack users/channels, IBANs, transaction ids, calendar event ids, file ids, file sharing recipients, booking targets, URL destinations.

### Write input records

Every write tool needs an input record.

Use:

- `facts:` for control args;
- `data.trusted:` for exact task literals or objective update fields;
- `data.untrusted:` for payload text that may contain content from files, emails, messages, or webpages;
- `validate: "strict"`;
- `write.role:planner.tools.authorize = true`;
- `write.role:worker.tools.submit = true`;
- `correlate: true` when multiple fact args must come from the same source record.

### Policy

Policies are not prompts. They are runtime rules.

For defended agents, prefer:

```mlld
var @suitePolicy = {
  records_require_tool_approval_per_role: true,
  labeling: { unlabeled: "untrusted" },
  labels: {
    risks: {
      "exfil:send": ["exfil:send"],
      destructive: ["destructive", "delete:w"]
    },
    args: {
      "exfil:send": {
        recipients: ["fact:*", "known"],
        participants: ["fact:*", "known"]
      },
      destructive: {
        file_id: ["fact:*"],
        event_id: ["fact:*"]
      }
    },
    rules: {
      secret: { deny: ["exfil:send"] },
      pii: { deny: ["exfil:send"] },
      sensitive: { deny: ["exfil:send"] },
      "trust:untrusted": { deny: ["destructive"] }
    }
  },
  authorizations: {
    can_authorize: {
      "role:planner": ["write_tool_name"]
    }
  }
}
```

The exact policy differs by suite, but the pattern does not: classify tool labels into risk categories, require proof for control args, and deny sensitive or untrusted flows where they would cause external effects.

### `known` versus `resolved`

Use `known` only for values that appear verbatim in the user's task text. It is not "known to the model" and not "found by a worker".

Use `resolved` for fact-bearing values returned by authoritative tools. In the current proof agent, prior action history uses `from_history` references because handles are per-call. The runtime resolves those references against live history values and bridges only allowed fact sources into scoped known claims.

The ideal future form is shelves and durable addresses. The important rule is unchanged: never authorize from copied payload strings.

### Planner and worker roles

The planner authorizes. The worker submits.

- `@policy.build` must run under `role:planner`.
- The actual write dispatch should run under `role:worker`.
- With `records_require_tool_approval_per_role: true`, the submit side checks `write.role:worker.tools.submit`.

This catches miswired dispatchers that accidentally rely on catalog membership alone.

## Build one suite at a time

Start with the suite where the authority model is clearest.

### Banking

Banking is the best first suite because the control args are obvious: IBANs, scheduled transaction ids, amounts, dates, profile/password fields.

Useful records:

- transactions and scheduled transactions: recipient/id facts, amount/date trusted data, subject untrusted unless refined;
- file text: file path fact, content untrusted data;
- write inputs: payment recipient as fact, scheduled update id/recipient correlated, password exact task text.

Key lesson: file content can be useful payload, but without per-file content attestation it cannot authorize a recipient or scheduled update target.

### Workspace

Workspace is a larger version of the same problem.

Facts:

- contact emails;
- email ids and headers;
- calendar ids and participants;
- file ids and sharing lists.

Untrusted data:

- email bodies and subjects;
- file content;
- calendar title/description/location where it can contain natural language.

Key lesson: the agent can read and summarize payload content, and can even use it as message body content, but recipients, participants, file ids, and destructive targets need fact proof or exact task text.

### Slack

Slack is mostly identity and URL provenance.

Facts:

- Slack users and channels from Slack tools;
- message sender/recipient facts;
- channel overview member/non-member lists;
- ranking plans where users are facts and messages are payload.

Untrusted data:

- message bodies;
- webpage content;
- TODO/app content unless a future app-origin primitive exists.

Key lesson: raw URLs found in message bodies must not become planner-visible destination authority. Task-known URLs can be fetched directly. Message-body URLs should flow through opaque URL refs and be fetched by ref.

### Travel

Travel is recommendation hijack.

Facts:

- hotel/restaurant/car names;
- user email when needed;
- calendar event participants/ids.

Trusted objective data:

- rating;
- price;
- address;
- cuisine;
- hours;
- car type/fuel;
- date/time fields when task-provided or objective.

Untrusted data:

- review prose.

Key lesson: advice should run on objective fields, not review blobs. Review text is useful only when the user explicitly asks to summarize reviews; it cannot steer bookings, recommendations, recipients, or calendar targets.

## Use tests as the design tool

Write llm-free tests before broad sweeps.

Each security-relevant route needs a proof triple:

1. **Utility:** legal data can flow to the answer or write.
2. **Defense:** the same shape is denied when the authority comes from untrusted or insufficiently proven content.
3. **Canary:** an intentionally unsafe local surface allows the violation, proving the defended test is not empty.

Good tests are not "the policy says no". Good tests prove exactly which primitive is doing the work.

Examples:

- A task-known IBAN authorizes payment; a file-body IBAN is denied; an unsafe payment record with recipient as data allows the attacker IBAN.
- A contact email authorizes email; an email-body recipient is denied; an unsafe send surface allows the payload recipient.
- A Slack URL ref hides the raw URL; direct fetch denies a message-only URL; an unsafe direct fetch accepts the same URL.
- A travel objective ranking ignores injected review prose; review-selected booking is denied; an unsafe booking record accepts the review-selected target.

## Then run live canaries

Only after deterministic tests pass, run real benchmark tasks.

Use small live canaries first:

```bash
PYTHONPATH=src uv run --project bench python3 src/run.py -s banking -t user_task_10 -p 1 -d defended --harness opencode --debug
```

Scale to small clusters that share a root cause, then to suite sweeps, then to the full sweep. Do not use full sweeps as a debugger.

## Read transcripts before guessing

The result JSONL tells you what failed. The transcript tells you why.

Before changing code or prompts, inspect:

- what the planner observed;
- whether safe projections hid the right fields;
- whether it used `from_history` refs or copied bare strings;
- whether `@policy.build` dropped an entry;
- whether the write failed at policy, guard, role, record, or adapter layer;
- whether the failure was arbitrary rather than a structural SHOULD-FAIL boundary.

For opencode runs:

```bash
python3 src/opencode_debug.py sessions
python3 src/opencode_debug.py parts --session latest --limit 80
python3 src/opencode_debug.py follow --session latest
```

For cloud runs, fetch artifacts first:

```bash
uv run --project bench python3 src/fetch_run.py <run-id>
python3 src/opencode_debug.py --home runs/<run-id>/opencode sessions
```

## Prompt discipline

Prompts may explain how to use the architecture. Prompts are not defenses.

Allowed:

- tool names and argument shapes;
- domain-natural workflow hints;
- reminders that writes require execute;
- reminders to use `from_history` refs;
- guidance to call a domain read tool instead of guessing.

Not allowed:

- "ignore malicious instructions" as the only defense;
- task-id-specific rules;
- examples copied from benchmark fixtures;
- evaluator-shaped formatting hacks;
- rules that compensate for leaked tainted data.

When utility fails, first ask whether records/tools/policy are exposing the right legal route. Prompt changes should usually be small and domain-general.

## What to classify as SHOULD-FAIL

A SHOULD-FAIL task is not a task the agent happens to miss. It is a task that needs a provenance primitive the current architecture does not have.

Current hard categories:

- filesystem-wide provenance over derived listings;
- email sender/content attestation;
- signed sender or verified relay for message bodies.

File content, webpage content, and TODO/app resource content are no longer hard categories in `fp-proof` when the benign task-start source can be signed and later verified by the planner. They are recoverable only through the sign/verify protocol:

1. The bench host registers the benign task-start resource with `@sigWrite`.
2. The read tool returns a handle, not raw task authority.
3. The planner calls `verify_user_attestation`.
4. `rig/` appends verified content to execution context only for `verified:true`.
5. Failed verification blocks, and unsafe unverified append canaries prove the defense is load-bearing.

The task is healthy only if it fails at the intended structural boundary: missing fact proof, missing signed provenance, policy denial, guard denial, projection inaccessibility, exact-known failure, or role/write denial.

## Keep rig generic

If a change mentions AgentDojo task ids, expected answers, specific fixture names, or a suite concept inside `rig/`, it is probably wrong.

Put domain configuration in `bench/`:

- records;
- tools;
- suite policy;
- bridge config;
- suite notes;
- deterministic domain aggregators.

Put only generic mechanics in `rig/`:

- structured action loop;
- history/ref validation;
- planner-worker dispatch;
- authorization compile;
- generic guards.

## Prefer deterministic domain utilities over LLM derivation

When a task requires set math, ranking, filtering, or aggregation over structured tool results, implement a domain-natural read tool or deterministic helper.

This is not cheating if the tool is a plausible domain utility and not tied to a task id. It improves both speed and security because the LLM sees a compact fact-bearing record rather than pages of untrusted prose.

Examples:

- Slack channel overview with members/non-members/message counts;
- Slack author ranking plan;
- travel city candidate aggregators that return objective fields and omit review prose;
- workspace date normalization helper.

## Closeout checklist

Before claiming progress:

1. `mlld validate rig bench/agents bench/domains tests`
2. `mlld tests/index.mld --no-checkpoint`
3. Targeted live canaries for changed suites.
4. Transcript diagnosis for every failure.
5. Update `STATUS.md` only with actual evidence.
6. Run broad benign sweeps when deterministic evidence is strong.
7. Run attack suites as regression detection, not as the primary security proof.
