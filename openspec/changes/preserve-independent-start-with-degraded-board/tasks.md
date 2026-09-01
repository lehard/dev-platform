# Tasks

## 1. Semantic preflight

- [x] 1.1 Reproduce the current independent-start behavior with controlled valid, terminal and branch/path-mismatched board entries.
- [x] 1.2 Confirm current specifications and template ownership boundaries; stop for user direction if the desired behavior conflicts with project-owned harness semantics.

## 2. Coordination and lifecycle contract

- [x] 2.1 Make the valid-active-versus-degraded board classification explicit in coordination code and diagnostics without altering sibling state.
- [x] 2.2 Ensure managed start reports hygiene warnings separately from `WAIT`, blocked error and successful materialization.
- [x] 2.3 Preserve atomic concrete-file admission, terminal/invalid claim exclusion and fail-closed unreadable/locking failures.
- [x] 2.4 Update central and rendered operator guidance consistently.

## 3. Regression and delivery coverage

- [x] 3.1 Add fixtures proving independent managed start with a branch/path-mismatched sibling leaves that sibling untouched.
- [x] 3.2 Add fixtures proving terminal sibling entries do not serialize unrelated starts.
- [x] 3.3 Add fixtures proving valid same-file overlap still produces `WAIT`, and unreadable/lock-failing board state still blocks safely.
- [x] 3.4 Add/extend fresh-render and Copier-update coverage for platform-owned multi-agent projects.

## 4. Verification and rollout readiness

- [x] 4.1 Run relevant unit/lifecycle tests, full required platform checks and semantic OpenSpec verification.
- [x] 4.2 Record truthful verification evidence, archive through the lifecycle helper and publish the release-ready PR.
- [x] 4.3 Verify release-rollout readiness through rendered fresh/Copier-update coverage: a later explicit immutable release remains responsible for opening reviewable downstream update PRs without direct default-branch mutation.
