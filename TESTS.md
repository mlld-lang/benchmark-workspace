# clean tests — mlld test framework

This is the canonical guide for testing in `clean/`. Tests live under `tests/`.

## Thesis

> A test is a value, produced by an exe that returns `{ ok, detail }`. A suite is a record. The runner is plain mlld.

No metaprogramming, no autodiscovery — explicit imports and explicit suite construction.

## Quick reference

```bash
# Zero-LLM invariant gate (must pass; ~10s)
mlld tests/index.mld --no-checkpoint

# Scripted-LLM tests (deterministic multi-turn, no LLM, requires AgentDojo env; ~15s)
uv run --project bench python3 tests/run-scripted.py --suite workspace
uv run --project bench python3 tests/run-scripted.py --suite travel

# Live-LLM worker tests (real LLM calls, ~50s, costs ~$0.05) — separate tier
mlld tests/live/workers/run.mld --no-checkpoint

# Framework self-tests
mlld tests/framework.tests.mld --no-checkpoint
mlld tests/framework.runner.tests.mld --no-checkpoint
```

## Three test tiers

| Tier | Determinism | LLM | Cost | Runner | Where |
|---|---|---|---|---|---|
| **Zero-LLM invariant** | deterministic | none | $0 | `tests/index.mld` (the new framework) | `tests/rig/`, `tests/bench/` |
| **Scripted-LLM** | deterministic | mocked | $0 (uses MCP infra) | `tests/run-scripted.py` → `tests/scripted-index.mld` | `tests/scripted/` |
| **Mutation coverage** | deterministic | none | $0 | `tests/run-mutation-coverage.py` | mutation registry inline in the script |
| **Live-LLM** | stochastic | real | ~$0.05 | `tests/live/workers/run.mld` (separate harness) | `tests/live/workers/` |

Live-LLM tests have a different contract (scoreboard, model comparison, parallel cost) and remain in `tests/live/`. They predate this framework and may be folded in later under their own runner. For now, treat them as a separate tier.

## Which test shape do I want?

| You want to… | Use |
|---|---|
| Assert on a primitive's behavior given an input | Plain assertion test (`assert.mld` helpers) |
| Assert that a guarded operation gets denied by the policy/firewall | Plain assertion test with the `when [denied]` recipe |
| Assert on multi-turn agent behavior, state accumulation, sequencing | Scripted-LLM test (`lib/mock-llm.mld`) |
| Assert that a multi-turn attack is blocked by the rig firewall | Scripted-LLM test that asserts on a denied/error step |
| Prove that a security test actually catches its claimed defense | Add a mutation entry in `tests/run-mutation-coverage.py` |
| Assert on what an LLM *does* with a real prompt | Worker test (`tests/live/workers/`, separate harness) |
| Assert on end-to-end utility | Bench task |

## File layout

```
tests/
  assert.mld                  Assertion helpers (@assertOk, @assertEq, etc.)
  runner.mld                  Suite/group construction + @runSuites runner
  framework.mld               DEPRECATED — tombstone, do not import
  framework.tests.mld         Self-tests for assertion helpers
  framework.runner.tests.mld  Self-tests for the runner
  index.mld                   Default runner — zero-LLM suites
  scripted-index.mld          Scripted-LLM runner (loaded by run-scripted.py)
  scripted-index-<suite>.mld  Per-suite scripted runners (banking/slack/travel/workspace)
  run-scripted.py             Python wrapper that wires MCP for scripted runs
  _template.mld               Copy-paste template for plain assertion suites
  fixtures.mld                Shared records, tools, sample state used by ported rig suites
  imported-tools-fixture.mld  Imported-tools fixture used by tool-metadata tests
  lib/
    mock-llm.mld              Re-export of mock-LLM harness + session schema
    security-fixtures.mld     State factories for security tests (@stateWithExtracted, etc.)
  rig/                        Zero-LLM suites testing the rig framework
    <topic>.mld               One file per topic cluster
  bench/                      Zero-LLM suites testing bench-domain logic (sparse for now)
  scripted/                   Scripted-LLM suites (run via run-scripted.py + MCP)
    _template.mld             Template for scripted-LLM suites
    security-<suite>.mld      Security tests against bench domains
  live/                       Live-LLM tier — real LLM calls, separate runner
    workers/run.mld           Worker LLM tests with scoreboard.jsonl (~50s, ~$0.05)
    flows/                    Flow integration tests
    patterns/                 Pattern integration tests
    helpers.mld               Test helpers used by flows/ and patterns/
    llm/lib/opencode/         Opencode harness utility
```

