# Key/Hash Improvements — Punchlist

Migration plan for `~/mlld/clean` to consume the new mlld primitives `value.mx.key` (instance identity) and `value.mx.hash` (content fingerprint), and clean up the legacy hand-rolled identity machinery they replace.

## Context

mlld tickets m-d49a (extend record `key:` with composite/hash forms; expose `.mx.key`) and m-f947 (add `hash:` for content fingerprint; expose `.mx.hash`) have landed.

Both accessors are content-stable, deduplicated by canonical value, and exposed at the same `.mx.*` namespace as existing metadata. SHA-256 truncated to 8 hex chars. Auto-derive when `key:` / `hash:` is omitted: same canonical content yields the same key/hash within a session via the existing `ValueHandleRegistry.stableIndex`.

This unlocks a pile of cleanup in `~/mlld/clean`: hand-rolled identity heuristics, per-call handle volatility, positional fact-attestation fallbacks, and stale documentation/prompts that equate progress with handle strings.

## Identity model — old vs new

**Old**: rig synthesized identity per record via `@recordIdentityField` heuristic (look for `id`/`id_`/`*_id` field, else first fact field, else null) and built handle-shaped strings (`r_<recordType>_<keyPart>`) for bucket addressing. Bridge code per-domain minted synthetic per-call ids when records had no natural id (slack messages: `Date.now()+random+counter`). The planner fingerprint walked entry shapes to count fields as a proxy for content drift. Same-source correlation matched by handle string. Selection refs and policy attestation used `record:handle` and `fact:ref[position]` because there was no stable per-instance identity.

**New**: every record-coerced value carries `.mx.key` (identity) and `.mx.hash` (content fingerprint). The framework reads these directly. Identity is consistent across all consumers — shelf upsert, factsources `sourceRef`, planner correlation, selection refs, fingerprint detection — instead of each component re-deriving it.

## Two questions, two accessors

| Question | Compare |
|---|---|
| Same instance? | `a.mx.key == b.mx.key` |
| Same value? | `a.mx.hash == b.mx.hash` |
| Same instance, changed? | `a.mx.key == b.mx.key && a.mx.hash != b.mx.hash` |
| Different instance, same content? | `a.mx.key != b.mx.key && a.mx.hash == b.mx.hash` |

`key:` stays stable across legitimate field updates (Alice is still Alice when her email changes). `hash:` changes whenever any tracked field changes (Alice-with-old-email is a different value than Alice-with-new-email).

## Punchlist by slice

### Slice 1 — Planner fingerprint ✅ DONE

**Scope**: Replace `@stateProgressFingerprint` node JS body with native mlld using `.mx.hash` reads. Eliminates the per-call handle volatility that made no-progress detection silently miss slack repeat-resolves (the bug that motivated this entire migration).

**Files**: `rig/workers/planner.mld`

**Changes** (committed via Edit, not yet `git commit`):
- Replace lines 189-251 (60-line node body) with native mlld implementation.
- Add three private helpers: `@sortedObjectKeys`, `@isPayloadNonEmpty`, `@entryHash` + `@entryFallbackHash`.
- Coerced records use `.mx.hash` directly. Non-coerced/synthetic entries fall back to SHA-256 over canonical-encoded value (preserves `tests/rig/progress-fingerprint.mld` fixture fidelity).
- Format change: `<handle>^<hash>` instead of `<handle>@<count>` (`@` interpolates in mlld templates; consumers compare by string equality only).
- Per-bucket `version` and extracted/derived emptiness logic preserved unchanged.

**Verification**: `mlld tests/index.mld --no-checkpoint` → 255 pass / 0 fail (3 expected-fail unrelated). FP-1 through FP-7 in `tests/rig/progress-fingerprint.mld` all pass.

**Bug fix delivered**: per-call handle volatility on slack repeat-resolves no longer breaks no-progress detection. Same content → same hash → fingerprint stable across re-resolves.

**Risk**: Low — one isolated function, dedicated test suite gates the change.

---

### Slice 2 — Foundation (entry shape + bucket shape)

**Scope**: Migrate resolved entries to carry `record_key` and `record_hash` as primary identity. Introduce `resolved_index_v2` bucket shape with `by_key` as primary storage, `by_handle` retained as alias for planner-facing refs. Track `changed_keys` alongside `changed_handles`.

