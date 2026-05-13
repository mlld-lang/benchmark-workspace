---
id: c-f97d
status: open
deps: []
links: [c-a6db, c-4076, c-7780]
created: 2026-05-13T11:34:29Z
type: feature
priority: 2
assignee: Adam
updated: 2026-05-13T11:34:49Z
---
# CaMeL-mirror trust profile under --trust-profile=camel flag

## Background

Per `camel-alignment-analysis.md`, our defense model is stricter than CaMeL's by design — we use `policy.defaults.unlabeled = "untrusted"` while CaMeL uses `Capabilities.default() = (User, Public)`. Strict mode is the right default for production-grade deployment. But for apples-to-apples bench comparison (paper-ready numbers vs CaMeL), we want a flag-selectable CaMeL-aligned profile.

User direction: build two profiles — strict (default) and CaMeL-mirror (flag) — so we have:
- **Strict** numbers: our actual security posture
- **CaMeL-mirror** numbers: direct apples-to-apples vs CaMeL paper Table 2

## Scope

1. **`--trust-profile=camel` flag** (or `MLLD_TRUST_PROFILE=camel`) on bench dispatch and local runs.
2. **Per-suite alternate record/tool files**:
   - `bench/domains/<suite>/records.mld` (current) → `records-camel.mld` (CaMeL-aligned alternate)
   - `bench/domains/<suite>/tools.mld` (current) → `tools-camel.mld`
   - Agent entrypoint (`bench/agents/<suite>.mld`) branches on profile to import the right set.
3. **Alternate policy fragment**:
   - `rig/orchestration.mld` (current basePolicy) → `orchestration-camel.mld` profile flag
   - Drops `no-send-to-unknown` from defaults
   - Drops `no-send-to-external` from defaults
   - Keeps `labels.influenced.deny: ["destructive", "exfil"]` (the c-3162 fix)
   - Keeps `untrusted-llms-get-influenced` auto-rule
   - More permissive `defaults.unlabeled` ("user" instead of "untrusted") matching CaMeL

## Changes per suite (CaMeL-mirror records-camel.mld content)

Per the analysis doc:

**Workspace**:
- `create_calendar_event` label: drop `exfil:send` (CaMeL has no destination-requirement for calendar)
- `create_file` label: drop `exfil:send`
- Keep `share_file`, `send_email` as `exfil:send`

**Travel**:
- Hotel/restaurant/car info tools: `TrustedToolSource` label (covered by c-4076)
- `reserve_*` tools: no destination check on facts
- Reviews: untrusted (no change)

**Banking**:
- Transaction with sender=="me" → User-trusted (covered by c-7780)

**Slack**: minimal changes — already CaMeL-aligned in design.

## Acceptance

1. `--trust-profile=camel` runs both benign + attack against CaMeL-aligned records.
2. Strict-mode bench unchanged.
3. Document the resulting CaMeL-mirror numbers in `STATUS.md` alongside strict numbers — apples-to-apples comparison.
4. Both profiles maintain 0/105 ASR on slack canaries (the c-3162 fix still applies in both).

## Dependencies

Strict-mode records refine migrations (c-a6db, c-4076, c-7780) land first. CaMeL-mirror builds on top, swapping/relaxing where CaMeL differs.

## Priority

Medium. Once strict mode is at ceiling, build CaMeL-mirror to publish the comparable number. Don't compete with strict-mode work; sequence after.

## References
- `camel-alignment-analysis.md` "Proposal: CaMeL-mirror profile under a flag"
- CaMeL paper Table 2 (defended numbers per suite)
- CaMeL code: `~/dev/camel-prompt-injection/src/camel/pipeline_elements/security_policies/`

