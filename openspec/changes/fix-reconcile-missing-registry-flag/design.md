# Design: Thread --registry into every rollout_supersession.py reconcile call

## Root cause, confirmed empirically

Reproduced live: dispatched `Roll Out Platform` for `lehard/planner-agent-lab` against `v1.5.3` (after both the legacy-baseline-bridge and trailing-blank-line fixes were already shipped and released). `copier update` and `git diff --cached --check` both succeeded; the run then failed at the "Supersede older validated rollout PRs" step with `rollout_supersession.py reconcile: error: the following arguments are required: --registry`.

Confirmed via `scripts/rollout_supersession.py`'s argparse definitions (`reconcile_parser.add_argument("--registry", type=Path, required=True, ...)`) that `reconcile` always required this flag, and via `reconcile`'s own body (`require_managed(repository, registry)`, which loads the registry and asserts the repository is `managed` with a matching `default_branch`) that it is a real safety check, not incidental. Confirmed via `git log --oneline -- scripts/rollout_supersession.py` that this file has exactly one commit ("Initial public snapshot") -- the missing flag at all three call sites is not a regression from recent work, it has always been missing, and simply was never reached by a real rollout run until the two prior fixes in this same investigation cleared the earlier blockers.

## Fix

`rollout_supersession.py reconcile` is invoked from three places, across two workflows, in two jobs that are NOT the `plan` job that already checks out the private operator registry in both files:

1. `.github/workflows/rollout.yml`'s `rollout` job (two `reconcile` calls: "Supersede older validated rollout PRs" and "Reconcile rollout PRs already adopted by downstream base").
2. `.github/workflows/reconcile-stale-rollouts.yml`'s `reconcile` job (one call: "Plan or apply stale rollout supersession").

Both of these jobs run on their own fresh GitHub Actions runner, separate from their respective `plan` job -- job outputs carry only explicitly declared step outputs (strings), never files or checked-out working trees, so `plan`'s `operator/` checkout cannot be reused. Each job therefore needs its own copy of the exact same "Require Dev Platform operator repository" -> "Create operator registry read token" -> "Checkout operator registry" step sequence already used in the corresponding `plan` job (byte-identical steps, just re-run once per job that needs the registry), then `--registry operator/managed-projects.json` passed at each of the three `reconcile` call sites.

`find-pending` (a fourth `rollout_supersession.py` subcommand, used once in `rollout.yml`) does not take `--registry` at all and needed no change -- confirmed by reading its own argparse definition.

## Explicitly out of scope

- Any change to `scripts/managed_projects.py` or the registry schema.
- Making `reconcile`'s `--registry` optional: it is a genuine safety check (repository is managed, base branch matches), not incidental friction.

## Tests

`tests/test_rollout_supersession.py`: two new regression tests -- `test_rollout_jobs_reconcile_calls_pass_the_required_registry_flag` (asserts both `reconcile` call sites in `rollout.yml` include `--registry operator/managed-projects.json`, and that the `rollout` job checks out the operator registry, via a duplicated "Checkout operator registry" step count of 2 across the whole file) and `test_reconcile_stale_rollouts_reconcile_call_passes_the_required_registry_flag` (same, for `reconcile-stale-rollouts.yml`). `tests/test_managed_rollout.py`: updated the existing pinned-action count assertion (`actions/create-github-app-token` pin count 3 -> 4 in `rollout.yml`) with an updated comment explaining the second `registry-token` instance.
