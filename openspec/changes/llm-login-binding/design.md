## Context

Review jobs run `claude -p` (or `codex exec`) through `pr_review_gate.execute_review`, whose default launcher uses `lifecycle_workers.credential_free_env(os.environ, checkout.parent / "llm-home")`. `scratch_home` copies only declared `--llm-home-file` paths. Claude's keychain login is not copyable and not visible from a scratch HOME. `claude auth status` and `codex login status` are offline, model-free probes with exit status 0 only when logged in; verified in a scratch HOME on the target host.

## Decisions

1. **Token by explicit file, not ambient env.** A worker is started from arbitrary shells, so an operator-declared file is the stable binding. `[independent_review.login.claude] token_file` is read via the same platform configuration (operator-merged), so declaring it once serves every project. The file must be a regular file, absolute (after `~` expansion), outside any git checkout, with no group/world permission bits, and non-empty. Any violation raises `WorkerError` naming the path and rule, never the content.
2. **Scoped injection.** A new `llm_env(provider, config, home)` builds `credential_free_env` plus, for `claude` with a declared `token_file`, `CLAUDE_CODE_OAUTH_TOKEN`. It is used only by the review launcher and the login preflight. `credential_free_env`, `harness_git` and push environments stay free of it, and `CLAUDE_CODE_OAUTH_TOKEN` joins the stripped credential variables so the former accidental pass-through ends.
3. **Preflight before claim.** `work_next` gets an optional `before_claim(job)` hook called after selection and before the claim comment; an exception propagates and nothing is posted. `main` supplies it only with `--run` for `review` jobs. For each provider in `job["providers"]` (or `job["provider"]`) it runs the provider's login probe in a scratch HOME prepared with `scratch_home(..., --llm-home-file)` and `llm_env`. Probe command and timeout come from `independent_review_runner`; a non-zero exit, timeout or missing binary raises naming the provider and both bindings (`[independent_review.login.<provider>]`, `--llm-home-file`). No provider is substituted.
4. **No mandatory binding.** A host whose login works through `--llm-home-file` (for example Codex `.codex/auth.json`) needs no `token_file`; the preflight, not the presence of a declaration, is the truth test.
5. **Separation from #432.** The change adds new functions and a hook but does not alter the harness-git or project-check environment purposes; the later change rebases over the touched call sites.

## Risks

- Token file readable by the user running the worker only; a leak path is the LLM process environment, which is the CLI's own credential by design. Output, comments and receipts never include the value; tests assert that.
- A probe that passes while the model call later fails (quota) is out of scope; the existing in-job readiness probe still applies.
