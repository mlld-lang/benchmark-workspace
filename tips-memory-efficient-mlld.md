# Tips for memory-efficient mlld programs

Practical lessons from the c-63fe rig state-projection rework. These are not style preferences — each one corresponds to a specific bug, OOM, or measured regression on the benchmark.

## Why memory matters here

mlld values are `StructuredValue` wrappers carrying `.text`, `.data`, and `.mx` (metadata: labels, factsources, projection, security). Every transformation that materializes data drops wrappers; every wrapper that survives carries its full security + provenance trail. Long-running sessions (planner with 20+ tool calls, growing resolved state) accumulate wrappers fast — a single travel session has hit 4+ GB heap before the OOM-killer fired.

The trade-off is real:
- **Wrappers must survive proof boundaries** (factsources, source-class checks, policy compilation).
- **Wrappers cost memory.** Each non-trivial value carries security labels, taint, source paths, projection metadata, factsources — easily 1-5KB of overhead per leaf field.
- **Materializing at the wrong boundary** (JS, JSON, object spread) silently strips metadata AND duplicates data into a fresh allocation.

## Principles

### 1. Spread is a metadata stripper

`{ ...obj, key: value }` materializes the spread into plain data. All wrappers, factsources, and security labels on the original keys are stripped.

```mlld
>> WRONG — strips factsources from every value in @ctx.by_handle
let @nextByHandle = { ...@ctx.by_handle, [@handleKey]: @entry }

>> RIGHT — build a list of pairs and let @pairsToObject preserve wrappers
let @nextPairs = @ctx.pairs.concat([{ key: @handleKey, value: @entry }])
=> @pairsToObject(@nextPairs)
```

This bit the c-63fe Phase 2.0 implementation. The merge built `by_handle` via spread; the `session-resolved-factsources-survive-boundary` test failed; the fix was switching to `@pairsToObject`. Same trap CLAUDE.md mlld-quickstart calls out, easy to miss in a hot path.

### 2. exe-returned `null` is a wrapper whose `.isDefined()` returns true

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

### 3. Don't drop into JS to traverse mlld objects

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

### 4. `for @x in @collection => @transform(@x)` produces a `for-result` envelope

When a `for` produces an array as a value (assigned to a `let`), the result has shape `{type: "array", name: "for-result", value: [...]}`. Iterating it again with `for` may not auto-unwrap. If you're chaining `for` over computed arrays, use a `loop` accumulator with explicit `.concat([@entry])` so the inner sequence stays as a plain mlld array.

This is what made the JS detour tempting in the first place — the `for`-of-`for` pattern doesn't always behave as expected on wrapped arrays.

### 5. Use `@valueField` for cross-shape field access

`@valueField(@obj, "key")` walks the wrapper chain (`mx.data[key]`, `data[key]`, `[key]`) and returns the first defined match. Direct `@obj.key` works on plain objects and most wrapped objects, but breaks on certain checkpoint-restored shapes. For internal helpers that traverse state, default to `@valueField`.

For *constructing* objects with computed keys, native `{ [@key]: @value }` works and preserves the value's wrapper.

### 6. Separate authoritative state from acceleration artifacts

The c-63fe rework lesson: durable proof-bearing state (`by_handle[handle] = entry` with full wrappers) stays canonical. Acceleration artifacts (`planner_cache.entries`) are a sidecar that can be rebuilt from authoritative state.

Why this matters:
- **Proof logic only reads authoritative state.** Cache invalidation bugs become "wrong projection rendered" not "wrong policy decision."
- **Cache can be aggressive without weakening security.** Worker projections are NOT cached (they may include raw tainted content per GPT decision D); planner projections are cached because they only contain pre-stripped fact handles + display fields.
- **Storage cost stays bounded.** The cache is one projection per record, not per call. Even with wrapper overhead, planner_cache scales O(N entries) not O(N entries × M calls).

### 7. Project once, reuse N times

Travel sessions render planner-visible state per planner tool call (15-30 times). Projecting fresh on every call is O(N entries × M calls). Eager-project-at-merge with version-keyed cache amortizes to O(N entries) total + O(1) per cache hit.

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

Watch the trade-off: eager projection re-projects ALL entries on every merge. Batch N merge projects N×M entries (super-linear). For very long sessions, *delta projection* (only project new+changed entries, splice into cache) is the next optimization.

### 8. Watch for super-linear allocation patterns

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

### 9. Suppress diagnostics when measuring

Rig's `diagnostics.mld` emits `[rig:diag:*]` lines on every dispatch boundary. For benchmark/measurement runs, redirect stderr to `/dev/null`. Diagnostic output can dominate the wall time and skew the picture.

```bash
mlld script.mld --no-checkpoint 2>/dev/null  # measurement
mlld script.mld --no-checkpoint 2>diag.log   # debugging
```

For the smallest possible memory footprint in production-like runs, also avoid `MLLD_TRACE=verbose` — `effects` is sufficient for most cases per DEBUG.md.

### 10. Don't materialize through `| @pretty` mid-pipeline

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
3. **Suppress stderr** (`2>/dev/null`) so diagnostics don't dominate the output.
4. **Compare per-stage growth slopes**, not just final values. Super-linear growth is the structural problem; flat reuse curves are the win.
5. **Run the same harness against the prior commit** for direct before/after numbers. Don't rely on rough recollection ("it was about 1.3GB").

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
