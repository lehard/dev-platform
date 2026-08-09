## Why

Managed Copier update smoke tests can execute a historical template's `_tasks` before the candidate template is installed. An old `platform_bootstrap.py` then calls an OpenSpec CLI with flags/configuration it no longer supports, blocking an otherwise valid, exact-version rollout before its updated bootstrap can run.

## What Changes

- Make managed Copier update and guarded recopy skip embedded template tasks.
- Run the newly rendered platform bootstrap exactly once after a conflict-free update, so stable platform-version metadata and platform doctor behavior remain intact.
- Repair the central OpenSpec YAML receipt guidance and add regression coverage for historical task isolation.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `platform-rollout`: managed rollout isolates historical Copier tasks while preserving candidate-version bootstrap and validation.

## Impact

- `scripts/rollout_project.py`, rollout smoke/unit tests, and root OpenSpec configuration.
- Existing managed-project updates only; new-project initial rendering retains its normal template task behavior.
