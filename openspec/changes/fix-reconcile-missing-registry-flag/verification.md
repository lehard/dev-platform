# Verification: Thread the required --registry flag into every rollout_supersession.py reconcile call

## Method

`/opsx:verify` was not available in this execution environment. Performed the documented equivalent manual OpenSpec semantic review: re-read `proposal.md`'s Why/What Changes/Success Evidence, `design.md`'s root-cause analysis, and the `managed-rollout` spec delta's ADDED requirement with its two scenarios, then checked the implementation (two workflow files) and the test suite against each individually.

## Root cause confirmation

Before writing this change: reproduced the failure live by dispatching `Roll Out Platform` for `lehard/planner-agent-lab` against `v1.5.3` (after the legacy-baseline-bridge and trailing-blank-line fixes were already shipped and released); `copier update` and `git diff --cached --check` both succeeded, and the run failed at "Supersede older validated rollout PRs" with `rollout_supersession.py reconcile: error: the following arguments are required: --registry`. Confirmed via `scripts/rollout_supersession.py`'s argparse (`reconcile_parser.add_argument("--registry", ..., required=True)`) and its `reconcile()` body (`require_managed(repository, registry)`) that this is a genuine safety check, not incidental. Confirmed via `git log --oneline -- scripts/rollout_supersession.py` (one commit: "Initial public snapshot") that this gap predates all work in this session.

## Success evidence review

- "A real rollout dispatch reaches and passes the supersession-reconcile step" — verified structurally: all three call sites (`rollout.yml`'s two `reconcile` calls, `reconcile-stale-rollouts.yml`'s one) now pass `--registry operator/managed-projects.json`, and each job that needs it independently checks out the operator registry first.
- "Full test suite stays green with new regression coverage" — `python3 scripts/run_test_groups.py --all`: 13/13 groups, 1142/1142 tests.

## Spec-delta scenario review

- "A rollout or maintenance job runs on a separate runner from its planning job" — both `rollout.yml`'s `rollout` job and `reconcile-stale-rollouts.yml`'s `reconcile` job now independently obtain a read-scoped operator registry checkout before their `reconcile` calls, confirmed by reading the full files (not just the diff hunks).
- "Reconcile is invoked without a registry" — this is the exact failure mode reproduced live before the fix; `scripts/rollout_supersession.py` itself already fails closed on a missing `--registry` (argparse `required=True`), unchanged by this fix.

## Independent review

A native Claude executor (general-purpose subagent) independently read the proposal/design/spec and the full diff, read `rollout_supersession.py`'s argparse directly to confirm `reconcile` requires `--registry` and `find-pending` does not (rather than trusting the design doc), confirmed step ordering/scoping/token permissions in both workflow files by reading the full post-change files, traced the new tests' regex against the actual file content to confirm they are not vacuous, and ran both the targeted tests (51 passed) and the full suite itself via a background Monitor (13/13 groups, 1142/1142 tests, outcome success). It reported no blockers and two nits, both addressed here:

- `design.md` described the new operator-checkout steps as "byte-identical" to the `plan` job's version, when they intentionally omit the `plan` job's own `APP_CLIENT_ID`/`APP_PRIVATE_KEY` presence check (redundant, since both the `rollout` job and the `reconcile` job already run an earlier, separate "Require rollout GitHub App configuration" step checking the same variables) and use different step names in each file. Reworded `design.md` to describe the sequences as equivalent rather than byte-identical, and to explain the intentional omission.
- `docs/managed-rollout.md`'s "CI resolution" section described the `--registry` threading as applying only to `scripts/managed_projects.py` invocations, without mentioning `rollout_supersession.py reconcile`'s independent requirement for the same flag, or that a job on a separate runner from `plan` must repeat the checkout itself. Extended that section's step 4 to cover both.

## Tests run

```
python3 -m compileall -q template/scripts scripts
python3 -m unittest tests.test_managed_rollout tests.test_rollout_supersession tests.test_rollout_control_plane_regressions -v   # 51 passed
python3 scripts/run_test_groups.py --all        # 13/13 groups passed, 1142 tests
openspec validate fix-reconcile-missing-registry-flag --strict   # valid
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/rollout.yml')); yaml.safe_load(open('.github/workflows/reconcile-stale-rollouts.yml'))"   # both parse
```

No unresolved finding remains.

OpenSpec-Verify: PASS
Verification-Method: manual-semantic-review (opsx:verify unavailable in this environment)
Automated-Checks-Evidence: automated-checks.json
