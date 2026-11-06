# DEC-0010: Finish reviews risky changes and skips all others

- **Status:** Current
- **Scope:** Independent review in `finish`, for quick and managed tasks
- **Decision date:** 2026-11-06
- **Authored against revision:** `5389f8ce694afbd1af4705fe95f61a9a00bd7da8`
- **Supersedes:** None
- **Superseded by:** None
- **Amends:** [DEC-0009](0009-single-stream-core.md): item 5 no longer holds. Review stays opt-in per repository, but it follows the risk of the change, not managed provenance, and this repository enables it.

## Accepted current decision

The coordinator accepted this rule on 2026-11-06 under the owner-delegated roadmap.

1. A change is risky exactly when the task's own diff, without declared generated files, touches a `[[protected]]` path of the protected surface.
2. With `[independent_review] enabled = true`, `finish` runs the existing reviewer for a risky quick or managed task and for no other task.
3. A material finding or a reviewer that could not run stops `finish`. Nothing repairs, retries with another provider or spends a budget.
4. A quick task keeps its review files in its own git directory, bound to its content. They are not in the PR.

## Rejected and deferred alternatives

- **Only the review, publication and credentials categories:** rejected. It would hit 36 of the last 60 commits instead of 49, but it is a second list to maintain.
- **Reviewing every managed change:** rejected. Provenance says nothing about risk, and quick tasks are the main path.
- **Committing quick review evidence:** rejected. The commit would change the diff it proves.

## Evidence

BR-1007. Before this decision nothing reviewed changes to the delivery gates: review was off here and quick tasks never got one.

## Revisit triggers

- Reviewer time or findings show the rule is too wide or too narrow for a sustained period.
- A project needs review evidence visible in the PR.
