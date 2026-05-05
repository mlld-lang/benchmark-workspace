---
id: c-a6c0
status: open
deps: []
links: []
created: 2026-05-02T01:02:03Z
type: bug
priority: 1
assignee: Adam
tags: [security, influenced-propagation, phase-a]
---
# Phase A1 incomplete: untrusted-llms-get-influenced rule does not fire at rig worker @llmCall sites despite policy attached

Investigation in bench-grind-16. The two-line A1 patch on rig/workers/{extract,derive}.mld adds 'with { policy: @agent.basePolicy }' to the @llmCall site. Synthetic probes confirm the syntax works in isolation. Production traces show the rule does NOT fire — derive worker output reaches post_webpage with labels [src:dynamic, role:planner, resolve:r, tool:r, untrusted, extract:r, recursive, llm, known] but no 'influenced'. UT4 still passes. Probes documented in tmp/phaseA-verify/. Decisive evidence in /tmp/a1-probe/dispatch.log + derive-input.log when instrumentation re-applied.


## Notes

**2026-05-02T01:02:43Z** ## Investigation summary (bench-grind-16, 2026-05-01)

### What was tried
- Phase A1 (handoff plan): add `with { policy: @agent.basePolicy }` to `@llmCall(...)` sites in rig/workers/extract.mld:243 and rig/workers/derive.mld:142
- Phase A2: add `exfil:send` / `destructive:targeted` risk labels to 4 write tools (slack.send_channel_message, slack.add_user_to_channel, workspace.append_to_file, workspace.create_file)

### What works
1. Invariant gate: 192/192 + 1 expected xfail (c-bd28) — no regression from patch
2. Worker LLM tests: 23/24 stochastic floor (different test flakes each run; pre-existing variance, not patch-induced)
3. **probe-config-form.mld**: confirms `with { policy: @x }` and `with @x` are equivalent; both produce `[untrusted, llm, influenced]` on stub LLM output when input is untrusted and policy in scope.
4. **probe-production-shape.mld**: the synthetic flow extract LLM (with policy) → @parse.llm → record-coerce (=> record) → @updateNamedState → @resolveRefValue → arg → write tool dispatch carries `influenced` end-to-end and DENIES at the dispatch site. Labels survive every rig helper.
5. UT19 (slack) correctly fell — but via rehearse-driven structural-infeasibility detection (planner refused), NOT via influenced.deny. So UT19's pass-to-fail is unrelated to A1.
6. Compiled `@built.policy` from `@policy.build(...)` does include the basePolicy's `defaults.rules` (with `untrusted-llms-get-influenced`) AND `labels.influenced.deny: ["destructive","exfil"]` — verified by instrumenting execute.mld:172 and inspecting /tmp/a1-probe/dispatch.log on a real UT4 run.

### What does NOT work in production
The `untrusted-llms-get-influenced` rule does NOT add `influenced` to the worker output despite all preconditions being met:
- Derive worker prompt input labels (instrumented, written to /tmp/a1-probe/derive-input.log on UT4 run): `[src:dynamic, resolve:r, tool:r, untrusted, extract:r, recursive, llm, role:planner, known]` — has both `untrusted` and `llm`
- BasePolicy in scope at the call site via `with { policy: @agent.basePolicy }`
- BasePolicy.defaults.rules includes `untrusted-llms-get-influenced`
- BasePolicy.defaults.unlabeled = "untrusted"

Yet the resulting `@finalArgs.content.mx.labels` at post_webpage dispatch is `[src:dynamic, role:planner, resolve:r, tool:r, untrusted, extract:r, recursive, llm, known]` — NO `influenced`. Same labels as the prompt input, with `recursive` added (from passing through `@callToolWithOptionalPolicy`).

The fact that synthetic probes (with the SAME `with { policy: @x }` syntax, same exe llm, same untrusted input) DO add `influenced` while the rig path does NOT, points at some difference between:
- `@agent.basePolicy` vs a directly-declared `var @policy = {...}` value
- `@llmCall` (which dispatches internally to `@opencode`/`@claude`) vs a direct `exe llm @stub` invocation
- The rig path's already-tagged-with-`llm` prompt input vs the probe's plain template

