# Verification

OpenSpec-Verify: PASS
Verification-Method: Equivalent semantic review of the materialized #18 contract against task-local state ownership, fresh/resume classification, exact-head terminal reconciliation, and Project-status mutation boundaries; no material findings remained.
Automated-Checks-Evidence: automated-checks.json

Evidence reviewed:

- Bounded bootstrap recovery confirmed the inherited integration marker named `lehard/development-backlog#15`; it was recorded and removed only inside the new #18 task worktree before materialization. The normal `start_managed_task.py` path then resumed #18 and reconciled `In progress`.
- Fresh starts accept only an inherited legacy tracked marker as non-authoritative; conflicting task-local state, missing canonical provenance for a genuine resume, and canonical/source mismatches remain fail-closed.
- Terminal reconciliation derives `source_issue` and `change` from archived task-local provenance/state, cross-checks any integration marker without adopting it, and reports pending reconciliation without changing a foreign Project item after GitHub has confirmed the exact PR merge.
- `python3 -m compileall -q template/scripts scripts`, `python3 scripts/managed_projects.py validate`, `python3 -m unittest discover -s tests -q`, `python3 template/scripts/openspec_lifecycle.py check`, and strict validation of this active change completed successfully before archival.
