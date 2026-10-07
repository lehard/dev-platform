## Context

`managed_project_status._project_state` raises when a source issue maps to zero Project items, and `requirement_intake.create_requirement` verifies only Issue labels. Live read-back on 2026-10-07 shows #415, #416, #433 and #436 each have exactly one item created seconds after the Issue, so the reported missing-auto-add could not be reproduced; the defect that remains is that nothing confirms or repairs membership, so correctness depends on an external asynchronous automation.

## Decisions

Extend `managed_project_status` rather than add a system: split item discovery from the exactly-one assertion, add `ensure_item(root, source_issue)`. When no item exists it resolves the Issue node id and calls `addProjectV2ItemById` (GitHub returns the existing item if one was added concurrently, so repeats and races cannot duplicate). It sets Status to `Backlog` only when Status is unset, never overwrites an existing Status, then re-reads through the existing exactly-one path and asserts the expected Status. Project API failures raise `ManagedProjectStatusError`.

`create_requirement` finds an open `type:requirement` Issue with identical title and body and reuses it, otherwise creates; after label reconciliation it calls `ensure_item` and reports success only afterwards. A Project failure raises `RequirementIntakeError` naming the durable Issue and the rerun/`reconcile-board` command. `reconcile-board --requirement` / `--all` ensures membership for existing open Requirements idempotently; `start` ensures membership before the card claim.

Connected GitHub cannot write the user-owned Project, so its adapter is specified as: create and read back the Issue, report fixation only when membership is confirmed, otherwise report the Issue as durable and fixation unconfirmed; the operator-side `reconcile-board` completes it. A pure reference model `connected_fixation_outcome` pins this rule in tests, mirroring `resolve_connected_routing`.

## Risks and Mitigations

- Duplicate items: rely on idempotent add plus mandatory read-back exactly-one assertion; more than one item fails.
- Clobbering status: only an unset Status is initialized.
- Unattended connected path needs an operator invocation of `reconcile-board`; documented as the supported completion path, never a user step.
- Title+body reuse could merge identical intents: identical body is an exact duplicate by definition.

## Verification

Unit tests with a fake GraphQL transport cover auto-add present/absent, existing item, repeat, duplicate refusal, unavailable API, Backlog initialization and preserved status; create tests cover reuse and fail-closed; connected model tests; live read-back of existing Requirements.
