# Future: Action-Type Allowlist (Probabilistic Security Layer)

**Status:** concept reference, not for benchmark deployment
**Audience:** future production deployments, custom rig guards, possible mlld primitives
**Distinction:** this layer is **probabilistic / audit-based security**. The benchmark security model is **deterministic-only**. This concept is explicitly out of scope for benchmark utility — it would let some currently-`SHOULD-FAIL` tasks pass, but only by trading an invariant ("structural firewall") for a governance contract ("we audited each profile correctly").

## What it is

An **action-type allowlist** is a per-task-class declaration of which write/side-effecting operations may be invoked from delegated content. When the user delegates to an untrusted source ("do the actions in this email"), the allowlist constrains which operations the content may propose.

Example, written informally:

> Job description for "do actions in email" tasks:
> - **Allowed**: append_to_file (user's own files only), send_email (recipients must ground against verified contacts), add_calendar_event
> - **Denied**: delete_file, share_file, transfer_money, update_password, share_publicly, anything destructive

Each task class (delegation pattern) gets its own job description. The content can suggest any action; anything outside the allowed set is rejected before grounding even runs.

This is conceptually a *capability contract*: when the user says "do what David says," they implicitly mean "do what David says, within the bounds of what a reasonable assistant in this role would do." The allowlist makes that implicit contract explicit and machine-checkable.

## What it is NOT

This is not the structural source-class firewall that rig already provides. The firewall is a single mechanical check — "is this control arg's source class `resolved` or `known`?" — that works identically for every tool, with no per-tool audit. That's a deterministic invariant.

The action-type allowlist's runtime check is also mechanical, but its **correctness depends on per-action audit**. Deciding which actions to allow under which delegation patterns, with which payload constraints, is human-judgment work. Each new action requires a security review. Each new payload schema requires verification. The benchmark eval cannot prove that our specific allowlists are correct — it only proves that a specific (allowlist + attack) combination doesn't break.

That's audit-based / probabilistic security. It is genuinely useful — but it is not invariant security.

## Why we don't ship it for the benchmark

The clean/rig benchmark target is **0% ASR with deterministic security only**. A task that requires probabilistic mechanisms to be solved safely should `SHOULD-FAIL` rather than be patched with audit-based extensions. This keeps the benchmark honest: utility numbers reflect tasks where the deterministic security model truthfully holds.

If we shipped action-type allowlists in the benchmark agent, every utility win on a `SHOULD-FAIL`-class task would carry an asterisk: *"passes utility because we audited the allowlist; ASR holds against current attacks but not provably against unseen attacks."* That asterisk doesn't belong on a deterministic-security utility number.

## Where it does belong

**Production deployments** where utility on delegation-class tasks is genuinely needed and where audit infrastructure exists:

- An organization deploying an mlld-rig agent for "personal assistant" workloads might add an action-type allowlist as a privileged guard. Their security team audits the profile. They accept the audit cost in exchange for utility on tasks that would otherwise fail.
- A vendor offering a defended-agent product might bundle pre-audited profile sets per use case (executive assistant, customer support, internal IT). Each profile is a versioned, auditable artifact.

**Custom privileged guards** layered on top of rig:

- An mlld user could add a guard to an existing agent without modifying rig itself. The guard rejects intents whose action types are outside an allowlist. This composes with rig's deterministic firewall: the firewall blocks structural violations, the allowlist blocks audit-policy violations, both must pass for execute.

**Future mlld primitive** (if a generalizable shape emerges):

- mlld could expose `policy.action_allowlist` as a first-class declaration on top of the existing policy framework. Per-task-class allowlists become composable, versionable, testable artifacts.
- Per-action payload schemas become first-class typed records.
- The benchmark agent does not enable this primitive; production deployments opt in.

## Mechanism sketch

If/when this is built, the rough shape:

### Record-level metadata (one path)

```mlld
profile @execute_action_list = {
  allowed_actions: {
    append_to_file: {
      payload: {
        content: { type: array<string>, max_items: 50, max_chars_per_item: 200 },
        no_urls: true,
        no_emails: true
      },
      target: { record: "file_entry", authority: "user_owned" }
    },
    send_email: {
      payload: {
        body: { type: string, max_chars: 5000 },
        subject: { type: string, max_chars: 200 }
      },
      target: { record: "contact", authority: "verified" }
    }
  },
  denied_actions: ["delete_file", "share_file", "update_password", "send_money"]
}
```

### Per-action enforcement layer (alternative path)

A guard that runs after intent_compile but before MCP dispatch:

```mlld
guard @action_allowlist_for(profile_name) = [
  let @profile = @lookupProfile(@profile_name)
  if @intent.operation not in @profile.allowed_actions [
    => deny("operation not allowed under profile @profile_name")
  ]
  if !@payloadMatchesSchema(@intent.args, @profile.allowed_actions[@intent.operation].payload) [
    => deny("payload violates profile schema")
  ]
  if !@targetMatchesAuthority(@intent.args, @profile.allowed_actions[@intent.operation].target) [
    => deny("target authority requirement not met")
  ]
  => allow
]
```

The guard would compose with `@policy.build` — both must pass for execute.

### Profile selection

Profile is selected from clean user task text, never from delegated content. Selection logic could be:

- a fast-model classifier ("which task class is this?")
- explicit user/operator-declared task type
- pattern-matching on task prompts (less robust)

The selection mechanism is itself non-deterministic in general, which is part of why this layer is probabilistic. A misclassified task gets the wrong allowlist.

## Composition with deterministic security

When deployed, action-type allowlist sits **on top of** the deterministic firewall, not replacing it:

```
intent_compile
  → source-class firewall (deterministic — control args grounded)
  → @policy.build (deterministic — base policy invariants)
  → action-type allowlist (probabilistic — operation in profile allowlist)
  → payload schema check (probabilistic — content matches declared shape)
  → MCP dispatch
```

A request must pass all layers. The allowlist is additive defense, not a replacement.

## What it would unblock if shipped

Tasks currently marked `SHOULD-FAIL` would become solvable for production deployments:

- WS-UT13 ("do actions in email")
- WS-UT19 (combined UT1+UT13)
- SL-UT18 ("do tasks at this URL")
- SL-UT19 (same)

Plus future task classes that involve user-delegated action sets to trusted sources.

The benchmark wouldn't run with this enabled — those tasks stay `SHOULD-FAIL` for the benchmark's deterministic-security model. A separate "production-mode benchmark" or "audited-deployment benchmark" could measure utility with allowlists enabled, but that's a different evaluation and would need its own attack matrix per profile audit.

## Open questions for future design

1. **Audit format**: how do profile reviews capture the assumptions made? Threat-model-style attack tables per profile? Versioning?
2. **Profile composition**: can profiles inherit from each other ("notify_assignees extends send_email_only")? At what cost in audit complexity?
3. **Payload schema language**: regex? typed schemas (JSON Schema, mlld records)? hybrid?
4. **Authority hierarchy**: how do `user_owned`, `verified_contact`, `source_authored`, `task_named` predicates relate? Per-suite or rig-general?
5. **Profile mismatch handling**: when the classifier picks the wrong profile, does the agent block, fall back, or ask for confirmation?
6. **Test methodology**: how do we test that a specific (profile + attack) combination is safe without per-profile-per-attack matrix?

## Relationship to other futr- primitives

- `futr-projection-aware-resolveRefValue` (mlld v2 cleanup): orthogonal, both could ship independently
- `futr-user-confirmation-surface`: complementary — the action-type allowlist could allow some operations only with explicit confirmation; user-confirmation provides the surface
- `futr-typed-instruction-binder`: the binder design assumed action-type allowlists as the security mechanism. With deterministic-only benchmark scope, the binder simplifies to "extract typed parameters → ground against trusted records." The allowlist is the production extension.

## Summary

Action-type allowlist is a real and useful **probabilistic security mechanism** for production deployments. Documenting the concept here so the next person designing a custom guard, a production deployment, or a candidate mlld primitive doesn't reinvent it from scratch — and so it stays clearly distinct from the benchmark's deterministic-security model.

For the benchmark agent: keep it out. Tasks that would need it should `SHOULD-FAIL`.

For everywhere else: this is one of the cleaner audit-based defenses available, especially when paired with rig's existing structural firewall as a base layer.
