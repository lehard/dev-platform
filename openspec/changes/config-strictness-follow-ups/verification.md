OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the platform-config delta, proposal, design and tasks; targeted unit tests; `openspec validate --strict`; repository-owned selected checks recorded by the lifecycle; local `public_distribution_snapshot_smoke.py` at candidate stage
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Owner decision 2026-10-28: `DEV_PLATFORM_GITHUB_RETRY_ATTEMPTS` stays; unset applies the documented 4 attempts, a non-integer or a value below 1 is an explicit error.

## Completeness

- Retry setting unset, invalid and below one: `tests/test_github_retry.py` `test_attempt_configuration` (unset is 4; `0`, `-1`, `invalid` and an empty value raise `PlatformConfigError` naming the variable and value).
- Configuration error hook keeps a host-installed hook: `tests/test_platform_common.py` `test_import_keeps_a_host_installed_exception_hook`.
- `capability_manager` reads `agent_tools` and `platform_version` through the validated configuration: `tests/test_capability_manager.py` `test_missing_agent_tools_is_the_named_schema_error`.
- Sandboxed writer probe fixture carries the real source contract: `tests/test_sandboxed_writer_probes.py` `test_synthetic_integration_carries_a_schema_valid_source_contract`.
- `_project_topology` named key: `tests/test_requirement_integration.py` `test_topology_reads_main_branch_and_worktree_root`, `test_missing_required_key_is_named`.

## Correctness

- The retry default applies only to an unset variable; no invalid value is clamped or replaced.
- The error hook is installed only over `sys.__excepthook__`, so an embedding host keeps its own hook.
- A capability configuration read failure raises `CapabilityError` naming the cause instead of reading an unvalidated TOML.

## Coherence

- `AGENTS.md` and `docs/engineering/agent-workflow.md` name the committed source contract `dev-platform/source-contract.toml` (the local `.dev-platform.toml` is its untracked installation) and document the retry error; `AGENTS.md` minimum validation adds ruff and the manifest check, matching CI.

## Noticed, not changed

- `rollout_project._read_operator_config` is best-effort; `shared_workspace_applicable` returns false on `OSError`/`SharedWorkspaceError`; `task_content_identity.content_identity` returns `None` on git failure (outside this slice).
