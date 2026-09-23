# Verification: Shared Requirement integration

## Semantic review

Reviewed proposal, design, both delta specs, implementation and tests together against the Requirement #164 shared-publication intent. The nonterminal receipt binds an archived managed child to its exact commit and checks committed tasks, automated checks and verification. Ordered assembly detects stale child heads, changed main and independent path overlap; a child based on its immediate predecessor can deliberately edit the same path. The dedicated candidate worktree preserves each exact child delta and a committed manifest, then runs the platform's full checks before using the existing protected PR publisher. Child terminal Project reconciliation is gated on GitHub's exact merged head and successful local-main synchronization. A linked child taking the separate publication route must have one committed, reciprocal-parent-checked exception reason. The parent terminal projection is deliberately left to the later derived-board-state change.

## Checks actually run

- Two-child local/bare-remote CLI `assemble`/`compose` rehearsal, including exact retry, in `test_bare_remote_two_child_cli_rehearsal` — passed.
- `python3 -m unittest tests.test_requirement_integration tests.test_managed_task -q` — 99 tests passed before reconciliation.
- `python3 -m unittest tests.test_git_lifecycle tests.test_merge_lifecycle_resilience tests.test_protected_main_zero_handoff tests.test_publication_recovery_cli -q` — 45 tests passed after repairing temporary-repository fixtures.
- `python3 -m compileall -q template/scripts scripts` — passed after reconciliation with `main`.
- `python3 scripts/managed_projects.py validate` — passed after reconciliation.
- `python3 scripts/run_test_groups.py --all` — 1244 tests discovered and covered, all 13 groups passed after reconciliation.
- `python3 template/scripts/openspec_lifecycle.py check` — passed after reconciliation.
- `openspec validate shared-requirement-integration --strict` — passed after reconciliation.
- `git diff --check` — passed before reconciliation.
- `python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/archive/2026-09-23-shared-requirement-integration/automated-checks.json` — compile, Ruff and full test groups passed again on the exact head after the PR-base reconciliation; refreshed the archived evidence identity.

The first live GitHub two-child shared-PR/full-CI dogfood has **not** run in this bootstrap change; it remains an explicit acceptance gate of the later terminal Requirement execution child. This receipt does not assert that #164 is complete.

OpenSpec-Verify: PASS
Verification-Method: manual semantic review of proposal/design/deltas against implementation, local bare-remote CLI rehearsal, focused and full automated regression checks
Automated-Checks-Evidence: automated-checks.json
Requirement-Integration-Exception: Bootstrap the shared protected-PR primitive independently before linked children can use it; live two-child publication remains a later Requirement acceptance gate
