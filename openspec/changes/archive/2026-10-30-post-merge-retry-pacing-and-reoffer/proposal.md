## Why

The post-merge runner (`scripts/post_merge_runner.py`) repeats `work-next` until idle inside one round. A post-merge obligation whose attempt ends `blocked` is derived as open again at once, so the same round spends all `MAX_POST_MERGE_ATTEMPTS` within minutes (#788, #789, #790, #795, #797, #801 on 2026-10-29/30). The accepted lifecycle-workers spec already says the runner never retries within a round; the code does. Half of the blocks were an environment defect of the runner (`lsof` not on the LaunchAgent PATH, reported by cleanup as `process-check-unavailable`), which is not a property of the obligation but was recorded as a blocked attempt. Once spent, nothing can move the obligation: `resume` covers only open PRs and the overview says no re-offer command exists, so the cards stay until the PR ages out of the merged window.

## What Changes

- Runner pacing: within one round, a PR whose post-merge run ended `blocked` or `failed` is excluded from further `work-next` runs of that round (`work-next --exclude-pr`, repeatable); other PRs are still served.
- Environment defects: the runner checks, before claiming anything, that the process-check tool cleanup needs (`lsof`) resolves on its PATH, and fails the round naming it. If the cleanup executor still meets `process-check-unavailable` after claiming, it raises an environment error: no result receipt is posted, the claim is released, and `work-next` exits non-zero so the round fails.
- New operator command `publication_queue.py reoffer-post-merge --pr N --expected-head H --reason TEXT [--via LABEL]`: for a merged PR whose post-merge obligation is exhausted and holds no live claim, appends one coordinator record at the merged head with a `post-merge-reoffers` sequence and the re-offer event (actor, via, reason, head, kind, time). Derivation then offers the exhausted obligation with a fresh attempt budget under re-offer job ids; completed obligations stay completed. The eligibility function is shared with the overview and the attention comment.
- Overview and attention: an exhausted post-merge obligation lists the exact `reoffer-post-merge` command with the merged head instead of "No supported re-offer command exists".
- Test confirming a cleanup with no worktree of the branch completes as `already-clean`.

## Impact

- `scripts/post_merge_runner.py`, `template/scripts/{candidate_lifecycle,lifecycle_workers,integration_contour,pr_review_gate,publication_queue,lifecycle_overview}.py`, tests, `docs/engineering/chat-coordinator.md` (operator command), platform manifest.
- Specs: lifecycle-workers (runner requirement modified; post-merge re-offer derivation added), publication-queue (re-offer command added), chat-coordinator (permitted actions modified).
- No change to the attempt limit, to completed obligations or to open-PR re-offer commands.
