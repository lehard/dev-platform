## Why

The delivered hosted worker ships with manual dispatch only. After the owner provisioned the provider secret and `DEV_PLATFORM_HOSTED_KINDS=review`, a manual run on `main` (run 38221555792) passed the inputs and runtime preflight — App identity, trust, installation-token scope, credential boundary and the real Claude readiness probe — and reported `idle`. Until automatic triggers exist, a published review job still waits for someone to dispatch the workflow, which is the problem BR-610 exists to remove. The same run also showed the pinned Claude CLI (2.1.287) declares `node >=22` while the workflow installs Node 20.19.0 (npm `EBADENGINE` warning); it worked, but running outside the CLI's supported engine is not acceptable for a permanent worker.

## What Changes

Current: `lifecycle-workers.yml` has `workflow_dispatch` only; Node 20.19.0 is installed for both classes.

Target:

- Add the `workflow_run` trigger (the *Dev Platform publication queue* workflow, `completed`) so a worker starts when the queue has published work, and a `schedule` of every 10 minutes as a backstop for missed events. Both execute the default-branch workflow with the same default-branch guard, per-class concurrency without cancellation and 25-minute timeout; neither reads the triggering event's payload.
- Install a supported Node (22.x, pinned exactly) so the pinned Claude CLI runs inside its declared engine.
- Update the structure tests to pin the exact allowed trigger set (including the queue workflow name, event type and cron), that no step uses the `workflow_run` payload, and that the Node pin satisfies the CLI engine.
- Update `docs/engineering/hosted-lifecycle-workers.md`: the triggers are now part of the workflow, step 5 of the enablement order becomes "done by this change", rollback is removing the two triggers.

## Capabilities

### Modified Capabilities

- `lifecycle-workers`: automatic triggers for hosted workers.

## Success evidence

- Tests show the workflow's triggers are exactly `workflow_dispatch`, `workflow_run` of the publication queue (`completed`) and a 10-minute `schedule`; no PR trigger; no use of the event payload; Node pin within the CLI engine.
- After merge, the first scheduled or queue-triggered run on `main` starts without a manual command and prints an outcome (`idle` or a resulted job); this is observed and reported, not assumed.

## Impact

`.github/workflows/lifecycle-workers.yml`, `tests/test_hosted_workers.py`, `docs/engineering/hosted-lifecycle-workers.md`. No change to the worker, preflight, job or claim formats, token rights or the publication queue. The `finalize` class stays configured but is not enabled (`DEV_PLATFORM_HOSTED_KINDS=review`).

## Non-goals

Enabling `finalize`; hosting repair or post-merge kinds; recording the placement decision (next child); changing the Claude isolation contract (BR-576); CI-only merge authority (BR-575); downstream rollout (BR-494).