### Where does my test go?

- Testing rig framework primitives (intent, runtime, workers, orchestration, transforms, validators, tooling) → `tests/rig/`
- Testing bench-specific logic (classifiers, exemplars, records) without LLM calls → `tests/bench/`
- Testing multi-turn agent behavior or attack scripts (uses bench domain tools) → `tests/scripted/`
- Testing what an LLM *does* with a real prompt → `tests/live/workers/` (separate live-LLM tier, not folded in yet)

### Why assert.mld and runner.mld are separate

mlld's static circular-reference detector flags `@runSuites -> test exe -> @assertOk` as a cycle when they're in the same import chain. Splitting assertion helpers from the runner avoids the false positive.

**Always import directly:**
```mlld
import { @assertOk, @assertEq } from "./assert.mld"
import { @suite, @group, @runSuites } from "./runner.mld"
```

**Never import from `framework.mld`** — it's a deprecated re-export that triggers the cycle detector.

## Framework API

### Assertion helpers (from `assert.mld`)

Each returns `{ ok: bool, detail: string }`.

| Helper | Purpose | Example |
|--------|---------|---------|
| `@assertOk(cond, detail)` | Boolean condition (escape hatch) | `@assertOk(@x > 0, "positive")` |
| `@assertEq(actual, expected)` | Structural deep-equality | `@assertEq(@result, 42)` |
| `@assertEqLabeled(a, e, label)` | Same with label prefix in detail | `@assertEqLabeled(@n, 2, "count")` |
| `@assertNeq(a, notExpected)` | Structural inequality | `@assertNeq(@result, "error")` |
| `@assertContains(haystack, needle)` | Substring or array element | `@assertContains(@list, "item")` |
| `@assertHas(record, key)` | Key-presence (null-tolerant) | `@assertHas(@obj, "name")` |

**Notes on `@assertHas`:** Key-presence test — a field set to `null` still counts as present. If you need non-null, use `@assertNeq(@r.field, null)`.

**Notes on deep equality:** mlld's native `==` is reference-equality for objects. `@assertEq` uses a JS deep-equality helper (`@deepEq`) for structural comparison.

**Guard/policy denial tests:** mlld's `denied` handler only catches denials in the immediate exe scope, so denial tests can't wrap the operation in `@assertOk(...)` or call into a helper exe — both shift the scope. Write the pattern directly in the test exe:
```mlld
exe @testMyDenial() = when [
  denied => { ok: true, detail: "denied as expected" }
  * => [
    let @_ = <operation that should be denied>
    => { ok: false, detail: "expected denial but operation succeeded" }
  ]
]
```

Note the test exe returns the assertion record shape `{ ok, detail }` directly — same contract as the assertion helpers. The `when [denied]` arm fires when any step inside `*` triggers a guard/policy denial in the same scope; the success arm fires only if the operation runs without being denied (i.e., the test should fail).

**Asserting on the denial reason.** The `denied` handler has access to `@mx.guard.reason` and `@mx.guard.name`. To assert *which* rule fired, capture them and check downstream:

