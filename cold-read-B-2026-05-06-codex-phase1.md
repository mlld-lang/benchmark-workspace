# Cold-read phase 1 — B — 2026-05-06-codex

Role: B. I picked Security auditor to trace authorization, proof flow, and trusted/untrusted boundaries through rig and bench.

## Topic 1: Authorization Policy Construction
1. How do the synthesized rules in `@synthesizedPolicy` map to concrete enforcement points once a planner calls an execute tool? (rig/orchestration.mld:25)
2. Why does the base policy allow broad capabilities like `cmd:*`, shell, filesystem write, and network while the framework is trying to constrain agent actions? (rig/orchestration.mld:57)
3. What prevents an override policy from weakening labels or operations when `@synthesizedPolicy` merges `overrideOperations` and `overrideLabels` over the base policy? (rig/orchestration.mld:69)
4. Which code derives the operation labels that policy rules such as `exfil:send`, `destructive:targeted`, or `privileged:account` actually inspect? (rig/tooling.mld:305)
5. Why do new-shape input-record tools default `can_authorize` to denied, while older tools fall back to planner authorization? (rig/tooling.mld:313)
6. How does `can_authorize: false` on a tool like `update_password` become a hard deny in defended mode rather than just omitted planner guidance? (bench/domains/banking/tools.mld:163)

## Topic 2: Source Classes And Proof
1. What exact metadata shape is expected in `.mx.factsources` or `.metadata.factsources`, and which producer attaches it to record fact fields? (rig/intent.mld:320)
2. When `@compileScalarRefWithMeta` falls back to synthetic attestations like `fact:@record.field`, how does policy know the value actually came from that record instance? (rig/intent.mld:680)
3. Why is `known` control authorization based on literal task-text inclusion instead of a structured fact source, and what threat cases does that leave open around paraphrase or normalization? (rig/intent.mld:612)
4. Why is datetime normalization the only accepted relaxation for `known` values, and where is that scope documented for suite authors? (rig/intent.mld:637)
5. What prevents a payload source such as `extracted` or `derived` from being relabeled into a control arg after it flows through array or family expansion? (rig/intent.mld:796)
6. How does array-valued authorization preserve per-element fact attestations when a control arg contains multiple resolved refs? (rig/intent.mld:885)
7. What guarantees that `resolved_family` expansion only expands entries that are legitimate for the tool argument being compiled? (rig/intent.mld:835)
8. For rigTransform `recordArgs`, why are selection refs rejected even though selection refs are lowered to resolved refs elsewhere? (rig/intent.mld:929)
9. How does `@compileRecordArgs` avoid trusting stale or forged handles when checking an indexed resolved bucket from JS? (rig/intent.mld:954)

## Topic 3: Planner And Worker Boundaries
1. Which planner-visible tool docs explain the permitted ref shapes, and how are those docs kept aligned with `planner_inputs.mld` validation? (rig/planner_inputs.mld:9)
2. Why does `@nonComposeDecisionArgIssues` allow compose to use non-structured data while all other phases require structured refs? (rig/runtime.mld:1007)
3. What prevents the planner from reading untrusted content that is present in resolved state but omitted from `role:planner` projection? (rig/runtime.mld:604)
4. How does the framework make sure a worker that sees untrusted content cannot leak literal fact identifiers back into a later execute control arg? (rig/runtime.mld:612)
5. What is the security rationale for masking fact identifiers in worker projection while still showing enough content for extraction and derivation? (rig/runtime.mld:430)
6. Why can compose read `workerStateSummary` with worker projections instead of planner projections, and what prevents compose from becoming an authorization source afterward? (rig/workers/compose.mld:52)
7. If an extract worker returns a payload containing selection refs, why is that forbidden while a derive worker may return them? (rig/workers/extract.mld:164)
8. How does `@validateSelectionRefs` prove that derive-produced selection refs came only from the derive input set and not from arbitrary state handles? (rig/workers/derive.mld:104)

## Topic 4: Execute-Time Enforcement
1. Where is the boundary between side-effect-free preflight and actual MCP dispatch, and which stages can block a write before tool execution? (rig/workers/execute.mld:68)
2. What does `@policy.build` receive in `policyIntent`, and how can an auditor inspect the compiled proof that was passed to the write tool? (rig/workers/execute.mld:120)
3. Why does a no-control-arg operation become an `allow` policy intent, and which safeguards keep that from allowing arbitrary payload writes? (rig/workers/execute.mld:120)
4. How does `@correlatedControlArgsCheck` decide that multiple control args came from the same record instance, and what happens for optional or array control args? (rig/runtime.mld:1175)
5. Why does `toolCorrelateControlArgs` default correlation on when an input record has more than one fact field, and when is it safe for suites to set `correlate: false`? (rig/tooling.mld:295)
6. How are `update` fields treated differently from ordinary payload fields when policy intent is flattened? (rig/intent.mld:1091)
7. What prevents bind args from overriding planner-compiled control or payload args when `@mergeArgSources` combines them before dispatch? (rig/workers/execute.mld:161)

## Topic 5: Domain Trust Decisions
1. How should an auditor verify that each fact field in a domain record is truly authoritative in the underlying AgentDojo data model? (bench/domains/slack/records.mld:44)
2. Why is Slack channel `name` kept as a fact even though it is attacker-controllable, and how does hiding it from planner projection avoid laundering attacker text? (bench/domains/slack/records.mld:76)
3. What is the residual risk of treating auto-populated workspace contacts as fact-grade email authority? (bench/domains/workspace/records.mld:32)
4. How do per-element fact labels on arrays such as email recipients or calendar participants survive through record coercion and policy checks? (bench/domains/workspace/records.mld:65)
5. Why is `subject` planner-visible for scheduled banking transactions but not ordinary transactions, and what prevents a malicious subject from steering writes? (bench/domains/banking/records.mld:37)
6. What is the intended security difference between `known` read tools and `untrusted` read tools in the tool catalog? (bench/domains/banking/tools.mld:26)
7. When a read tool is labeled `known` but accepts a control arg from prior state, what prevents a malicious control arg from selecting attacker-controlled output? (bench/domains/travel/tools.mld:89)
8. How are optional-benign fact fields like calendar participants represented in policy so omitted recipients do not require proof but supplied recipients still do? (bench/domains/travel/records.mld:187)

## Topic 6: URL And Output Defenses
1. What invariant ensures URL strings stored in `state.capabilities.url_refs` never appear in public records, planner-visible state, or debug logs? (rig/runtime.mld:635)
2. Why are URLs with query strings or fragments blocked during URL ref minting, and where should a suite author look to decide if that is too conservative? (rig/transforms/url_refs.mld:70)
3. How does `get_webpage_via_ref` prevent a blocked or forged `url_ref` handle from being dereferenced? (rig/workers/resolve.mld:93)
4. Why does the no-untrusted-URLs guard cover only `before untrusted` and not the commented `before influenced` case? (rig/policies/url_output.mld:40)
5. Where are compose output validators wired into the actual compose retry path, since the validator module exports defaults but compose dispatch only checks malformed JSON? (rig/validators/output_checks.mld:229)
6. How are lifecycle logs and LLM call logs kept from becoming proof-bearing or authorization inputs after they serialize potentially sensitive prompts and outputs? (rig/lifecycle.mld:7)
