## Decisions

- **Model.** `worker_preflight` reuses `lifecycle_preflight`: `Condition`, `ConditionResult` and its states. Each condition calls the function the real path calls. A condition that cannot be evaluated refuses.
- **Conditions by kind.** Trusted contract: all kinds. `gh` credential with repository write: kinds that push or post. Provider credential and readiness: review, repair kinds. Writer runtime (macOS, sandbox runtime, Claude CLI): repair kinds with `--writer`. Finalize tools: finalize. Backlog access and shared workspace: post-merge kinds.
- **Job-dependent condition.** Without `--providers`, the providers a selected review job names are probed after selection and before claim, through the existing eligibility path; a refusal is listed in `refused` and is never a quiet skip. A worker with `--providers` keeps its accepted filtering: a job with no ready provider is skipped without a claim.
- **One module identity.** The script runs through the importable `lifecycle_workers`, so `except` and `isinstance` see the classes the executors raise.
- **Exit code.** An environment stop, before or after claim, exits 3, so the post-merge runner tells it from a job failure.
- **Gate functions.** `active_gh_token` keeps its body and gains the condition by a decorator, leaving a sibling change to that function untouched.
- **Environment class.** `EnvironmentFailure(WorkerError)` carries a condition id from the registry, and only a registered condition raises it. The `released` result records `class: environment` and the condition.
- **Counting.** `release_count` skips the environment class, while `_releases` keeps every release because a claim ends on any of them. A separate `MAX_ENVIRONMENT_RELEASES` bound ends in `blocked-escalation` with an operational cause, which `operational_escalation` recognizes, so `resume` applies. Old `released` comments carry no class and count as before.
- **Finalize.** `run_claimed_finalize` lets `EnvironmentFailure` pass instead of turning it into `blocked`.
- **Post-merge.** The runner journals a preflight refusal as an environment stop, not a job failure. The `process-check-unavailable` path keeps its behavior through the same class.
- **Receipt order.** `validated-push` stays before the push; recovery depends on it. The push credential is proven before claim instead.

## Risks

This changes queue job accounting. Unit tests and offline acceptance carry it; if the BR-993 queue scenarios are not in main at handoff, there is no live proof and the report says so.
