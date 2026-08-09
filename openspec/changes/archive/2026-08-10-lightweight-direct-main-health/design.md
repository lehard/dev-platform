# Design: keep direct-mode main health lightweight

## Event contract

For generated Dev Platform CI with `harness_mode=platform`:

- `pull_request` -> common platform/OpenSpec hygiene + selected checks for the PR diff;
- `push` to main (available for `publish_mode=direct`) -> common platform/OpenSpec hygiene only;
- `workflow_dispatch` -> common platform/OpenSpec hygiene + full platform-managed checks.

For `harness_mode=project`, generated CI continues to run only common platform/OpenSpec hygiene and delegates product/application checks to repository CI.

## Why event-specific execution

The generic workflow cannot safely install arbitrary project application dependencies. Repeating `full_commands` on direct main is both expensive and brittle. The platform lifecycle already requires local selected/full verification before publication, so the post-publish main run should detect platform/OpenSpec health regressions rather than re-run application acceptance.

Manual dispatch retains an explicit cloud full-check option for diagnosis or deliberate clean-run validation when the project's check configuration is cloud-compatible.

## Template change

Change the full-check step condition from `github.event_name != 'pull_request'` to `github.event_name == 'workflow_dispatch'`. No trigger changes are needed.

## Tests

Template contract coverage SHALL assert:

- selected checks use the PR condition;
- full checks use the manual-dispatch condition;
- the old broad non-PR condition is absent;
- local-heavy/cloud-final guidance mentions lightweight direct main health and manual full dispatch.

## Rollout

Publish as the next immutable patch after verification. Managed rollout updates generated workflow/docs; direct-mode Cuby provides the real post-merge health proof.
