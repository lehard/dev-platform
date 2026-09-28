# Verification: connected-requirement-operator-routing

OpenSpec-Verify: PASS

Verification-Method: Manual semantic review of the Requirement outcome, proposal, design and the managed-task-intake delta against the implementation diff; an independent re-routed executor verification pass; targeted unit tests including the connected operator-managed fixture; full platform validation; strict OpenSpec validation; private-reference guard; a live `routing-parameters` run on an operator checkout whose `.dev-platform.toml` is untracked.

Automated-Checks-Evidence: automated-checks.json

## Outcome and evidence

- Connected ChatGPT routing is resolved in order. The target's committed `[development_backlog]` is used when present and is authoritative. Otherwise the operator-declared Project parameters `BACKLOG_REPOSITORY`, `TARGET_REPOSITORY`, `PROJECT_LABEL` and `DEFAULT_PRIORITY` are used. Declared values that disagree with committed configuration are a conflict. Missing, invalid, wrong-Backlog or wrong-target routing fails closed.
- `requirement_intake.py routing-parameters` renders those parameters from `managed_task.authoring_config` and the checkout origin, the same resolver `create` uses. No second routing source exists. Non-test source and docs contain no concrete project label, priority or operator path.
- `resolve_connected_routing` and `verify_connected_requirement` are the reference model of the connected path. The read-back uses the shared `requirement_label_problems` check. Local `_reconcile_requirement_labels` behavior and messages are unchanged.
- Both protocol copies are byte-identical and describe the ordered rule and the operator-managed fallback. The read-back and Incubator text are unchanged.
- The live check ran in the task worktree, where `.dev-platform.toml` is untracked: `routing-parameters` printed the Backlog repository, target, project label and default priority that a Requirement created through local `create` in this lifecycle actually received.

## Automated checks

- `python3 -m compileall -q template/scripts scripts`: passed.
- `python3 -m ruff check scripts template/scripts tests`: passed.
- `python3 scripts/managed_projects.py validate`: passed, three managed projects.
- `python3 template/scripts/openspec_lifecycle.py check`: passed.
- `openspec validate connected-requirement-operator-routing --strict`: valid.
- `python3 scripts/check_private_backlog_refs.py --root .`: no direct private references.
- `python3 -m pytest -q tests/test_requirement_intake.py -k ConnectedRequirementRouting`: 15 passed.
- `DEV_PLATFORM_TEST_JOBS=3 python3 scripts/run_test_groups.py --all`: all 13 groups passed on the reconciled head. The archive helper reruns the selected full checks on the final candidate and records the exact result in `automated-checks.json`.

## Semantic OpenSpec review

- **Outcome:** Connected ChatGPT again has a supported routing path for an operator-managed target, and every new Requirement still requires exactly one verified project and priority label.
- **Completeness:** The spec scenarios for normal fixation, an operator-managed target without committed configuration, unresolved or conflicting routing, and package publication are each covered by tests or unchanged behavior. `tests/test_requirement_intake.py::ConnectedRequirementRoutingTests` uses `tests/fixtures/chatgpt_project_requirement_operator_routing.json` (target `lehard/dev-platform`, `committed_config: null`).
- **Correctness:** Committed configuration always wins. The fallback applies only when committed configuration is absent. Invalid owner/name values raise `RequirementIntakeError`; the verification pass found and fixed a leak of `ManagedTaskError` and added a regression test for it. An explicit priority overrides only the default.
- **Coherence:** The proposal, design, delta and implementation agree. The protocol edit from a concurrently merged change merged cleanly into a different paragraph.

## Execution provenance

The first routed executor's containment postcheck was invalidated when another session's PR merge fast-forwarded integration main during its run. The detection-only Claude postcheck does not downgrade a verified external advance, so that execution could not be recorded. The route was re-prepared on the new head. A second executor then independently verified the existing diff, fixed one defect, and was recorded with a clean postcheck. The implementation itself was written by the first executor.

The automated-checks marker names evidence the archive helper will generate; it does not assert that this file existed before archive.