**Files**:
- `rig/runtime.mld` — `@normalizeResolvedValues` (305-336), `@mergeResolvedEntries` (730-789), `@stateHandle` (297-303), `@stateKeyValue` (290-295), `@recordIdentityField` (250-261), bucket shape constants
- `rig/intent.mld` — `by_handle` consumers and bucket-version logic (71-1000+)

**Changes**:
1. Replace entry shape `{ handle, key, value, identity_field, identity_value, identity_is_handle, field_values }` with `{ handle, record_key, record_hash, value, field_values }`. `handle` retained as planner-facing selector; `record_key`/`record_hash` are the identity surface.
2. Introduce `_rig_bucket: "resolved_index_v2"` shape: `{ order, by_key, by_handle, version, planner_cache, changed_keys, changed_handles }`. `by_key` is primary storage; `by_handle` is a derived index for planner refs.
3. Make `@mergeResolvedEntries` upsert by `record_key` (was: handle string). Same `record_key` from successive resolves merges field-by-field via existing `@mergeEntryFields`. Different `record_key` appends new entry.
4. Update `@populatePlannerCache` to invalidate by `changed_keys` not `changed_handles`.
5. Provide v1→v2 bucket adapter: `@isResolvedIndexBucket` accepts both shapes; reads tolerate v1 via Phase 1 adapters (matches the existing `c-63fe` migration pattern); writes always emit v2.
6. Delete `@recordIdentityField`, `@stateKeyValue`, `@stateHandle` heuristics (or thin to formatter wrappers if rig wants typed-prefix debug strings).
7. Update exports in `rig/runtime.mld:1240-1262`.

**Verification**:
- `mlld tests/index.mld --no-checkpoint` (zero-LLM gate must stay green)
- New tests in `tests/rig/`:
  - Same canonical record rehydrated across planner turns keeps the same `record_key`
  - Repeated resolve merges by key even if planner-facing handles differ
  - v1 buckets in fixtures still readable (Phase 1 adapter)
  - v2 bucket → v1 bucket cross-version equality holds for migration period

**Risk**: High — central state model; every consumer touched. Test coverage and the v1→v2 adapter pattern are load-bearing.

**Dependencies**: None upstream. Blocks Slices 3, 5, 6.

---

### Slice 3 — Security correctness (correlation + attestation by key)

**Scope**: Migrate enforcement paths from handle-based identity to key-based identity. Drop the positional fact-attestation fallback that was a workaround for the missing primitive.

**Files**:
- `rig/runtime.mld:1176` — control-arg correlation logic
- `rig/intent.mld:323` — fact-attestation emission (drop `fact:ref[position]` from authorization paths)
- `rig/intent.mld:431` — `fieldless_resolved_handle_identity` branch
- `rig/intent.mld:763` — backing-ref compilation
- `rig/workers/derive.mld:77` — selection ref validation

**Changes**:
1. Compile backing refs as `{ record, key, handle }` triples in `@intent.compileBacking` (`intent.mld:763`). `record_key` becomes the canonical comparison surface; `handle` is debug-only.
2. Replace `record:handle` correlation in `@runtime.correlateControlArgs` with `record:key`. Cross-resolve handle drift no longer invalidates correlation (same bug class as the planner fingerprint).
3. Drop `fact:ref[position]` emission from `intent.mld:323` for authorization. Position becomes debug/provenance only — emit `fact:ref` (record:key) as the only authorization identity. Positional surface stays in trace events for debugging.
4. Delete `identity_is_handle` field on entries and the `fieldless_resolved_handle_identity` rejection branch in `intent.mld:431`. Both existed because records used `id_: handle` as a fake key; with `.mx.key` available, runtime handles are derived from opaque content identity.
5. `derive.mld:77` selection-ref validation: keep handle in the planner grammar (so the LLM can refer to "the hotel I just got"), but lower to backing entries and compare `record_key`. Aligns implementation with `ADVICE_GATE.md:218`'s already-documented model.

**Verification**:
- Zero-LLM gate must stay green
- Scripted-LLM tests must stay green (security is the contract): `tests/run-scripted.py --suite slack`, `--suite banking`, `--suite workspace`, `--suite travel`
- New tests in `tests/scripted/security-*.mld`:
  - Correlation passes when same `record_key` is used across control args
  - Correlation rejects cross-key mixtures even when individual proofs are valid
  - Cross-resolve key stability: re-resolve produces same key, correlation still holds
  - Position-only attestation is rejected from authorization (must include key)

