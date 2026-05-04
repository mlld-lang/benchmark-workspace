# Tips for memory-efficient mlld programs

Practical lessons from the c-63fe rig state-projection rework. These are not style preferences — each one corresponds to a specific bug, OOM, or measured regression on the benchmark.

## Why memory matters here

mlld values are `StructuredValue` wrappers carrying `.text`, `.data`, and `.mx` (metadata: labels, factsources, projection, security). Many materialization boundaries (JS, JSON, object spread) drop wrappers; surviving wrappers carry the full security + provenance trail. Long-running sessions (planner with 20+ tool calls, growing resolved state) accumulate wrappers fast — a single travel session has hit 4+ GB heap before the OOM-killer fired.

The trade-off is real:
- **Wrappers must survive proof boundaries** (factsources, source-class checks, policy compilation).
- **Wrappers cost memory.** Wrapper overhead can be substantial per leaf in provenance-heavy rig state — security labels, taint, source paths, projection metadata, factsources accumulate per field.
- **Materializing at the wrong boundary** (JS, JSON, object spread) silently strips metadata AND duplicates data into a fresh allocation.

## Principles

### Spread is a metadata stripper

`{ ...obj, key: value }` materializes the spread into plain data. All wrappers, factsources, and security labels on the original keys are stripped.

```mlld
>> WRONG — strips factsources from every value in @ctx.by_handle
let @nextByHandle = { ...@ctx.by_handle, [@handleKey]: @entry }

>> RIGHT — build a list of pairs and let @pairsToObject preserve wrappers
let @nextPairs = @ctx.pairs.concat([{ key: @handleKey, value: @entry }])
=> @pairsToObject(@nextPairs)
```

This bit the c-63fe Phase 2.0 implementation. The merge built `by_handle` via spread; the `session-resolved-factsources-survive-boundary` test failed; the fix was switching to `@pairsToObject`. Same trap CLAUDE.md mlld-quickstart calls out, easy to miss in a hot path.

### exe-returned `null` is a wrapper whose `.isDefined()` returns true

When an exe returns `=> null`, the result is a *wrapped null* — `.isDefined()` reports true, masking degenerate output. Use `== null` for the actual null check.

```mlld
>> WRONG — early-returns even on cache miss because null is "defined"
let @cached = @cachedPlannerEntries(@bucket)
if @cached.isDefined() [ => @cached ]
=> @freshProjection

>> RIGHT
if @cached != null [ => @cached ]
=> @freshProjection
```

Same family as c-aed5 / c-4a08 — derive/extract returning null silently looking like success. Bit Phase 2.5 in the same way: every cache miss returned an empty cached array because `if @cached.isDefined()` was always true.

### Don't drop into JS to traverse mlld objects

JS auto-unwraps `StructuredValue` into plain data when values cross the `js {}` boundary. If the value re-enters mlld via the JS return, factsources and labels are gone — even on what looks like the same data.

```mlld
>> WRONG — JS sees {handle: "h1", ...} as plain data; returned entries
>> have lost their identity_value/field_values/value wrappers
exe @indexedBucketEntries(bucket) = js {
  const order = bucket.order;
  const out = [];
  for (const h of order) out.push(bucket.by_handle[String(h)]);
  return out;
}

>> RIGHT — mlld-native loop accumulator preserves wrappers
exe @indexedBucketEntries(bucket) = [
  let @rawOrder = @valueField(@bucket, "order") ?? []
  let @byHandle = @valueField(@bucket, "by_handle") ?? {}
  let @orderLength = ...
  let @resolved = loop(1000) [
    let @ctx = ...
    if @ctx.index >= @orderLength [ done @ctx.entries ]
    let @handle = @rawOrder[@ctx.index]
    let @entry = @valueField(@byHandle, @name(@handle))
    let @nextEntries = when [
      @entry.isDefined() => @ctx.entries.concat([@entry])
      * => @ctx.entries
    ]
    continue { ... }
  ]
  => @resolved
]
```