```mlld
exe @testCorrectGuardFires() = when [
  denied => when [
    @mx.guard.reason.includes("no_secret_exfil") => { ok: true, detail: `denied by @mx.guard.name` }
    * => { ok: false, detail: `denied but wrong rule: @mx.guard.reason` }
  ]
  * => [
    let @_ = <operation that should be denied>
    => { ok: false, detail: "expected denial" }
  ]
]
```

For working examples, see `tests/rig/execute-worker-policy.mld` (`testInputRecordAllowlistReject` and siblings).

**Dual-path denial pattern (c-a873 robustness).** When other suites have already imported `tests/fixtures.mld`, `with { policy: ... }` calls can return an *error envelope* instead of throwing a `denied` event. Both surfaces carry the same `code` and `phase` fields. Tests that need to be robust across import order should accept either:

```mlld
exe @testInputRecordAllowlistReject() = when [
  denied => when [
    @mx.guard.code == "allowlist_mismatch" && @mx.guard.phase == "dispatch" => { ok: true, detail: "denied (event)" }
    * => { ok: false, detail: `denied but wrong code/phase: @mx.guard.code/@mx.guard.phase` }
  ]
  * => [
    let @callResult = @policySectionTools.send_email(@rejectedRecipient, "hi") with { policy: @builtPolicy.policy }
    => when [
      @callResult.ok == false && @callResult.code == "allowlist_mismatch" && @callResult.phase == "dispatch" => { ok: true, detail: "denied (envelope)" }
      * => { ok: false, detail: `expected denial, got: @callResult | @pretty` }
    ]
  ]
]
```

This is needed because `tests/fixtures.mld` activates global state on import that flips the denial surface. Until the underlying mlld bug (c-a873) is fixed, security tests that run alongside other suites should use the dual-path pattern.

### Suite construction (from `runner.mld`)

| Helper | Purpose |
|--------|---------|
| `@suite(name, groups, opts)` | Top-level container |
| `@group(name, tests, opts)` | Named cluster of test exes |
| `@xfailGroup(name, tests, opts)` | Sugar: `@group` with `xfail: true` |
| `@runSuites(suites)` | Walk suites, invoke tests, return results |

`opts` is always required (pass `{}` for no opts). Supported fields: `ticket`, `xfail`, `notes`, `slow`.

### Suite-level opts propagation

Suite-level opts merge into group-level opts:
- **ticket**: group overrides suite; suite is the fallback when group has none
- **notes**: same fallback logic as ticket
- **xfail**: OR logic — suite or group xfail is enough
- **slow**: OR logic — suite or group slow is enough

```mlld
var @s = @suite("name", [
  @group("g", [@test1], {}),             >> inherits ticket from suite
  @group("g2", [@test2], { ticket: "c-override" })  >> group ticket wins
], { ticket: "c-suite" })
```

### Slow groups

Groups or suites with `{ slow: true }` in opts:
- Get wall-time measurement (printed in `timingLines`)
- Are skipped when `SKIP_SLOW=1` env var is set
- Still fail the gate when not skipped — `slow` is categorization, not tolerance

```bash
# Run everything including slow
mlld tests/index.mld --no-checkpoint

# Skip slow suites/groups
SKIP_SLOW=1 mlld tests/index.mld --no-checkpoint
```

### Runner results

`@runSuites` returns:
- `results` — all `{ id, ok, detail, xfail, ticket, notes, slow }` records
- `passes` — passing, non-xfail tests
- `fails` — failing, non-xfail tests (exit 0 iff empty)
- `xfails` — failing, xfail-marked tests (expected)
- `xpasses` — passing, xfail-marked tests (unexpected — might need ticket update)
- `skippedSlow` — count of slow suites/groups skipped (when `SKIP_SLOW=1`)
- `report` — flat one-line-per-test string, greppable
- `xpassNudge` — non-empty string when xpasses exist, explaining what to do
- `skippedLine` — non-empty string when suites were skipped, explaining why
- `timingLines` — array of "suite/group: N ms" strings for slow groups

