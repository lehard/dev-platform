# Verification: claim Requirement card at start

OpenSpec-Verify: PASS
Verification-Method: Manual scenario-by-scenario review of Requirement development-backlog#333, the proposal, design, the agent-workflow delta spec, the changes in requirement_intake.py and execute_requirement.py, the task-intake doc and the new regression tests; the platform check suite.

Scenarios: (1) Card claimed before slow preparation: `start` calls `claim_started_requirement` right after durable state init; test_second_agent_does_not_see_started_requirement_as_free. (2) Restart continues: rerun is idempotent and `advance` reconciles at entry; test_rerun_continues_without_parallel_ownership_or_ready_write and the updated advance tests (entry plus post-start reconcile). (3) Failure after durable start: state kept, rerun instruction reported, `Ready` never written; test_claim_failure_keeps_state_reports_rerun_and_never_writes_ready.

Defect demonstrated before repair: with the claim call disabled, 3 of 4 new tests failed; with it restored all pass.

Not exercised: a real GitHub Project card mutation (the board is a stateful fake; `requirement_board.reconcile_nonterminal` and its status mapping are existing, separately tested code), and the release and downstream rollout, which are separate steps of the Requirement after merge.

Checks completed before archive:

- `python3 -m unittest tests.test_requirement_card_claim tests.test_requirement_execution tests.test_requirement_flow_e2e` — 18 passed.
- `python3 scripts/run_test_groups.py --all --jobs 2` — all 15 groups passed. Two earlier runs at default parallelism each had one failing group: fast-b (three existing advance tests that did not expect the new entry reconcile; tests updated) and fast-c (test_already_merged_reconciliation_still_times_out_for_a_hung_lock_holder, a 10s lock-holder readiness timeout under load, unrelated to this change; fast-c passed when rerun alone).
- `python3 scripts/managed_projects.py validate` — passed.
