---
id: SL-directory-tool
status: open
deps: []
links: []
created: 2026-05-14T18:34:07Z
type: task
priority: 3
assignee: Adam
---
# [SL] Introduce list_known_users_with_emails directory primitive (or accept UT2/UT11/UT16 refusal)

Architectural design question: UT2/UT11/UT16 require resolving Dora's email from `data.untrusted` webpage content. Under strict fact-floor enforcement on `@invite_user_to_slack_inputs.user_email: kind:email`, there is no path to mint `fact:email` from untrusted extract. Decision: introduce a directory tool that mints fact:email from a trusted source, OR accept UT2/UT11/UT16 as architecturally refused like banking UT0? From sec-slack.md §8 Class D + §9 question 3.

