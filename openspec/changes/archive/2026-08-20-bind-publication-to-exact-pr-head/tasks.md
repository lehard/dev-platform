# Tasks

## 1. Close the platform exact-head identity gap

- [x] 1.1 Enumerate structured PR candidates by repository/base/head branch and select only exact `headRefOid`.
- [x] 1.2 Retain a stable PR number/URL after discovery or creation.
- [x] 1.3 Bind required-check reads to that stable PR ref plus `expected_head`.
- [x] 1.4 Bind merge requests and merge-state reads to the same stable PR identity and preserve expected-head server guards.
- [x] 1.5 Require exact `MERGED + headRefOid` confirmation on zero-exit and non-zero recovery before cleanup.
- [x] 1.6 Preserve idempotent already-merged/restart recovery and creation-race convergence.

## 2. Protect managed project-owned harnesses

- [x] 2.1 Define a bounded compatibility/conformance mechanism without changing harness ownership.
- [x] 2.2 Add a synthetic Jara-like fixture and preserve board/worktree/serialized integration semantics.
- [x] 2.3 Add a synthetic Planner-like fixture and preserve standalone integration-clone semantics.
- [x] 2.4 Make unknown or drifted project-owned publication shapes fail closed with no overwrite.
- [x] 2.5 Prove the compatibility step is idempotent and generic.

## 3. Regression and platform verification

- [x] 3.1 Reproduce old merged PR A plus reused branch/current head B and prove A cannot authorize checks, merge, cleanup, or terminal success for B.
- [x] 3.2 Cover exact PR B coexisting with historical same-name PRs.
- [x] 3.3 Cover zero-exit merge confirmation, non-zero recovery, required checks, head changes, and concurrent creation.
- [x] 3.4 Run minimum platform validation plus publication/reconciliation/rollout tests and semantic OpenSpec verification.

## 4. Release and reviewed rollout

- [x] 4.1 Archive through the normal lifecycle and publish the next immutable patch release.
- [x] 4.2 Confirm reviewed exact-version rollout for `lehard/cuby`, `lehard/Jara_Fin`, and `lehard/planner-agent-lab`.
- [x] 4.3 Confirm Cuby receives the platform-owned fix.
- [x] 4.4 Confirm Jara and Planner are exact-head safe after bounded project-harness conformance; version-only advancement is incomplete.
- [x] 4.5 Confirm candidate/excluded repositories are not mutated and rollout PRs are not auto-merged by the platform.
