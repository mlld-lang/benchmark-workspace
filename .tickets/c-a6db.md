---
id: c-a6db
status: closed
deps: []
links: [c-3162, c-d0e3, c-4076, c-7780, c-f97d]
created: 2026-05-13T11:33:07Z
type: feature
priority: 1
assignee: Adam
updated: 2026-05-14T18:05:14Z
---
# [bench migration] Apply ? field-optional + drop optional_benign across records

## Background

mlld 2.1.0 implemented two changes that change our record vocabulary (mlld-dev confirmed implemented + pushed):

1. **`refine [...]` replaces record-level `when [...]`** — conditional record refinement with `@input` qualifier for dispatch-state scope. Per `RECORD-REFINE-MIGRATION.md`.
2. **`?` field-optional → conditional `facts.requirements`** — drops `optional_benign:` section; field-level `?` on the field name means "this field is optional; if present, fact-provenance required; if absent, no rule fires."

Per `~/mlld/clean/mlld-dev-prompt-field-optional.md` brief.

This eliminates the `optional_benign:` section and consolidates optionality on the `?` marker. Bench-side migration must apply this across all `*_inputs` records and verify downstream behaviors.

## Scope

**Records currently using `optional_benign:`** (4 declarations):
- `bench/domains/workspace/records.mld` — `@create_calendar_event_inputs`, `@send_email_inputs`
- `bench/domains/travel/records.mld` — `@create_calendar_event_inputs`, `@send_email_inputs`

**Records that should likely add `?` for analogous fields**:
- Any `_inputs` record with truly-optional facts. Audit pass needed; banking/slack may have implicit optional facts.

## Migration shape

```mlld
>> Before
record @create_calendar_event_inputs = {
  facts: [participants: { type: array?, kind: "email" }],
  data: { trusted: [title, start_time, end_time, location?], untrusted: [description?] },
  optional_benign: [participants],
  labels: ["execute:w", "tool:w", "calendar:w"],
  refine [
    participants.isDefined() && participants.length > 0 => labels += ["exfil:send"]
  ],
  validate: "strict",
  write: { role:planner: { tools: { authorize: true } } }
}

>> After
record @create_calendar_event_inputs = {
  facts: [participants?: { type: array, kind: "email" }],
  data: { trusted: [title, start_time, end_time, location?], untrusted: [description?] },
  labels: ["execute:w", "tool:w", "calendar:w"],
  refine [
    participants.isDefined() && participants.length > 0 => labels += ["exfil:send"]
  ],
  validate: "strict",
  write: { role:planner: { tools: { authorize: true } } }
}
```

`array?` → `array` (type-level optional drops — field-level `?` carries the optionality). `optional_benign:` section deletes.

## Downstream behaviors to verify (each one tests one of the spec implications)

1. **`facts.requirements` synthesis is now conditional**: solo focus block dispatch (no participants) succeeds; with-participants dispatch enforces fact-provenance.
2. **Input record validation at dispatch**: missing `?`-field doesn't raise validation error under `validate: "strict"`.
3. **Tool documentation surface (`@toolDocs` / `<tool_notes>`)**: planner sees `?`-fields marked optional. Verify by inspecting the rendered tool surface.
4. **MCP-served schema** (if applicable): `?` fields appear in JSON Schema as not-required.
5. **`allowlist:` / `blocklist:` interaction**: absent `?`-field skips these checks.
6. **`correlate:` interaction**: absent `?`-fact exempt from correlation check.
7. **Effective label propagation**: absent `?`-fact doesn't contribute its `fact:@<record>.<field>` label.
8. **Refine `@input.<field>` access**: `@input.x.isDefined()` returns false; pattern `@input.x.isDefined() && @input.x.length > 0` continues to work.
9. **Bound exe param matching**: exe receives `null` when field absent.

## Acceptance

1. Zero-LLM gate: `mlld tests/index.mld --no-checkpoint` at 264+/0/X (no regression from current 263/0/5).
2. WS UT12 (solo focus block) — `create_calendar_event` no longer fails on `policy.facts.requirements.op:named:create_calendar_event.participants`. Direct local probe verifies + bench task run recovers.
3. WS UT15/UT18/UT20/UT21 — re-test; some may recover via this fix alone (the facts.requirements blocker was a contributor). Others may need reader-set propagation work separately.
4. Banking + travel `@send_email_inputs` with absent cc/bcc — dispatches don't fail on cc/bcc fact-requirements.
5. Slack atk_direct + atk_important_instructions canaries stay at 0/105 ASR after migration.

## Estimated bench impact

3-6 tasks recover at this layer:
- WS UT12 confirmed via local probe earlier
- Possibly WS UT15/18/20/21 if their dispatch shape was blocked by facts.requirements
- Compound with records refine (Tier 1) — clean labels now flow through without facts.requirements over-firing

## References

- `~/mlld/clean/mlld-dev-prompt-field-optional.md` — the brief that drove the mlld fix; covers spec details + acceptance criteria.
- `~/mlld/clean/RECORD-REFINE-MIGRATION.md` — current migration guide; this ticket adds the field-optional dimension.
- `~/mlld/clean/camel-alignment-analysis.md` — broader CaMeL trust-model alignment context.

## Linked
- c-3162 (Gap C closure, predecessor work)
- c-d0e3 (untrusted-derived-into-body class)


## Notes

**2026-05-14T18:05:14Z** Closed 2026-05-14 (ticket-review pass): Fold into MIGRATION-PLAN records/policy migration; not a standalone ticket.
