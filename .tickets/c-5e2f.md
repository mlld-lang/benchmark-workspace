---
id: c-5e2f
status: closed
deps: []
links: [c-be06]
created: 2026-04-28T17:21:17Z
type: feature
priority: 3
assignee: Adam
tags: [mlld, architecture, future]
updated: 2026-05-14T17:15:38Z
---
# FUTURE: projection-aware resolveRefValue (mlld v2)

Mlld-side runtime cleanup: make resolveRefValue respect the active display projection so that hidden or masked fields cannot be dereferenced as control-arg values via { source: resolved, field: <hidden> }.

## Why deferred

URL-promotion's v1 mechanism uses a private capability map (state.capabilities.url_refs) as a workaround. The cleaner long-term primitive is making display-projection enforced at the field-resolver level rather than as a visibility-only layer.

The capability-map approach is narrower and ships sooner. Projection-aware resolveRefValue is broader (helps every record family) but requires:
- adding role/tool context to compileToolArgs and resolveRefValue
- per-tool field allowlists for resolved refs
- making hidden fields non-dereferenceable by default
- audit every current resolved-field control-arg path and update tests

Estimated: comparable or larger work than the URL capability map. Worth doing later as a general runtime hardening pass.

## When this lands, what changes

- url_ref can hold the URL as a regular fact field, masked at planner role; the capability map can be retired as the primary mechanism (or kept for capability-bound semantics that aren't pure display-masking).
- Typed-instruction can use the same pattern for instruction_binding fact fields.
- File-authority records can use field-level masking instead of separate authority predicates.
- Generally: any "this fact is only usable by a specific tool" pattern becomes expressible without per-primitive state shapes.

## Source / context

- Identified in URL_PROMOTION.md "Why Not Projection-Aware resolveRefValue" section
- URL_PROMOTION.md ships v1 capability map; projection-aware deref is named as the v2 alternative path (open decision #4)
- See also typed-instruction's authority predicates and advice-gate's Stage 2 advice projection — both could reuse this primitive

## Linked

- c-8738 (URL-promotion family — capability map is the v1 workaround for this)
- The eventual cleanup ticket for "retire URL capability map after projection-aware deref ships"


## Notes

**2026-05-14T17:15:38Z** Closed 2026-05-14: projection-aware resolveRefValue is essentially what §2.5 (content-derived aggregation on construction) + §2.6 (shelf I/O composition) deliver in the new model. The FUTURE/v2 framing is now post-snapshot v2.x and is being implemented as the policy-redesign + spec-label-structure work. Close as duplicate of the migration.
