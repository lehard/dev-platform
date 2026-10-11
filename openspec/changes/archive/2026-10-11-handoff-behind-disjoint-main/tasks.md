## 1. Classifier

- [x] 1.1 Add `observe_task_base_currency` to `template/scripts/_platform_common.py`: `fresh` / `behind-disjoint` / `reconcile-required` with observed main, merge base, overlapping paths or conflict; explicit `TaskFreshnessError` on fetch failure, missing merge base or unsupported git.
- [x] 1.2 Add `coordinator_candidate(root)` derived from the existing publication-queue configuration.

## 2. Gates

- [x] 2.1 `template/scripts/select_checks.py`: for a coordinator candidate without `--proven-base`/`--contribution-base`, accept `behind-disjoint` for evidence-producing execution, print the contract line and record it in the evidence payload; block `reconcile-required` before any command with files/conflict and the reconcile command.
- [x] 2.2 `template/scripts/project_publish.py` (the developer handoff's first-publication fresh-base check, which is the `branch-base` gate a coordinator candidate reaches), `template/scripts/task_reconciliation.py` and `template/scripts/finish_task.py` status: accept `behind-disjoint` for a coordinator candidate; `status` reports it as not requiring reconcile.

## 3. Tests

- [x] 3.1 Classifier tests on a real temporary git repository: fresh; behind with disjoint files; behind with an overlapping file; behind with a conflict; no merge base.
- [x] 3.2 Gate tests: coordinator candidate behind-disjoint passes select_checks evidence and finish preflight; overlapping blocks with the named file; a non-coordinator task behind main is still blocked.

## 4. Readiness

- [x] 4.1 Real dogfood is observed after this change reaches main: a coordinator candidate handed off behind a disjoint main without reconcile and merged by the queue on green integrated-head checks. It is recorded in the Requirement retrospective, because it can only happen after this change merges.

## 5. Delivery

- [x] 5.1 Required platform checks, truthful verification, archive, retrospectives, publication.

## 6. Documentation

- [x] 6.1 `docs/engineering/agent-workflow.md` describes the behind-disjoint developer-handoff contract next to the proven-base contract.