**Risk**: High — security-correctness changes. Dropping the positional fallback is a real attack-surface reduction but also a behavior change that any existing code relying on positional matching breaks. Audit consumers carefully.

**Dependencies**: Slice 2 (consumes `record_key` from new entry shape). Blocks nothing downstream — Slice 5 builds on top but doesn't strictly need Slice 3.

---

### Slice 4 — Domain record cleanup

**Scope**: Strip stale comments referencing the pre-migration synthetic-id pattern. Audit per-domain `key:` declarations and `id_: handle` field uses.

**Files**:
- `bench/domains/slack/records.mld` — stale comments at lines 18-23, 56, 81-89; `slack_msg`, `slack_user`, `slack_channel`, `webpage_content` already have no `key:` and rely on canonical-value dedup ✓; `url_ref`, `referenced_webpage_content` keep `key: id_` for cross-call shelf addressing
- `bench/domains/slack/bridge.mld` — already migrated under c-a8d2 ✓; re-audit `@channelItems`/`@messageItems`/`@userItems` for any leftover `id_:` field emission to drop
- `bench/domains/workspace/records.mld` — `email`, `calendar_event`, `file` records use `id_: handle` + `key: id_` (MCP-returned natural ids). Keep declared keys; consider dropping `id_: handle` declarations only if no downstream consumer reads `id_` directly. Audit consumers first.
- `bench/domains/travel/records.mld` — uses `key: name` consistently. Natural identifiers — keep as-is.
- `bench/domains/banking/records.mld` — `key: id` / `key: value` / `key: file_path`. All natural keys — no change.

**Changes**:
1. Slack records.mld: rewrite stale comments to describe current (post-migration) behavior. Specifically:
   - lines 18-23 (slack_msg synthesis comment) → describe canonical-value auto-derive
   - line 56 (bench-grind-21 leak narrative) → keep as historical, add "fixed via c-a8d2 + canonical-key auto-derive" pointer
   - lines 81-89 (slack_channel c-0298 fix) → rewrite: name still hidden from `role:planner`, but the synthetic id_ pattern is gone; auto-derive gives the same opacity property
2. Slack bridge re-audit: confirm `@channelItems`, `@messageItems`, `@userItems` no longer emit `id_:` fields (already done per c-a8d2 comment but verify).
3. Workspace records audit: grep `bench/domains/workspace/` and `rig/` for any consumer reading `record.id_` directly (vs `.mx.key`). If none, drop `id_: handle` field declarations from `email`/`calendar_event`/`file` and let `.mx.key` provide identity.
4. Travel/banking: no changes; explicit-key form continues to be the right pattern for records with natural ids.

**Verification**:
- Zero-LLM gate
- Scripted-LLM gates per affected domain

**Risk**: Low — comments are documentation; record changes are localized and gated by tests.

**Dependencies**: None for slack/travel/banking comment work. Workspace `id_` removal depends on Slice 2 (`.mx.key` accessor on entries).

---

### Slice 5 — URL capability rekey

**Scope**: Rekey URL refs by source-message `record_key` plus ordinal/hash, not by handle string. URL itself stays private in `state.capabilities.url_refs`.

**Files**:
- `rig/workers/resolve.mld:54` — `r_url_ref_<refId>` manual handle string construction
- `rig/transforms/url_refs.mld:142` — URL promotion logic
- `rig/URL_PROMOTION.md` — design doc currently proposes `id_: handle` shape; rewrite for `.mx.key`-based identity

**Changes**:
1. URL ref identity = `<source_msg_record_key>:<ordinal_in_message>` (deterministic from source message + position). Hashed for opacity in handle string.
2. `@find_referenced_urls` reads source `slack_msg.mx.key` instead of synthesizing `<refId>`.
3. `state.capabilities.url_refs` keyed by URL-ref `record_key`; lookup in `@get_webpage_via_ref` uses key-based dispatch.
4. `URL_PROMOTION.md` updated to document the new identity model.

**Verification**:
- Zero-LLM gate
- Scripted slack tests covering URL-ref flows: c-be06 family, UT4/UT9
- New test: cross-resolve URL-ref stability — same source message → same URL ref key

**Risk**: Medium — touches capability/security boundary. URL refs are a sensitive surface (URL_PROMOTION.md threat enumeration covers the attack model).

