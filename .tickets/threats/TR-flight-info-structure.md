---
id: TR-flight-info-structure
status: open
deps: []
links: []
created: 2026-05-14T18:34:47Z
type: task
priority: 4
assignee: Adam
---
# [TR] Restructure @flight_info into per-flight handles with fact:flight_number if any future task books flights

get_flight_information returns a single formatted blob string (@flight_info.info_text). No per-flight handles minted; no fact:flight_number or fact:airline records exist. UT16 is the only flight-using task and is read-only (no flight reservation tool); but if a future task booked a flight, the current data model has no defense surface. Decision shape: extend the upstream tool adapter to return structured flights and add @flight records with fact:flight_number? Or accept current scope given no UT books flights. Deferred until a reserve_flight tool would be added. From sec-travel.md §5 row T13 + §9 question 3.

