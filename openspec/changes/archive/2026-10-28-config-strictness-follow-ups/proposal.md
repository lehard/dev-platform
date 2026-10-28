## Why

The previous slices left four configuration readers with hidden or surprising fallbacks. `github_retry_attempts` silently uses 4 for a non-integer `DEV_PLATFORM_GITHUB_RETRY_ATTEMPTS` and turns 0 or a negative value into 1. Importing `_platform_common` replaces any exception hook the host installed. `capability_manager` reads `.dev-platform.toml` with its own raw loader, so a missing `agent_tools` surfaces as a bare `KeyError` instead of the schema diagnostic. The sandboxed writer probe writes a partial source contract that the schema now rejects. Separately, `AGENTS.md` and `docs/engineering/agent-workflow.md` say the committed source contract is `.dev-platform.toml`, while the code installs `dev-platform/source-contract.toml`, and the `AGENTS.md` minimum validation omits two checks CI runs.

## What Changes

- `template/scripts/_platform_common.py`: `github_retry_attempts` raises naming the variable and value for a non-integer or below-one value; unset keeps the documented default 4. The configuration error hook is installed only while `sys.excepthook` is the interpreter default.
- `template/scripts/capability_manager.py`: `configured_providers` and `create_from_descriptor` read the validated platform configuration.
- `scripts/sandboxed_writer_probes.py`: the synthetic integration repository carries the real source contract.
- `tests/test_requirement_integration.py`: `_project_topology` reports a missing required key by name.
- `AGENTS.md`, `docs/engineering/agent-workflow.md`: the committed contract is `dev-platform/source-contract.toml`, installed as the local `.dev-platform.toml`; minimum validation adds `python3 -m ruff check scripts template/scripts tests` and `python3 scripts/generate_platform_manifest.py --check`.
- Tests for each change.

## Impact

- About 11 files under `template/scripts/`, `scripts/`, `tests/`, `AGENTS.md` and `docs/`.
- Spec: platform-config (one ADDED requirement for the retry setting).
- Downstream: a project exporting an invalid retry value now stops with a named error.
