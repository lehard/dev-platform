# Design: Rollout validates Harness compatibility; CI validates product behavior

## Boundary

`scripts/rollout_project.py` is a control-plane updater. Its validation proves that Copier applied the selected immutable platform version safely and that the rendered platform Harness is coherent in the target checkout. It is not an application test runner.

`run_project_validation()` will retain its ordered fail-closed checks:

1. reject files from Copier update;
2. whitespace/diff hygiene;
3. rendered `platform_doctor`.

It will then return without locating or running `scripts/select_checks.py`. This applies to `harness_mode=platform` and `harness_mode=project`: the mode continues to decide lifecycle implementation ownership, but neither mode makes rollout preparation own product verification.

## Downstream behavior and safety

The generated/repository-native CI on the reviewed rollout pull request remains the product/application merge gate. No CI configuration is changed by this task; the change removes duplicate local execution during preparation only. If Harness installation is invalid, the existing doctor/integrity checks fail before a rollout branch or PR is published.

## Compatibility and rollback

Existing downstream repositories receive the behavior only when they review a Copier update to a release containing this change. No data or configuration migration is needed. Reverting the platform release restores the previous rollout validator behavior through the same reviewed release/rollout mechanism; no downstream CI state is mutated.

## Risks and mitigations

- A product regression could be missed if a downstream rollout PR lacks meaningful CI. This is not hidden by repeating checks in preparation: the rollout PR remains subject to its existing required checks before merge. Tests and the spec make this ownership explicit.
- An implementation might accidentally weaken Harness validation while removing the selector. Focused tests assert retained diff and doctor calls for both modes, and existing rollout integration coverage continues to exercise Copier safety gates.
