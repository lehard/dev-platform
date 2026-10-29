# DEC-0004: Main advance and repeated validation

- **Status:** Current
- **Scope:** Freshness gates, check-evidence reuse and queue integration when `main` advances under a task
- **Decision date:** 2026-10-26 (current choice), recorded 2026-10-29
- **Authored against revision:** `ffc0b55e2be8bee27a152a98cbb04642ecaac3fe`
- **Problem root issue:** [lehard/dev-platform#553](https://github.com/lehard/dev-platform/issues/553) (full-validation-rerun-cost)
- **Supersedes:** None
- **Superseded by:** None

## Problem

Several agents publish to one `main`. Whenever `main` advanced while a task ran its full local validation (10–35 minutes), a gate refused the head: the task reconciled, reran the full set, refreshed its receipts and re-admitted, and the next advance repeated the loop. Each attempt below fixed one gate; none linked the earlier ones, so later work rediscovered the same problem.

## Accepted current decision

One task-base classifier decides for every gate. A head that does not contain the current `origin/main` is `behind-mergeable` when a trial merge with `main` is clean, even when both changed the same files. Such a head may be handed off, validated and published, because the publication queue merges `main` into it, regenerates deterministic generated files (the platform manifest), and merges only on green required checks of the integrated head. Check evidence is reused across a clean base move when the task's own diff is unchanged. Developer handoff, quick-task freshness, the publication step and the agent board's scope all read the same classifier and the task's own diff against the observed `origin/main`.

Executable behavior lives in OpenSpec (`platform-lifecycle`, `completion-lifecycle` and the active deltas); this record keeps only the history and the reasons.

## Attempts

| Date | Change (PR) | What it did | Why it was not enough / left out |
| --- | --- | --- | --- |
| 2026-09-24 | recover-shared-candidate-after-main-advance (#103) | A shared Requirement candidate can be recomposed after an unrelated main advance. | Shared candidates only; developers still had to be fresh. |
| 2026-10-06 | relevant-drift-and-transient-retry, BR-353 (#327) | ADD freshness follows bound sources instead of exact HEAD equality. | Pre-authoring only; validation gates unchanged. |
| 2026-10-10 | finalize-proven-base, BR-536 (#462) | Finalization reruns checks against the proven base instead of current main. | Coordinator finalization only. |
| 2026-10-11 | handoff-behind-disjoint-main, BR-567 (#505) | Handoff accepts a head behind main when main's files are disjoint from the task and a trial merge is clean. | The platform manifest changes in almost every PR, so the overlap almost always existed. |
| 2026-10-21 | reuse-archive-check-evidence-at-portable-finish, BR-692 (#669) | Portable finish reuses the archive's check evidence instead of a second run. | Required an equal base, so any main advance still meant a rerun. |
| 2026-10-22 | handoff-mergeable-task-base and queue-regenerates-generated-files, BR-748 (#684) | `behind-mergeable`: overlap allowed when the trial merge is clean; the queue regenerates the manifest. | Coordinator candidates only; quick tasks were explicitly out of scope. |
| 2026-10-23 | quick tasks behind a mergeable main, BR-774 (#718) | Quick tasks integrated by the queue pass the freshness gate behind a mergeable main. | The publication step still used a plain ancestry check. |
| 2026-10-23 | agent board scope against origin main (#716) | Board scope is the task's own diff from its merge base with the observed `origin/main`. | Shared generated files still counted as hard overlap. |
| 2026-10-26 | publish step reads the same classifier, BR-774 (#726) | Publication applies the same classifier as the other gates. | — |
| 2026-10-26 | declared generated files are a soft overlap, BR-777 (#728) | The manifest no longer produces a hard board overlap. | — |
| 2026-10-26 | reuse-check-evidence-unchanged-task-content, BR-785 (#730) | Finish reuses evidence across a clean base move when the own diff is unchanged; quick tasks record evidence. | — |
| 2026-10-29 | quick-task-behind-mergeable-spec, BR-774 (in progress) | Writes the quick-task behaviour of #718/#726 into the accepted spec. | Spec catch-up, no behaviour change. |

The agent board was not considered by the first five attempts and quick tasks were excluded twice (BR-567, BR-748) before BR-774.

## Rejected and deferred alternatives

- **Rebase or force-push of published task branches** — rejected: it changes PR identity and the platform never rewrites published history.
- **GitHub "update branch"** — rejected: the merge it creates is not recognised as the task's own reconciliation and breaks exact-PR identity.
- **Require a head that contains current main at every gate** (the state before these attempts) — rejected: each advance costs a full rerun of 10–35 minutes and the loop does not converge with several publishers.
- **GitHub merge queue** — not available: the repository belongs to a personal account. Revisit if it moves to an organization.
- **Freezing `main` during a developer's full run** — kept as an operator practice of the coordinator, not a platform mechanism.

## Evidence

- Friction root issue lehard/dev-platform#553 and the issues merged into it.
- Archived changes listed above under `openspec/changes/archive/`.

## Revisit triggers

- A full rerun caused only by a main advance that the classifier did not cover is recorded on the root issue.
- A new gate checks task freshness without the shared classifier.
- GitHub merge queue becomes available for the repository.
- Full local validation becomes cheap enough (well under 10 minutes) that reuse no longer pays for its complexity.
