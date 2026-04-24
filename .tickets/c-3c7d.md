---
id: c-3c7d
status: open
deps: []
links: []
created: 2026-04-24T13:23:29Z
type: feature
priority: 1
assignee: Adam
updated: 2026-04-24T20:04:36Z
---
# Topic router + dual model config. Add a fast-model topic router before the planner to filter the tool catalog by task relevance. Travel has 28 tools but a hotel task only needs ~10. Router uses the fast model (gemma-3n-e4b) to classify which tool families the task needs, then passes a filtered catalog to the planner (thinking model, glm-5.1 or gemma-4-31b). CLI changes: --thinking-model and --fast-model replace --model. Together AI model IDs: google/gemma-4-31B-it (thinking), google/gemma-3n-E4B-it (fast).

Travel tool router. CLI done (--model, --planner, --worker). Travel tool groups defined in tools.mld. Router exe at bench/domains/travel/router.mld. Rig toolFilter mechanism works. Will be tested as part of c-161f (remaining suite runs). Not a separate work item.

