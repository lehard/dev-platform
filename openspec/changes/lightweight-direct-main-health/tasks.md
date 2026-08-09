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
- [x] 3.2 Run Platform CI and strict OpenSpec validation (Platform CI #235 passed on `dbd2a8ba1653a02d36d8219af34c1e36ee35016a`).
- [x] 3.3 Record semantic verification, reconcile canonical spec and archive the change.

## Post-archive release operation

Publish the next immutable patch, roll managed projects forward, merge green rollout PRs, and confirm Cuby's post-merge direct `main` health run succeeds without installing project application dependencies. These are operational release steps after the implementation contract is archive-ready.
