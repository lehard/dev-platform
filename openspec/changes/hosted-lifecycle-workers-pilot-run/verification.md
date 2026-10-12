OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the committed diff against the lifecycle-workers delta, proposal, design and tasks; deterministic workflow-structure tests; repository-owned selected checks on the committed head
Automated-Checks-Evidence: automated-checks.json

Implementation: authored by a delegated Claude Sonnet executor opened with `begin-claude-delegation` before any write and recorded with `record-claude-execution`; the supervisor reviewed the diff (workflow, tests, document) before committing. No supervisor-written content, no process deviation.

Scope: the package was narrowed from "run the pilot and record the decision" to "enable the automatic triggers and fix the first-run findings" before start (superseded package revision, Issue body aligned); recording the evidence and the placement decision is the separate change `hosted-lifecycle-workers-placement-decision`.

Completeness: `.github/workflows/lifecycle-workers.yml` keeps `workflow_dispatch` and adds `workflow_run` of "Dev Platform publication queue" (`completed`) and a 10-minute `schedule`, installs Node 22.12.0 (the pinned Claude CLI declares `node >=22`; the first manual run, run 38221555792, passed all preflights including the Claude readiness probe, reported `idle` and warned `EBADENGINE` on Node 20); tests pin the exact trigger set, the queue workflow name and event type, the cron, the absence of pull-request-style triggers, that no step reads `github.event.workflow_run`, and the Node major; `docs/engineering/hosted-lifecycle-workers.md` documents the triggers, rollback (remove `workflow_run` and `schedule`) and the first manual run.

Correctness: jobs, permissions, token rights, guards, concurrency, timeout, worker identity and preflight are unchanged; the existing default-branch guard holds for the new triggers because `workflow_run` and `schedule` run the default branch; the payload is unused so a PR-influenced value cannot reach a token-holding step. `DEV_PLATFORM_HOSTED_KINDS` is still required and `finalize` stays off (variable is `review`).

Coherence: delta requirement, design decisions 1-6, tasks and the document agree on triggers, runtime and the `finalize` boundary.

Limits stated plainly: the new triggers have not yet fired on `main`; the first automatic run is observed and reported after merge, not claimed here. Idle runs start about every 5 minutes (the queue workflow's own schedule drives `workflow_run`) plus the 10-minute tick; the cost of that cadence is part of the next change's record.

Checks actually run: `python3 -m compileall -q template/scripts scripts`, `python3 -m ruff check scripts template/scripts tests` and `python3 scripts/run_test_groups.py --all` success on the committed head via `select_checks.py --execute --evidence`; `check_docs_links.py`, `check_private_backlog_refs.py` and the 51 tests of `test_hosted_workers` OK.
