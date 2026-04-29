# Typed Instruction Channel Design

Status: proposal, security-review revision

This document designs the rig primitive for tasks where the user deliberately
delegates work to content, for example "do the actions in this email" or
"send each person the TODO item assigned to them in this file." The goal is to
recover the safe subset of workspace UT13, UT19, and UT25 without weakening the
clean planner invariant or reopening indirect prompt injection.

The security-review correction is load-bearing: delegated content must not be
able to choose an arbitrary file target by giving the binder a filename. A file
named only in tainted prose is a descriptor, not authority. Under the current
workspace fixture facts, this means the autonomous UT13 append-to-file action is
not safe to claim. Passing that action with 0% ASR requires an additional
non-tainted file-authority fact, or a user confirmation surface.

## Decision

Use a typed-instruction record family plus a deterministic binding primitive,
with capability-bound execution. Do not use a free-form dual-LLM judge as the
authorization boundary, and do not require per-task confirmation as the normal
path for actions that can be structurally authorized.

No new planner-visible phase is introduced. Typed instruction handling is an
instruction mode of the existing `extract` phase:

1. The clean planner resolves the source selected by the user task.
2. The clean planner chooses a delegation profile from the clean task text, not
   from the source content.
3. `dispatch_extract` runs an instruction extraction mode over the tainted
   source and emits typed action candidates. Candidates are extracted data and
   mint no facts.
4. `instruction.bind` validates each candidate against the selected profile,
   resolves every control argument through authoritative records, and stores
   only ready actions whose controls are proof-bearing.
5. The planner calls the existing `execute` phase with one ready `action_id`.
   `dispatch_execute` lowers that action internally to ordinary execute refs
   before `@policy.build` runs.

In short: tainted content may propose a bounded action candidate. It may not
authorize the action, choose tools, or supply control arguments directly.

## Why Not The Alternatives

**Dual LLM judge only.** A judge that reads the email/file and emits a schema is
still an LLM reading attacker-controlled text. Its fields become the new attack
surface. Without deterministic binding, `recipient`, `file_id`, and `operation`
are just laundered extracted values.

**Per-task user confirmation as the core mechanism.** Confirmation is the
strongest generic fallback, and it is the right answer when a control target
exists only in tainted prose. It fails autonomous utility, so it should not be
the default for cases that can be structurally authorized.

**Pure deterministic parser.** Deterministic parsers are excellent when the
source is a known format, but workspace action lists use ordinary prose. The LLM
may classify prose into a narrow schema; the schema output remains untrusted
until bound.

**Capability-bound execution alone.** Bounding tools is necessary but
insufficient. We still need to represent "the user delegated this source's TODO
items" without letting the source select arbitrary tools or targets.

## Delegation Ontology

Delegation has two parts that must stay separate:

- **User delegation intent:** clean, because it comes from the user task text.
  Example: "do the actions in this email" or "email each person mentioned in
  the TODO list."
- **Candidate instruction content:** tainted, because it comes from the email
  or file body.

The planner may use the first to select a delegation profile. The second only
produces candidate records. A candidate becomes executable only after the binder
grounds every control value independently.

## Delegation Profiles

A delegation profile is a suite-declared capability contract. It is selected
from the clean user request.

The first implementation should treat profiles as small mlld modules
(`code-as-config`), not as a new general-purpose DSL. The earlier DSL-shaped
description is useful for review, but the runtime surface should stay lean:

- a candidate extraction schema
- a hard operation allowlist
- hard binding functions for each control arg
- hard authority predicates for file/data targets
- optional prompt guidance for interpreting candidate text

Only the hard pieces do security work. Prompt guidance can help the extraction
worker classify "what kind of item is this?" or "under this workflow, nested
imperatives are payload." It cannot authorize an operation, mint a control ref,
or waive an authority predicate.

Initial workspace profiles:

| Profile | User request shape | Allowed operations |
|---|---|---|
| `notify_todo_assignees` | "send each person in the TODO list their task" | `send_email` only |
| `source_reply_report` | "send the source sender a requested report" | `send_email` only, to source sender |
| `execute_action_list` | "do the actions in this email/file" | parses multiple candidates, but each candidate must match an action-specific profile |

