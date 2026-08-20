# Verification: Bind publication to exact PR head

OpenSpec-Verify: PASS
Verification-Method: Equivalent manual semantic review plus targeted automated coverage and the platform selected-check receipt.
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- Compared both delta specifications with the implementation. Exact identity is
  now established from structured PR candidates and retained as a stable PR
  number/URL for checks, merge, and state confirmation; a same-name historical
  PR cannot authorize the current head.
- Confirmed both zero-exit and non-zero merge paths require `MERGED` with the
  expected `headRefOid` before branch deletion or terminal success.
- Confirmed recognized Jara and Planner harnesses keep their respective
  board/worktree and standalone-clone entrypoints. Their narrow migration is
  fingerprint-gated, idempotent, and fails closed without overwriting drift.
- Confirmed the explicit `1.4.34` release PR delegates immutable tag creation
  and exact-version downstream rollout to the existing post-merge workflow;
  rollout PRs remain reviewed and are never auto-merged by the platform.

## Automated checks run before archive

- `python3 -m unittest tests.test_pr_reconciliation_concurrency tests.test_rollout_preflight tests.test_rollout_recopy tests.test_managed_status_lifecycle tests.test_task_reconciliation` — 79 tests passed.
- `python3 -m unittest tests.test_publication_recovery_cli.PublicationRecoveryConcurrencyTests.test_two_publishers_creating_the_same_exact_pr_converge_on_one tests.test_publication_recovery_cli.PublicationRecoveryConcurrencyTests.test_two_merge_requests_for_the_same_exact_head_are_convergent tests.test_publication_recovery_cli.ExactHeadMergeGuardTests` — 4 tests passed.
- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/managed_projects.py validate`
- `python3 template/scripts/openspec_lifecycle.py check`
- `git diff --check`

The archive helper will add the authoritative selected-check receipt named above
before it validates and archives this change.
