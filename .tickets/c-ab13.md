---
id: c-ab13
status: open
deps: []
links: []
created: 2026-04-21T14:15:19Z
type: task
priority: 1
assignee: Adam
tags: [rig, planner]
---
# Raise invalid-call budget from 3 to 5

The error budget of 3 consecutive invalid calls is too tight. UT8 shows the model learning from errors and constructing the correct ref on attempt 4, but it's already dead at attempt 3. Raise to 5 to give the model room for ref construction learning. The model is not looping — it tries different strategies each time.