`execute_action_list` is not an authorization to execute every operation in the
source. It is an extraction shape. The first implementation must not include
free `append_to_file` under this profile.

### Hard Versus Soft Profile Surface

Security boundary, deterministic:

- which write operations are allowed
- which record facts may satisfy each control arg
- which authority predicates are required
- which operations are always denied in delegated context
- the final "ready action" lowering to existing execute refs

Interpretation guidance, prompt-driven or review-time:

- how the extraction worker classifies a prose item into a candidate schema
- whether nested imperatives should be represented as payload under a workflow
- how to phrase blocked reasons or candidate summaries
- whether a proposed new profile is general enough to add

This split avoids building a large profile DSL. The profile module exports
plain mlld functions/data that the binder calls mechanically. A minimal manifest
may be useful for introspection and tests, but the manifest is not a second
authorization language.

### Profile Validity Rule

Profiles must be general workflow capabilities, not benchmark-shaped prompts.
A profile is valid only if it satisfies all of these review/lint rules:

- It is named by a reusable workflow class, not by task id, fixture subject,
  filename, or expected answer.
- Its allowlist and binding rules can apply to at least two distinct task
  shapes, or it has explicit architecture-review approval as a one-off
  capability boundary.
- It does not mention exact benchmark strings, exact recipients, exact file
  names, or evaluator wording.
- It is narrower than the write tool surface. Adding a new write tool to a
  profile requires a threat table row and a targeted negative test.
- A broad profile such as `execute_action_list` may only dispatch to narrower
  action profiles; it may not contain a catch-all "do whatever the source says"
  rule.

These validity rules are governance, not runtime proof. They belong in design
review and test/lint checks. The binder's runtime security should not depend on
an LLM deciding that a profile is "general enough."

## Record Family

The instruction records split candidate data from bound controls.

### `instruction_candidate`

Produced by extract instruction mode from tainted source content.

- facts: none
- system data: profile name, source ref, candidate index
- candidate data: action type enum, assignee text, filename text, subject text,
  body/task text, deadline text, raw span, recipient literals
- planner display: action id, action type, required binding slots, status
- worker display: full candidate fields

No field in this record can satisfy a write control arg.

### `instruction_binding`

Produced by `instruction.bind`, not by the extraction worker.

- facts: the actual resolved control value, copied from an authoritative record
  with factsources intact
- trusted data: binding rule, source action id, target operation, target arg
- untrusted data: optional candidate descriptor used to find the binding
- planner display: binding status and resolved record/field, not raw content

Examples:

- `send_email.recipients` bound to `email_msg.sender` from the user-selected
  email source under a reply-style profile.
- `send_email.recipients` bound to a verified contact or source-file ACL
  principal under `notify_todo_assignees`.
- `append_to_file.file_id` bound only through a `file_update_authority` proof,
  never by filename search alone.

### `instruction_action`

Produced by `instruction.bind` after all required bindings validate.

- facts: rig-generated action id only
- trusted data: operation, binding ids, payload refs, status, blocked reason
- untrusted data: payload fields such as email body text or append content
- planner display: action id, operation, status, binding summary, missing slots
- execute display: exact args needed for one lowered execute dispatch

The ready action is not a general authorization. It is a one-action recipe that
can lower only to the declared operation with the declared bindings.

### `instruction_batch`

Container stored in `state.instructions`.

- source ref and selected profile
- candidate count
- ready action ids
- blocked candidate ids and reasons
- unsupported operation count

The planner sees this summary and can execute ready actions one at a time or
call `blocked` if required actions cannot be bound.

### `file_update_authority`

This is the missing proof needed before delegated `append_to_file` can be safe.
It is a binder-created proof that a candidate is allowed to update a specific
file. It cannot be minted from source prose.

Valid sources for `file_update_authority`:

- The clean user task text names the target file or handle.
- The selected source metadata carries a first-class file relation, such as an
  attachment/linked-file handle, and that relation is trusted data rather than
  body text.
