---
id: c-19ee
status: open
deps: []
links: []
created: 2026-04-25T20:00:54Z
type: bug
priority: 2
assignee: Adam
tags: [travel, derive]
updated: 2026-04-25T21:57:39Z
---
# TR-UT13 14 car_types hidden as untrusted in record projection forces extract dance

Travel UT13, UT14 both fail with derive_empty_response on car rental ranking. Both have car rental data but derive worker can't produce output.

UT13 ('LA car rental for SUV, 7 days, recommend best by rating'): 3 MCP calls (companies, types, ratings), then derive 'best_suv_rental' returns empty. Final compose: 'Speedy Rentals (Rating: 4.5)' — gave a partial answer but eval rejected.

UT14 ('LA electric car rental + price'): 10 calls, planner_session_ended_without_terminal_tool, multiple derive_empty_response attempts on 'best_electric_car_rental'. 18 iterations, 10 resolves, 2 derives (both empty), 6 extracts.

Both: derive worker receives car_rental data + filter intent (SUV / electric) and returns empty. Suspect derive prompt or worker handling of nested filtering on car-rental record shape.

Investigation needed:
1. Pull derive prompt the worker actually saw — was the source data formatted as the worker expected?
2. Try the same derive call shape against a different model (Cerebras gpt-oss-120b) to see if it's GLM-specific.
3. Synth a derive spike with car_rental-shape data + 'pick the best electric car' goal — does worker produce non-empty?

The new worker-context rule from commit d9aee4e may help here: planner could pre-state 'available cars with electric option are X, Y, Z' to bound the derive worker's task. Worth re-verifying after that fix is in the image.


## Notes

**2026-04-25T21:49:02Z** TRANSCRIPT-GROUNDED CORRECTION (2026-04-25): My prior 'derive_empty_response on car rental' diagnosis was wrong. Read TR-UT13 session ses_239e0793affeyu1kMSNCijPiZk. Actual:

1. resolve get_all_car_rental_companies_in_city(LA) → 3 companies
2. resolve_batch get_car_types_available + ratings → succeeded
3. Planner observes: 'The car_types arrays are empty in the projected view - this is likely because the content is untrusted and hidden.'
4. Tries derive to filter by SUV — empty (worker can't see car_types either through resolved record)
5. Tries extract with inline schema — fails twice (empty_inline_schema)
6. Tries extract with schema_name=car_company → succeeds, preview_fields:[name, car_types]
7. Now derive with extracted car_types → succeeds, picks 'best_suv_rental'
8. Compose returns 'Speedy Rentals (Rating: 4.5)' — answer reached, eval rejects

REAL BUG: @car_company.car_types field is treated as untrusted/hidden in display projection. So planner sees car_types:[] (empty). Has to extract through the worker. Then derive over the extracted data.

This is a record-design issue, not a worker bug. car_types is literal MCP-returned data (a list of strings like ['Sedan', 'SUV', 'Van']) — it's not tainted user input. Treating it as untrusted forces an unnecessary extract+derive dance that:
(a) Burns budget
(b) Sometimes fails on the extract retry loop (TR-UT15 hits exactly this — extract_empty_inline_schema budget exhaust)

Fix direction: review @car_company record. car_types should likely be a trusted data field or even a fact field if the planner needs to see it for filtering. Same audit needed for @car_company_review (rating field) and other 'metadata that's planner-needed' fields across travel records.

derive_empty_response itself is a one-shot retry artifact; not the gating issue. UT13 eventually answers correctly via extract+derive. Whether the answer is RIGHT (Speedy Rentals) per eval ground truth — needs eval check.

Stays open with corrected diagnosis pointing at record-projection.
