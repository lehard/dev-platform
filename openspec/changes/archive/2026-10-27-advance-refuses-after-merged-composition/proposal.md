## Why

After a Requirement composition PR is merged, the queue deletes `requirement/BR-N`. A later `execute_requirement.py advance` runs `ensure_integration_branch` before any merged-composition detection, finds no remote branch, creates a fresh one on the new main and pushes it. The coordinator's post-merge retrospective then checks out the composition head from that branch and fails ("reference is not a tree"), exhausting its retries (BR-573, 2026-10-12). Operators avoid it only by remembering never to run advance after a Compose merge (BR-771).

## What Changes

- `template/scripts/execute_requirement.py`: `_advance_contributions` first lists PRs with head `requirement/BR-N` and base `main`; a merged one stops advance with a `RequirementExecutionError` that names the PR and the supported next steps. The integration branch is not created, fetched or pushed. An unreadable PR inventory stops the same way, naming that.
- `docs/engineering/hosted-lifecycle-workers.md`: the placement and status text follow the code and the repository setting (`DEV_PLATFORM_HOSTED_KINDS=review,finalize`), and the preflight command lists every class.

## Impact

- `template/scripts/execute_requirement.py`, `docs/engineering/hosted-lifecycle-workers.md`.
- Spec: agent-workflow (one added requirement).
- Tests: Requirement execution tests.