The exception: when the JS code only computes a scalar from the data (e.g., `@previewFields` extracting key names from an array's first object) and that scalar isn't proof-bearing, JS is fine. But never use JS to *return collections of mlld values intended to keep their wrappers*.

### `for @x in @collection => @transform(@x)` produces a `for-result` envelope

When a `for` produces an array as a value (assigned to a `let`), the result has shape `{type: "array", name: "for-result", value: [...]}`. Iterating it again with `for` may not auto-unwrap. If you're chaining `for` over computed arrays, use a `loop` accumulator with explicit `.concat([@entry])` so the inner sequence stays as a plain mlld array.

This is what made the JS detour tempting in the first place — the `for`-of-`for` pattern doesn't always behave as expected on wrapped arrays.

### Use `@valueField` for cross-shape field access

`@valueField(@obj, "key")` walks the wrapper chain (`mx.data[key]`, `data[key]`, `[key]`) and returns the first defined match. Direct `@obj.key` works on plain objects and most wrapped objects, but breaks on certain checkpoint-restored shapes. For internal helpers that traverse state, default to `@valueField`.

For *constructing* objects with computed keys, native `{ [@key]: @value }` works and preserves the value's wrapper.

### Separate authoritative state from acceleration artifacts

The c-63fe rework lesson: durable proof-bearing state (`by_handle[handle] = entry` with full wrappers) stays canonical. Acceleration artifacts (`planner_cache.entries`) are a sidecar that can be rebuilt from authoritative state.

Why this matters:
- **Proof logic only reads authoritative state.** Cache invalidation bugs become "wrong projection rendered" not "wrong policy decision."
- **Cache can be aggressive without weakening security.** Worker projections are NOT cached (they may include raw tainted content per GPT decision D); planner projections are cached because they only contain pre-stripped fact handles + display fields.
- **Storage cost stays bounded.** The cache is one projection per record, not per call. Even with wrapper overhead, planner_cache scales O(N entries) not O(N entries × M calls).

### Cache projections — pick the strategy that fits the call shape

Three strategies, in order of safety:

**Lazy version-keyed (default).** Build the projection on first read after `bucket.version` changes, then reuse. Cache misses cost one projection; subsequent reads on the same version are O(1). Safe when the projection is pure — no side effects, no external state.

**Eager at merge.** Pre-project at write time so reads are always cache hits. Wins when merges are rare relative to planner renders (e.g., a session with 5 resolves and 25 planner-visible renders). Loses when merges happen often or each merge requires re-projecting a growing bucket.

**Delta projection.** Only project newly-added or changed entries; splice into the existing cache. The right choice for long sessions that repeatedly merge one/few entries into a large bucket. Most code complexity, biggest win on travel-shape workloads.

The c-63fe rework shipped eager projection because the prototype showed it was 10× faster on synthetic loads. In production it still wins on time but trades memory: every merge projects the full bucket into a fresh planner_cache. Travel sessions with many small merges see this growth — delta projection is the next iteration.

```mlld
>> Cache shape: {version: number, entries: [...]}
>> Bucket carries {version: number, planner_cache: {version, entries}}
>> Cache hit when bucket.version == cache.version (no merge since)
exe @cachedPlannerEntries(bucket) = [
  if !@isResolvedIndexBucket(@bucket) [ => null ]
  let @cache = @valueField(@bucket, "planner_cache")
  ...
  if @cacheVersion != @bucketVersion [ => null ]
  ...
]
```

### Avoid append-one-to-growing-array loops

`@acc.concat([@entry])` repeated over a growing array copies the growing prefix on every iteration — classic O(N²). On a hot state path this is the most common path to super-linear memory.

```mlld
>> WRONG — N² copies; the prefix grows on every iteration
let @acc = loop(1000) [
  let @ctx = ...
  if done ...
  continue { entries: @ctx.entries.concat([@newEntry]) }
]

>> RIGHT — batch into a list of pairs, materialize once
let @pairs = for @item in @incoming => { key: `@item.handle`, value: @item }
=> @pairsToObject(@pairs)
```

When lookups/replacements dominate, an indexed structure (`{by_handle: {h1: entry, h2: entry, ...}}`) avoids the rebuild entirely.

### Watch for super-linear allocation patterns

The c-63fe Phase 3 measurement showed:
- batch 1 (40 entries): +30MB RSS
- batch 2 (80 entries): +80MB
- batch 3 (120 entries): +200MB
- batch 4 (160 entries): +750MB

Linear data growth (40 entries per batch) → super-linear memory growth. The cause: every merge re-projects the *full* bucket into planner_cache, AND every merge emits a fresh bucket value (no in-place mutation in mlld). So batch N copies N entries to a new bucket AND projects all N entries.

Diagnostics for this:
- Add per-stage `process.memoryUsage()` samples (use `js {}` for the syscall — read-only inspection, no value passing).
- Compare growth slope: linear growth is healthy. Quadratic or worse means you're rebuilding accumulating state.
- Suppress stderr (`mlld script.mld 2>/dev/null`) when measuring — `[rig:diag:*]` lines are large and slow.

### Heap limit is diagnostic, not an optimization

`MLLD_HEAP=6g` (or higher) lets a run complete past the default heap cap. That's useful for **confirming** "this is OOM pressure, not a logic failure" — if the run completes with more heap, the failure was capacity-sensitive, not algorithmic.

It is NOT proof the memory shape is acceptable. The c-63fe travel investigation completed with `MLLD_HEAP=6g` but underlying state was still growing super-linearly; the heap headroom only postponed the cliff. Fixing the growth pattern is the optimization; raising the heap is the workaround.

### Measure per process, not just suite aggregate

With `-p 20`, the OOM-killer fires per-process, not per-suite. Total container RSS may sit comfortably under the cap while individual mlld/node processes cross the danger zone. When investigating an OOM:

- Capture per-process peak heap and RSS, not just the parent's totals
- Look at the *worst* process in the fan-out, not the average
- Per-task timing matters too: a single long task whose memory keeps growing will OOM even when 19 short tasks would have been fine

### Operational measurement pattern

`MLLD_TRACE_MEMORY=1` is decoupled from `--trace effects` since the docs fix landed. Use it independently for memory profiling without paying the verbose-trace cost:

```bash
# Memory-only trace, larger heap to allow completion
MLLD_TRACE_MEMORY=1 MLLD_HEAP=6g \
  mlld script.mld --no-checkpoint 2>mem.log

# With trace file for post-run analysis
MLLD_TRACE_MEMORY=1 MLLD_TRACE_FILE=/tmp/run.jsonl \
  mlld script.mld --no-checkpoint
```

Diagnostic chatter can dominate wall time and skew memory peaks. For benchmark/measurement runs, redirect stderr to `/dev/null`. Use `MLLD_TRACE=effects` (default) over `verbose` unless you need unredacted content.

### Watch finalization spikes separately from steady-state growth

Memory peaks at `llm.call:finish`, checkpoint write, SDK result construction, or session-snapshot serialization may look like state growth but are different in kind: they're momentary materialization spikes around a session boundary that drop after the boundary completes.

Travel sessions that complete will sometimes show a large spike near `llm.call:finish` then a drop as the session closes. This is wrapper round-tripping through the SDK return path, not accumulating planner state. Distinguish:

- **Steady-state growth**: per-batch RSS that doesn't release between calls. Fix the merge/projection path.
- **Finalization spikes**: peaks near `:finish` / checkpoint / session snapshot that release. Fix the boundary serialization (or accept and budget heap).

Measure with and without checkpointing where possible (`--no-checkpoint`) to separate steady-state from boundary effects.

### Keep planner display modes intentionally small

Before optimizing wrappers, reduce what's projected. Long raw fields, reviews, notes, tool transcripts, and tainted payloads should stay out of planner-visible display unless there's a security/design reason they must be there.

```mlld
record @restaurant = {
  facts: [id_: string, name: string],
  data: {
    trusted: [city: string?, cuisine: string?, rating: number?],
    untrusted: [reviews: string?, notes: string?]   >> 2KB+ each
  },
  display: {
    role:planner: [{ ref: "id_" }, { ref: "name" }, city, cuisine, rating],
    >> reviews + notes intentionally absent — planner doesn't need them
    role:worker: [{ ref: "id_" }, { ref: "name" }, city, cuisine, rating, reviews, notes]
  }
}
```

The planner sees the small fields; the worker sees content. Projection cache then stores only the small projection. Even with 1000 entries with 2KB reviews each, the planner cache holds ~1KB per entry, not 3KB.

### Don't eagerly materialize derivative structures

If a derivative data structure is computed once at build time but consumers can hit the source directly with cheap filtering, the materialization is dead weight on every build.

Found in workspace agent build: `validateConfig` was eagerly producing `routedTools` (a per-task tool routing index). But every consumer (dispatch helpers, doc generators) had already converged on filtering directly from the flat `agent.tools` catalog. `routedTools` only survived as a fallback that nobody hit.

Removing the eager build saved ~2s on every workspace agent setup — measurable on the build-only harness (`scripts/repro_workspace_build_agent.py` 12.3s → 10.0s).

The pattern: if a derivative structure exists "for performance" but the consumers don't use it, it's pure cost. Periodically grep the consumers; if every read does something like `for @t in @agent.tools when @taskNeedsTool(@t)`, the derivative is dead weight.

### Guard no-op work in hot paths

`finishPlannerTool` (called per planner step) invokes lifecycle helpers that write to `phaseLogFile` / `phaseStateFile` / `llmCallLogFile`. When those paths are null (the common bench case), the helpers were checking-and-returning *inside the shell body* — meaning a shell was still spawned per step just to discover there's nothing to write.

Splitting the helpers into mlld-side guards plus raw shell writers means null/empty paths return before any shell spawn. Cost on the hot path drops by hundreds of ms × N planner steps.

Pattern: any helper that is dispatch-frequent and conditionally a no-op should have the no-op check *outside* the syscall boundary. `if @paramIsEmpty [ => null ]` in mlld before invoking the shell/JS, not inside.

### Don't materialize through `| @pretty` mid-pipeline

`| @pretty` produces a STRING. All `.mx` metadata is gone; the only thing that survives downstream is whatever a JSON parse can recover from text. It's fine for debug `show` calls; it's wrong inside any chain that proceeds to `@parse` or treats the result as data.

```mlld
>> WRONG — strips wrappers; downstream policy checks see no factsources
let @serialized = @resolvedRecord | @pretty
let @reparsed = @serialized | @parse
=> @doSomethingThatNeedsFactsources(@reparsed)

>> RIGHT — pass the value directly
=> @doSomethingThatNeedsFactsources(@resolvedRecord)
```

Per DEBUG.md "Serialization is a one-way trip."

## Patterns for measurement

When refactoring a hot path:

1. **Build a synthetic harness in `tmp/`** that exercises the path at scale (4 batches × 40 entries minimum, 80+ for realistic). Mirror real record shapes — facts, trusted/untrusted data, display modes.
2. **Sample memory at each stage** via `js { return process.memoryUsage(); }`. Print RSS + heapUsed in MB.
3. **Use `MLLD_TRACE_MEMORY=1`** for memory-only tracing without the verbose-trace cost.
4. **Suppress stderr** (`2>/dev/null`) so diagnostics don't dominate the output.
5. **Compare per-stage growth slopes**, not just final values. Super-linear growth is the structural problem; flat reuse curves are the win.
6. **Watch per-process peaks under fan-out**, not just totals. The OOM-killer fires per-process at `-p N`.
7. **Distinguish steady-state from finalization spikes** — run with and without `--checkpoint` to separate them.
8. **Run the same harness against the prior commit** for direct before/after numbers. Don't rely on rough recollection ("it was about 1.3GB").

The c-63fe harness at `tmp/c63fe-state-projection-baseline/harness.mld` is a working template.

## When to use which abstraction

| Scenario | Pattern |
|---|---|
| Build dict from list of computed pairs | `@pairsToObject(@pairs)` — preserves wrappers |
| Build dict from a literal | Native `{ key: @value, [@computedKey]: @v2 }` |
| Read a field from possibly-wrapped object | `@valueField(@obj, "key")` |
| Read a field path with array indices | `@fieldPathSteps + @pathStepValue` |
| Detect a tagged shape | Sentinel field check (`_rig_bucket: "version"`) |
| Iterate a possibly-wrapped array | `@arrayItems` (generic) or `@bucketItems` (resolved-state-aware) |
| Cache an expensive projection | Side-by-side `{version: N, entries: [...]}` keyed off the source's own version |
| Check exe-returned null | `== null` (NOT `.isDefined()`) |
| Pass mlld value to JS for inspection only | OK — but don't return mlld-typed collections from JS |

## Related docs

- `CLAUDE.md` "Ticket Conventions D + E" — transcript-grounded diagnoses, full-denominator reporting
- `DEBUG.md` "Serialization is a one-way trip" — `| @pretty` and `@parse` strip metadata
- `labels-policies-guards.md` "JS/Python data boundary" — auto-unwrap behavior at language boundaries
- `mlld qs` "JS/Python data boundary" — `.keep` for crossing JS with metadata
- `~/mlld/mlld/tmp/rig-memory-repro/` — OOM agent's prototype + projection-repro harness
- `tmp/c63fe-state-projection-baseline/harness.mld` — production-rig measurement harness
