# Design

## Completion contract

For a non-trivial OpenSpec change, `done` means:

`implementation -> project checks -> semantic OpenSpec verify -> verification receipt -> archive -> publication`

Prefer `/opsx:verify` when the installed agent integration exposes it. OpenSpec itself permits an equivalent review of the change and diff when that tool-integrated workflow is unavailable. The platform therefore enforces the semantic result and recorded method rather than coupling completion to one chat command surface.

The platform must prevent a completed task list from remaining active at publication time.

## Verification receipt

After material findings are resolved, the agent records `openspec/changes/<change>/verification.md` containing:

- `OpenSpec-Verify: PASS`
- `Verification-Method: <method>`

The report must cover completeness, correctness and coherence and state what was actually checked. Python does not pretend to reproduce semantic verification; it only validates that an explicit review result and method were recorded.

## Lifecycle tool

Add `scripts/openspec_lifecycle.py` with two operations:

- `check`: scan active changes (excluding `archive/`). If a change has at least one task checkbox and all are checked, fail and require archive before publication. Incomplete changes are allowed.
- `archive <change>`: require all tasks checked plus the PASS receipt and method; run strict OpenSpec validation for the change; invoke `openspec archive <change> --yes`; then run strict global validation.

The tool never edits planning artifacts to make them pass and never installs/upgrades OpenSpec.

## Publication gate

`finish_task.py` runs lifecycle `check` before normal Git/check/publication behavior. This makes forgetting archive a blocking condition rather than a reminder.

## CI/check integration

Generated project checks run lifecycle hygiene for OpenSpec/process changes and full checks. This catches stale completed active changes even outside `finish_task.py`. `platform_doctor.py` also requires the lifecycle helper to be present in a healthy generated installation.

## Legacy reconciliation

Historical dev-platform changes predate the receipt marker. Existing `verification.md` evidence is preserved. Where completion is already demonstrated and later changes/releases satisfy stale task text, archive them as migration cleanup rather than fabricating a literal `/opsx:verify` run that did not happen.

## Rollback

The enforcement is contained in platform-managed scripts/rules. A downstream project can roll back through a reviewed Copier downgrade/update; no application data migration is involved.
