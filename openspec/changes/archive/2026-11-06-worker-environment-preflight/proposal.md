## Why

`work-next` has no shared preflight. The provider probe runs only with `--providers`, sandbox conditions are checked inside a claimed run, and the push credential is used only at the end of expensive work. A failed environment then looks like a failed run: three releases give `blocked-escalation`, and a `WorkerError` in finalize blocks at once.

The no-budget rule and the preflight are one policy: a failure may stay free of charge only because a persistent one is stopped before claim.

## What Changes

- `work-next --run` evaluates every condition of the requested kinds before the first claim and the first GitHub write, and refuses naming all unmet conditions. Job-dependent conditions run after selection and before claim. A standalone command runs the same check.
- A failure of a registered condition after claim is an environment failure: the claim is released with its class, it is not counted in `MAX_RELEASES` or attempts, and it produces no review report and no finalize block. `work-next` exits non-zero naming the condition.
- Environment releases have their own bound, which ends in an operational block lifted by `resume`, with candidate counters unchanged.
- Any other failure stays an ordinary failed run.

## Impact

- `template/scripts/lifecycle_workers.py`, new `template/scripts/worker_preflight.py`, `candidate_lifecycle.py`, `post_review_finalization.py`, `pr_review_gate.py`, `lifecycle_overview.py`, `scripts/post_merge_runner.py`; tests; `docs/engineering/chat-coordinator.md`, `docs/engineering/hosted-lifecycle-workers.md`; manifest.
- `hosted-preflight` keeps stopping at the first failure. BR-996 uses this class for an interrupted runner and adds no second class.