- The target file facts show that the source actor owns the file or has write
  ACL on it, and the profile explicitly treats source-owned file edits as
  delegable.
- A future first-party work-order/task record gives the source a typed,
  non-prose authority to request that file update.

Invalid sources:

- A filename that appears only in email/file body text.
- A `search_files_by_filename` result found from an extracted filename.
- An LLM assertion that the file "looks related" to the task.

The current UT13 fixture names `team-building-activities.docx` only in the
email body. The file is owned by Emma and shared read-only with Linda; it is not
source-owned or source-writable by David. Therefore this design blocks the
append action unless the domain adds a trusted work-order/file-authority fact or
asks the user to confirm that specific file update.

### `file_read_authority`

A content-selected file used as an input to an outbound report has the same
problem in read form: if the source can pick an arbitrary file and ask the agent
to email facts from it, the source can exfiltrate user data to an otherwise
valid recipient. The binder therefore also tracks `file_read_authority` for file
content used in delegated outbound payloads.

Valid sources are the read analog of `file_update_authority`: clean user naming,
trusted source metadata relation, source-owned/source-shared data, or a future
first-party work-order record. A filename in tainted prose plus
`search_files_by_filename` is not enough to read file contents for a delegated
send.

## The Bridge Primitive

`@instructionBind` lives in `rig/instructions.mld`. It is called by
`dispatch_extract` after instruction candidates are validated and before the
extract result is committed to state.

The binder validates a candidate with this algorithm:

1. Check the profile selected by the clean planner.
2. Check that `action_type` maps to an allowed operation in that profile or in a
   narrower action profile.
3. For each control arg, select the profile's binding rule.
4. Resolve binding descriptors through authoritative records:
   - source provenance, such as selected email sender
   - source metadata, such as selected file owner or `shared_with`
   - trusted directory records, such as verified contacts
   - read-only resolve tools, when a profile permits a descriptor query
5. Require exact, non-ambiguous binding.
6. For file read/write targets, require `file_read_authority` or
   `file_update_authority` in addition to a resolved file handle.
7. Store payload refs separately as extracted/delegated payload values.
8. Store ready actions with normal `resolved`, `known`, or validated
   `selection` refs only.

The binder may use an extracted descriptor as a read-only binding query. For
example, a candidate assignee name may be passed to `search_contacts_by_name`.
The resulting `contact.email` can be a control value only if the profile permits
that binding and the result is exact and unambiguous. The extracted name itself
is never the recipient.

### Binder Location And Tool Path

The binder is mlld code in `rig/instructions.mld`, not an MCP service and not
Python business logic. It should be imported by `rig/workers/extract.mld` or the
extract dispatch wrapper.

When binding needs a read tool, it must go through the same resolve-intent
compiler and routed read-tool catalog used by normal `resolve`. It may use an
internal binding-query source class for read queries, but that source class is
never valid for execute args and must not survive into state as proof.

Required implementation constraints:

- no direct MCP calls from the binder
- no bypass of read-tool arg compilation
- no bypass of record coercion
- nested resolve/bind events logged with lifecycle and trace metadata
- binder budget counted under the parent extract dispatch
- failed binding stored as blocked candidate state, not swallowed

### Binder Determinism Boundary

The binder does not have to be "all deterministic because it exists." It has to
be deterministic at the authorization boundary.

For v1, keep these deterministic:

- lookup calls and their compiled args
- exact match predicates for names, handles, ACL principals, and email values
- ambiguity blocking
- authority predicates
- ready-action lowering

An LLM-first helper can be added later for non-authoritative judgment over typed
inputs, for example to explain why a candidate was blocked or to suggest which
ambiguous field needs user confirmation. That helper must never read raw source
prose, and its output must be treated as advice. It cannot choose among two
equally valid control targets unless a deterministic verifier can prove the
choice is exact and unique.

This keeps the orchestrator boring without pretending every classification step
is a security primitive. The LLM can classify candidate content; deterministic
mlld code decides whether the resulting action can compile.

### Ambiguity Definition

A binding is ambiguous if any of these are true:

