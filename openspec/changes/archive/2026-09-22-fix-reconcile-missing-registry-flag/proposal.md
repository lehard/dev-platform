# Proposal: Thread the required --registry flag into every rollout_supersession.py reconcile call

## Why

The first real post-cutover rollout to get past both the legacy-baseline-bridge fix and the trailing-blank-line fix (`lehard/planner-agent-lab`, `v1.4.38 -> v1.5.3`) failed one step further, at `rollout_supersession.py reconcile: error: the following arguments are required: --registry`. `reconcile`'s `--registry` argument is `required=True` (it verifies the repository is genuinely `managed` and that the requested base branch matches the registry's recorded `default_branch` before closing any PR), but none of its three call sites across two workflows ever passed it — a gap present since this repository's first fresh-history commit, simply never exercised by a real end-to-end rollout run before now.

## What Changes

- `.github/workflows/rollout.yml`'s `rollout` job: add its own "Require Dev Platform operator repository" / "Create operator registry read token" / "Checkout operator registry" steps (the `rollout` job runs on a separate runner from `plan` and cannot reuse `plan`'s checkout), then pass `--registry operator/managed-projects.json` to both `reconcile` calls in that job.
- `.github/workflows/reconcile-stale-rollouts.yml`'s `reconcile` job: the same addition, for its one `reconcile` call.

## Success Evidence

A real `Roll Out Platform` dispatch for a managed project reaches and passes the supersession-reconcile step without a missing-argument error. `python3 scripts/run_test_groups.py --all` stays green, with new regression tests asserting `--registry operator/managed-projects.json` appears in all three call sites.

## Dependencies

None. This is a narrower continuation of `isolate-operator-registry` (lehard/development-backlog#145), which threaded the operator registry into `managed_projects.py` calls but did not cover `rollout_supersession.py reconcile`'s separate, job-scoped requirement.
