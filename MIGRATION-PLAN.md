# Migration Plan: clean Repo Adoption Of Policy Redesign And Structured Labels

## Overview

This guide is for `/Users/adam/mlld/clean`. It explains how to adopt the combined work from:

- `/Users/adam/mlld/mlld/plan-policy-box-urls-records-design-updates.md`
- `/Users/adam/mlld/mlld/plan-label-structure-implementation.md`

The migration has two coupled goals:

1. Land the policy / box / URL / records design updates completely.
2. Land the structured label model that separates security-gating state from inert provenance.

Do not migrate by cherry-picking isolated whack-a-mole security fixes from the old flat-label model. Treat those commits as regression requirements and reconcile them after the structured implementation is complete.

## Branch Context

At guide creation time:

- Source implementation repo: `/Users/adam/mlld/mlld`
- Source branch: `policy-redesign`
- Source head: `f90d47e77`
- Local target integration branch in source repo: `2.1.0`
- Local `2.1.0` head in source repo: `034af723e`
- Clean repo: `/Users/adam/mlld/clean`
- Clean repo branch: `main`
- Clean repo head: `096bcd2`

Re-check these values before migration:

```bash
git -C /Users/adam/mlld/mlld status --short
git -C /Users/adam/mlld/mlld branch --show-current
git -C /Users/adam/mlld/mlld rev-parse --short HEAD
git -C /Users/adam/mlld/mlld branch --list '2.1.0' 'policy-redesign' --format='%(refname:short) %(objectname:short)'

git -C /Users/adam/mlld/clean status --short
git -C /Users/adam/mlld/clean branch --show-current
git -C /Users/adam/mlld/clean rev-parse --short HEAD
```

## Source Documents To Copy Or Keep In Sync

Copy these into `/Users/adam/mlld/clean` or keep them explicitly referenced from the source repo:

- `plan-policy-box-urls-records-design-updates.md`
- `plan-label-structure-implementation.md`
- `spec-policy-box-urls-records-design-updates.md`
- `spec-label-structure.md`
- `docs/dev/DATA.md`
- `docs/dev/LLM-MCP.md`
- `docs/dev/RECORDS.md`
- `docs/dev/TESTS.md`
- `docs/dev/SECURITY.md`

If the clean repo intentionally keeps plans outside version control, record the source SHA and file paths in the migration commit message.

## Required Target Architecture

The clean repo must end with this value model:

- `mx.trust`: `"trusted" | "untrusted" | null`
- `mx.influenced`: boolean
- `mx.labels`: ordinary data/security labels only
- `mx.factsources`: structured proof handles
- `mx.sources`: inert provenance/audit strings
- `mx.urls`: inert URL provenance
- `mx.tools`: inert tool provenance

Trust and influenced must not be stored in `mx.labels`. Policy matching must synthesize transient tokens:

- `trust:trusted`
- `trust:untrusted`
- `influenced`

Code-routing labels such as `src:js`, `src:py`, `src:sh`, `src:node`, `src:template`, `src:exe`, `src:exec`, `src:dynamic`, `dir:*`, `op:*`, and `src:shelf:*` route to `mx.sources`. `src:file` remains a security-relevant data-load label.

## Migration Phases

### Phase 0 - Prepare The Clean Repo

1. Save local work:

```bash
git -C /Users/adam/mlld/clean status --short
```

2. Create a migration branch:

```bash
git -C /Users/adam/mlld/clean switch -c policy-structured-labels-migration
```

3. Record source refs:

```bash
git -C /Users/adam/mlld/mlld rev-parse HEAD > /tmp/mlld-source-head.txt
git -C /Users/adam/mlld/clean rev-parse HEAD > /tmp/mlld-clean-base.txt
```

Exit criteria:

- Clean repo is on a dedicated migration branch.
- Existing untracked local work is identified and not overwritten.

### Phase 1 - Policy / Box / URL / Records Design Updates

Implement the policy plan first unless the source branch already contains it completely.

Port or verify these areas:

- `core/policy/union.ts`: strict V2 policy normalization and migration errors.
- `core/policy/label-flow.ts`: combo label rules and hierarchical matching.
- `core/policy/fact-requirements.ts`: `labels.args` proof floors.
- Policy action runtime: centralized action execution for `enrich`, `transform`, `check`, and `apply`.
- Record refine/per-field actions: record coercion and dispatch metadata integration.
- Default box runtime behavior.
- Box config cleanup and retired syntax rejection.
- Importable `@mlld/policy/*` fragments replacing hardcoded public built-ins.
- Trace events and denial payloads for policy actions, default boxes, and record refine.
- Fixtures and docs for policy authoring migration.

Validation:

```bash
npm run build:fixtures
npx vitest run core/policy interpreter/policy interpreter/eval/records interpreter/eval/exec --reporter=verbose
npm test interpreter/interpreter.fixture.test.ts
```

