## 1. Hosted preflight

- [x] 1.1 `template/scripts/lifecycle_workers.py`: add the `hosted-preflight` subcommand (`--mode ci`, `--class`, `--repo`) implementing the ordered checks of the hosted-enablement requirement; one named, secret-free diagnostic per failure; no default or alternate strategy; unchanged adapter `scripts/lifecycle_workers.py`.
- [x] 1.2 Class table (`review`, `finalize`) with its kinds, token rights and provider need as the single source used by the preflight and asserted against the workflow; a table of unhosted kinds (`repair`, `integration-repair`, `retrospective`, `terminal-reconciliation`, `cleanup`) with the named basis each is refused for.
- [x] 1.3 Worker identity helper for `gha-<run_id>-<run_attempt>-<class>` validated by the existing identity pattern.

## 2. Workflow

- [x] 2.1 `.github/workflows/lifecycle-workers.yml`: `workflow_dispatch` as the only trigger, default-branch-only checkout with the installed source contract, keyless `plan` job that requires `DEV_PLATFORM_HOSTED_KINDS` and fails naming it when absent, per-class job with class-scoped App token, `hosted-preflight`, one `work-next --run` with provider declaration, per-class concurrency (no cancel), `timeout-minutes` below the claim TTL, result written to the job summary, pinned third-party actions as in `publication-queue.yml`, and a pinned install of the Claude CLI (exact version, installed before the preflight; a failed install fails the job).
- [x] 2.2 Provider secret passed only to the worker step as the provider's own variable; presence flags only to the preflight; no secret echoed.

## 3. Tests

- [x] 3.1 Workflow structure tests: no `pull_request`/`pull_request_target` trigger, allowed trigger set pinned, no PR-ref checkout; token-holding jobs run only default-branch code; permissions and token inputs per class; no forbidden scopes; timeout < TTL; concurrency; unique worker identity; classes match the preflight table.
- [x] 3.2 Preflight tests: each failing input (unknown kind, unhosted kind with its basis, empty setting, missing secret flag, provider limitation, credential visible to child, token not scoped to this repository) names its input and prints no secret; a passing configuration exits zero.
- [x] 3.3 Behavior tests with the existing fakes: idle outcome and exit; unavailable provider ends unsuccessfully and keeps the job claimable; overlapping claims yield one owner; expired claim reclaimed; moved head discards the old result; hosted kinds issue no merge request.

## 4. Documentation

- [x] 4.1 `docs/engineering/hosted-lifecycle-workers.md`: the owner's ordered enablement instruction (dedicated revocable provider secret, App variables, `DEV_PLATFORM_HOSTED_KINDS` starting with `review`, manual run and reading its preflight outcome, then adding the `workflow_run` and `schedule` triggers through a reviewed change), rollback, the per-kind constraints the pilot must verify, and the BR-433 basis rule; `docs/engineering/agent-workflow.md` links to it without restating the rules (the root `AGENTS.md` concern map is unchanged: this is an operator document, not an always-on rule).

## 5. Delivery

- [x] 5.1 Required platform checks (selected checks with the full test groups, ruff, regenerated `template/dev-platform/platform-manifest.json`) pass and truthful semantic verification is recorded; the real-PR pilot is explicitly not claimed.
- [x] 5.2 Developer friction checkpoint and exact-head developer handoff; archive, review, finalization and merge are run by the coordinator's lifecycle jobs and publication queue.
