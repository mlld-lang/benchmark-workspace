---
id: TR-stage2-debiased-extraction-activation
status: open
deps: []
links: []
created: 2026-05-14T18:34:50Z
type: task
priority: 4
assignee: Adam
---
# [TR] Activate @travel_fact schema + Stage-2 advice extension (only if Stage-1 ASR regresses)

@travel_fact schema is declared in records but currently unused. The Stage-2 advice-gate extension (rig/ADVICE_GATE.md §'Stage 2 Advice Schema') would populate it via debiased extraction. Decision shape: only activate if Stage-1 (current implementation) shows measured residual ASR on recommendation-hijack. Currently IT6 ASR = 0/4 (bench-grind-18/19), so Stage 2 is deferred per ADVICE_GATE.md. Re-evaluate if attack sweeps show residual recommendation-hijack ASR > 0. From sec-travel.md §4 + §9 question 4.

