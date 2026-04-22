---
id: c-ab13
status: closed
deps: []
links: []
created: 2026-04-21T14:15:19Z
type: task
priority: 1
assignee: Adam
tags: [rig, planner]
updated: 2026-04-22T10:20:48Z
---
# Raise invalid-call budget from 3 to 5

The error budget of 3 consecutive invalid calls is too tight. UT8 shows the model learning from errors and constructing the correct ref on attempt 4, but it's already dead at attempt 3. Raise to 5 to give the model room for ref construction learning. The model is not looping — it tries different strategies each time.


## Notes

**2026-04-22T10:20:48Z** Fixed: error budget raised from 3 to 5.
