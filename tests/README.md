# clean/tests — mlld test framework

## Thesis

> A test is a value, produced by an exe that returns `{ ok, detail }`. A suite is a record. The runner is plain mlld.

No metaprogramming, no autodiscovery — explicit imports and explicit suite construction.

## Which test shape do I want?

| You want to… | Use |
|---|---|
| Assert on a primitive's behavior given an input | Plain assertion test (`assert.mld` helpers) |
| Assert that a guarded operation gets denied by the policy/firewall | Plain assertion test with the `when [denied]` recipe |
| Assert on multi-turn agent behavior, state accumulation, sequencing | Scripted-LLM test (`lib/mock-llm.mld`) |
| Assert that a multi-turn attack is blocked by the rig firewall | Scripted-LLM test that asserts on a denied/error step |
| Assert on what an LLM *does* with a real prompt | Worker test (`rig/tests/workers/`, separate harness) |
| Assert on end-to-end utility | Bench task |

## File layout

```
tests/
  assert.mld                  Assertion helpers (@assertOk, @assertEq, etc.)
  runner.mld                  Suite/group construction + @runSuites runner
  framework.mld               DEPRECATED — tombstone, do not import
  framework.tests.mld         Self-tests for assertion helpers
  framework.runner.tests.mld  Self-tests for the runner
  index.mld                   Default runner — plain assertion suites
  scripted-index.mld          Scripted-LLM runner (loaded by run-scripted.py)
  run-scripted.py             Python wrapper that wires MCP for scripted runs
  lib/
    mock-llm.mld              Re-export of mock-LLM harness + session schema
  suites/
    _template.mld             Copy-paste template for plain assertion suites
    rig/                      (future: ported rig suites)
    bench/                    (future: bench-side tests)
  suites-scripted/
    _template.mld             Copy-paste template for scripted-LLM suites
```

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

See `rig/tests/index.mld:957-981` for working examples in the existing test gate.

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
mlld clean/tests/index.mld --no-checkpoint

# Skip slow suites/groups
SKIP_SLOW=1 mlld clean/tests/index.mld --no-checkpoint
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

- **`tests/index.mld`** — imports only `suites/` (no MCP). Plain `mlld tests/index.mld` always works.
- **`tests/scripted-index.mld`** — imports `suites-scripted/` (which can import bench domain tools). Only loaded by `run-scripted.py`, which has MCP wired up.

### Writing a scripted suite

1. `cp tests/suites-scripted/_template.mld tests/suites-scripted/<your-suite>.mld`
2. Pick the bench domain you're testing against (workspace / travel / banking / slack). Update the `import { @records } from "../../bench/domains/<suite>/records.mld"` and `@tools` lines to match.
3. Update the agent build (`@rig.build({ suite: "...", ... })`) to match the chosen domain.
4. Write test exes that invoke `@runScriptedQuery(query, script)` (the call-site helper from the template) with a tool-call script.
5. Group them with `@group(..., { slow: true, ticket: "c-..." })`. Scripted groups should always be marked slow.
6. `export { @<your>SuiteName }`.
7. Add an import line to `tests/scripted-index.mld` (NOT `tests/index.mld` — scripted suites must not be loaded by the plain runner because they import bench tools that need MCP):
   ```mlld
   import { @<your>SuiteName } from "./suites-scripted/<your-suite>.mld"
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

Each scripted run targets one bench suite (workspace/travel/banking/slack) because the MCP env is per-suite. `run-scripted.py --suite <name>` picks which env to wire up. `--task-id <id>` overrides the default seed task (defaults are in `run-scripted.py:DEFAULT_TASK_ID`); use it when a test needs a specific AgentDojo env state (e.g., a task whose initial inbox contains an attack message). If you need multiple suites in one CI cycle, run the wrapper once per suite. Scripted suites that don't match the active env will fail at import — keep one bench domain's tools per `suites-scripted/` file.

## How to add a new suite

1. `cp tests/suites/_template.mld tests/suites/<your-suite>.mld`
2. Edit imports, write test exes, build your suite
3. Add one line to `tests/index.mld`:
   ```
   import { @<your>Suite } from "./suites/<your-suite>.mld"
   ```
   And add `@<your>Suite` to the `@suites` array.
4. Run: `mlld tests/index.mld --no-checkpoint`

## How to port an existing suite from `rig/tests/index.mld`

1. Find the topic cluster (marked by `>>` comment headers)
2. Create a new file: `tests/suites/rig/<topic>.mld`
3. For each `@check(id, ok, detail)` in the cluster:
   - Create an `exe @test<Description>() = [...]` that returns an assertion record
   - Setup variables go inside the exe as `let` (block-scoped, not leaked)
   - Use `@assertEq` instead of manually constructing detail strings
4. Group tests by subtopic with `@group`
5. Build `@suite`, export it
6. Import in `index.mld`

Key differences from the old pattern:
- Setup, assertion, and identity are in ONE place (the exe), not 4000 lines apart
- No manual `detail` string construction — `@assertEq` auto-formats
- No module-level pollution — everything is scoped to the exe
- xfail is a group/suite-level opt, not a string-prefix hack on the id
- Tickets are an opt field, not embedded in the id

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
mlld clean/tests/index.mld --no-checkpoint

# Skip slow groups (when scripted runs are folded into the default loop)
SKIP_SLOW=1 mlld clean/tests/index.mld --no-checkpoint

# Scripted-LLM suites (requires AgentDojo env)
uv run --project bench python3 clean/tests/run-scripted.py
uv run --project bench python3 clean/tests/run-scripted.py --suite travel

# Framework self-tests
mlld clean/tests/framework.tests.mld --no-checkpoint
mlld clean/tests/framework.runner.tests.mld --no-checkpoint

# Single suite standalone (works because suite files have a runnable tail)
mlld clean/tests/suites/_template.mld --no-checkpoint
```

## Validating

```bash
mlld validate clean/tests/assert.mld
mlld validate clean/tests/runner.mld
mlld validate clean/tests/index.mld
mlld validate clean/tests/lib/mock-llm.mld
```
