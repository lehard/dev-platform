OpenSpec-Verify: PASS
Verification-Method: equivalent semantic OpenSpec review of completeness, correctness and coherence against the accepted platform specs plus this active delta
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

Implementation was delegated to a Claude Sonnet subagent in this worktree (Codex quota reserved) from a read-only plan prepared earlier by Codex, and reviewed by the supervisor.

Offline scenario. `parallel_lifecycle_acceptance.py run --output <dir>` admits three managed candidates before any merge in a disposable sandbox with real git, the real coordinator and worker code, deterministic provider responses and a strict local GitHub adapter over a bare remote: B receives a material review finding, a real repair, a repeat review, finalization and a main update; C is finalized, conflicts with A, goes through integration repair, is re-reviewed against its archive, finalizes again and merges; merges run in order, followed by retrospective, terminal reconciliation and cleanup. Operator actions are recorded at the adapter (with a negative test); failed runs still clean up, verify containment and write the summary; lifecycle checks are structured. Runtime about 30-45 s.

Platform gap fixed: a finalized candidate returned to review after integration repair is now reviewed against its archived change (`pr_review_gate.execute_review` resolves archived changes), with a regression test.

Contract change approved by the user: the real dogfood run is deferred to lehard/development-backlog#391 after BR-353 merges, because the coordinator only runs once its workflow is on main. This change delivers the offline scenario, portability notes and the dogfood evidence template; no real dogfood run is claimed.

Known limitations (advisory): faked components are the gh adapter, reviewer launcher, scripted writers, scripted archiver and post-merge Requirement/Project operator; developer semantic handoffs are scripted; the scenario mutates process globals and is safe as a one-shot process; a partial setup failure can leave sandboxes.

Independent review: round 1 blocked only on the missing real dogfood run (resolved by the approved contract change); round 2 ready (advisories).

Checks: compileall, ruff, `tests/test_parallel_lifecycle_acceptance.py`, affected gate tests, import-isolation, module-identity and shared-writer guards, `openspec_lifecycle.py check`, `run_test_groups.py --all` and the selected full validation (automated-checks.json). Completeness: tasks 1.1-3.2 (2.1 as reworded).
