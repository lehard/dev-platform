## 1. Execution plan and pre-snapshot

- [x] 1.1 Add `execution_plan` to `Route` and `_route_from_payload` in `template/scripts/model_routing.py`; derive `delegated-child` vs `supervisor-retained` (with policy) from `_retention_policy` in `prepare`, keeping `start_tier` and actual `execution` as separate fields.
- [x] 1.2 Add the task-content pre-snapshot (`snapshot(task_root)` minus the lifecycle allow-list constant) and `_task_content_diverged(route)`; make `prepare` refuse when task content or non-package commits already diverged, naming the paths, including source deletions from staged or committed moves into excluded lifecycle locations.
- [x] 1.3 Make a missing/invalid plan or snapshot a named `RoutingError`; no default plan.

## 2. Delegation lifecycle

- [x] 2.1 Add `begin_claude_delegation` plus `begin-claude-delegation` CLI in `model_routing.py` and `dogfood_task.py`; refuse after divergence, for retained plans, with an existing execution or an already-open delegation.
- [x] 2.2 Require an open delegation in `record_claude_execution`; close it; keep `launched: None`, `outcome: "claimed"`, self-reported evidence; update `prepare_claude_handoff` output to name the mandatory begin step.
- [x] 2.3 Open a platform-observed delegation in `dispatch_codex` only after confirmed child process launch; close pre-launch refusals/failures with outcome `not-launched` and prevent them authorizing supervisor writes, retention or escalation.
- [x] 2.4 Require a matching `supervisor-retained` plan in `record_retained_execution`; refuse for a delegated plan; restrict `escalate` plan switch to real-delegation or unchanged-content cases; preserve child outcomes during retained finalization after escalation and refuse unresolved containment or writer safety in recovery.

## 3. Early gate wiring

- [x] 3.1 Implement `require_early_routing_gate(root)` and call it from `dogfood_task.py` `status` and `finish`, `model_routing.py verify-routing` (active change), and the check/test execution entrypoint before any check runs; keep the archive gate in `openspec_lifecycle.py`.
- [x] 3.2 Keep projects without managed state or `model_routing` unaffected; confirm the guard matches `dogfood_task.require_routing_gate`.

## 4. Regression tests

- [x] 4.1 Delegated R2: route, begin, child content change, record, early and archive gates pass.
- [x] 4.2 Retained: `complex` and `parent-only-topology` plans declared at route, supervisor content change, `record_retained_execution`, gates pass; retained recording on a delegated plan refused.
- [x] 4.3 Early block: supervisor writes under a delegated plan without begin; `status`, check entrypoint and `verify-routing` fail before archive; record-after-the-fact and late begin refused; route refused on pre-diverged content.
- [x] 4.4 Recovery: escalation without real delegation on diverged content refused; escalation with a real delegation allowed; no path writes `launched: true` or a fake retrospective delegation.
- [x] 4.5a Re-route after a failed/abnormal platform-observed Codex delegation whose post-snapshot equals current content is permitted; re-route after any other divergence (including self-reported Claude delegation) is refused; unresolved containment violations, ambiguous writers and escaped integration writes cannot become a fresh baseline.
- [x] 4.5 Codex plan/delegation consistency and legacy plan-less record behavior; update existing `record_claude_execution` tests to begin a delegation first.
- [x] 4.6 Source/template parity: render a downstream fixture and run the early gate there; update `docs/engineering/model-routing.md` (plan, pre-launch step, early gate, refused recovery).

## 5. Verify and record

- [ ] 5.1 Run `python3 -m compileall -q template/scripts scripts`, the targeted routing tests, `python3 scripts/run_test_groups.py --all` and `python3 template/scripts/openspec_lifecycle.py check`.
- [ ] 5.2 Run semantic OpenSpec verification and record the actual commands/results in verification.md.

## 6. Complete delivery

- [ ] 6.1 Resolve the developer friction checkpoint and publish through the managed lifecycle.
- [ ] 6.2 Complete coordinator handoff or terminal archive/publication according to the authoritative lifecycle state.
