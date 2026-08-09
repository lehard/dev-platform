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
- [ ] 3.3 Run platform CI/template render/update smoke coverage.

## 4. Downstream compatibility

- [ ] 4.1 Publish an immutable patch release after implementation is verified and archived.
- [ ] 4.2 Roll managed projects forward through reviewed Copier PRs.
- [ ] 4.3 Confirm direct-mode rollout PRs produce the required `platform-ci` check and can merge normally.
- [ ] 4.4 Supersede stale v1.4.5 rollout PRs rather than force-updating them.

## 5. Completion

- [ ] 5.1 Perform semantic OpenSpec completeness/correctness/coherence verification and record the receipt.
- [ ] 5.2 Archive the verified change through the platform lifecycle and strict-validate the resulting specs.

## Commit boundaries

1. OpenSpec contract.
2. Template/docs/tests implementation.
3. Verification + archive.
4. Patch release.
5. Reviewed downstream rollout merges.