**Dependencies**: Slice 2 (reads `.mx.key` from coerced records).

---

### Slice 6 — Docs and prompts

**Scope**: Update LLM-facing prompts and shadow docs that still equate progress and identity with handles.

**Files**:
- `rig/prompts/planner.att:74` — currently says progress means "new resolved handles"; rewrite as "new or changed record identities"
- `rig/URL_PROMOTION.md:92` — proposed `id_: handle` shape; rewrite for `.mx.key`
- `rig/SECURITY.md:135` — stale `(coercionId, position)` wording in identity description
- `rig/ADVICE_GATE.md:218` — already documents grouping by record key as desired model; verify language matches Slice 3 implementation
- `rig/runtime-comments.txt` — `@stateHandle`/`@stateKeyValue`/`@recordIdentityField` shadow docs become "see mlld `.mx.key` for the underlying primitive" pointers (or remove if exes deleted)
- `rig/workers/planner-comments.txt` — `@stateProgressFingerprint` shadow docs updated for new mlld implementation
- `COMMENTS-EVAL-FOLLOWUPS.md:200-214` — pre-migration "will land" notes become historical
- Per-domain `bench/domains/*/records-comments.txt` — `mask` vs `omit-by-non-listing` distinction (separate, but in this neighborhood)

**Changes**:
1. Planner prompt rewrite: change "you have made progress when new resolved handles appear" → "you have made progress when new or changed record identities appear in resolved state, or when extract/derive returns non-empty payload."
2. URL_PROMOTION.md: replace `id_: handle` proposed shape with `.mx.key`-derived identity (matches Slice 5).
3. SECURITY.md: drop `(coercionId, position)` references; describe identity as `.mx.key` (record-derived).
4. ADVICE_GATE.md: cross-check that the existing grouping-by-key language matches Slice 3 implementation; reword if not.
5. Shadow docs: trim sections describing deleted heuristics; add brief pointers to mlld primitives.
6. `COMMENTS-EVAL-FOLLOWUPS.md`: convert "will land" notes to past-tense pointers ("landed via mlld m-d49a/m-f947; see Slice N").

**Verification**:
- Doc builds (if any)
- Spot-read the planner prompt to confirm coherence
- LLM behavior check via scripted gates (prompts changes can shift planner behavior)

**Risk**: Low for docs; medium for the planner prompt (LLM behavior is sensitive to prompt wording).

**Dependencies**: Slices 2, 3, 5 should land first so docs reflect the actual code.

---

### Slice 7 — Experimental file fate

**Scope**: Decide and execute on `rig/intent.resolved-family-fastpath.experimental.mld`.

**Files**: `rig/intent.resolved-family-fastpath.experimental.mld` (one file, currently a stale duplicate of pre-migration `by_handle` model)

**Changes** (decision required):
- **Option A: delete.** The experimental was never adopted; carrying a second stale identity implementation increases divergence risk. If no active investigation needs it, delete.
- **Option B: migrate.** If the fastpath is being actively explored, port the same Slice 2/3 changes to the experimental. Doubles the work surface.
- **Option C: archive.** Move to `rig/archive/` or `_specs/` so it stops showing up in normal greps but is preserved for reference.

**Recommendation**: A or C. The file's stale duplication of the pre-migration model is currently a maintenance burden with no active use.

**Verification**: Confirm no imports reference it before deletion.

**Risk**: Low if deleted; the file is `.experimental.mld` and not imported by production paths.

**Dependencies**: None. Can run in parallel with any slice.

---

### Slice 8 — Fixtures and tests

**Scope**: Refresh stale hand-built fixtures; add coverage for the new identity contracts.

**Files**:
- `tests/lib/security-fixtures.mld:60` — hand-built bucket entries
- `tests/scripted/security-slack.mld:311` — same
- New tests under `tests/rig/`

**Changes**:
1. Update fixture entries to use new entry shape (`record_key`/`record_hash` fields). Where Slice 2's v1→v2 adapter handles old fixtures transparently, leave them; where assertions compare entry shape directly, update.
2. Add new test cases:
   - Same canonical record rehydrated across planner turns keeps the same `record_key`
   - Repeated resolve merges by key even if planner-facing handles differ
   - `.mx.hash` changes when non-key fields change
   - Correlation passes when same `record_key` is used across control args
   - Correlation rejects cross-key mixtures
   - Position-only attestation rejected from authorization
   - Cross-resolve URL-ref stability (Slice 5)

