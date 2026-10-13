## 1. Triggers and runtime

- [x] 1.1 `.github/workflows/lifecycle-workers.yml`: add the `workflow_run` trigger for *Dev Platform publication queue* (`completed`) and a 10-minute `schedule`; keep `workflow_dispatch`; update the header comment; install Node 22.12.0 for both classes.
- [x] 1.2 `tests/test_hosted_workers.py`: pin the exact trigger set with the queue workflow name, event type and cron, no use of the `workflow_run` payload, the default-branch guard on every job, and a Node pin within the Claude CLI engine range.

## 2. Documentation

- [x] 2.1 `docs/engineering/hosted-lifecycle-workers.md`: record the first manual run's findings, mark the automatic triggers as part of the workflow, and update rollback (remove `workflow_run` and `schedule`).

## 3. Delivery

- [x] 3.1 Required platform checks, truthful verification and developer handoff; the first automatic run after merge is observed and reported after delivery, not claimed here.
