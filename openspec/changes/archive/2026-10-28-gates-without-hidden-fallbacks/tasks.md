## 1. Private-reference guard

- [x] 1.1 `private_lineage.py`: guard decision helper (enabled+present, enabled+missing blocker, disabled -> not applicable).
- [x] 1.2 `finish_task.observe_private_reference_blocker` and `project_publish` (`_safe_presentation`, publish path) use it and print the not-applicable line.
- [x] 1.3 Tests: enabled+missing blocks, disabled prints not applicable, existing private-reference tests enable private lineage.

## 2. Selected-check base

- [x] 2.1 `select_checks.py`: base resolution without `HEAD~1`, git diff failures are errors.
- [x] 2.2 `scripts/select_checks.py` resolves the base before the selector.
- [x] 2.3 Tests: explicit base, task branch, main branch, detached HEAD, failing git diff, wrapper.
- [x] 2.4 `docs/engineering/agent-workflow.md`: document the base rule; `docs/engineering/openspec-workflow.md`: document the guard rule.

## 3. Friction checkpoint staleness

- [x] 3.1 Reproduce the false staleness; remove the swallowed exception in `current_task_content`; regression tests for an unreadable task state and a quick task.

## 4. Verification

- [x] 4.1 Run full validation, the public distribution snapshot smoke and semantic OpenSpec verification.
