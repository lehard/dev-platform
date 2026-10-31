## 1. Contract
- [ ] 1.1 `requirement_terminal.py`: item parsing, decision markers and trust, `OwnerAcceptancePending` gate in `reconcile_parent`, `accept` command, explicit Issue state.
- [ ] 1.2 `requirement_intake.py create`: accept the `## Operator acceptance` section.

## 2. Runner and overview
- [ ] 2.1 `integration_contour.py` and composition terminal path: completed outcome `requirement-awaits-owner-acceptance`.
- [ ] 2.2 `lifecycle_overview.py`: waiting-for-owner listing with check and accept command; `execute_requirement._await_post_merge` explicit state.

## 3. Docs and tests
- [ ] 3.1 Docs: task-intake, chat-coordinator, requirement authoring; platform manifest.
- [ ] 3.2 Tests: parsing and malformed lines, untrusted and latest decisions, gate before mutation, terminal outcome without attempts, accept closes or reports, unknown item and closed Requirement refused, overview listing, explicit state.

## 4. Verification
- [ ] 4.1 Full validation and semantic OpenSpec verification.
