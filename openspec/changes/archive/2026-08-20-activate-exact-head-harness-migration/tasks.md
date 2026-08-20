# Tasks

## 1. Correct migration activation

- [x] 1.1 Inspect current release/main and the v1.4.34 rollout state before changing migration behavior.
- [x] 1.2 Replace append-after-`__main__` migration with a deterministic pre-entrypoint transform.
- [x] 1.3 Preserve reviewed SHA predicates, idempotence, and fail-closed drift behavior.

## 2. Prove real CLI behavior

- [x] 2.1 Add a Jara-like CLI fixture proving exact-head code runs before its entrypoint while board/worktree/serialized semantics remain.
- [x] 2.2 Add a Planner-like CLI fixture proving exact-head code runs before its entrypoint while standalone integration-clone semantics remain.
- [x] 2.3 Cover stale merged PR A plus reused branch head B with no terminal success or cleanup.
- [x] 2.4 Retain unknown project-owned drift no-overwrite coverage.

## 3. Verify and release

- [x] 3.1 Complete selected platform verification and semantic OpenSpec review.
- [x] 3.2 Prepare the archived change and `1.4.35` patch-release input.
- [x] 3.3 Prepare standard rollout supersession verification for Jara #72 and Planner #45 without auto-merging downstream PRs.
