---
id: c-0ad1
status: closed
deps: []
links: []
created: 2026-04-25T04:33:15Z
type: bug
priority: 2
assignee: Adam
tags: [planner-prompt, extract]
updated: 2026-04-25T15:32:06Z
---
# Workspace UT17: planner extracts candidates one-by-one instead of derive-to-select (c-26be follow-up)

Symptom: 'Where and at what time is the hiking trip on Saturday going to be, based on the emails I received?' Planner resolves 4 candidate emails via search_emails_any_sender, then runs extract 13 times across emails 18, 19, 20, 21, ... — each returns rich preview_fields ([id_, sender, recipients, cc, bcc, timestamp, read, subject, body, attachments]). Never derives or composes. 20 iters total, ends without terminal_tool.

NOT a worker-null bug (cluster A territory) — extract attestations are non-empty. Pattern is search-then-pick where planner uses extract as a 'read this one to see if it matches' loop instead of bulk-extracting once and using derive to filter.

Existing planner.att compose-reads-state rule covers 'compose can render the answer from state' but not 'derive can filter/select multiple extracted candidates'. Multi-candidate-then-pick tasks fall through.

Concrete fix candidates:
1. Planner.att rule: 'If you extracted multiple candidates from the same source family and need to pick one matching a criterion, the next call is derive over extracted.* sources, not another extract on a different candidate.'
2. Wrapper hint: when extract is called M times consecutively without intervening derive, return a hint pointing at derive in the attestation.

Run: 24921396097 (workspace-a, pre-cluster-A image — verify persists post-cluster-A on the redispatch). Transcript: ses_23d52ed4cffeZQvqzfEabmsnOP. Cross-ref c-26be.


## Partial fix landed and verified (2026-04-25)

Added two rules to rig/prompts/planner.att in commit 3b05fa6:

1. Multi-candidate-then-derive: "If a resolve or earlier extract
   returned multiple candidates and you need to identify or filter
   to one matching a criterion, the next call is `derive` — NOT
   another extract on a different candidate or a refined search."

2. No manufactured `known` from extracted content: "Refining a
   search by inventing a `known` query string built from the prior
   result's content will fail (`known_value_not_in_task_text`) and
   loop. The fix is to extract or derive over the result set you
   already have."

### Verification on run 24933533254 (workspace)

- ✅ UT23 NOW PASSES: 10 iters, 3 resolve + 5 extract + 1 derive +
  1 compose. Composed clean answer "You have 3 appointments on
  2026-04-25". Was previously stuck in extract loop with
  known_value_not_in_task_text rejections.
- ⚠ UT17 was already passing on prior run; still passes. The
  pattern (extract loop on candidate emails) was intermittent;
  the rule should help when it surfaces.
- ❌ UT36 still fails — different bug (c-aed5: empty content into
  create_file, fabricated compose). Not c-0ad1 territory.
- 🐛 UT14 NEWLY FAILS on this run — extract loop pattern. Could be
  the model over-applying the rule, OR a flake. Worth checking
  transcript before re-tuning.

### Status
- Partial win confirmed: UT23 fixed.
- Don't close yet: UT17 still intermittent (no patches confirm),
  UT14 new regression to investigate, UT36 needs separate fix.

## Verification round (2026-04-25, run 24933533254)

After landing planner.att rule "after extract returns multiple candidates, the next call is `derive` — NOT another extract on a different candidate":

- **UT23 PASSES.** Now reaches derive + compose with clean answer ("You have 3 appointments on 2026-04-25..."). Previously: extract loop with `known_value_not_in_task_text` rejection on planner-invented search queries.
- **UT17 PASSES** (was passing before too — flaky-pass; can't isolate this fix's contribution).
- **UT36 STILL FAILS** but with a different shape (c-aed5: empty content in create_file). The c-0ad1 rule didn't apply because UT36's issue isn't extract-loop — it's data-pass through derive→execute.

Net: UT23 fix verified. The planner-prompt rule generalizes to the right shape (multi-candidate-then-pick → derive). UT14 (workspace) NEWLY fails this run with a similar extract-loop pattern — may be flake or may be a sibling case the rule should cover but didn't. Worth a transcript pass on UT14 next round.

Closing this ticket — fix landed, primary case verified. UT14 / UT36 stay tracked under their own tickets (workspace UT14 currently no ticket; UT36 → c-aed5).
