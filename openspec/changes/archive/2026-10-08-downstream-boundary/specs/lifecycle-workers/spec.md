## ADDED Requirements

### Requirement: Coordinator logic is source-only and never a mandatory downstream dependency

The coordinator stack (`publication_queue`, `lifecycle_workers`, `pr_review_gate`) SHALL be loaded only after the committed contract selected coordinator mode. No entrypoint reachable from a generated downstream project (archive, finish, Requirement lifecycle, terminal reconciliation) SHALL import it at module level or require it to be present or enabled for portable behavior.

#### Scenario: Downstream entrypoints import without the coordinator stack
- **WHEN** `openspec_lifecycle`, `execute_requirement` and `requirement_terminal` are imported in a downstream-shaped checkout with the coordinator modules unimportable
- **THEN** the imports succeed and no coordinator module is loaded

#### Scenario: Coordinator mode loads the stack on demand
- **WHEN** the source contract selects coordinator mode for an archive
- **THEN** the coordinator modules are imported at that point and their failures surface unchanged
