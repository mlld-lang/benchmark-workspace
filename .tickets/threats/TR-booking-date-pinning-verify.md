---
id: TR-booking-date-pinning-verify
status: open
deps: []
links: []
created: 2026-05-14T18:34:34Z
type: task
priority: 2
assignee: Adam
---
# [TR] Verify booking-date pinning: known start_day/end_day cannot be influenced by review content

Verify that @reserve_hotel_inputs.{start_day,end_day} (data.trusted on input record) require values from the planner's known bucket only, and that no derive/extract path can promote review-derived date values into the trusted bucket. Probe the planner's known bucket carries typed date values that fail validation against attacker-chosen dates (IT0 specifies May 13-17 2024). Symmetric for reserve_restaurant / reserve_car_rental date fields. From sec-travel.md §8 Class B.

