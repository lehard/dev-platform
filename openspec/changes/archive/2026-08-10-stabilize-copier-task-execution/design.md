## Decision

`copier update` and the guarded `copier recopy` fallback will use `--skip-tasks`. Copier can otherwise run `_tasks` from a historical source snapshot while it constructs an update, which makes rollout behavior depend on an obsolete bootstrap's OpenSpec CLI assumptions.

After Copier has completed without unresolved rejects, managed rollout will invoke the rendered candidate's `scripts/platform_bootstrap.py` once. In an existing Git repository this bootstrap synchronizes the platform-version record and runs the platform doctor; it does not initialize or overwrite project-owned OpenSpec integration state.

## Safety and rollback

- No bootstrap runs after a failed/conflicted Copier update.
- Project-owned file snapshots and strict diff validation continue unchanged.
- A missing candidate bootstrap is blocking rather than silently skipped.
- Rollback is a reviewed platform version rollback; no downstream default branch is changed directly.

## Verification

Tests will assert task skipping for both update paths, assert candidate bootstrap invocation, parse the root OpenSpec configuration as YAML, and run the real project-harness recopy smoke with the supported OpenSpec CLI.