Exit criteria:

- `policy-redesign-coverage.md` or equivalent clean-repo checklist shows complete policy design coverage.
- Retired public policy syntax has fixture coverage for migration errors.
- Record and box runtime behavior has direct Vitest and fixture coverage.

### Phase 2 - Structured Label Foundation

Port the structured descriptor model:

- `core/types/security.ts`
  - Add `trust`, `influenced`, and `factsources`.
  - Keep `sources`, `urls`, and `tools` top-level and inert.
  - Add `descriptorPolicyMatchSet`.
  - Normalize legacy `trusted`, `untrusted`, and `influenced` tokens into structural fields.
  - Route code/source labels into `sources` except `src:file`.
- `core/types/variable/VariableTypes.ts`
- `core/types/variable/VarMxHelpers.ts`
- `core/types/variable/VariableMetadata.ts`
- `interpreter/utils/structured-value.ts`
- `core/types/provenance/ExpressionProvenance.ts`

Validation:

```bash
npx vitest run tests/core/security-descriptor.test.ts core/types/variable/VariableFactories.test.ts interpreter/utils/structured-value.test.ts interpreter/utils/field-access.test.ts --reporter=verbose
```

Exit criteria:

- Trust/influenced are never persisted into `mx.labels`.
- `mx.taint` exists only as a compatibility view.
- Serialization/deserialization preserves all channels.

### Phase 3 - Policy Matching And Flow

Update policy matching to use synthetic match-time tokens:

- `core/policy/fact-labels.ts`: hierarchical label matching.
- `core/policy/label-flow.ts`: match against synthesized trust/influenced tokens.
- `core/policy/union.ts`: normalize bare `trusted` and `untrusted` policy keys to `trust:*`.
- `core/policy/standard-library.ts`: use structured trust keys.
- `interpreter/policy/PolicyEnforcer.ts`: remove hardcoded default LLM/untrusted cascade; apply policy actions only.

Validation:

```bash
npx vitest run core/policy/label-flow.test.ts core/policy/standard-library.test.ts core/policy/union.test.ts interpreter/policy/PolicyEnforcer.test.ts interpreter/policy/dataflow-cascade.test.ts --reporter=verbose
```

Exit criteria:

- `known` matches `known:internal`; `known:internal` does not match `known`.
- `trust:untrusted+llm` can match without storing `trust:untrusted` in labels.
- `labeling.unlabeled` is no longer load-bearing for structured trust propagation.

### Phase 4 - Runtime Boundaries

Port runtime call sites that previously merged flat taint:

- Var assignment and interpolation.
- Exec invocation and return label modifications.
- Run command/code execution.
- Show/output/effect descriptors.
- Imports, module export serialization, dynamic payload modules.
- Environment security snapshots and ambient `@mx`.
- Guard pre-hooks and guard candidate selection.
- Runtime trace envelopes.
- SDK execute payload labels.

Rules:

- Field-local descriptors win over parent aggregate smearing.
- Environment snapshots can carry audit/context fields into outputs, but must not downgrade field trust.
- Dynamic payload fields are classified only by explicit `payloadLabels`.
- Code execution provenance is audit/source metadata, not security-gating labels.

Validation:

```bash
npx vitest run sdk/execute.test.ts tests/interpreter/security-metadata.test.ts tests/interpreter/hooks/guard-pre-hook.test.ts interpreter/runtime-trace.test.ts interpreter/eval/import/variable-importer/module-export-serializer.test.ts --reporter=verbose
```

Exit criteria:

- SDK payload named imports, namespace imports, and direct `@payload.field` reads preserve per-field trust.
- Imported module exports do not inherit unrelated ambient labels.
- Guard and trace surfaces expose structured trust/influenced fields.

### Phase 5 - Records, Shelves, And LLM/MCP

Port record and shelf behavior:

- `interpreter/eval/records/coerce-record.ts`: fact/trusted-data fields become trusted; untrusted-data fields remain untrusted.
- Record display projection: content-derived aggregate descriptor after projection.
- Shelves: store field-local descriptors only; derive aggregate descriptors on read/projection.
- LLM bridge: mark outputs influenced when policy actions classify them, not by global cascade.
- MCP bridge: use read projection and canonical handle resolution; do not materialize hidden runtime values.

Validation:

```bash
npx vitest run interpreter/eval/records/coerce-record.test.ts interpreter/eval/shelf.test.ts interpreter/eval/session.test.ts interpreter/eval/tools-collection.test.ts interpreter/eval/field-provenance-flow.test.ts --reporter=verbose
```

Exit criteria:

- Fact fields and trusted data fields do not inherit sibling untrusted state.
- Shelf round trips preserve fact sources and field trust.
- LLM/MCP outputs use structured channels consistently.

### Phase 6 - Fixtures, Docs, And User-Facing Migration

Update docs and fixtures:

