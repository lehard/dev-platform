# Verification

OpenSpec-Verify: PASS
Verification-Method: manual semantic review against proposal/design/delta spec, plus local automated validation (compileall, managed-project registry validation, full unit suite including the new `tests/test_delegation_containment.py`, OpenSpec lifecycle hygiene, and strict OpenSpec validation with the CI-pinned openspec 1.6.0).

## Automated validation

- `python3 -m compileall -q template/scripts scripts` — passed.
- `python3 scripts/managed_projects.py validate` — OK (3 managed, 7 candidate, 3 excluded).
- `python3 -m unittest discover -s tests` — 163 tests passed (152 pre-existing + 11 new in `tests/test_delegation_containment.py`).
- `python3 template/scripts/openspec_lifecycle.py check` — OK.
- `openspec validate contain-delegated-write-scope --strict --no-interactive` (pinned 1.6.0, matching this repository's CI pin) — valid.
- No `python3 -m pip install copier`/factory-render/upgrade-smoke run was needed: this change adds one new library module (`template/scripts/delegation_containment.py`, following the same unlisted-in-`REQUIRED_COMMON` convention as `_platform_common.py`) and does not touch Copier rendering, `.dev-platform.toml` schema, or any required-files list, so the template contract is unaffected. `tests/test_template_contract.py` (part of the full suite above) still passed.

## Semantic review

Completeness: PASS against the in-scope items from the proposal — the contract requirement (`assigned_worktree`), snapshot/diff-based detection, fail-closed behavior on violation and on a failed containment check itself, pre-existing-vs-new classification, no automatic stash/reset/delete, and GitHub-auth-independent local friction logging are all implemented and tested.

Correctness: PASS. `check_containment` treats a path present in both snapshots (same status) as pre-existing regardless of content, and only classifies genuinely new status entries or a moved `HEAD` as a violation — verified by `test_pre_existing_dirty_integration_main_is_not_a_new_violation` and `test_pre_existing_dirty_state_does_not_mask_a_new_violation` together (the latter proves pre-existing dirt does not mask a real new violation, nor does a real new violation get misattributed to pre-existing dirt). `record_containment_friction` only runs after `check_containment` has already produced a result — there is no code path that logs friction before the check completes. The module never calls `git stash`/`reset`/`clean`/`rm` anywhere.

Coherence: PASS. Code, design, and delta spec agree on the contract shape and on the explicit limitation for Claude Code (detection, not prevention, without a correctly wired `PreToolUse` hook). `resolve_assigned_worktree` enforces the "registered worktree distinct from the integration copy" requirement from both design.md and the delta spec.

## Known scope note (not a gap, a boundary)

Task 4 ("wire `cwd=assigned_worktree` wherever the platform directly controls subprocess/subagent launch") is satisfied by documentation in design.md, not by a code change to an existing call site: dev-platform's own scripts (`finish_task.py`, `project_publish.py`, `merge_to_main.py`) launch `git`/`gh` subprocesses, not subagent delegations, so there is currently no dev-platform-owned call site that spawns a write-capable subagent to wire this into. The guidance is forward-looking for whichever component (this session's own orchestration, or a future platform capability) does spawn one.

## Known follow-up boundary

This change does not implement an actual `PreToolUse` hook script or a Codex sandbox-policy wrapper — design.md documents the enforcement points precisely enough to wire them up, but building and testing a concrete hook implementation for a specific harness is left for whoever integrates this module into their own delegation call site, since the correct wiring (tool-name matching, path resolution, hook installation location) is harness-specific.
