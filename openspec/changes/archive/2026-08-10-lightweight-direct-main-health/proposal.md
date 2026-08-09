# Proposal: keep direct-mode main health lightweight

## Why

The v1.4.7 Cuby rollout proved that the generated direct-mode post-publish health signal is still too heavy. After a green rollout PR was merged, the `main` push workflow executed `scripts/select_checks.py --full --execute`. Cuby's full check set includes backend pytest and frontend install/test/build, but the generic Dev Platform workflow intentionally does not install project application dependencies. The run therefore failed immediately because `pytest` was unavailable.

More importantly, running the full project check set again after publication contradicts the local-heavy/cloud-final cost policy: required full verification already belongs before publication, while the post-direct-publish cloud run is only a clean-environment platform/OpenSpec health signal.

## What Changes

- Pull-request runs for `harness_mode=platform` continue to execute selected checks.
- Manual `workflow_dispatch` remains the explicit cloud path for full platform-managed checks.
- Direct-mode `push` to `main` runs only the common platform/OpenSpec health steps and does not execute `select_checks.py --full`.
- Project-owned harness behavior remains unchanged.
- Generated guidance is clarified so manual dispatch is the optional full cloud diagnostic path.

## Compatibility Risks

A direct-mode repository will no longer repeat its entire platform-managed full check set after publication. This is intentional because required checks must already pass locally before publication. The `main` health signal still validates platform doctor, OpenSpec lifecycle and strict OpenSpec structure in a clean runner.

## Non-goals

- Do not weaken PR merge gates.
- Do not remove manual full cloud validation.
- Do not install arbitrary project dependencies in generic Dev Platform CI.
- Do not change project-owned CI.

## Definition of Done

- Generated workflow executes selected checks only on PRs and full checks only on manual dispatch.
- Direct `main` push performs only lightweight common health checks.
- Template tests and generated docs reflect the event-specific contract.
- Platform CI and semantic OpenSpec verification pass.
- The fix is archived, released immutably, and rolled to managed repositories; Cuby's post-merge direct health run succeeds without project dependency installation.
