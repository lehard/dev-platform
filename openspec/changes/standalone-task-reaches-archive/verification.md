OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the model-routing delta, proposal, design and tasks; targeted unit tests (test_model_routing, test_managed_task, test_managed_task_exact_state: 331 tests); repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Option A for the standalone-clone postcheck, reviewed and approved by the coordinator on 2026-10-29: implementation commits that descend from the snapshot HEAD are the task; leftovers, a changed pre-dirty path and a non-descendant HEAD stay violations. B (declared-scope check) and C (no postcheck) were rejected. A commit unrelated to the task is not detected in this topology (stated in the spec and the doc).
- Direct handoff (bounded evidence, no ADD).

## Completeness

- Commits between `prepare` and `record_retained_execution` are accepted with `task_commits` (two commits counted); an untracked leftover, a changed pre-dirty path (snapshot replaced by one that includes it, because prepare itself refuses diverged task content) and an unrelated-history HEAD each fail with a containment violation: `StandaloneStandardCloneRoutingTests`.
- Shipped hints, gate recovery and docs no longer name `dogfood_task.py`, `route-codex` or `route-claude`; `TemplateCommandReferenceTests` checks every `python3 scripts/<x>.py` in the hint files and docs exists in `template/scripts` and that the platform-only subcommands are not named.
- `.managed-task-state.json` is ignored through `.git/info/exclude` (idempotent, project `.gitignore` untouched, explicit error when it cannot be written): two tests in `test_managed_task.py`.
- `model-routing.md` describes the implemented postcheck; the platform manifest is regenerated.

## Correctness

- The linked-worktree branch of `_postcheck` is unchanged (the new acceptance requires `STANDALONE_CLONE` and a route with no delegated child); the existing linked-worktree and external-advance tests pass.
- `ensure_task_state_ignored` does nothing outside a git work tree (no repository to commit to); inside one, a failure raises.

## Coherence

- Spec delta, design, tasks and docs state the same acceptance and the same limit.

## Not verified / limits

- Not run end to end through `execute_requirement.py advance` in a real standalone project (agent-control-room); covered by the unit tests of the postcheck and archive-independent routing gate only.
- Other platform-only script mentions in shipped code constants (for example `scripts/check_private_backlog_refs.py` in `private_lineage.py`) were left alone: they are operator-side checks, not hints to a project user.
