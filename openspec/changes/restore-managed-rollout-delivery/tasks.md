## 1. Establish incident evidence

- [x] 1.1 Re-read rollout diagnostics for `lehard/cuby`, `lehard/Jara_Fin` and `lehard/planner-agent-lab` at the failing v1.4.25 run.
- [x] 1.2 Resolve the narrow failure stage/root cause for each repository and classify ownership as platform defect, project-specific reconciliation, or dependency on backlog #12.
- [x] 1.3 Confirm no existing managed change already owns any newly identified non-permission platform defect before implementing it.

## 2. Repair platform-owned rollout defects

- [x] 2.1 Repair the Cuby `.github/workflows/dev-platform.yml` rollout conflict only if the root cause is platform-owned and can be solved without silent overwrite.
- [x] 2.2 Repair any independently confirmed platform-owned failure behind Jara_Fin/planner-agent-lab `exit 2`.
- [x] 2.3 Improve terminal classification where structured state can replace an avoidable `unknown` result.
- [x] 2.4 For permission-owned failures, record the #12 dependency and do not duplicate its implementation.

## 3. Regression coverage

- [ ] 3.1 Reproduce each platform-owned failure class with deterministic rollout tests/fixtures.
- [ ] 3.2 Prove unresolved Copier/ownership conflicts still fail closed.
- [ ] 3.3 Prove successful retry uses the existing exact-version reviewable-PR path and tracker reset semantics.

## 4. Acceptance and delivery

- [ ] 4.1 Run full applicable platform/OpenSpec/rollout validation.
- [ ] 4.2 Retry the current cumulative immutable release across all managed inventory entries.
- [ ] 4.3 Confirm Cuby, Jara_Fin and planner-agent-lab each reach successful preparation/PR-or-already-current state; any leg dependent on #12 must use its shipped result.
- [ ] 4.4 Confirm rollout-failure trackers close through normal successful automation.
- [ ] 4.5 Record truthful semantic verification, archive the change and publish any required cumulative platform release through protected main.
