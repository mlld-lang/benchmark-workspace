---
id: c-5f4d
status: closed
deps: []
links: []
created: 2026-05-14T00:01:55Z
type: feature
priority: 3
assignee: Adam
tags: [compose, defense, prompt-overfit, post-snapshot]
updated: 2026-05-14T18:05:14Z
---
# [post-snapshot] structural compose anti-fabrication: replace 10d861a prompt rule with structural enforcement

Per advisor (fray msg this session): substantive prompt changes are a canary for architectural overfit. 10d861a (compose anti-fabrication: 'never claim sent unless status:\"sent\" in execution_log') is the canonical prompt-as-defense example — we're asking the LLM to be honest about success/failure rather than structurally preventing it from making the false claim.

**Why it's prompt-as-defense, not framework discipline:**
- Defense relies on the compose worker following the rule
- An adversarial or sloppy compose LLM could still emit 'we have sent...' text
- The verification gate is implicit (test assertions catch some cases but not all)
- Defense-adjacent: an agent that blocks correctly but tells the user 'we sent it' is a side-channel leak to the user about what was/wasn't denied

**Structural alternatives worth designing:**
- Compose-level validation that strips/rewrites text claims of success when no successful execute exists (output validator pattern)
- A pre-compose typed-state-only path: compose receives a structured answer-template grounded in execution_log + typed state, then renders. LLM sees only state, not free-form synthesis. Cuts both fabrication AND substring-leak attack vectors.
- A post-compose check (similar to URL output validators at rig/validators/output_checks.mld) that rejects/regenerates compose outputs containing success-claim verbs ('sent', 'created', 'scheduled', etc.) when the corresponding execute entry shows status:'error' or no entry exists.

**Sequencing:**
- Keep 10d861a in place transitionally — it does the job and worker gate is green at 24/24.
- Don't add more prompt-as-defense rules to compose — flag any such proposal as structural-ticket-worthy.
- Design structural enforcement post-snapshot when v2.x architecture work happens.

**Reference:**
- 10d861a: rig/prompts/compose.att output rules (anti-fabrication section)
- c-6a39: original BK-UT6 / BK-UT3 / TR-UT3 compose fabrication ticket (closed by 10d861a)
- Sibling URL output validator pattern: rig/validators/output_checks.mld + rig/policies/url_output.mld


## Notes

**2026-05-14T18:05:14Z** Closed 2026-05-14 (ticket-review pass): Post-snapshot structural compose anti-fabrication; refile with concrete post-migration design + test plan when the structural enforcement is scoped.
