# AGENTS.md - fp-proof orientation

This repo builds a defended mlld proof agent. The timeless rule is:

> Preserve utility by giving the model safe routes, but make every external effect pass through deterministic mlld authority.

## Read First

- `ARCHITECTURE.md`: the intended generic architecture.
- `PLAN.md`: current implementation plan, suite threat model, and proof backlog.
- `STATUS.md`: task accounting and evidence ledger.
- `DEBUG.md`: debug/diagnose protocol. Read transcripts first when anything fails.
- `HARDENING.md`: clean-derived hardening applied here and future hardening candidates.
- `mlld-agentdojo-guide.md`: process guide for rebuilding from first principles.
- `mlld-feedback.md`: mlld friction and ergonomic/security opportunities.
- `mlld-security-fundamentals-review.md`: suggested changes to the fundamentals doc.
- `mlld-security-primitives.md` and `sec-*.md`: primitive and suite threat-model notes.
- `mlld-friction.md`: dogfooding feedback for mlld friction that is not a showstopper.

## Directory Boundaries

- `rig/` must stay generic. No AgentDojo task ids, expected answers, suite-specific branches, or benchmark shortcuts.
- `bench/` may contain suite records, tools, policy, fixture/source classifications, and small prompt addenda.
- `tests/` should prove architecture data flow and security boundaries without LLM calls.
- `llm/` and `src/` are bridge layers. They should not become policy engines.

## Terminology

| Term | Meaning |
|---|---|
| `PASS` | Real AgentDojo benchmark pass in this repo. Nothing is `PASS` without that run evidence. |
| `PASS*` | Deterministic local proof exists: utility route, defended-block proof, and disabled-defense breach canary. |
| `OPEN` | Expected secure utility, not yet proven by real benchmark pass. |
| `FLAKY` | Expected secure utility, but unstable until canaries/runs show otherwise. |
| `*-FAIL` | Missing provenance primitive. It must fail at the planned security boundary, not by accident. |
| Structural refusal | A denial caused by a deliberate security primitive boundary. Arbitrary tool errors do not count. |
| Control arg | Recipient, target id, URL, channel, user, IBAN, event id, file id, or similar effect-defining value. |
| Payload arg | Body text, summary, description, file content, advice prose, or other content that does not choose the effect target. |
| `known` | Exact value from the user task text, allowed only where the write input record permits it. |
| Fact/kind | Metadata proving a value has authority and type, such as `kind: iban` or `kind: email`. |
| Projection | Role-specific view of a record. Planner projections should omit instruction-bearing untrusted content. |
| Disabled-defense canary | A minimal unsafe variant that breaches when exactly one defense is removed. |

## Non-Negotiables

- Prompts are not defenses. They can explain the action contract, but security must survive if the model ignores the prompt.
- Do not add task-id routing or expected-answer maps.
- Do not mark a task `PASS` without real benchmark evidence.
- Do not mark a task `PASS*` without all three proof pieces.
- Do not run attack suites as security proof.
- For `*-FAIL`, prove the data reaches the intended boundary and is blocked there.
- Read the agent transcript as the source of truth for failures. Start with the actual planner action, resolved records, policy input, guard decision, and tool result.
- Preserve user or prior-agent changes. Do not revert unrelated files.

## Useful Commands

Validate mlld files:

```sh
mlld validate rig tests/index.mld tests/*.mld bench/agents bench/domains llm/lib/opencode/index.mld
```

Run the full deterministic proof index:

```sh
mlld tests/index.mld --no-checkpoint
```

Run suite proofs in parallel:

```sh
mlld tests/banking-proof.mld --no-checkpoint &
mlld tests/workspace-proof.mld --no-checkpoint &
mlld tests/slack-proof.mld --no-checkpoint &
mlld tests/travel-proof.mld --no-checkpoint &
mlld tests/cross-domain-proof.mld --no-checkpoint &
wait
```

Anti-overfit scan:

```sh
rg -n "user_task_|injection_task_|MUST_CALL_TOOL|MUST_EXECUTE_INTENT|expected_answer|ground_truth" rig tests
```

## Development Pattern

For each new utility route:

1. Add or tighten the record/projection/policy shape in `bench/`.
2. Add the generic runtime support in `rig/` only if the capability is suite-independent.
3. Add deterministic tests for utility, blocked attack, and disabled-defense canary.
4. Run the proof tests.
5. Run a small benign canary and inspect the transcript.
6. Update `STATUS.md` only with evidence that exists.

If a run fails, use `DEBUG.md`. Do not guess from the final score. The transcript explains whether the failure was model utility, missing data flow, wrong projection, policy denial, guard denial, bridge bug, or grader mismatch.

## Model Wiring

When real LLM calls are needed, use the wiring in `GLM-AND-CEREBRAS-WIRING.md`:

- Smart planner/selector: GLM 5.1 through OpenCode.
- Fast extractor/composer: `gpt-oss-120b` on Cerebras.

Model wiring is not security. The records, facts, handles, projections, policies, and guards are the security boundary.