### Test exe naming

Test exes should be named `@test<CamelCaseDescription>`. The runner derives the leaf id by:
1. Reading the exe's `.mx.name`
2. Stripping the `test` prefix
3. Lowercasing the first character

Example: `@testMergeDedupByHandle` → id leaf `mergeDedupByHandle`

## Scripted-LLM testing

Scripted-LLM tests verify multi-turn agent behavior against a deterministic tool-call script — no LLM calls, but the real rig pipeline (state merge, projection, planner cache, firewall) runs end-to-end. Useful for state accumulation, sequencing, and security-firewall tests.

### Running

```bash
uv run --project bench python3 tests/run-scripted.py                 # default: workspace
uv run --project bench python3 tests/run-scripted.py --suite travel  # different env
```

The wrapper activates the AgentDojo Python env, builds an MCP server command via `src/host.py:_build_local_mcp_command`, and invokes the mlld SDK with `mcp_servers={'tools': <cmd>}` so domain `tools.mld` imports resolve cleanly. `tests/scripted-index.mld` then runs whichever suites it imports.

The wrapper exits 1 on any test failure (parsed from a `__SCRIPTED_STATUS__:` marker line emitted by the index) and 0 on full success. Diagnostic output (`[rig:diag:...]`, etc.) is routed to stderr; the test report lands on stdout.

### Why a separate index/runner

The default `mlld tests/index.mld` runs from a plain shell with no MCP server reachable. Bench domain `tools.mld` files connect to MCP at *import* time, so any test file that imports `@tools` would fail under the default runner. Two indexes solve this:

- **`tests/index.mld`** — imports only `tests/rig/` and `tests/bench/` (no MCP). Plain `mlld tests/index.mld` always works.
- **`tests/scripted-index.mld`** — imports `tests/scripted/` (which can import bench domain tools). Only loaded by `run-scripted.py`, which has MCP wired up.

### Writing a scripted suite

1. `cp tests/scripted/_template.mld tests/scripted/<your-suite>.mld`
2. Pick the bench domain you're testing against (workspace / travel / banking / slack). Update the `import { @records } from "../../bench/domains/<suite>/records.mld"` and `@tools` lines to match.
3. Update the agent build (`@rig.build({ suite: "...", ... })`) to match the chosen domain.
4. Write test exes that invoke `@runScriptedQuery(query, script)` (the call-site helper from the template) with a tool-call script.
5. Group them with `@group(..., { slow: true, ticket: "c-..." })`. Scripted groups should always be marked slow.
6. `export { @<your>SuiteName }`.
7. Add an import line to `tests/scripted-index.mld` (NOT `tests/index.mld` — scripted suites must not be loaded by the plain runner because they import bench tools that need MCP):
   ```mlld
   import { @<your>SuiteName } from "./scripted/<your-suite>.mld"
   ```
   And add `@<your>SuiteName` to the `@suites` array in that file.
8. Run via the wrapper, with the matching `--suite`:
   ```bash
   uv run --project bench python3 tests/run-scripted.py --suite <suite>
   uv run --project bench python3 tests/run-scripted.py --suite <suite> --task-id <id>
   ```

The `with { session: @planner }` clause must be expanded at the call site, not hidden inside a closure-bearing helper — see the template's `@runScriptedQuery` for the canonical wrapper.

### Result shape

`@runScriptedQuery(query, script)` (which calls `@mockOpencode` under the hood) returns:

| Field | Meaning |
|---|---|
| `result.results` | Array of per-step return values, in script order |
| `result.lastResult` | Same as `result.results[result.results.length - 1]` |
| `result.index` | Number of steps executed |

Each step's return value is whatever the planner-tool wrapper produced. For a successful `resolve`/`resolve_batch`, that's a record like `{ status: "resolved", record_type: "...", count: N, records: [...], handles: [...] }`. For a step blocked by the framework (firewall reject, policy denial, malformed args), it's typically an error envelope `{ error: true, reason: "...", ... }` — read `tests/runtime.mld:@toolCallError` and the worker dispatch files (`rig/workers/<phase>.mld`) for the canonical shapes.

