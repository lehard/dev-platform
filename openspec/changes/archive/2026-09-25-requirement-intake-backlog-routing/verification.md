# Verification: requirement-intake-backlog-routing

OpenSpec-Verify: PASS

Verification-Method: Manual semantic review of the Requirement outcome, proposal, design and both specification deltas against the implementation diff; targeted unit tests; full platform validation; strict OpenSpec validation.

Automated-Checks-Evidence: automated-checks.json

## Outcome and evidence

- `requirement_intake.py create` resolves routing from the existing `managed_task.authoring_config` (`[development_backlog]`) and creates the Issue with `type:requirement`, the configured `project:*` label and `priority:<explicit or default_priority>`. No new configuration key or default was introduced; `--priority` is optional and limited to P0–P3.
- Routing fails closed before any Issue mutation when `--repository` differs from `development_backlog.repository`, when `--target-repository` is not the checkout's origin repository, or when `validate_backlog_labels` cannot confirm a configured label.
- After creation the Issue is read back. A conflicting `project:*`/`priority:*` label raises an error naming the exact Issue; only missing expected labels are added to that Issue and re-verified. Success is returned only for the exact expected label set.
- The ChatGPT Project protocol (central and template copies, byte-identical) requires the same labels from the target repository's default-branch `.dev-platform.toml`, stops when that configuration is missing, invalid or names another Backlog repository, and verifies all labels in read-back. `task-intake.md` and its template describe the repository-local behavior.
- The Incubator section and internal-change lifecycle were not changed.

## Automated checks

- `python3 -m compileall -q template/scripts scripts`: passed (supervisor rerun).
- `python3 -m pytest -q tests/test_requirement_intake.py tests/test_agent_instruction_architecture.py tests/test_requirement_first_intake_contract.py tests/test_template_contract.py`: 94 passed (supervisor rerun).
- `python3 scripts/managed_projects.py validate`: passed, three managed projects (supervisor rerun).
- `openspec validate requirement-intake-backlog-routing --strict`: valid (supervisor rerun).
- `python3 template/scripts/openspec_lifecycle.py check`: passed (supervisor rerun).
- `DEV_PLATFORM_TEST_JOBS=3 python3 scripts/run_test_groups.py --all`: all 13 groups, 1331 tests passed, as reported by the routed Sonnet executor in this worktree. The archive helper reruns the selected full checks on the final candidate and records the exact result in `automated-checks.json`.

## Semantic OpenSpec review

- **Outcome:** New Requirements get exactly one project and one priority label at creation, or creation fails before success is reported.
- **Completeness:** Every acceptance item has a matching change: default priority, project routing, read-back, the ChatGPT path, the unchanged Incubator, and regression tests. The tests cover default and explicit priority, target and Backlog mismatch, an unavailable label, repair of a missing label, and a conflicting label found in read-back.
- **Correctness:** Label comparison is case-insensitive through `managed_task.issue_labels`. Routing and label availability are checked before `gh issue create`. Repair only adds labels and never removes or replaces a label that someone chose differently.
- **Coherence:** The proposal, design, delta specs and code agree. Existing Requirements are not relabelled, and managed technical authoring is unchanged.

The automated-checks marker names evidence the archive helper will generate; it does not assert that this file existed before archive.

## Post-archive reconcile refresh

After archive, `origin/main` advanced (#127, #128) and the task branch was reconciled by a normal merge (`857a66d`) without conflicts. Full validation was rerun on the reconciled head: compile, managed-project registry, OpenSpec lifecycle hygiene and all 13 test groups passed. `automated-checks.json` was then regenerated with `scripts/select_checks.py --base origin/main --execute` at that exact head (compile, ruff and the full test suite passed). The original archive-time run also succeeded; the refreshed file replaces it only so its checkout identity matches the published head.
