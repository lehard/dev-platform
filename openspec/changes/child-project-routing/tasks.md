## 1. Implement routing derivation and proof

- [x] 1.1 Add `resolve_child_routing(parent_issue, requirement_ref, config)` in `template/scripts/requirement_intake.py`: exactly one parent `project:*` label, Backlog repository equals the Requirement repository, committed `config.project_label` equals the parent label; every violation raises `RequirementIntakeError` naming Requirement, expected and found values.
- [x] 1.2 Call it in `materialize_handoff` after the `type:requirement` check and before candidate search and `managed_task.create_task`; keep missing configuration and missing Backlog label as explicit named errors.
- [x] 1.3 Add `verify_child_routing` (exact `project:*` set, `type:internal-change`, open Issue in the Backlog repository, parent back-reference) and run it for the reused-candidate path before `link_child` and for both paths after linkage, before building the success result.
- [x] 1.4 Make a pre-existing child with a conflicting or absent `project:*` label a visible error with repair guidance and zero label mutation; only a missing `type:internal-change` is completed through existing `link_child`, then re-verified.
- [x] 1.5 Extend `link_child` to reject a contradictory child `project:*` label before editing and to read back `type:internal-change` after the label write.

## 2. Verify behavior

- [x] 2.1 Add regression tests in `tests/test_requirement_intake.py`: consistent routing; label contradiction (assert `create_task` not called); Backlog repository contradiction; parent with zero and with two `project:*` labels; missing configuration; read-back missing project label, missing `type:internal-change`, missing back-reference; reused child with conflicting project label (assert no label mutation command); reused child missing only `type:internal-change` repaired once and re-verified; `link_child` contradictory label and non-persisted label write.
- [x] 2.2 Confirm in `tests/test_managed_task.py` that direct `create_task` behavior is unchanged, and verify source/template parity (`scripts/requirement_intake.py` shim, rendered template) through the standard checks.
- [x] 2.3 Run `python3 -m compileall -q template/scripts scripts`, `python3 scripts/managed_projects.py validate`, `python3 scripts/run_test_groups.py --all`, `python3 template/scripts/openspec_lifecycle.py check`, semantic OpenSpec verification; write truthful verification.md.

## 3. Deliver through managed lifecycle

- [ ] 3.1 Resolve the developer friction checkpoint (`python3 scripts/agent_friction.py checkpoint --result none --review-note "Reviewed actual task path"` or the recorded event id).
- [ ] 3.2 Publish through the authoritative managed lifecycle (`python3 scripts/dogfood_task.py finish`); complete the coordinator handoff or terminal archive/publication according to the authoritative lifecycle state, reporting any blocker instead of completion.