- `docs/dev/SECURITY.md`
- `docs/dev/DATA.md`
- `docs/dev/RECORDS.md`
- `docs/dev/LLM-MCP.md`
- Policy docs under `docs/src/atoms/`
- Security fixtures under `tests/cases/security/**`
- Record and policy fixtures under `tests/cases/feat/**` and `tests/cases/exceptions/**`

Regenerate fixtures:

```bash
npm run build:fixtures
npm test interpreter/interpreter.fixture.test.ts
```

Exit criteria:

- Fixture expectations use `mx.trust`, `mx.influenced`, and `mx.sources` correctly.
- User docs no longer teach trust/influenced as labels.
- Retired syntax examples have explicit migration coverage.

### Phase 7 - Whack-A-Mole Fix Reconciliation

After the structured implementation passes focused validation, triage these commits by intent. Do not apply their old code blindly.

Likely superseded by construction:

- `955e63628` - shelf trust refinement round-trip
- `e7793cce5` - inherited ambient labels in child frames
- `367ccf0eb` - exec routing taint and label proofs
- `53bd03591` - module import source/file/dir taint split
- `e8ff25521` - record coercion trust refinement
- `034af723e` - whole-object input field taint
- `bbcc3d1af` - public provenance label semantics
- `6593af2bc` - provenance descriptor inventory
- `776c0579e` - security metadata propagation
- `975a0ff76` - provenance overhead

Partially superseded; keep invariant tests:

- `4a27abee4` - influenced cascade near-miss invariants
- `dfa8d5c1b` - influenced cascade narrowed to provenance evidence
- `f3dd43663` - `src:file` data-load and code-exec routing split
- `7d7399dbc` - session-seeded shelf bridge writes
- `8b1c43576` - untrusted LLM influenced rule on payload/nested exe blocks

Bench-side clean commits that should become unnecessary:

- `096bcd2` - elevate `@deriveAttestation.payload` to `data.trusted`
- `f168037` - banking sender refinement to trusted fields

For each commit:

```bash
git -C /Users/adam/mlld/mlld show --stat --oneline <sha>
git -C /Users/adam/mlld/mlld branch --contains <sha>
git -C /Users/adam/mlld/clean branch --contains <sha>
```

Record disposition:

- `test-only`: port or preserve regression test only.
- `refactor-invariant`: implement the invariant in the structured path.
- `merge-code`: independent fix; merge normally.
- `no-op`: fully impossible under structured model and already covered.

Exit criteria:

- Every listed commit has a recorded disposition in the migration PR/commit message.
- No cherry-picked code reintroduces routing labels as security labels or ambient label inheritance.

### Phase 8 - Final Validation

Run the full release-level checks from the clean repo:

```bash
npm run build
npm run build:fixtures
npm test
```

If the repo has language-server or docs-token validation scripts enabled, run them too:

```bash
npm run test:lsp
npm run docs:validate
```

Use only scripts that exist in `package.json`; do not invent missing commands.

Exit criteria:

- Build passes.
- Fixture generation is clean.
- Full test suite passes.
- Remaining diffs are intentional implementation, docs, fixture, or migration-guide changes.

## Rollback Plan

Before merge:

```bash
git -C /Users/adam/mlld/clean status --short
git -C /Users/adam/mlld/clean diff --stat
```

To abandon only the migration branch:

```bash
git -C /Users/adam/mlld/clean switch main
git -C /Users/adam/mlld/clean branch -D policy-structured-labels-migration
```

To keep the branch but undo a bad commit:

```bash
git -C /Users/adam/mlld/clean revert <commit>
```

Avoid `git reset --hard` unless explicitly approved, because the clean repo contains untracked local work.

## Merge Guidance

Preferred final path:

1. Complete implementation and validation on the migration branch.
2. Rebase or merge latest `2.1.0` into the migration branch.
3. Resolve conflicts in favor of structured channels when old whack-a-mole fixes touch the same paths.
4. Re-run Phase 8.
5. Merge migration branch to `2.1.0`.
6. Only then merge or fast-forward the clean repo branch as appropriate.

Commit message checklist:

- Source repo SHA and branch.
- Clean repo base SHA.
- Both plan filenames.
- Whack-a-mole disposition summary.
- Validation commands and pass/fail result.

## Completion Checklist

- [ ] Policy / box / URL / records design updates complete.
- [ ] Structured label channels complete.
- [ ] `mx.sources`, `mx.urls`, and `mx.tools` are inert for security checks.
- [ ] Trust/influenced participate through synthetic match-time tokens only.
- [ ] Dynamic payload and module imports preserve field-local descriptors.
- [ ] Records and shelves preserve field metadata and derive aggregates from contents.
- [ ] Docs and fixtures migrated.
- [ ] Whack-a-mole commits reconciled by intent.
- [ ] `npm run build` passes.
- [ ] `npm run build:fixtures` passes.
- [ ] `npm test` passes.
