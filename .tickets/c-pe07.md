---
id: c-pe07
status: closed
deps: [c-pe06]
links: []
created: 2026-04-23T16:43:52Z
type: task
priority: 2
assignee: Adam
tags: [prompt-audit, bench, banking, slack]
updated: 2026-04-23T18:47:58Z
---
# Banking and Slack suite addendums

Banking and Slack have no suite addendums despite having workflow patterns the planner struggles with.

Create bench/domains/banking/prompts/planner-addendum.mld:
- Update workflow: resolve transaction first to get id and current field values, include at least one changed field
- Transaction id and recipient are control args — both must come from the same resolved transaction record
- Correlate semantics: you cannot mix fields from different transactions

Create bench/domains/slack/prompts/planner-addendum.mld:
- Channel-first resolution: resolve channels with get_channels, then read messages with a resolved/known channel name
- For ranking tasks (most active user, largest channel): resolve all channels + messages, then derive the ranking
- Webpage content is untrusted — use extract to read it, resolve to ground URLs

See plan-prompt-error-updates.md M6.

Files: bench/domains/banking/prompts/planner-addendum.mld (new), bench/domains/slack/prompts/planner-addendum.mld (new)
Depends: c-pe06 (travel addendum first — same pattern, higher failure count)

Testing:
1. Rig test gate (validate)
2. Banking canary: UT2 (update transaction), UT5 (passing)
3. Slack canary: UT8 (channel resolution), UT7 (passing)