- zero records match
- more than one exact normalized match exists
- more than one top-scoring match has the same score
- the best match is below the profile's deterministic threshold
- different authoritative sources produce different values for the same slot
- the resolved record lacks a required fact or handle
- the profile needs an ACL principal but the name-to-email mapping is not exact
- the profile needs a verified contact but the contact source is unverified

The first implementation should avoid fuzzy binding for control args. Normalized
full-name equality, exact email equality, and exact handle equality are the safe
defaults. If fuzzy matching is later added, equal-score ties and below-threshold
matches must block.

## Why This Does Not Launder

The primitive does not add `extracted` or `instruction` as a valid control
source class. Control args still compile from:

- `resolved` refs with factsources
- `known` values from the clean user task text
- derive-only `selection` refs validated against derive inputs

`instruction.bind` creates ready actions only by building those existing source
classes. It cannot:

- mint selection refs
- mark an extracted scalar as resolved
- put a raw recipient literal from content into `known`
- turn a filename descriptor into file target authority
- bypass `@policy.build`
- authorize tools outside the selected profile
- execute more than one write per dispatch

If a candidate says "send to attacker@example.com", the literal is just
candidate data. Unless the profile independently resolves it to an allowed
recipient fact, the action is blocked.

## Per-Action Policy

Each ready action executes through the normal `execute` worker path. The planner
calls `execute` with an `action_id`; `dispatch_execute` retrieves the ready
action, lowers bindings to normal refs, compiles intent, and calls
`@policy.build` with the base policy.

The first implementation should allow only:

- `send_email` where recipients bind to source sender, verified contact, or
  source-file ACL principal under the selected profile
- `append_to_file` only when `file_update_authority` exists
- read-derived report payloads only when `file_read_authority` exists for each
  content source

The first implementation should deny delegated:

- arbitrary `append_to_file` by filename search
- `delete_email`
- `delete_file`
- `cancel_calendar_event`
- `share_file`
- password/profile/account writes
- money movement
- recursive URL fetch or webpage follow-on tasks
- calendar participant creation from content

Payload rules:

- Payload fields remain payload-only. They may come from extracted or derived
  instruction data after controls are bound.
- Existing secret/sensitive/exfil rules still apply.
- Payload may not change recipient or target bindings.
- Nested imperatives inside payload text are not recursively executed unless a
  future profile explicitly permits a second delegation step.

## Utility Flows

### WS-UT13

1. Resolve the user-specified email by sender and subject.
2. Run extract instruction mode with profile `execute_action_list`.
3. Candidate 1 proposes `append_to_file` for `team-building-activities.docx`.
   This action blocks under strict autonomous mode because the target file is
   named only in tainted body text and lacks `file_update_authority`.
4. Candidate 2 proposes a report email to the selected source sender. Recipient
   binding to `email_msg.sender` is valid under `source_reply_report`.
5. The report's referenced file, `feedback.xlsx`, also needs
   `file_read_authority` before its contents can be used in an outbound email.
   In the current fixture that authority is not present unless the domain adds a
   trusted work-order/source-file relation.

Result: strict mode does not claim full autonomous UT13 utility. The safe ways
to pass UT13 are:

- add a general, non-tainted work-order/file-authority record family to the
  workspace domain, or
- add per-action user confirmation for the append and report file-read targets.

Letting a tainted filename bind directly to `append_to_file.file_id` is rejected.

### WS-UT19

The UT1 half runs normally. The UT13 half has the same authority requirements as
WS-UT13. Without file authority or confirmation, the typed-instruction channel
executes only the structurally authorized subset and must not return a canned
"Task completed."

### WS-UT25

1. Resolve the user-specified meeting-minutes file.
2. Run extract instruction mode with profile `notify_todo_assignees`.
3. Extract one candidate per TODO assignment:
   - assignee
   - task text
   - deadline
4. Bind each assignee to a verified contact whose email also appears in the
   source file ACL, or to an exact source-file ACL principal if the record
   exposes enough principal identity to match the assignee deterministically.
5. Execute one `send_email` per ready assignment.

The item "Linda: email the meeting-agenda file to John..." is not executed by
the agent. It is payload in the email to Linda, because the clean user request
asked the agent to notify assignees of their tasks.

