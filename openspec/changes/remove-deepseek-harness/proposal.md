## Why

Owner decision 2026-10-28 (repository audit, stabilization mode): remove the DeepSeek harness. It is disabled (`[experimental_runtime.deepseek_harness] enabled = false`), takes no part in the lifecycle, and costs about 760 lines in `template/scripts/deepseek_harness_adapter.py` plus a shim, a test, two docs, a Cordis observation profile, a requirements file, protected-surface entries, an Explorer node and spec requirements.

## What Changes

- Delete `template/scripts/deepseek_harness_adapter.py`, `scripts/deepseek_harness_adapter.py`, `template/dev-platform/deepseek-harness-observation.cordis.yml`, `template/requirements/deepseek-harness.txt`, `template/docs/engineering/deepseek-harness-runtime.md`, `docs/engineering/deepseek-harness-runtime.md`, `tests/test_deepseek_harness_runtime.py`.
- Remove the `[experimental_runtime.deepseek_harness]` section from `template/.dev-platform.toml.jinja`, the protected-surface entries, the `dev-platform/checks.toml` test entry, the Explorer node and its references, and the precedent link in `docs/engineering/upstream-substitution.md`.
- `validate_platform_config` raises a `PlatformConfigError` naming the file and telling to delete the section when `[experimental_runtime.deepseek_harness]` is present.
- Specs: agent-runtime loses the three DeepSeek-specific requirements; its three generic requirements with DeepSeek scenarios are replaced by runtime-neutral versions; model-routing's efficiency requirement no longer names DeepSeek Harness; platform-config adds the leftover-section error.

## Impact

- Template-visible. New render: no DeepSeek files or section. Copier update of an existing project: files deleted by the template are deleted (unchanged local copies), `.dev-platform.toml` is skip-if-exists, so the update's bootstrap task deletes the exact shipped section; an edited section stays and fails with the explicit error. Verified with a render of v3.0.0 updated to the change head.
- Release: removal of a shipped (disabled) capability and a new configuration error; classified by the release owner.
- Archived OpenSpec changes and `docs/decisions/` keep their history.
