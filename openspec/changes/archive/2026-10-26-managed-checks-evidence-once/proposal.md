## Why

A full selected-check run takes 20–40 minutes. After an agent records green evidence with `select_checks.py --execute --evidence`, the portable `archive` runs the same checks again over the same task content (observed in a downstream project: about 40 minutes per archive), and nothing stops a second manual run of unchanged content. The private-reference guard runs before archive and in finish preflight, but not in `select_checks`, so a direct run discovers a private reference only afterwards. When the affected-test precheck is unavailable (the runner produced no usable result), `select_checks` prints a line and continues with the full set: a degraded path that hides a runner fault behind a long run.

Slice 2 of Requirement BR-773; the split into small children is a technical decision of the backlog-revision session (2026-10-26). The scope-overlap gate in `select_checks` already uses the board's `enforce_scope_gate`, which computes the task's own diff against the observed `origin/<main>` (BR-777), so it needs no change here.

## What Changes

- `select_checks.py --execute` that would write evidence (managed `--evidence`, quick `--task-evidence`) refuses before any command when the existing evidence at that path is reusable for the current task content by `check_evidence_reuse`, naming the evidence and the reason; a not-reusable decision is printed and the run proceeds.
- Portable `archive` reuses the change's existing reusable `automated-checks.json` by the same rule instead of running the selected checks again, printing the decision; otherwise it runs them as before. `finish` already reuses by that rule, so archive and finish share one receipt.
- `select_checks.py --execute` runs `private_lineage.require_clean_candidate` before any command.
- An `unavailable` affected-test precheck stops validation before the full set with a failure descriptor in the precheck phase.

## Impact

- `template/scripts/select_checks.py`, `template/scripts/openspec_lifecycle.py`, tests, generated platform manifest.
- Specs `completion-lifecycle` (two added requirements) and `platform-lifecycle` (modified precheck requirement).
