# Design

## Completion contract

For a non-trivial OpenSpec change, `done` means:

`implementation -> project checks -> /opsx:verify -> verification receipt -> archive -> publication`

The platform must prevent a completed task list from remaining active at publication time.

## Verification receipt

`/opsx:verify` remains an agent workflow. After material findings are resolved, the agent records `openspec/changes/<change>/verification.md` containing the exact marker:

`OpenSpec-Verify: PASS`

The receipt is intentionally simple and reviewable. Python does not pretend to reproduce semantic verification.

## Lifecycle tool

Add `scripts/openspec_lifecycle.py` with two operations:

- `check`: scan active changes (excluding `archive/`). If a change has at least one task checkbox and all are checked, fail and require archive before publication. Incomplete changes are allowed.
- `archive <change>`: require all tasks checked and the PASS receipt; run strict OpenSpec validation for the change; invoke `openspec archive <change> --yes`; then run strict global validation.

The tool never edits planning artifacts to make them pass and never installs/upgrades OpenSpec.

## Publication gate

`finish_task.py` runs lifecycle `check` before normal Git/check/publication behavior. This makes forgetting archive a blocking condition rather than a reminder.

## CI/check integration

Generated project checks run lifecycle hygiene for OpenSpec/process changes and full checks. This catches stale completed active changes even outside `finish_task.py`.

## Legacy reconciliation

Historical dev-platform changes predate the receipt marker. Existing `verification.md` evidence is preserved. Where completion is already demonstrated and later changes/releases satisfy stale task text, archive them as migration cleanup rather than fabricating a literal `/opsx:verify` run that did not happen.

## Rollback

The enforcement is contained in platform-managed scripts/rules. A downstream project can roll back through a reviewed Copier downgrade/update; no application data migration is involved.