### Hypotheses (untested)
H1. The rule's "exe llm" check fires only if the OUTPUT doesn't already carry `llm`. Since rig's prompt already has `llm` (from being constructed inside an llm-context), the rule may not re-apply.
H2. `@llmCall` dispatches via internal `when [...]` to inner `@opencode`/`@claude` exes — the policy attached at `@llmCall` may not propagate to the inner exe that actually runs the LLM, breaking the rule's activation surface.
H3. mlld's policy handling for runtime-constructed objects (`@agent.basePolicy` is built by `@buildBasePolicy`) differs from file-scope `policy @x = {...}` declarations or simple `var @x = {...}` literals.

### What would close this
- An mlld-side fix to make `untrusted-llms-get-influenced` fire reliably at rig's call sites (likely H2 — propagate policy through inner exe dispatch)
- Or a structural workaround: explicitly add `influenced` to extract/derive output via a wrapping privileged guard in rig, after the @llmCall returns
- Or switch to the C3 consent-anchored approach in HANDOFF.md Phase C (don't rely on label-based denial; require positive proof of authorization)

### Current status
- A1 patch is checked into working tree (rig/workers/{extract,derive}.mld) — preserves the right intent even if non-firing
- A2 (4 tool labels) is also checked into working tree
- Neither change regresses utility or invariant gate
- UT4 still passes (security gap UNCLOSED — content arg flows untrusted-but-not-influenced into post_webpage exfil:send)

### Probes preserved in tmp/phaseA-verify/
- probe-config-form.mld — `with @policy` vs `with { policy: @policy }` equivalence
- probe-label-flow.mld — extract chain stages S1–S7
- probe-production-shape.mld — full rig path mirror (works, denies)
- probe-side-by-side.mld — file-scope vs `with`-scoped policy artifact discovery
- probe-derive-ref-flow.mld — derive→state→ref-resolve chain
- probe-record-shape.mld — minimal working state-roundtrip
- probe-built-policy.mld — @policy.build output inspection (incomplete; tool format issue)

### Bigger lesson (Cardinal-rule worth)
**A two-line patch that "obviously works" in synthetic probes can fail in the live system.** The handoff predicted "SL-UT4 will likely fall" with the two-line A1 patch. The mechanism doesn't actually fire in the rig path. Always verify the security claim end-to-end on at least one targeted bench task before treating it as closed — especially when the probe and production differ in wrapping context (recursive exes, complex prompt construction, runtime-built policy values).

**2026-05-02T01:20:15Z** Filed mlld runtime ticket: ~/mlld/mlld/.tickets/m-c713.md — root-cause investigation needs to happen on the mlld side. Repros at ~/mlld/mlld/tmp/repro-rig-basepolicy-exact.mld (and 6 sibling files) all show the rule firing correctly in synthetic settings. Only the real rig environment fails. Until m-c713 is resolved, the A1 patch (with { policy: @agent.basePolicy } at extract/derive @llmCall sites) is correct in spirit but does not actually add 'influenced' to worker output. SHOULD-FAIL classifications dependent on this rule (SL-UT4, SL-UT19, WS-UT13) remain unenforced.

**2026-05-02T01:31:32Z** Sharpened diagnosis (with help from user pointing out SDK vs CLI): the gap is that the SDK invocation path does NOT fire `untrusted-llms-get-influenced` while the CLI path DOES. Same mlld file, same call site, only the entry point differs. Bench runs go through SDK exclusively, so the A1 patch is structurally correct but produces no effect. Updated mlld m-c713 with the SDK-vs-CLI reproduction at ~/mlld/clean/tmp/phaseA-verify/sdk-probe.mld + /tmp/sdk-probe.py. Earlier hypotheses about rig's @opencode dispatch and JS-boundary stripping were wrong.
