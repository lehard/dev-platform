# Verification

OpenSpec-Verify: PASS
Verification-Method: equivalent completeness/correctness/coherence review (no `/opsx:verify` tool integration in this environment) against proposal/design/delta spec plus the full local platform test and validation matrix
Automated-Checks-Evidence: automated-checks.json

## Automated validation

Run locally on branch `agent/remove-finish-git-config-mutation`:

- `python3 -m compileall -q template/scripts scripts` — OK
- `python3 scripts/managed_projects.py validate` — OK (3 managed, 7 candidate, 3 excluded)
- `python3 scripts/run_test_groups.py --all` — OK (810 tests, 13 groups, exit 0),
  including the new `test_shared_workspace` and `test_harness_safety` regressions
- `python3 template/scripts/openspec_lifecycle.py check` — OK
- `openspec validate remove-finish-git-config-mutation --strict` — valid

New regression coverage:

- `test_fix_repairs_registered_paths_without_touching_git_config` — the POSIX
  permission audit no longer runs `git config core.sharedRepository`.
- `test_preflight_does_not_rewrite_a_correct_shared_repository_value` — two
  ordinary preflights against a correct value make no `.git/config` write and
  never enter the serialized repair path (injected serializer asserts).
- `test_preflight_repairs_missing_shared_repository_through_serializer` — a
  missing value is repaired exactly once inside the injected serialization
  boundary and rechecked.
- `test_verify_shared_repository_reports_unset_without_writing` /
  `test_preflight_readonly_mode_reports_misconfiguration_without_repairing` —
  read-only verification and `fix=False` preflight never mutate config.
- `test_shared_repository_grants_group_accepts_git_aliases` — symbolic, integer
  and octal forms git accepts are all treated as compliant.
- `test_audit_tolerates_a_registered_path_that_disappears_mid_scan` — an
  ephemeral Git lock removed between discovery and inspection triggers a bounded
  re-scan and produces no finding for the vanished path.
- `test_audit_still_fails_closed_on_a_durable_permission_finding` — a durable
  restrictive-permission finding is still reported.
- `test_serialized_integration_is_reentrant_within_one_process` — a nested
  acquisition on the same lock path does not self-deadlock and the lock is fully
  released afterwards; `test_serialized_integration_rejects_concurrent_holder`
  still proves cross-process contention is unchanged.

## Semantic review

Completeness: PASS. Both delta requirements and all four scenarios are
implemented. `verify_shared_repository` / `read_shared_repository` /
`shared_repository_grants_group` provide read-only verification;
`configure_shared_repository` isolates the mutation; `audit` no longer writes
`.git/config`; `_repair_shared_repository` performs a required repair through the
existing `integration_state.serialized_integration` boundary
(`.claude/main-merge.lock`) and rechecks before returning;
`_audit_permissions` performs a bounded re-scan (`EPHEMERAL_RESCAN_ATTEMPTS`) on
a `FileNotFoundError` for a registered path. Initial configuration remains with
bootstrap/adoption via an explicit `configure_shared_repository` call in
`platform_bootstrap.py`. `platform_doctor` keeps diagnostic-only coverage.

Correctness: PASS. An already-correct value produces zero config writes and zero
lock acquisition, so independent task publications no longer contend on
`.git/config.lock` because of platform verification. The repair re-checks the
value under the lock, so a concurrent holder that already repaired it is not
rewritten. `serialized_integration` was made reentrant within a single process
(keyed by the resolved lock path) so the existing nested call during direct
publication — `finish_task` holds the lock, then `project_publish.publish_direct`
calls `preflight` — cannot self-deadlock if a repair is ever needed there; a
separate process still blocks and fails closed with the unchanged message.
Durable permission, ownership, symlink and boundary-escape problems still raise
`SharedWorkspaceError` or surface as findings; only a `FileNotFoundError` for a
disappeared path is retried, and a still-missing path on the final pass
constrains nothing.

Coherence: PASS. Code, design and delta spec agree: bootstrap/adoption and
explicit `scripts/shared_workspace.py fix` own the write, ordinary preflight
verifies, the rare repair reuses the one existing integration serialization, and
no new lock service or whole-`finish` serialization is introduced.
`docs/project-owned-config.md` was updated to describe the verify-not-mutate
contract and the bounded ephemeral-path re-scan. Existing shared-workspace,
harness-safety and PR-reconciliation-concurrency tests remain green.

## Scope boundary

No new lock manager, no global task serialization, and no foreign-workspace
cleanup were added, per the accepted change boundary. `harness_mode=project`
consumers are unaffected: their repository-owned lifecycle is not replaced here.
