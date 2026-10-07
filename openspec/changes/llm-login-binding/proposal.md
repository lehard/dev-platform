## Why

On macOS the Claude CLI stores its login in the login keychain. The review worker runs the reviewer with a scratch HOME whose keychain search list contains only the system keychain, so the CLI reports "Not logged in" and every `claude` review job ends `availability: unavailable` and `blocked-retryable`; providers are sticky, so retries repeat it. Readiness is currently proven only inside the claimed job (`independent_review_runner.preflight`), after the claim, so each failure burns an attempt.

The CLI also accepts `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`). `credential_free_env` only removes GitHub-scoped variables, so such a token passes into every environment built from it, including harness Git, by accident rather than by contract.

## What Changes

- Add an explicit provider-scoped login binding read from `[independent_review.login.<provider>]` in the platform configuration (operator-merged, machine-local): for `claude`, a `token_file` path. The worker validates the file and injects its content as `CLAUDE_CODE_OAUTH_TOKEN` only into the LLM environment of that provider.
- Make `credential_free_env` strip `CLAUDE_CODE_OAUTH_TOKEN`, so no environment receives it implicitly.
- Add a login preflight run by `work-next --run` after a review job is selected and before its claim comment is posted: each provider of the job must pass its offline login probe in the scratch HOME and environment the reviewer will run in.
- Document the macOS keychain cause and the operator steps.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `lifecycle-workers`: explicit LLM login binding and a login preflight before claiming a review job.

## Impact

Platform-owned `template/scripts/lifecycle_workers.py` (environment construction, `work_next` hook, CLI), the review launcher environment in `template/scripts/pr_review_gate.py`, `template/scripts/independent_review_runner.py` (login settings and probe commands), their tests and the docs that describe `[independent_review]`. Operators who declare no `token_file` keep working with `--llm-home-file` logins; the preflight now fails them early and explicitly if the login is absent. An ambient `CLAUDE_CODE_OAUTH_TOKEN` stops reaching reviewers; the operator declares the file instead.

## Success Criteria

With a valid token file declared in the operator config, a `claude` review job runs on this macOS host with the worker's scratch HOME and no change to the credential-free boundary. Without any usable login, `work-next --run` exits non-zero before claiming, naming the provider and how to bind a login. No token value is printed, recorded or present in harness Git or GitHub-facing environments.

## Non-goals

Creating or rotating tokens, touching the keychain or the operator's machine config (the operator does these), cross-provider fallback, project-check environments, worker identity and repair provider routing (lehard/development-backlog#432), and repair or finalize executors beyond reviewing.
