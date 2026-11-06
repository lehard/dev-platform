## Why

Independent review runs only for managed changes and is switched off here, so nothing reviews changes to the delivery gates, and quick tasks, now the main path, never get a review. The reviewer code is still in place.

## What Changes

- A change is risky exactly when the task's own diff touches a `[[protected]]` path of the protected surface. Declared generated files do not count.
- Review is required when it is enabled and the change is risky, for quick and managed tasks. A managed change that touches nothing protected is no longer reviewed.
- A quick task keeps its review files in its own git directory, bound to its content, next to its check evidence.
- `finish` reviews a risky quick task after validation and before publication.
- `independent_review.py` accepts the reserved target `quick-task` wherever it takes a change name.
- This repository enables review with an explicit Claude provider. The project template stays off.

## Non-goals

No repair cycle or budget, no new perspective, no provider or model substitution, no release and no rollout.

## Impact

- `template/scripts/independent_review.py`, `independent_review_runner.py`, `finish_task.py`, `task_content_identity.py`.
- `dev-platform/source-contract.toml`, `template/.dev-platform.toml.jinja` comment, a new decision record that replaces item 5 of DEC-0009, workflow documentation, tests, manifest.