### Common scripted-LLM patterns

**Happy path** — single resolve, assert structure:
```mlld
let @script = [{ tool: "resolve", args: { tool: "list_files", args: {}, purpose: "..." } }]
let @r = @runScriptedQuery("query", @script)
=> @assertEq(@r.lastResult.status, "resolved")
```

**Expected denial** — assert a step that *should* be rejected by the firewall:
```mlld
exe @testDerivedControlArgRejected() = [
  let @script = [
    { tool: "resolve_batch", args: { ... seed state ... } },
    { tool: "execute", args: {
        tool: "send_email",
        args: { recipient: "<derived/extracted ref>" }   >> control-arg from untrusted source
    }}
  ]
  let @r = @runScriptedQuery("query", @script)
  let @last = @r.lastResult
  => @assertEq(@last.error, true)
]
```

For finer-grained assertions on the denial reason, add `@assertContains(@last.reason, "derived_control_arg")` etc.

**Multi-step attack with mid-script denial** — assert the chain stopped at step N:
```mlld
let @r = @runScriptedQuery("query", @script)
=> @assertEq(@r.results.length, 2)   >> only 2 of N steps ran before firewall halted
```

### Starting points (existing fixtures + reproducers)

Existing scripted runs that capture realistic shapes:

- `rig/test-harness/fixtures/workspace-list-files-tool-script.json` — single resolve, simplest possible
- `rig/test-harness/fixtures/ut19-tool-script.json` — 4-step travel script (resolve_batch + derive + compose), shows realistic multi-turn flow
- `rig/test-harness/run-ut19-mock.mld`, `run-workspace-list-files-mock.mld` — the underlying reproducers; the JSON shape they consume is the same one your script array uses

Crib the script structure from these when writing attack-shaped scripts. The fixture JSON's `script` field is `[{ tool, args }, ...]` — paste it directly into a `let @script = [...]` in mlld.

### Bench-suite scoping

Each scripted run targets one bench suite (workspace/travel/banking/slack) because the MCP env is per-suite. `run-scripted.py --suite <name>` picks which env to wire up. `--task-id <id>` overrides the default seed task (defaults are in `run-scripted.py:DEFAULT_TASK_ID`); use it when a test needs a specific AgentDojo env state (e.g., a task whose initial inbox contains an attack message). If you need multiple suites in one CI cycle, run the wrapper once per suite. Scripted suites that don't match the active env will fail at import — keep one bench domain's tools per `tests/scripted/` file.

## Mutation coverage for security tests

Scripted security tests assert that an attack-shaped tool sequence rejects (`@assertEq(@last.ok, false)`). That's necessary but not sufficient — `ok=false` only means *some* code path rejected. It doesn't prove the *specific defense the test docstring claims* actually fired. Tests can pass for the wrong reason: a malformed seed shape, a different rule catching the attack, or a compile short-circuit.

`tests/run-mutation-coverage.py` is the meta-test. For each registered defense:

1. Confirm the canonical baseline is green.
2. Apply a one-line mutation that disables the defense (e.g. `if @role == "control"` → `if false`).
3. Re-run the affected suites.
4. Compare the actual `[FAIL]` set to the `expected_fails` list.
5. Restore the file (always — `try/finally`).

A test that `expected_fails` lists but doesn't fail under the mutation is **fake coverage** — the test passes for some reason other than the defense it claims to verify. Either the seed is wrong, or another defense catches the attack first; investigate before the test ships.

Run the harness:

```bash
uv run --project bench python3 tests/run-mutation-coverage.py
uv run --project bench python3 tests/run-mutation-coverage.py --only source-class-firewall
```

Add a mutation when you add a security test:

