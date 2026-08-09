# Tasks: Preserve required PR platform check

## 1. Contract

- [x] 1.1 Record the v1.4.5 rollout failure mode and compatibility scope.
- [x] 1.2 Define direct-mode PR compatibility without weakening required checks.
- [x] 1.3 Define upgrade/rollback behavior for managed repositories.

## 2. Template and guidance

- [x] 2.1 Update generated `dev-platform.yml` so PR mode stays PR-only while direct mode supports main push plus PR compatibility.
- [x] 2.2 Update generated README and agent workflow guidance to describe the compatibility exception.
- [x] 2.3 Preserve concurrency cancellation and harness ownership behavior.

## 3. Tests

- [x] 3.1 Add focused template contract coverage for the new trigger matrix.
- [x] 3.2 Keep central CI single-job PR validation and release/rollout side-effect safety assertions unchanged.
- [x] 3.3 Run platform CI/template render/update smoke coverage (Platform CI #203 passed on `b5f78815064a319e54ba2e508740ed4b9e17e24a`).

## 4. Completion

- [x] 4.1 Perform semantic OpenSpec completeness/correctness/coherence verification and record the receipt.
- [x] 4.2 Reconcile the durable `platform-ci` spec and archive the verified change.

## Post-archive rollout

After the implementation/archive PR merges, publish an immutable patch release, let managed rollout create reviewed Copier PRs, confirm direct-mode rollout PRs produce `platform-ci`, merge green rollouts, and close stale v1.4.5 rollout PRs. These are release operations after the change itself is archive-ready, not prerequisites for archiving the implementation contract.

## Commit boundaries

1. OpenSpec contract.
2. Template/docs/tests implementation.
3. Verification + archive.
4. Patch release.
5. Reviewed downstream rollout merges.
