## Why

Material pre-authoring names handoffs by intent id (`I1`), while a materialized child is known by its authored managed change (`object-client-contract`). When a handoff was refreshed after materialization, `advance` maps it to the child through `bundles/<intent>`; an agent that authored the bundle as `bundles/object-client-contract` hit a swallowed lookup error, the handoff stayed keyed `I1`, and `advance` failed with the misleading "historical linked child … is not terminal" (friction lehard/dev-platform#392). No document names the bundle key.

## What Changes

- One resolver for a handoff's authored bundle: `bundles/<handoff id>/` if present; otherwise the single bundle whose `manifest.json` declares `"handoff": "<handoff id>"`. Two declaring bundles, or a `bundles/<id>` whose manifest declares a different handoff, stop naming both.
- Materialization of a fresh handoff and the refreshed-handoff reuse (`_bundle_reused_child`) both use it. A missing bundle for a not-yet-materialized handoff is still a named "unavailable" stop at materialization; a malformed bundle stops instead of being ignored.
- A non-terminal linked child that no current handoff maps to fails naming the child, its change and the handoffs left unmapped, with the bundle naming rule as the next action.
- `docs/engineering/task-intake.md` states the bundle key.

## Impact

`template/scripts/execute_requirement.py`, `tests/test_requirement_execution.py`, `docs/engineering/task-intake.md`, generated manifest. Spec `agent-workflow`: one added requirement. The lifecycle stage model and the handoff format are unchanged (BR exclusion).