1. Identify the line(s) in `rig/` that implement the defense your test exercises.
2. Add a `MUTATIONS` entry: `id`, `description`, `file`, `search`, `replace` (must match exactly once), `suites`, `expected_fails`.
3. Run the harness. The mutation is real if and only if the registry's `expected_fails` matches the actual fail set under mutation.
4. If your test isn't in the actual fail set, your test is passing for the wrong reason — fix the seed or strengthen the assertion before merging.

The registry is the canonical record of which security tests are mutation-verified. Tests not represented in any mutation's `expected_fails` are unverified and should be treated with the same skepticism as untested code.

## How to add a new suite

1. Pick the right directory:
   - Rig framework test → `tests/rig/<your-suite>.mld`
   - Bench-domain test (zero-LLM) → `tests/bench/<your-suite>.mld`
   - Scripted-LLM test → `tests/scripted/<your-suite>.mld`
2. `cp tests/_template.mld tests/<dir>/<your-suite>.mld`
3. Edit imports, write test exes, build your suite
4. Add one line to the matching index:
   ```
   import { @<your>Suite } from "./rig/<your-suite>.mld"     >> for tests/rig/
   import { @<your>Suite } from "./bench/<your-suite>.mld"   >> for tests/bench/
   import { @<your>Suite } from "./scripted/<your-suite>.mld" >> for tests/scripted/
   ```
   And add `@<your>Suite` to the `@suites` array.
5. Run: `mlld tests/index.mld --no-checkpoint` (or scripted runner for tests/scripted/)

## Things we explicitly don't do

- **No autodiscovery.** New suite = one import line in index.mld.
- **No describe/it nesting beyond suite/group.** Two levels covers everything.
- **No before/after hooks.** Fixtures are exes; call them inside the test.
- **No id-prefix special meanings.** xfail is a field. Tickets are a field.
- **No assertion-message DSL.** Helpers return `{ ok, detail }`. Custom messages: `@assertOk`.
- **No @assertDenies helper.** mlld's `denied` handler is scope-limited. Write the inline `when [denied]` pattern instead.

## Running

```bash
# Plain assertion suites
mlld tests/index.mld --no-checkpoint

# Skip slow groups (when scripted runs are folded into the default loop)
SKIP_SLOW=1 mlld tests/index.mld --no-checkpoint

# Scripted-LLM suites (requires AgentDojo env)
uv run --project bench python3 tests/run-scripted.py
uv run --project bench python3 tests/run-scripted.py --suite travel

# Framework self-tests
mlld tests/framework.tests.mld --no-checkpoint
mlld tests/framework.runner.tests.mld --no-checkpoint

# Single suite standalone (works because suite files have a runnable tail)
mlld tests/_template.mld --no-checkpoint
```

## Validating

```bash
mlld validate tests/
```

## Known issues / xfails

The current gate has 3 xfails. Treat the first as a permanent demo; the other two are real mlld bugs being tracked.

| xfail | Ticket | Type | Why |
|---|---|---|---|
| `template/known-broken/intentionallyFails` | c-9999 (placeholder) | demo | Permanent example in the template. Not a bug. |
| `xfail-and-null-blocked/.../uh1...UnicodeDashVariant` | c-bd28 | mlld bug | Selection-ref handle matching doesn't tolerate U+2011 non-breaking-hyphen variants of ASCII handles. |
| `named-state-and-collection/.../rescheduleDispatchSucceeds` | c-a873 | mlld bug | `policy.build`'s fact-mapping resolution drops when `tests/fixtures.mld` is imported first. Module-import side-effect on global policy-engine state. Affects denial surface (event ↔ envelope) too — handled in security tests via the dual-path pattern. |

When c-a873 is fixed at the mlld layer, the rescheduleDispatchSucceeds xfail can be flipped back to a regular test, and security tests using the dual-path pattern can be simplified to single-path (denied event only).
