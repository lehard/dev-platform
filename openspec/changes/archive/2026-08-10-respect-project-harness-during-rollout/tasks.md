# Tasks: Respect project harness during managed rollout

## 1. Contract

- [x] 1.1 Record the v1.4.6 Jara_Fin rollout failure mode.
- [x] 1.2 Define validation ownership by `harness_mode`.

## 2. Implementation

- [x] 2.1 Update central rollout validation to skip downstream selector execution for `harness_mode=project`.
- [x] 2.2 Preserve existing selected-check execution for `harness_mode=platform`.

## 3. Regression coverage

- [x] 3.1 Add unit test proving project-mode rollout does not invoke project selector.
- [x] 3.2 Add unit evidence that platform-mode rollout invokes the platform selector with `--execute`.
- [x] 3.3 Run full Platform CI including render/upgrade/mature-adoption smokes and strict OpenSpec validation (Platform CI #218 passed on `1d43532da952f6dbe5e1fe8d1ea12b0d131c482e`).

## 4. Completion

- [x] 4.1 Record semantic verification with no critical findings.
- [x] 4.2 Reconcile canonical `platform-rollout` spec and archive the change.

## Post-archive release operation

Publish the next immutable patch and complete managed rollout. This is an operational release step after the implementation contract is archive-ready, not a prerequisite for archiving the fix itself.
