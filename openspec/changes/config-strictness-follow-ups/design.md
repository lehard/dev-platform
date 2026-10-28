## Context

- `github_retry_attempts` (`_platform_common.py`) reads `DEV_PLATFORM_GITHUB_RETRY_ATTEMPTS`; `docs/engineering/agent-workflow.md` documents the default 4.
- The configuration error hook is set at import so every entry point reports a `PlatformConfigError` in one line (coordinator decision for the previous slice).
- `capability_manager._load_toml` reads raw TOML; `configured_providers` indexes `agent_tools`, `create_from_descriptor` reads `platform_version` with `.get`.
- `sandboxed_writer_probes.build_repositories` writes `dev-platform/source-contract.toml` with only `main_branch`; `lifecycle_workers.prepare_checkout` installs it as `.dev-platform.toml`.

## Decisions

- **Retry setting (owner decision 2026-10-28: keep).** Unset keeps the documented default 4 (documented optional setting). A value that is not an integer or is below 1 raises `PlatformConfigError` naming the variable and the value; there is no clamp.
- **Hook installation.** Keep the one-line report (decision of the previous slice); install it only when `sys.excepthook is sys.__excepthook__`, so a host or test runner hook is never replaced. Entry points still get the one-line report.
- **capability_manager.** Use `read_project_config` (schema-validated, no operator merge); its `PlatformConfigError` names the key.
- **Probe fixture.** Copy the repository's real `dev-platform/source-contract.toml` into the synthetic integration repository.
- **`_project_topology`.** Full-schema validation stays (owner variant B: validate once against one schema); a test pins the named diagnostic.
- **Kept by rule.** `shared_workspace_applicable` now raises on an invalid configuration instead of answering "not applicable"; that is the intended explicit failure.

## Fail-open inventory

- `github_retry_attempts` invalid value -> 4, below one -> 1: FIXED (error naming variable and value). Unset: documented optional default.
- `capability_manager` raw `agent_tools` / `.get("platform_version")`: FIXED (schema diagnostic).
