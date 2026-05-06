---
id: c-48cc
status: open
deps: []
links: []
created: 2026-05-06T18:37:05Z
type: task
priority: 4
assignee: Adam
tags: [bench, infra, scripts]
---
# [infra] bench-attacks.sh: retry on TLS / transient gh CLI failures

scripts/bench-attacks.sh has crashed mid-dispatch twice on transient `gh` CLI failures (TLS timeout in the system_message cycle and again in the tool_knowledge cycle). Symptom: the script exits partway through a 5-suite dispatch loop, leaving some suites un-dispatched and requiring manual replay.

## Acceptance

- bench-attacks.sh logs each suite-dispatch attempt + outcome to a known file (e.g. tmp/bench-attacks-<runid>.log)
- On transient gh CLI failure (TLS timeout, 5xx, etc.) retry up to N times with backoff
- On persistent failure, log which dispatches succeeded and which need manual replay; print a recovery one-liner
- Exit code reflects whether all suites dispatched

## Why low priority

The attack matrix completed despite both failures via manual replay. This is annoyance, not blocking. File now while the pattern is fresh; pick up when it bites a third time or when a fresh agent hits it during the c-1bd4 closeout sweep.

