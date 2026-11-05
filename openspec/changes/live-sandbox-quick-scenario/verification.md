# Verification: live-sandbox-quick-scenario

OpenSpec-Verify: PASS
Verification-Method: documented equivalent semantic review of proposal, design, tasks and delta specs against the implementation, scenario by scenario, plus real runs of the runner on the private sandbox. No opsx tool invocation.
Automated-Checks-Evidence: automated-checks.json

## Semantic assessment

- Sandbox shape: `compose_snapshot` builds the tree from an exact head, keeps the queue and worker workflows and applies the fixture overlay. Head recorded in `dev-platform/live-sandbox-head.txt`. Rollout cannot reach it: the runner's one-entry registry lives in its workdir and the sandbox is not in the production registry.
- Isolation: dedicated App, own operator config, registry and Backlog binding. `assert_target` refuses another repository, a public one and the platform origin before any write.
- Reset: closes open work, deletes branches and commits forward. PR 1 of the sandbox, left blocked by a failed run, did not stop the next run; PR 2 went through on a new number.
- Entry points: the quick scenario uses `dogfood_task.py`, `agent_friction.py` and the queue only. No label, comment or queue record is written.
- Failure by step: nine runs before success each named the step and observed state.
- Private access: `prepare_checkout`, `prepare_harness`, `_git` and `harness_git` remote reads use the push credential mechanism. Tests prove no token in argv, a named error when the token is missing, and no credential for local reads.
- Repaired delta: the review repair scoped the publication-queue requirement to the sandbox snapshot. `grant_token_reads` implements exactly that; platform workflows are unchanged, and `tests/test_live_scenarios.py` covers both the grant and a workflow without the token step.
- Public snapshot: `sandbox.toml` is excluded from the candidate set; `tests/test_public_distribution.py` and `tests/public_distribution_snapshot_smoke.py` prove audit and archive. Runner tests no longer read that file.
- Failure by step, after review: a command error inside a scenario is reported with its step and keeps earlier results; both output streams reach the error, so the queued handoff is found. The overlay is read from the installed head, not the working tree.
- Target guard: spec wording now matches the check, which refuses another repository, a public one and the platform origin. No production App name exists in configuration to compare with.
- Private queue reads: the snapshot adds Checks and Actions read to each App token step. Without Checks read the queue blocked sandbox PR 1 with `validate` green; with the grant PR 2 merged. This confirms the Checks read need.

## Evidence

- Real run on head 5b1a431c: sandbox PR 2 MERGED by `app/dev-platform-sandbox-lehard`, the change is on sandbox main, `finish` after merge passed.
- Queue preflight passed on the sandbox with the dedicated App.
- `tests/test_live_scenarios.py` and `tests/test_lifecycle_workers.py` pass; selected checks are recorded in `automated-checks.json`.

## Not verified

- The need for Actions read: only the red CI log path uses it, which arrives with the queue scenarios. It stays until that run shows it is needed or not.
- A live concurrent second run: the lock is proven by unit tests only.
- The hosted worker paths on a private repository beyond the queue: a quick task uses no review or finalize. Hosted finalize runs in the queue scenarios.
- Missing token on a private repository is proven by a unit test only.
- The changes after review (error reporting, overlay source, public exclusion) did not get a new live run in this task; the next live run is child two's. The runner path of a green quick task is unchanged by them.
- Known and left: a hung subprocess is bounded only by the lock lease; an edited sandbox ruleset is not reconciled by reset; clone and fetch accept only an uncredentialed github.com HTTPS origin or a local path, which fails explicitly otherwise.
