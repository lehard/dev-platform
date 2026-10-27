## 1. Fallback removal
- [x] 1.1 `select_checks.py`: import `block_for_scope_conflict` directly and remove the `ImportError` stub.
- [x] 1.2 `finish_task.observe_private_reference_blocker`: apply by `private_lineage.enabled`; a missing guard with private lineage enabled is a named blocker.
- [x] 1.3 `finish_task.find_board_id` / `finish_board`: explicit errors for an unreadable or malformed board and for a failed release in every caller; keep the inventoried legitimate absences.

## 2. Verification
- [x] 2.1 Tests: corrupt board and failed release stop finish naming the board or claim; absent claim releases nothing; guard missing with private lineage enabled is a blocker, disabled is not applicable; select_checks has no stub.
- [x] 2.2 Run full validation and semantic OpenSpec verification.
