## Why

Every task that changes a template script also regenerates `template/dev-platform/platform-manifest.json`, so two concurrent tasks almost always share that one file. The agent board treats it as an exact concrete shared path and reports a hard overlap, which stops `finish` after a full validation run until an operator acknowledges it by hand (2026-10-23: after a 1155 s green run; 2026-10-26: again on BR-774's publish PR). The file is declared generated and the publication queue regenerates it on the merged tree, so the overlap is never a real conflict.

## What Changes

- Hard-overlap classification on the agent board excludes paths declared generated in `[[generated_files]]` of the check configuration committed at the observed `origin/<main>`. This applies to admission, the pre-validation recheck and the pre-publication recheck (one shared function).
- Such a path stays in the advisory scope-overlap warning as a soft overlap.
- A shared path that is not declared generated stays a hard overlap; a task cannot make its own file soft by declaring it in its branch, because the declaration is read at main.
- An unobserved `origin/<main>` or a malformed declaration stops the scope gate with a diagnostic instead of treating the declaration as empty.

## Impact

- `template/scripts/agent_board.py` (`_admission_conflicts`).
- Spec: worktree-coordination ("Hard and soft overlap are classified deterministically").
- Docs: `docs/engineering/agent-workflow.md` board/scope-gate paragraph.
- Tests: `tests/test_task_base_matrix.py` (generated-file row), `tests/test_worktree_hygiene.py`.