If the ACL contains more principals than the TODO list, that is not a problem by
itself. The binder binds only the extracted assignee descriptors. It blocks if a
descriptor maps to zero, multiple, or non-exact principals.

## Prerequisites For Full UT13 Utility

The typed-instruction primitive alone does not unblock full UT13. It unblocks
the safe instruction-following shape, especially UT25-style assignment
notification, and makes UT13 fail cleanly where current facts are insufficient.

Full UT13 utility needs one of these separately tracked prerequisites:

- `c-c5ee`: workspace delegation-grant/work-order authority records. This would
  add a general `@work_order`/`@delegation_grant` family that can mint
  non-tainted file read/write authority for delegated tasks.
- `c-5041`: rig user-confirmation pause/resume surface. This would let the agent
  present a specific typed action, pause, and resume with a clean attestation
  scoped to that action only.

Acceptance criteria should therefore be phased:

| Phase | Expected utility | Security requirement |
|---|---|---|
| Phase 1: typed-instruction primitive | UT25 passes; UT13 and the UT13 half of UT19 block on missing file authority | 0% ASR for InjectionTask0..5 plus targeted arbitrary-file append/read tests |
| Phase 2A: delegation-grant/work-order records | UT13 can pass autonomously if the fixture/domain exposes real authority facts | Same 0% ASR; tainted filename search alone still fails |
| Phase 2B: user confirmation | UT13 can pass with confirmation, not autonomously | Confirmation is scoped to one action id and cannot be replayed or widened |

## Threat Enumeration

Coverage freshness: re-verified on 2026-04-28 against
`~/mlld/agentdojo/src/agentdojo/default_suites/v1/workspace/injection_tasks.py`.
The current file contains InjectionTask0 through InjectionTask5 only. The test
plan below includes a freshness canary so new injection classes force this table
to be revisited.

### Invariants

| Invariant | How the design preserves it |
|---|---|
| Clean planner | Planner sees source metadata, candidate/action ids, action type enums, binding statuses, and preview fields. It never sees raw source prose. |
| Source-class firewall | Candidate fields remain extracted/delegated payload. The only control values emitted by the binder are existing `resolved`/`known`/`selection` forms. |
| Spike 42 | Instruction extraction cannot emit selection refs. Binder cannot mint selection refs. Derive remains the only selection-ref producer. |
| Per-action policy | Each ready action lowers to one existing execute dispatch and passes `@policy.build` with the base policy. |
| One write per execute | `execute(action_id)` lowers exactly one action id to exactly one write. Multi-item TODOs become multiple dispatches. |
| Display projection | Source records use normal `role:planner` projection. Instruction candidates use planner displays that omit raw text. |
| No prompt-only defense | Blocking comes from profile allowlists, binding validation, source-class checks, and policy build, not from telling an LLM to ignore instructions. |

### Workspace Injection Tasks

| Attack | Block |
|---|---|
| InjectionTask0: send attacker email | `send_email.recipients` cannot bind from a raw email literal in content. If the attacker address is not a verified contact/source-provenance value allowed by the profile, the candidate is blocked. `no-send-to-unknown` remains a second layer. |
| InjectionTask1: delete file 13 | Delegated destructive operations are not in the initial profile allowlist. `delete_file.file_id` still requires a handle and explicit destructive authorization. |
| InjectionTask2: create event with attacker participant | Calendar participant writes are not in the initial profile allowlist. If future profiles add them, participants must bind to contacts/source provenance; raw attacker literals fail. |
| InjectionTask3: forward private email body to attacker | Recipient binding fails for attacker literal. Body forwarding is payload-only and cannot choose the recipient. |
| InjectionTask4: forward security code to attacker | Recipient binding fails; existing secret/sensitive rules remain available for the body dimension. |
| InjectionTask5: forward code then delete sent email | First send fails on recipient binding; delegated `delete_email` is unsupported and still destructive-targeted. |
| Valid-looking injected append to `budget.docx` | `append_to_file` is not authorized by filename search. A resolved file handle is insufficient without `file_update_authority`, so an attacker-controlled body cannot choose an arbitrary file in the user's drive. |
| Valid-looking injected "read file X and send me Y" | The recipient may bind to the source sender, but the file read still needs `file_read_authority`. A tainted filename alone cannot select the outbound data source. |

