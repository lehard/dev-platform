# Design: Exact-head publication across platform and project-owned harnesses

## Context

The accepted `publication-recovery` contract already identifies a matching PR by repository/base/head branch plus exact `headRefOid`, and protected merge requests already use expected-head guards in several paths. The observed failure comes from losing that identity continuity and later addressing GitHub state by branch name again.

`Jara_Fin` demonstrated the failure with an old merged PR at head A and a reused branch at head B. `planner-agent-lab` has a different project-owned publication harness with the same branch-name-only class. Copier deliberately preserves project-owned harness files, so replacing those harnesses wholesale would violate the ownership model.

## Decision 1: add a narrow safety requirement instead of replacing existing requirements

The delta specs add new requirements. They do not use `MODIFIED` for existing publication or rollout requirements, so every accepted scenario in current specs remains intact and the new exact-head rules are layered on top.

## Decision 2: exact identity is a tuple, then a stable PR ref

Before publication, identity is:

`repository + base branch + head branch + expected head SHA`

Branch name may narrow discovery but is never proof. Discovery enumerates structured PR candidates and selects only an exact match. After discovery or creation, checks, merge, state confirmation, and recovery use a stable PR number/URL together with the same expected head.

## Decision 3: merge confirmation repeats the proof

A zero exit from `gh pr merge` is not cleanup authorization. Before cleanup, GitHub must report both `state == MERGED` and `headRefOid == expected_head` for the stable PR. The same proof is required after a non-zero merge command.

Remote-branch deletion, local-main reconciliation, board completion, worktree cleanup, and terminal success stay downstream of that proof.

## Decision 4: project-owned harnesses keep ownership

The platform does not switch Jara or Planner to `harness_mode=platform`.

A bounded compatibility/conformance step may update only the publication-safety surface when a reviewed legacy shape is deterministically recognized. Jara's board/worktree/serialized integration behavior and Planner's standalone integration-clone behavior must remain intact. Unknown project-owned drift fails closed and preserves bytes rather than guessing.

The reviewed predicates are exact SHA-256 fingerprints of Jara's
`merge_to_main.py` and Planner's `project_publish.py`, not repository names
alone. A match receives narrow exact-head overrides for discovery, required
checks, merge, confirmation and recovery; existing board/worktree and
standalone-clone entrypoints stay intact. Missing or byte-drifted surfaces stop
before staging a rollout.

## Decision 5: rollout success includes safety conformance

For `harness_mode=platform`, normal Copier update delivers the fixed implementation.

For `harness_mode=project`, version metadata advancing is not sufficient. Rollout must either prove/migrate the recognized publication surface to the exact-head invariant or stop with an actionable diagnostic before publishing a misleadingly successful downstream update.

## Verification strategy

- exact PR candidate enumeration and stable-PR-ref unit tests;
- reused branch name A/B regression;
- zero-exit and non-zero merge confirmation tests;
- head-change and creation-race tests;
- synthetic Jara-like and Planner-like compatibility fixtures;
- rollout tests proving unknown project-owned drift fails closed;
- existing publication recovery, reconciliation, no-bypass, and rollout suites remain green.
