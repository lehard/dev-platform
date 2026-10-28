## Context

Git does not write `MERGE_HEAD` before it runs `pre-merge-commit`; the hook sees its environment, `GIT_REFLOG_ACTION` (`merge <ref>`) and the repository layout (`git rev-parse --git-dir` versus `--git-common-dir` distinguishes a linked worktree from the integration copy).

## Decisions

- Owner decisions: on 2026-10-23 the owner chose a scoped environment variable on the reconcile merge (variant A); on 2026-10-29, comparing a strengthened A with a per-worktree intent (variant B), the owner chose the more reliable option, B. B binds the admission to the worktree, the branch and the exact main commit and is one-shot, at the same code cost.
- The intent lives in the per-worktree git directory, so another worktree never sees it. It records `branch` and `target` (the commit of `origin/<main_branch>` reconcile observed); the hook compares both, plus `GIT_REFLOG_ACTION == "merge origin/<main_branch>"`, with `main_branch` read from the intent's own `ref` field written by reconcile.
- Reconcile removes the intent in a `finally` after the merge; the hook removes it once it admits a merge. A leftover intent from an interrupted run is stale as soon as `origin/<main_branch>` moves or the branch changes, and the next reconcile overwrites it.
- The integration-copy check stays first: an intent never admits a merge there.

## Boundary

The hook guards against accidental agent actions, not against local processes of the same user. Accepted by the owner: the intent can be forged by deliberately writing the file with the exact commit; the three existing bypasses stay unchanged — `DEV_PLATFORM_ALLOW_MERGE_COMMIT=1`, `git merge --no-verify`, and finishing a refused or conflicted merge with `git commit`, which does not run `pre-merge-commit`. Tests prove what the boundary guarantees: no ad-hoc merge, no other ref, no other worktree, no stale intent, no integration-copy merge, no leftover intent.

## Verification limits

Downstream behaviour is proven before release on a repository carrying the hook exactly as doctor installs it. Confirmation on a real downstream project with the released platform is a post-release step and is reported as such in `verification.md`.
