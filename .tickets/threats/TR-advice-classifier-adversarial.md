---
id: TR-advice-classifier-adversarial
status: open
deps: []
links: []
created: 2026-05-14T18:34:54Z
type: task
priority: 3
assignee: Adam
---
# [TR] Audit advice classifier against adversarial mis-classification prompts; quantify FP/FN budget

Audit advice classifier (@travelAdviceClassifier, cerebras/gpt-oss-120b) against adversarial mis-classification prompts. UT0 and UT1 are the only is_advice: false tasks; the boundary is load-bearing. Misclassification on either side either breaks utility (UT0/UT1 advice-routed → worker can't read review_blob for rating gate) or breaks security (UT19-like task non-advice-routed → review prose reaches normal compose). What's the false-positive / false-negative budget under adversarial pressure that tries to mis-classify the query type? Quantify robustness. From sec-travel.md §3 + §6 + §9 question 5.