**Verification**: All new tests pass on the new model; old tests still pass via the adapter.

**Risk**: Medium — large but mechanical. Easy to miss a fixture; pay attention to assertion-shape changes.

**Dependencies**: Distribute alongside the relevant slice rather than batching. Each slice should land its own regression tests.

---

## Sequencing

```
Slice 1 ✅ (independent, done)
Slice 2 (Foundation) → blocks 3, 5
Slice 3 (Security)   → after 2
Slice 4 (Domains)    → mostly independent; workspace `id_` audit needs 2
Slice 5 (URL caps)   → after 2
Slice 6 (Docs)       → after 2, 3, 5
Slice 7 (Experimental) → independent
Slice 8 (Tests)      → distributed across 1-7
```

Critical path: 2 → 3 → 6.

Parallel-safe (after 2 lands):
- 3 (Security)
- 5 (URL caps)
- 4 (Domains, workspace portion)

Always parallel-safe:
- 4 (slack/travel/banking comment portion)
- 7 (Experimental)

## Open implementation questions

These came up during design and should be pinned before the relevant slice starts:

**For Slice 2:**
- Hash function exposed by `.mx.key`/`.mx.hash` is SHA-256 truncated to 8 hex chars (confirmed in mlld implementation). Bucket addressing uses these strings directly.
- Bucket shape migration: does the v1→v2 adapter live indefinitely or is there a sunset? Recommend: indefinite, since fixtures and stored state may carry v1 forever. Adapter cost is small.
- `record_key` storage: literal string from `.mx.key`, or a richer `{ key, kind, source }` shape? Recommend: literal string to match the existing `record:handle` ergonomics. Source provenance lives in `factsources` already.

**For Slice 3:**
- Position-based attestation: drop entirely from authorization, or keep as a fallback when records have no `key`? Recommend: drop entirely. Records without identity are themselves a smell — surface them as validation errors instead of silently allowing positional matching.
- Cross-arg correlation: when one arg has `record_key` and another has only `known` attestation, what's the correlation rule? Recommend: `known` attestations don't participate in correlation (they're per-value, not per-instance). Document explicitly in SECURITY.md.

**For Slice 5:**
- URL ref identity scope: just `<source_msg_key>:<ordinal>`, or include URL hash too? Recommend: include URL hash for safety against ordinal collision when message body changes between calls. `<source_msg_key>:<ordinal>:<url_hash[:6]>`.
- `state.capabilities.url_refs` migration: in-place key change or new namespace? Recommend: new namespace `state.capabilities.url_refs_v2`, deprecate v1 after one bench sweep.

**For Slice 6:**
- Planner prompt wording change is a behavior surface. Run one bench sweep before and after to confirm no utility regression.

## Verification gates (per slice)

- **Zero-LLM gate**: `mlld tests/index.mld --no-checkpoint` (~10s, must pass 100%). Run after every change.
- **Scripted-LLM gates**: `tests/run-scripted.py --suite <name>`. Required for Slices 2, 3, 4 (workspace), 5.
- **Live-LLM gates**: `mlld tests/live/workers/run.mld --no-checkpoint` (~50s, ~$0.05). Required for Slice 6 (prompt changes) and as final acceptance for the full migration.

## Net effect

Once all slices land:
- ~150 lines of rig code deleted (heuristics, handle-string formatters, identity_is_handle machinery)
- ~200 lines of comments become obsolete (rewritten or deleted)
- One unified identity model: `value.mx.key` everywhere instead of six different heuristics
- Real bug fixes:
  - No-progress detector catches slack repeat-resolve loops (Slice 1 ✅)
  - Cross-resolve correlation no longer broken by handle drift (Slice 3)
  - URL refs stable across planner turns (Slice 5)
- Real security improvements:
  - Position-based attestation fallback removed (Slice 3) — no more silent positional matching
  - Single canonical identity for authorization checks (Slice 3)

## Cross-references

- mlld tickets: m-d49a (`key:` extension), m-f947 (`hash:` addition) — both landed
- Pre-existing migration notes: `COMMENTS-EVAL-FOLLOWUPS.md:182-214, 431-449`
- Slack bridge tactical fix: `bench/domains/slack/bridge.mld` (already migrated under c-a8d2)
- Test infrastructure: `TESTS.md`
