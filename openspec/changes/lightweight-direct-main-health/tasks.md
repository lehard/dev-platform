# Tasks: Keep direct-mode main health lightweight

## 1. Contract

- [x] 1.1 Record the Cuby post-merge failure and cost-policy mismatch.
- [x] 1.2 Define PR / direct-main / manual event behavior.

## 2. Implementation

- [x] 2.1 Run selected platform-managed checks only on pull requests.
- [x] 2.2 Run full platform-managed checks only on manual dispatch.
- [x] 2.3 Keep direct main push to common platform/OpenSpec health only.
- [x] 2.4 Update generated guidance.

## 3. Tests and verification

- [x] 3.1 Update template contract assertions for event-specific selected/full execution.
- [ ] 3.2 Run Platform CI and strict OpenSpec validation.
- [ ] 3.3 Record semantic verification, reconcile canonical spec and archive the change.

## 4. Release and rollout

- [ ] 4.1 Publish the next immutable patch.
- [ ] 4.2 Roll managed projects forward and merge green rollout PRs.
- [ ] 4.3 Confirm Cuby's post-merge direct main health run succeeds without installing project dependencies.
