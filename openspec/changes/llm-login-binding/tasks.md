## 1. Login binding

- [x] 1.1 Add the `[independent_review.login.<provider>]` settings validation (supported providers, `token_file` shape) as `login_bindings` and the per-provider login probe commands as `LOGIN_PROBES` in `template/scripts/lifecycle_workers.py`; the runner's `settings` reader supplies the table.
- [x] 1.2 In `template/scripts/lifecycle_workers.py` add `read_login_token(path)` (regular file, absolute after `~`, outside any git checkout, no group/world bits, non-empty; errors name the path and rule and never contain the content) and `llm_env(provider, config, home)`; add `CLAUDE_CODE_OAUTH_TOKEN` to the stripped credential variables.
- [x] 1.3 Use `llm_env` for the review launcher in `template/scripts/pr_review_gate.py`; leave `harness_git`, push and `run_llm` environments untouched.

## 2. Preflight before claim

- [x] 2.1 Add the optional `before_claim` hook to `work_next` (called after selection, before the claim comment, skipped for dry runs) and the login preflight in `main` for `--run` review jobs: per job provider, run the probe in the prepared scratch HOME and `llm_env`; failure exits 2 naming the provider and both bindings and posts nothing.
- [x] 2.2 Expose the same login check through `independent_review.py preflight` output so its readiness matches the worker's.

## 3. Documentation

- [x] 3.1 Describe the macOS keychain cause, the `token_file` binding, file requirements and the `--llm-home-file` alternative where `[independent_review]` settings are documented (`docs/engineering/openspec-workflow.md` and its `template/` counterpart).

## 4. Regression tests

- [x] 4.1 `tests/test_lifecycle_workers.py`: valid and invalid token files (missing, empty, directory, relative, group/world readable, inside a checkout); `llm_env` includes the token only for `claude`; `credential_free_env`, harness Git and push environments never contain it; an ambient `CLAUDE_CODE_OAUTH_TOKEN` is stripped; the token value appears in no output or error.
- [x] 4.2 `tests/test_lifecycle_workers.py` and `tests/test_pr_review_gate.py`: failing probe for `claude` and for `codex` exits non-zero before any claim comment and records no attempt; passing probe proceeds to the unchanged claim; dry run runs no probe; the review launcher uses the bound environment.
- [x] 4.3 `tests/test_independent_review.py`: preflight output reflects the login check.

## 5. Verify

- [x] 5.1 Run `python3 -m compileall -q template/scripts scripts`, `python3 scripts/managed_projects.py validate`, `python3 scripts/run_test_groups.py --all` and `python3 template/scripts/openspec_lifecycle.py check`.
- [x] 5.2 Run semantic OpenSpec verification for every delta scenario and write a truthful `verification.md` naming the commands and methods actually used and the limitation that the real macOS keychain host check is operator-performed.

## 6. Complete delivery

- [x] 6.1 Resolve the developer friction checkpoint and publish through the managed lifecycle.
- [x] 6.2 Complete coordinator handoff or terminal archive/publication according to the authoritative lifecycle state.