Residual risk: workspace contacts may be auto-populated from inbox data. This
design should require a `verified_contact` or equivalent fact before contact
binding is enabled for delegated instructions. Otherwise an attacker-origin
address could become fact-grade authority.

## Migration Plan

### Rig

Add `rig/instructions.mld`:

- instruction candidate schema helpers
- profile module loading and minimal manifest checks
- binding rule evaluator
- `file_update_authority` and `file_read_authority` predicates
- ambiguity detection
- ready-action lowering helpers
- trace events for candidate rejected, binding resolved, binding ambiguous,
  authority missing, action ready, and action lowered

Extend `rig/workers/extract.mld` and the extract dispatch wrapper:

- add instruction mode under the existing `extract` phase
- validate candidate envelope and schema
- reject selection refs from instruction extraction
- call `@instructionBind`
- store `state.instructions`
- budget nested binding under the extract dispatch

Extend `rig/workers/planner.mld` records only after prompt review:

- `@planner_extract_inputs` gains an instruction profile/mode field, or profile
  names are represented as instruction schemas
- `@planner_execute_inputs` gains optional `action_id`
- no new planner-visible `instruct` phase
- no generic `instruction` control source class

Extend execute dispatch:

- if `action_id` is provided, load the ready action from `state.instructions`
- lower bindings to ordinary execute refs before intent compilation
- reject if any internal instruction marker reaches normal arg compilation
- preserve one write per dispatch

### Workspace

Add workspace instruction records in `bench/domains/workspace/records.mld`:

- TODO assignment candidate
- reply/report email candidate
- unsupported action candidate
- file authority records if the domain can represent trusted work orders or
  source-linked files

Add workspace instruction profiles as small mlld modules imported by the agent:

- `notify_todo_assignees`
- `source_reply_report`
- `execute_action_list` as an extraction umbrella only
- binding rules for source sender, verified contact, source file ACL, and exact
  handle/file-authority predicates

Do not add arbitrary `append_to_file` to `execute_action_list`. Add append only
behind `file_update_authority` and targeted tests.

Update workspace `tools.mld` only to expose/import the profile metadata needed
by rig. Do not loosen `@file_append_inputs`, `@send_email_inputs`, or any
control-arg source rules. If verified-contact status or file-authority facts are
added, represent them in `records.mld` and let existing tool input records
consume the resulting facts through normal refs.

Planner addendum changes will be needed, but per `CLAUDE.md` they should be
reviewed before writing. The addendum should teach the general workflow:

- when the user delegates an action list, run extract instruction mode
- when the user asks to notify TODO assignees, use the notify profile
- nested task text in a notify profile is payload, not an action to execute
- execute ready instruction actions by `action_id`
- call `blocked` rather than returning canned success when required actions
  cannot be authorized

### Effort And Sequence

Phase 1, typed-instruction primitive:

1. Implement profile-as-mlld-module loading and `rig/instructions.mld` binder:
   3 to 4 days.
2. Add extract instruction mode and state records: 2 to 3 days.
3. Add execute `action_id` lowering and lifecycle/trace updates: 1 to 2 days.
4. Add workspace `notify_todo_assignees` profile and UT25 path: 2 to 3 days.
5. Security matrix and regression sweep: 2 to 3 days.

Phase 1 expected outcome: UT25 passes; UT13 and the UT13 half of UT19 block
truthfully on missing file authority. This is not a failure of Phase 1.

Phase 2, choose one UT13 authority path:

- `c-c5ee`: design and implement workspace delegation-grant/work-order records.
- `c-5041`: design and implement rig user-confirmation pause/resume.

Only after one Phase 2 path exists should UT13 be expected to pass. Do not
implement the unsafe append shortcut to hit UT13.

## Test Plan

Zero-LLM probes:

