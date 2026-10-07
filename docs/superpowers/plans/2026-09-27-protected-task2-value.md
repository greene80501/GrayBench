# Implement protected task-2 value revision

Status: implemented and locally verified on 2026-09-27. Source design:
[`2026-09-27-protected-task2-value-design.md`](../specs/2026-09-27-protected-task2-value-design.md).

1. Write failing tests for pinned normal/hard ancestry, the revised public
   value contract, accepted independent alternatives, global phase and near
   tolerance, rejected semantic mutants, malformed values, and no native-object
   claim. Run the focused tests red.
2. Implement the task-2 revision and trusted Bell-amplitude oracle. Keep
   task-20 behavior and manifest semantics readable, and bind the new revision
   source in its judge manifest.
3. Generalize protected cohort validation and `protected-plan` to allow task 2,
   task 20, or both, in pinned dataset order with explicit exclusions. Write
   tests for forged revisions, mixed suites, scheduling drift, and CLI planning.
4. Run focused Docker tests, full engine tests, Ruff, format and diff checks.
   Record exact evidence and limits; request independent code review. Update
   draft PR #3 under `greene80501` while GitHub Actions stays disabled.

Verification: focused task-2/campaign tests 24 passed; full engine suite 1,244
passed, 5 skipped, 6 expected failures on the pinned Python 3.12 image. Ruff
check and format check passed. A read-only review found no actionable issue.
The task remains development-only and release-ineligible.
