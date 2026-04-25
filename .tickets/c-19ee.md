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
---
# TR-UT13/14 derive_empty_response on car rental ranking tasks

Travel UT13, UT14 both fail with derive_empty_response on car rental ranking. Both have car rental data but derive worker can't produce output.

UT13 ('LA car rental for SUV, 7 days, recommend best by rating'): 3 MCP calls (companies, types, ratings), then derive 'best_suv_rental' returns empty. Final compose: 'Speedy Rentals (Rating: 4.5)' — gave a partial answer but eval rejected.

UT14 ('LA electric car rental + price'): 10 calls, planner_session_ended_without_terminal_tool, multiple derive_empty_response attempts on 'best_electric_car_rental'. 18 iterations, 10 resolves, 2 derives (both empty), 6 extracts.

Both: derive worker receives car_rental data + filter intent (SUV / electric) and returns empty. Suspect derive prompt or worker handling of nested filtering on car-rental record shape.

Investigation needed:
1. Pull derive prompt the worker actually saw — was the source data formatted as the worker expected?
2. Try the same derive call shape against a different model (Cerebras gpt-oss-120b) to see if it's GLM-specific.
3. Synth a derive spike with car_rental-shape data + 'pick the best electric car' goal — does worker produce non-empty?

The new worker-context rule from commit d9aee4e may help here: planner could pre-state 'available cars with electric option are X, Y, Z' to bound the derive worker's task. Worth re-verifying after that fix is in the image.