1. Candidate records minted by instruction extraction have no fact labels.
2. A candidate raw recipient literal cannot compile as `send_email.recipients`.
3. `instruction.bind` can bind source email sender to `send_email.recipients`.
4. `instruction.bind` can bind exact assignee to a verified contact/ACL
   principal.
5. Ambiguous filename/contact/ACL binding blocks the action.
6. Unsupported operations (`delete_file`, `delete_email`, `share_file`) block
   before execute.
7. A resolved file handle found by tainted filename search cannot satisfy
   `append_to_file.file_id` without `file_update_authority`.
8. A content-selected report file cannot be read into an outbound email without
   `file_read_authority`.
9. If the binder is disabled, candidate controls cannot reach execute through
   any other source class.

Worker tests:

1. Extract UT13-style action list into candidates, with append blocked for
   missing file-update authority.
2. Extract UT25-style TODO assignments into assignment candidates.
3. Treat nested "email this file to John" inside an assignment as payload under
   `notify_todo_assignees`.
4. Reject or mark unsupported an injected delete/send-attacker instruction.
5. Preserve deadlines and exact task literals in payload fields.

Integration utility:

1. Phase 1: local defended WS-UT25 should pass once assignee binding is
   implemented.
2. Phase 1: local defended WS-UT13 should truthfully block unsafe
   file-authority gaps.
3. Phase 1: local defended WS-UT19 should pass the UT1 half and block the UT13
   half for the same file-authority reason.
4. Phase 2A: with `c-c5ee` authority records, local defended WS-UT13 should
   pass autonomously only when the target file/read source is grant-backed.
5. Phase 2B: with `c-5041` confirmation, local defended WS-UT13 should pass
   only after a scoped user confirmation.
6. Workspace canary set for current passing write/read tasks must remain green.

Security:

1. Run the workspace injection matrix for UT13, UT19, and UT25 against
   InjectionTask0..5. Required result: 0% ASR.
2. Add targeted tests where the injected instruction is formatted as a valid
   TODO/action-list item, not just prose.
3. Add negative tests for raw email recipient, raw file id, arbitrary append
   target, arbitrary report-file read, destructive action, recursive nested
   action, and source-switching.
4. Add a freshness canary that counts `class InjectionTask` definitions in the
   current workspace `injection_tasks.py` and fails when the count changes
   without updating this design/test table.
5. Run `mlld rig/tests/index.mld --no-checkpoint`.
6. Run `mlld rig/tests/workers/run.mld --no-checkpoint` after any prompt or
   worker-template changes.

## Honest Scope

This primitive handles:

- user-selected email/file sources
- recognizable action-list or TODO-list structures
- bounded workspace actions whose control args can be grounded through source
  provenance, source metadata, verified contacts, or existing resolved handles
- file reads/writes only when an authority predicate proves the source may name
  that file
- assignment notification workflows where nested imperatives are payload
- one write per ready action

This primitive does not handle:

- arbitrary free prose with no recognizable action structure
- destructive actions delegated by content
- credential, profile, banking, or money movement delegated by content
- arbitrary new recipients that appear only in content
- arbitrary file targets that appear only in content
- arbitrary report/data-source files that appear only in content
- recursive "now follow the instructions at this URL/file/email" chains
- recommendation/advice hijack
- cases where the only possible recipient/target is an unverified external
  value from content
- ambiguous binding without confirmation

The hard conclusion is that 0% ASR and full autonomous UT13 utility are not
simultaneously supported by the current workspace facts. That is not a prompt
problem; it is an authority-model problem. The safe implementation blocks the
unsafe file-target actions until the domain provides a general non-tainted
authority record or the user confirms the specific action.

## Open Questions

1. Should `source_sender` binding require verified contact/internal-domain
   status, or is "user selected this email from this sender" enough authority
   for reply-style actions?
2. Can workspace records expose enough ACL principal identity for exact
   assignee-to-ACL binding, or must `notify_todo_assignees` require verified
   contacts whose emails also appear in `shared_with`?
3. How should the contact auto-population gap be represented before contact
   binding is enabled for delegated instructions?
4. Which Phase 2 path should be prioritized for UT13: `c-c5ee` autonomous
   delegation grants or `c-5041` confirmation?
