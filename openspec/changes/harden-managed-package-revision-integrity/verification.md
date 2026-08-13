# Verification: harden managed package revision integrity

OpenSpec-Verify: PASS
Verification-Method: manual equivalent completeness/correctness/coherence review (no `/opsx:verify` tool integration available in this environment) plus `openspec validate harden-managed-package-revision-integrity --strict --no-interactive` and the full platform test suite

## Completeness

- Requirement "Authoring validates against the exact prepared target revision": implemented via `exact_target_context` (`template/scripts/managed_task.py`), a short-lived detached `git worktree` checked out at the exact `prepared_against` SHA; `validate_authoring_bundle` and `supersede_task` both validate inside it instead of against `root`'s possibly-stale working tree. Both spec scenarios (stale local checkout; exact state cannot be established) are covered by `tests/test_managed_task_exact_state.py`.
- Requirement "Managed packages carry bounded source-Issue revision evidence": implemented via `Package.source_issue_evidence` (`updated_at` + `body_sha256`), captured in `create_task` and `supersede_task`. Pre-materialization drift is enforced in `import_task` (`require_no_unacknowledged_source_issue_drift`), with an explicit `--acknowledge-source-issue-revision` reconcile path on both `managed_task.py <issue>` and `start_managed_task.py`. Post-materialization drift is surfaced (never blocking) via `observe_source_issue_drift`, wired into `finish_task.py`'s `--status` JSON/text output and the `--cleanup` path.
- Requirement "Published managed package revisions can be superseded safely before execution": implemented via `managed_task.py supersede --bundle <dir> owner/repo#N` (`supersede_task`), which validates the replacement against exact current target state, rewrites the predecessor comment to a non-active `managed-openspec-superseded:v1` marker carrying a bounded `predecessor_revision`/`superseded_by` link, and activates the new package as the sole active revision.
- All three process-friction issues named in tasks.md 4.1 were read directly from `lehard/dev-platform` (#208 managed-task-authoring stale-checkout-vs-current-specs; #210 managed-task-intake no repair path; #218 managed-task-issue-drift undetected post-import Issue edits) and map 1:1 onto sections 1, 3, and 2 respectively of this change.

## Correctness

- `content_fingerprint` (excludes `supersedes`) makes supersede's retry-convergence check correct: a well-formed predecessor's own `revision` structurally can never equal a freshly built candidate's (the candidate's `supersedes` field always points at the predecessor), so the no-op check compares fingerprints with `supersedes` stripped from both sides. `test_supersede_retried_with_identical_bundle_converges_as_noop_without_duplicate_comment` exercises this end-to-end (activate once, then retry with an unchanged bundle) and would have failed under the original design (verified during implementation, before the fingerprint fix was added).
- `source_issue_evidence` is deliberately excluded from `revision()`'s hash and from post-materialization drift's `updated_at` comparison (`body_sha256` only), because GitHub bumps an Issue's `updated_at` on every comment post, including the platform's own package/supersede comment; an `updated_at`-keyed check would false-positive on every already-published task.
- The pre-materialization drift check lives inside `import_task`'s genuinely-not-yet-materialized branch only (after the `existing_state`/archived-resume/`destination_exists` early-return paths), not in `discover_task` itself -- resuming an already-materialized task (existing worktree, existing local change directory, or an archived canonical change) never re-triggers it, matching design.md's "canonical-after-materialization" rule that status/finish surface drift but never block an already-agreed implementation. `test_import_never_blocks_on_drift_when_resuming_an_already_materialized_change` covers this directly.
- `MARKER_RE` (`<!--\s*(managed-openspec:v[0-9]+)\s*-->`) does not match the literal `managed-openspec-superseded:v1` string (confirmed by direct regex inspection and by `test_supersede_rewrites_predecessor_comment_and_posts_new_active_package`/the retry test observing exactly one marker survives), so a superseded comment is invisible to `parse_package`'s "exactly one active marker" scan and the importer never sees ambiguity after a successful supersede.
- Legacy packages (no `source_issue_evidence` in the manifest) parse with `source_issue_evidence=None` and skip the drift check entirely (`test_discover_task_skips_drift_check_for_legacy_packages_without_evidence`), satisfying the backward-compatibility requirement.
- Fail-closed coverage for supersede: multiple active markers, a marker embedded in the Issue body itself, a closed Issue, a change-name mismatch against a well-formed predecessor, and a task already at `In review`/`Done` Project status are each covered by a dedicated test and raise before any GitHub mutation.

## Coherence

- All behavioral changes land in `template/scripts/{managed_task.py,start_managed_task.py,finish_task.py}`, which ship to downstream Copier-managed projects; `scripts/managed_task.py` and `scripts/start_managed_task.py` remain pure `runpy` shims (confirmed by inspection, unchanged).
- `dev-platform/checks.toml` gained one new dedicated test group (`managed_task_exact_state`, isolated for its real-git worktree tests, matching the existing `git_lifecycle`/`worktree_hygiene`/`task_freshness` pattern); `template/dev-platform/checks.toml` is a generic downstream starter with no Python test-group machinery and was confirmed to need no change.
- `docs/engineering/agent-workflow.md` and `template/docs/engineering/agent-workflow.md` both received matching additive documentation for exact-state validation, `--acknowledge-source-issue-revision`, `supersede`, and the `source_issue_drift` status field; `docs/engineering/openspec-workflow.md` has no existing "managed" content and was left untouched, per design.md's "no raw history warehouse" / narrow-scope principles.
- No change to release refs, rollout registry, or provider-local routing surfaces.

## Acceptance evidence

- `python3 -m compileall -q template/scripts scripts` — pass.
- `python3 scripts/managed_projects.py validate` — `Managed project registry: OK (3 managed, 7 candidate, 3 excluded)`.
- `python3 scripts/run_test_groups.py --all` — all 13 declared test groups pass, 575 declared tests with exact discovery-coverage equivalence (`declared_but_not_discovered: []`, `missing_from_groups: []`), including the 8 new `test_managed_task_exact_state` tests, 21 new/changed tests in `test_managed_task.py` (exact-state, source-Issue evidence/drift, supersede), 3 new tests in `test_managed_status_lifecycle.py`, and 1 extended wiring assertion in `test_template_contract.py`.
- `python3 template/scripts/openspec_lifecycle.py check` — `OpenSpec lifecycle hygiene: OK`.
- `openspec validate harden-managed-package-revision-integrity --strict --no-interactive` — `Change 'harden-managed-package-revision-integrity' is valid`.
- `python3 scripts/check_docs_links.py` — `Documentation link/anchor check: no problems found.`

No CRITICAL or WARNING findings remain. Ready for archive and publication.
