## Why

BR-610's acceptance evidence is not the mechanism but a real PR carried by a hosted worker after its developer session ended, with the constraints that make the hosted path trustworthy and the decision on where each lifecycle kind should run. The earlier slices deliver the worker, the owner enablement and the automatic triggers; only observation of real traffic can show whether the Claude runtime, credential boundary, duration, cost and failure behavior are acceptable, so the Requirement must not close before that is recorded.

## What Changes

- Observe real PRs of the normal delivery flow once the automatic triggers are live; confirm at least one review job claimed and resulted by a `gha-` worker without a manual command.
- Record in `docs/engineering/hosted-lifecycle-workers.md`, per hosted kind: Claude runtime and credential availability on the runner, the credential-boundary proof, that the read-only reviewer left the workspace unchanged, observed duration, cost and rate limits, behavior under a duplicate trigger, an expired claim, a moved head and an advanced `main`, and provider/auth/network/check failure behavior.
- Record the placement decision per kind and the comparison with the minimal local fallback; name the BR-433 basis for every kind left off the hosted path.
- Fix any defect observed within the existing contract, with a regression test, or record it as friction.

## Capabilities

### Modified Capabilities

- `lifecycle-workers`: the pilot ends in a recorded placement decision.

## Success evidence

- At least one real PR was reviewed by a `gha-` worker (claim and result by that identity, evidence pushed by the harness) with no manual command, or the document records the exact limitation that prevented it.
- The document contains, per hosted kind, the constraint list with observed values or the stated reason a value could not be obtained, and the placement decision.
- No kind is moved to CI by default; no local worker gains merge authority.

## Impact

`docs/engineering/hosted-lifecycle-workers.md`; tests only if a defect is fixed. No change to job, claim, result or marker formats or to the publication queue.

## Non-goals

Hosting repair, integration-repair or post-merge kinds; changing the Claude isolation contract (BR-576); CI-only merge authority (BR-575); downstream rollout (BR-494); the operator chat surface (BR-611); building the BR-433 node.
